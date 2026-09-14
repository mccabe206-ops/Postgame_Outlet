"""Localhost Game Report screen for the Power Ratings hub (Lane-2 WIP).

A clickable per-game summary: pick a week, click a game, and get a nicely laid-out
report on one screen — final + quarter line score, the expected-points model vs.
actual vs. the garbage-time-aware COMPETITIVE score, the game's half-by-half shape,
the full team-stat comparison (ESPN box), a QB matchup (QBR / passer rating / PFF
grade), top PFF performers per side, and auto sustainability flags.

Assembled server-side from: espn_api + results.fetch_boxscore (ESPN box + QB lines),
game_estimate (expected pts / competitive score / half splits), and the local PFF
cache from pff.py when present (degrades gracefully if not).

Binds 127.0.0.1:8792. Stdlib only. Launched by the hub (card) or:
    python3 game_server.py            # opens browser
    python3 game_server.py --no-open
"""

import csv
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from espn_api import fetch_json
import results
import game_estimate as GE

try:
    import team_view as TV  # abbr <-> full-name resolution
except Exception:  # noqa: BLE001
    TV = None

HOST, PORT = "127.0.0.1", 8792
REPO = os.path.dirname(os.path.abspath(__file__))
RATINGS = os.path.join(REPO, "data", "ratings.csv")
WRITEUP_ALIAS = {"WSH": "WAS"}  # ESPN abbr -> write-up filename abbr where they differ
SB = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
      "scoreboard?dates={year}&seasontype=2&week={week}")
SUM = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={e}"

# ESPN abbr -> PFF abbr (PFF uses a few different codes)
ESPN_TO_PFF = {"ARI": "ARZ", "BAL": "BLT", "CLE": "CLV", "HOU": "HST",
               "LAR": "LA", "WSH": "WAS"}

_MODEL = None
def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = GE.fit_model()
    return _MODEL


# ---- PFF cache -------------------------------------------------------------
def _pff(season, week):
    """Load per-facet PFF rows for the week if cached; else {}."""
    d = os.path.join(REPO, "data", "pff", str(season), f"wk{week}")
    out = {}
    if not os.path.isdir(d):
        return out
    for facet, key in (("passing", "passing_summary"), ("rushing", "rushing_summary"),
                       ("receiving", "receiving_summary"), ("defense", "defense_summary")):
        p = os.path.join(d, f"{facet}.json")
        if os.path.exists(p):
            try:
                out[facet] = json.load(open(p)).get(key, [])
            except Exception:  # noqa: BLE001
                pass
    return out


def _pff_for(pff, facet, pff_abbr, grade_key, n=4):
    rows = [r for r in pff.get(facet, []) if r.get("team_name") == pff_abbr and r.get(grade_key) is not None]
    rows.sort(key=lambda r: r[grade_key], reverse=True)
    return rows[:n]


# ---- ratings + write-up + suggestion ---------------------------------------
def _name_by_abbr():
    if TV is None:
        return {}
    idx = TV.espn_team_index()
    return {(m.get("abbr") or "").upper(): name for name, m in idx.items()}


def _rating_row(abbr):
    """Current McCabe rating row for an ESPN abbr, or None."""
    name = _name_by_abbr().get(abbr.upper())
    if not name:
        return None
    with open(RATINGS, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("team") == name:
                def fnum(v):
                    try:
                        return float(v or 0)
                    except ValueError:
                        return 0.0
                qb, off, dfn = fnum(r["qb_value"]), fnum(r["off_value"]), fnum(r["def_value"])
                return {"team": name, "qb_name": r.get("qb_name", ""),
                        "qb": qb, "off": off, "def": dfn, "total": round(qb + off + dfn, 1),
                        "needs_review": (r.get("needs_review") or "").strip().upper(),
                        "notes": r.get("notes", "")}
    return None


def _writeup(abbr):
    ab = WRITEUP_ALIAS.get(abbr.upper(), abbr.upper())
    p = os.path.join(REPO, "data", "writeups", f"{ab}.md")
    if os.path.exists(p):
        with open(p) as f:
            return f.read()
    return ""


def _suggest(abbr, won, comp_for, comp_against, score_for, exp_for, qb_grade, qb_qbr, opp_rating):
    """Rule-based, evidence-only prompts (NOT auto-moves) — your judgment leads in
    Update ratings. Mirrors results.py adjustment signals, tuned to this screen."""
    s = []
    margin = comp_for - comp_against  # competitive-time margin
    if qb_grade is not None and qb_grade <= 45:
        s.append(f"QB graded poorly ({qb_grade}) — consider a QB downgrade / backup-watch.")
    elif qb_grade is not None and qb_grade >= 85:
        s.append(f"Elite QB game ({qb_grade}) — consider a QB bump, but weigh opponent quality.")
    if qb_qbr is not None:
        try:
            if float(qb_qbr) <= 30:
                s.append(f"QBR {qb_qbr} — bottom-tier efficiency this week.")
        except (TypeError, ValueError):
            pass
    if margin <= -17:
        s.append(f"Beaten by {abs(margin)} in competitive time — look hard at whichever unit failed.")
    elif margin >= 17 and (opp_rating is not None and opp_rating >= 2.0):
        s.append(f"Won by {margin} in competitive time vs. a strong opponent ({opp_rating:+.1f}) — quality-win signal, consider a bump.")
    elif margin >= 17:
        s.append(f"Controlled the game (+{margin} competitive) — but weigh opponent quality before moving.")
    if exp_for is not None and score_for - exp_for >= 7:
        s.append(f"Scored {score_for - exp_for:.0f} more than the box supports — finishing spike, likely regresses; don't overreact.")
    if not s:
        s.append("No strong single-game signal — hold unless your read says otherwise.")
    return s


# ---- week + game lists -----------------------------------------------------
def list_games(week, year):
    sb = fetch_json(SB.format(year=year, week=week))
    games = []
    for e in sb.get("events", []):
        c = e["competitions"][0]
        st = c.get("status", {}).get("type", {})
        comp = {t["homeAway"]: t for t in c["competitors"]}
        if "home" not in comp or "away" not in comp:
            continue
        games.append({
            "event": e.get("id"),
            "away": comp["away"]["team"]["abbreviation"],
            "home": comp["home"]["team"]["abbreviation"],
            "away_name": comp["away"]["team"].get("shortDisplayName"),
            "home_name": comp["home"]["team"].get("shortDisplayName"),
            "as": comp["away"].get("score"), "hs": comp["home"].get("score"),
            "final": st.get("completed", False), "status": st.get("shortDetail", st.get("name")),
        })
    return {"week": week, "year": year, "games": games}


# ---- one game report -------------------------------------------------------
def _qb_line(box_side):
    qb = (box_side or {}).get("qb")
    if not qb:
        return None
    ln = qb.get("line", {})
    return {"name": qb.get("name"), "cmpatt": ln.get("C/ATT"), "yds": ln.get("YDS"),
            "td": ln.get("TD"), "int": ln.get("INT"), "sacks": ln.get("SACKS"),
            "qbr": ln.get("QBR"), "rtg": ln.get("RTG")}


def _stat_pairs(box):
    """Aligned away/home stat rows from the ESPN team box (all_stats)."""
    a = {s["name"]: s for s in (box.get("away") or {}).get("all_stats", [])}
    h = {s["name"]: s for s in (box.get("home") or {}).get("all_stats", [])}
    order = [s["name"] for s in (box.get("away") or {}).get("all_stats", [])]
    return [{"label": a[n]["label"], "away": a[n]["value"], "home": h.get(n, {}).get("value", "—")}
            for n in order if n in a]


def build_report(event, week, year):
    summary = fetch_json(SUM.format(e=event))
    hdr = summary.get("header", {}).get("competitions", [{}])[0]
    comp = {c.get("homeAway"): c for c in hdr.get("competitors", [])}
    if "home" not in comp or "away" not in comp:
        return {"ok": False, "message": "teams not found"}
    aa = comp["away"]["team"]["abbreviation"]
    ha = comp["home"]["team"]["abbreviation"]
    a_name = comp["away"]["team"].get("displayName")
    h_name = comp["home"]["team"].get("displayName")
    a_sc = int(float(comp["away"].get("score") or 0))
    h_sc = int(float(comp["home"].get("score") or 0))

    box = results.fetch_boxscore(event)
    model = _model()

    def _exp(side):
        ty, to, fd = GE._box_inputs(box.get(side) or {})
        if None in (ty, to, fd):
            return None, None
        return GE.expected_points(model, ty, to, fd), (ty, int(to), int(fd))
    a_exp, a_in = _exp("away")
    h_exp, h_in = _exp("home")
    ca, ch, dec = GE.competitive_score(summary)
    hs = GE.half_splits(summary)

    # scoring timeline
    timeline = []
    prev = {"away": 0, "home": 0}
    for p in summary.get("scoringPlays", []):
        aw, hm = p.get("awayScore"), p.get("homeScore")
        if aw is None or hm is None:
            continue
        side = aa if aw > prev["away"] else ha
        timeline.append({"q": (p.get("period") or {}).get("number"),
                         "clock": (p.get("clock") or {}).get("displayValue"),
                         "team": side, "a": aw, "h": hm, "text": (p.get("text") or "")[:90]})
        prev = {"away": aw, "home": hm}

    # PFF
    season = year
    pff = _pff(season, week)
    pa, ph = ESPN_TO_PFF.get(aa, aa), ESPN_TO_PFF.get(ha, ha)
    def perf(pabbr):
        if not pff:
            return None
        return {
            "passing": [{"p": r["player"], "g": r.get("grades_offense"),
                         "line": f"{r.get('completions')}/{r.get('attempts')} {r.get('yards')}y "
                                 f"{r.get('touchdowns')}TD {r.get('interceptions')}INT"}
                        for r in _pff_for(pff, "passing", pabbr, "grades_offense", 1)],
            "rushing": [{"p": r["player"], "g": r.get("grades_run"),
                         "line": f"{r.get('attempts')}-{r.get('yards')}y {r.get('touchdowns')}TD"}
                        for r in _pff_for(pff, "rushing", pabbr, "grades_run", 3)],
            "receiving": [{"p": r["player"], "g": r.get("grades_offense"),
                           "line": f"{r.get('receptions')}/{r.get('targets')} {r.get('yards')}y {r.get('touchdowns')}TD"}
                          for r in _pff_for(pff, "receiving", pabbr, "grades_offense", 4)],
            "defense": [{"p": r["player"], "g": r.get("grades_defense"),
                         "line": f"{r.get('total_pressures',0)}prs {r.get('sacks',0)}sk "
                                 f"{r.get('tackles',0)}tk {r.get('stops',0)}stp"}
                        for r in _pff_for(pff, "defense", pabbr, "grades_defense", 4)],
        }

    # flags
    flags = []
    gb_a = a_sc - ca
    gb_h = h_sc - ch
    if gb_a or gb_h:
        flags.append(f"Garbage-time points — {aa}: {gb_a}, {ha}: {gb_h}. Competitive score {aa} {ca}–{ch} {ha}"
                     + (f" (decided Q{dec[0]} {dec[1]})." if dec else "."))
    if a_exp is not None and a_sc - a_exp >= 6:
        flags.append(f"{aa} scored {a_sc - a_exp:.0f} more than the box supports — finishing/TD spike, watch for regression.")
    if h_exp is not None and h_sc - h_exp >= 6:
        flags.append(f"{ha} scored {h_sc - h_exp:.0f} more than the box supports — finishing/TD spike, watch for regression.")
    A, H = hs.get(aa, {}), hs.get(ha, {})
    for lbl, k in (("1st half", "h1"), ("2nd half", "h2")):
        if A and H:
            if A[k + "_yds"] - H[k + "_yds"] >= 60 and A[k + "_pts"] <= H[k + "_pts"]:
                flags.append(f"{aa} out-gained {ha} by {A[k+'_yds']-H[k+'_yds']} in the {lbl} but didn't lead the scoring — left points.")
            if H[k + "_yds"] - A[k + "_yds"] >= 60 and H[k + "_pts"] <= A[k + "_pts"]:
                flags.append(f"{ha} out-gained {aa} by {H[k+'_yds']-A[k+'_yds']} in the {lbl} but didn't lead the scoring — left points.")

    # per-team rating + write-up + suggested move
    rt_a, rt_h = _rating_row(aa), _rating_row(ha)

    def _qbg(pabbr):
        rows = _pff_for(pff, "passing", pabbr, "grades_offense", 1) if pff else []
        return rows[0].get("grades_offense") if rows else None

    def _qbr(side):
        q = (box.get(side) or {}).get("qb")
        return (q or {}).get("line", {}).get("QBR")
    teams = {
        "away": {"rating": rt_a, "writeup": _writeup(aa),
                 "suggest": _suggest(aa, a_sc > h_sc, ca, ch, a_sc, a_exp, _qbg(pa), _qbr("away"),
                                     rt_h["total"] if rt_h else None)},
        "home": {"rating": rt_h, "writeup": _writeup(ha),
                 "suggest": _suggest(ha, h_sc > a_sc, ch, ca, h_sc, h_exp, _qbg(ph), _qbr("home"),
                                     rt_a["total"] if rt_a else None)},
    }

    return {
        "ok": True, "event": event, "week": week, "year": year,
        "teams": teams,
        "away": aa, "home": ha, "away_name": a_name, "home_name": h_name,
        "away_score": a_sc, "home_score": h_sc,
        "final": comp["home"].get("winner") is not None or True,
        "quarters": {"away": hs.get(aa, {}).get("quarters", []), "home": hs.get(ha, {}).get("quarters", [])},
        "expected": {"away": a_exp, "home": h_exp, "away_in": a_in, "home_in": h_in},
        "competitive": {"away": ca, "home": ch, "decided": dec},
        "shape": {"away": hs.get(aa, {}), "home": hs.get(ha, {})},
        "qb": {"away": _qb_line(box.get("away")), "home": _qb_line(box.get("home"))},
        "stats": _stat_pairs(box),
        "pff": {"away": perf(pa), "home": perf(ph), "have": bool(pff)},
        "timeline": timeline,
        "flags": flags,
    }


# ---- page ------------------------------------------------------------------
PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Game Report</title>
<style>
 :root{--bg:#0e1116;--card:#171c24;--line:#273040;--ink:#e6edf3;--dim:#93a1b0;
       --good:#2ea043;--bad:#e5534b;--warn:#d8c534;--accent:#3b82f6}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
   font:15px/1.45 -apple-system,Segoe UI,Roboto,sans-serif}
 header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;position:sticky;top:0;background:var(--bg);z-index:5;flex-wrap:wrap}
 h1{font-size:18px;margin:0} .dim{color:var(--dim)}
 input,button{background:#0e1116;border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:6px 10px;font-size:13.5px}
 button{cursor:pointer;background:#12233f;border-color:var(--accent);color:#dbe9ff}
 .wrap{padding:18px 20px;max-width:1080px;margin:0 auto}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
 .gcard{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;cursor:pointer}
 .gcard:hover{border-color:var(--accent)} .gcard .score{font-size:20px;font-weight:700}
 .gcard .st{font-size:11.5px;color:var(--dim)}
 .sec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:14px 0}
 .sec h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim)}
 .score-big{display:flex;gap:22px;align-items:baseline;flex-wrap:wrap}
 .score-big .t{font-size:26px;font-weight:800} .score-big .w{color:var(--good)}
 table{border-collapse:collapse;width:100%} th,td{padding:5px 9px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
 th:first-child,td:first-child,.l{text-align:left}
 th{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.03em}
 .cmp{display:grid;grid-template-columns:1fr auto 1fr;gap:6px 14px;align-items:center}
 .cmp .lab{text-align:center;color:var(--dim);font-size:12px}
 .cmp .av,.cmp .hv{font-variant-numeric:tabular-nums} .cmp .av{text-align:right} .cmp .hv{text-align:left}
 .win{color:var(--good);font-weight:700}
 .three{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
 @media(max-width:720px){.three{grid-template-columns:1fr}}
 .box{border:1px solid var(--line);border-radius:10px;padding:10px 12px}
 .box .k{font-size:11px;color:var(--dim);text-transform:uppercase} .box .v{font-size:19px;font-weight:700}
 .flag{background:#2a2f0e;border:1px solid #4a4a1c;border-radius:8px;padding:8px 11px;margin:6px 0;font-size:13px}
 .qbs{display:grid;grid-template-columns:1fr 1fr;gap:12px} @media(max-width:640px){.qbs{grid-template-columns:1fr}}
 .pill{font-size:11px;color:var(--dim);border:1px solid var(--line);border-radius:20px;padding:2px 8px;margin-right:5px;display:inline-block}
 .tl{font:12.5px/1.5 ui-monospace,Menlo,monospace;color:#cdd9e5}
 .grade{font-weight:700} .g-hi{color:var(--good)} .g-lo{color:var(--bad)}
 a.back{color:var(--accent);text-decoration:none;cursor:pointer}
</style></head><body>
<header>
  <h1>🏈 Game Report</h1>
  <span class="dim">Week</span><input id="wk" value="1" style="width:52px">
  <span class="dim">Year</span><input id="yr" value="2026" style="width:66px">
  <button onclick="loadGames()">Load week</button>
  <span id="crumb" class="dim"></span>
</header>
<div class="wrap" id="main"></div>
<script>
const $=(id)=>document.getElementById(id);
function el(t,c,h){const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;}
async function api(p){const r=await fetch(p);return r.json();}
function gradeCls(g){return g==null?'':(g>=80?'g-hi':(g<=45?'g-lo':''));}
function renderMd(src){
  const esc=s=>(s==null?'':(''+s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const inl=s=>esc(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');
  const lines=(src||'').split(/\r?\n/); let h='',inList=false;
  const close=()=>{if(inList){h+='</ul>';inList=false;}};
  for(const raw of lines){const line=raw.replace(/\s+$/,'');
    if(/^###\s+/.test(line)){close();h+='<h4>'+inl(line.replace(/^###\s+/,''))+'</h4>';}
    else if(/^##\s+/.test(line)){close();h+='<h4>'+inl(line.replace(/^##\s+/,''))+'</h4>';}
    else if(/^\s*[-*]\s+/.test(line)){if(!inList){h+='<ul style="margin:.3em 0;padding-left:1.1em">';inList=true;}h+='<li>'+inl(line.replace(/^\s*[-*]\s+/,''))+'</li>';}
    else if(line.trim()===''){close();}
    else{close();h+='<p style="margin:.4em 0">'+inl(line)+'</p>';}}
  close(); return h||'<p class="dim">—</p>';
}

async function loadGames(){
  $('crumb').textContent=''; const wk=$('wk').value, yr=$('yr').value;
  const m=$('main'); m.innerHTML='<div class="dim">loading week…</div>';
  const j=await api(`/api/games?week=${wk}&year=${yr}`);
  m.innerHTML=''; const g=el('div','grid');
  (j.games||[]).forEach(x=>{
    const c=el('div','gcard');
    const done=x.final;
    c.innerHTML=`<div class="score">${x.away} ${done?x.as:''} <span class="dim">@</span> ${x.home} ${done?x.hs:''}</div>`
      +`<div class="st">${done?'Final':x.status}</div>`;
    if(done) c.onclick=()=>openGame(x.event,wk,yr); else c.style.opacity=.55;
    g.appendChild(c);
  });
  m.appendChild(g);
}
function cmpRow(label,a,h,better){
  // better: 'hi' higher wins, 'lo' lower wins, null none
  let aw='',hw=''; const an=parseFloat(a),hn=parseFloat(h);
  if(better && !isNaN(an)&&!isNaN(hn)&&an!==hn){
    const awin = better==='hi'?an>hn:an<hn;
    if(awin) aw='win'; else hw='win';
  }
  return `<div class="av ${aw}">${a}</div><div class="lab">${label}</div><div class="hv ${hw}">${h}</div>`;
}
async function openGame(ev,wk,yr){
  const m=$('main'); m.innerHTML='<div class="dim">building report…</div>';
  const j=await api(`/api/report?event=${ev}&week=${wk}&year=${yr}`);
  if(!j.ok){m.innerHTML='<div class="flag">'+(j.message||'error')+'</div>';return;}
  $('crumb').innerHTML=`<a class="back" onclick="loadGames()">← week ${wk}</a>`;
  m.innerHTML='';
  const aw=j.away_score>j.home_score;
  // score header
  const sh=el('div','sec');
  sh.innerHTML=`<div class="score-big"><span class="t ${aw?'w':''}">${j.away} ${j.away_score}</span>`
    +`<span class="dim">@</span><span class="t ${aw?'':'w'}">${j.home} ${j.home_score}</span></div>`;
  const q=el('table'); const qa=j.quarters.away||[],qh=j.quarters.home||[];
  q.innerHTML='<thead><tr><th>Qtr</th>'+qa.map((_,i)=>`<th>Q${i+1}</th>`).join('')+'<th>T</th></tr></thead>'
    +`<tbody><tr><td class="l">${j.away}</td>`+qa.map(v=>`<td>${v}</td>`).join('')+`<td><b>${j.away_score}</b></td></tr>`
    +`<tr><td class="l">${j.home}</td>`+qh.map(v=>`<td>${v}</td>`).join('')+`<td><b>${j.home_score}</b></td></tr></tbody>`;
  q.style.marginTop='10px'; sh.appendChild(q); m.appendChild(sh);
  // score analysis
  const sa=el('div','sec'); sa.innerHTML='<h3>Score analysis</h3>';
  const three=el('div','three');
  const ex=j.expected, cp=j.competitive;
  three.appendChild(el('div','box',`<div class="k">Actual</div><div class="v">${j.away_score}–${j.home_score}</div>`));
  three.appendChild(el('div','box',`<div class="k">Expected (box stats)</div><div class="v">${ex.away==null?'—':ex.away.toFixed(0)}–${ex.home==null?'—':ex.home.toFixed(0)}</div>`));
  const decTxt = cp.decided?`decided Q${cp.decided[0]} ${cp.decided[1]}`:'competitive throughout';
  three.appendChild(el('div','box',`<div class="k">Competitive (garbage stripped)</div><div class="v">${cp.away}–${cp.home}</div><div class="k">${decTxt}</div>`));
  sa.appendChild(three); m.appendChild(sa);
  // shape
  const sp=el('div','sec'); sp.innerHTML='<h3>Game shape — yards → points by half</h3>';
  const A=j.shape.away,H=j.shape.home;
  const st=el('table');
  st.innerHTML='<thead><tr><th>Team</th><th>1H yds</th><th>1H pts</th><th>2H yds</th><th>2H pts</th></tr></thead>'
    +`<tbody><tr><td class="l">${j.away}</td><td>${A.h1_yds??'—'}</td><td>${A.h1_pts??'—'}</td><td>${A.h2_yds??'—'}</td><td>${A.h2_pts??'—'}</td></tr>`
    +`<tr><td class="l">${j.home}</td><td>${H.h1_yds??'—'}</td><td>${H.h1_pts??'—'}</td><td>${H.h2_yds??'—'}</td><td>${H.h2_pts??'—'}</td></tr></tbody>`;
  sp.appendChild(st); m.appendChild(sp);
  // flags
  if(j.flags&&j.flags.length){const f=el('div','sec');f.innerHTML='<h3>Read — sustainability / luck</h3>';
    j.flags.forEach(x=>f.appendChild(el('div','flag',x)));m.appendChild(f);}
  // team analysis — rating + suggested move + write-up
  if(j.teams){const ta=el('div','sec');
    ta.innerHTML='<h3>Team analysis — rating, suggested move & write-up</h3>'
      +'<div class="dim" style="font-size:12px;margin-bottom:8px">Suggestions are single-game signals, not auto-moves — your judgment leads in Update ratings.</div>';
    const tg=el('div','qbs');
    [['away',j.away,j.teams.away],['home',j.home,j.teams.home]].forEach(([s,ab,t])=>{
      const bx=el('div','box'); let html=`<div class="v" style="font-size:16px">${ab}</div>`;
      if(t.rating){const r=t.rating;
        html+=`<div style="margin:4px 0">${r.qb_name||''} — QB ${r.qb} · Off ${r.off} · Def ${r.def} = <b>${r.total}</b>`
          +(r.needs_review==='Y'?' <span class="pill" style="color:var(--warn);border-color:#4a4a1c">needs review</span>':'')+`</div>`;}
      else html+='<div class="dim">rating not found</div>';
      html+='<div style="margin-top:8px"><span class="pill">Suggested move — signals</span></div>';
      html+='<ul style="margin:6px 0 0;padding-left:18px">'+(t.suggest||[]).map(x=>`<li>${x}</li>`).join('')+'</ul>';
      bx.innerHTML=html;
      if(t.writeup){const d=el('details');d.style.marginTop='10px';
        d.innerHTML='<summary style="cursor:pointer;color:#9dc1ff">Current write-up</summary>';
        const w=el('div');w.style.marginTop='6px';w.innerHTML=renderMd(t.writeup);d.appendChild(w);bx.appendChild(d);}
      tg.appendChild(bx);
    });
    ta.appendChild(tg); m.appendChild(ta);}
  // QB matchup
  if(j.qb.away||j.qb.home){const qb=el('div','sec');qb.innerHTML='<h3>Quarterbacks</h3>';
    const g=el('div','qbs');
    [['away',j.qb.away],['home',j.qb.home]].forEach(([s,x])=>{
      if(!x){g.appendChild(el('div','box','—'));return;}
      const pg=pffQB(j,s);
      g.appendChild(el('div','box',`<div class="v">${x.name}</div>`
        +`<div style="margin:6px 0">${x.cmpatt||''} · ${x.yds||0} yds · ${x.td||0} TD / ${x.int||0} INT · ${x.sacks||''} sk</div>`
        +`<span class="pill">QBR ${x.qbr||'—'}</span><span class="pill">Rating ${x.rtg||'—'}</span>`
        +(pg!=null?`<span class="pill">PFF <b class="grade ${gradeCls(pg)}">${pg}</b></span>`:'')));
    });
    qb.appendChild(g);m.appendChild(qb);}
  // team stats comparison
  if(j.stats&&j.stats.length){const ts=el('div','sec');
    ts.innerHTML=`<h3>Team stats — ${j.away} vs ${j.home}</h3>`;
    const c=el('div','cmp');
    c.innerHTML=`<div class="av"><b>${j.away}</b></div><div class="lab"></div><div class="hv"><b>${j.home}</b></div>`;
    const HI=new Set(['1st Downs','Total Yards','Yards per Play','Passing','Rushing','3rd down efficiency','4th down efficiency','Red Zone (Made-Att)','Possession']);
    const LO=new Set(['Turnovers','Interceptions thrown','Sacks-Yards Lost','Penalties','Fumbles lost']);
    j.stats.forEach(r=>{const b=HI.has(r.label)?'hi':(LO.has(r.label)?'lo':null);
      c.innerHTML+=cmpRow(r.label,r.away,r.home,b);});
    ts.appendChild(c);m.appendChild(ts);}
  // PFF performers
  if(j.pff&&j.pff.have){const pf=el('div','sec');pf.innerHTML='<h3>Top PFF performers</h3>';
    const g=el('div','qbs');
    [['away',j.pff.away,j.away],['home',j.pff.home,j.home]].forEach(([s,p,ab])=>{
      if(!p){g.appendChild(el('div','box','—'));return;}
      let html=`<div class="v" style="font-size:15px">${ab}</div>`;
      const grp=(t,arr)=>{if(!arr||!arr.length)return'';return `<div style="margin-top:8px"><span class="pill">${t}</span></div>`
        +arr.map(x=>`<div>${x.p} <b class="grade ${gradeCls(x.g)}">${x.g??''}</b> <span class="dim">${x.line}</span></div>`).join('');};
      html+=grp('Passing',p.passing)+grp('Rushing',p.rushing)+grp('Receiving',p.receiving)+grp('Defense',p.defense);
      g.appendChild(el('div','box',html));
    });
    pf.appendChild(g);m.appendChild(pf);}
  else {m.appendChild(el('div','sec','<span class="dim">PFF player grades not cached for this week — run a PFF fetch in Claude Code to enrich this screen.</span>'));}
  // timeline
  if(j.timeline&&j.timeline.length){const tl=el('div','sec');tl.innerHTML='<h3>Scoring timeline</h3>';
    j.timeline.forEach(p=>tl.appendChild(el('div','tl',`Q${p.q} ${p.clock} — ${p.team} (${p.a}-${p.h})  ${p.text}`)));
    m.appendChild(tl);}
}
function pffQB(j,side){
  const p=j.pff&&j.pff[side]; if(!p||!p.passing||!p.passing.length)return null; return p.passing[0].g;
}
loadGames();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if u.path == "/api/games":
                wk = int((q.get("week") or ["1"])[0]); yr = int((q.get("year") or ["2026"])[0])
                return self._send(200, json.dumps(list_games(wk, yr)))
            if u.path == "/api/report":
                ev = (q.get("event") or [""])[0]
                wk = int((q.get("week") or ["1"])[0]); yr = int((q.get("year") or ["2026"])[0])
                return self._send(200, json.dumps(build_report(ev, wk, yr)))
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"ok": False, "message": str(e)}))
        return self._send(404, "not found", "text/plain")


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Game Report screen at {url}")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
