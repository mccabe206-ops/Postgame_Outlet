"""NFL Guru dashboard — one UI over the knowledge base + Sleeper fantasy market.

A localhost page (like the pick/team/injury servers) with four tabs, all read-only:
  Query    — run read-only SQL or one-click canned reports; browse the schema.
  Betting  — ATS / over-under with situational filters (home/away/div/fav/dog/rest).
  Fantasy  — KB PPR leaders & usage beside Sleeper trending adds/drops + value rank.
  Norms    — league-evolution charts by season (scoring, home win%, pass rate, ...).

Everything reads the local KB (`data/nfl_kb/nfl.sqlite`) read-only via kb.py and reuses
kb_query's guard + report helpers. Never edits ratings or the site.

Run:
    python3 guru_server.py            # opens http://127.0.0.1:8790
    python3 guru_server.py --no-open
"""

import json
import sys
import threading
import types
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import kb
import kb_query

HOST = "127.0.0.1"
PORT = 8790

NORMS = {
    "scoring": ("Points per game (both teams) — REG",
                "SELECT season, ROUND(AVG(home_score+away_score),2) v FROM games "
                "WHERE game_type='REG' AND home_score IS NOT NULL GROUP BY season ORDER BY season"),
    "home_win": ("Home win % — REG",
                 "SELECT season, ROUND(100.0*SUM(CASE WHEN result>0 THEN 1 ELSE 0 END)/"
                 "SUM(CASE WHEN result<>0 THEN 1 ELSE 0 END),1) v FROM games "
                 "WHERE game_type='REG' AND result IS NOT NULL GROUP BY season ORDER BY season"),
    "fav_cover": ("Home favorite ATS cover % — REG",
                  "SELECT season, ROUND(100.0*SUM(CASE WHEN result>spread_line THEN 1 ELSE 0 END)/"
                  "SUM(CASE WHEN result<>spread_line THEN 1 ELSE 0 END),1) v FROM games "
                  "WHERE game_type='REG' AND spread_line>0 AND result IS NOT NULL "
                  "GROUP BY season ORDER BY season"),
    "pass_rate": ("Pass-play rate % (team) ",
                  "SELECT season, ROUND(100.0*SUM(attempts)/(SUM(attempts)+SUM(carries)),1) v "
                  "FROM team_week GROUP BY season ORDER BY season"),
    "plays": ("Plays/game (pass att + rush att, per team)",
              "SELECT season, ROUND((SUM(attempts)+SUM(carries))*1.0/COUNT(*),1) v "
              "FROM team_week GROUP BY season ORDER BY season"),
}
_FANTASY = {
    "leaders": ("SELECT player_display_name player, position pos, COUNT(*) g, "
                "ROUND(SUM(fantasy_points_ppr),1) ppr, ROUND(AVG(fantasy_points_ppr),1) ppg "
                "FROM player_week WHERE position=? AND season=? GROUP BY player_id "
                "ORDER BY ppr DESC LIMIT 25"),
    "usage": ("SELECT player_display_name player, COUNT(*) g, SUM(COALESCE(carries,0)) car, "
              "SUM(COALESCE(targets,0)) tgt, SUM(COALESCE(carries,0)+COALESCE(targets,0)) touches "
              "FROM player_week WHERE position=? AND season=? GROUP BY player_id "
              "ORDER BY touches DESC LIMIT 25"),
}


def api_query(sql):
    s = (sql or "").strip().rstrip(";").strip()
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return {"error": "Only read-only SELECT/WITH queries are allowed."}
    if ";" in s:
        return {"error": "One statement at a time."}
    if set(low.replace("(", " ").replace(",", " ").split()) & set(kb_query._WRITE):
        return {"error": "Write/DDL keywords are not allowed (read-only)."}
    try:
        rows = kb.query(s)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    cols = list(rows[0].keys()) if rows else []
    return {"columns": cols, "rows": [[r.get(c) for c in cols] for r in rows]}


def api_betting(q):
    team = (q.get("team") or [""])[0].upper()
    since = int((q.get("since") or ["1999"])[0])
    flags = {f: (q.get(f, ["0"])[0] in ("1", "true", "on")) for f in
             ("home", "away", "div", "fav", "dog", "rest")}
    ns = types.SimpleNamespace(team=team, since=since, **flags)
    games = kb_query._games_for_team(team, since, kb.DB_PATH) if team else []
    ats = {"w": 0, "l": 0, "p": 0}
    ou = {"o": 0, "u": 0, "p": 0}
    for g in games:
        if not kb_query._situational_ok(g, team, ns):
            continue
        sl = g.get("spread_line")
        if sl is not None:
            he = g["result"] - sl
            edge = he if g["home_team"] == team else -he
            ats["p" if abs(edge) < 1e-9 else ("w" if edge > 0 else "l")] += 1
        tl, hs, as_ = g.get("total_line"), g.get("home_score"), g.get("away_score")
        if tl is not None and hs is not None and as_ is not None:
            pts = hs + as_
            ou["p" if abs(pts - tl) < 1e-9 else ("o" if pts > tl else "u")] += 1
    return {"team": team, "since": since, "flags": flags, "ats": ats, "ou": ou}


def api_fantasy(q):
    kind = (q.get("kind") or ["leaders"])[0]
    if kind in _FANTASY:
        pos = (q.get("pos") or ["RB"])[0].upper()
        season = int((q.get("season") or ["2024"])[0])
        return {"rows": kb.query(_FANTASY[kind], (pos, season))}
    if kind == "trending":
        direction = (q.get("direction") or ["add"])[0]
        limit = int((q.get("limit") or ["25"])[0])
        return {"rows": kb.query(
            "SELECT f.full_name player, f.position pos, f.team, f.search_rank rank, t.count "
            "FROM trending t JOIN fantasy_value f ON t.sleeper_id=f.sleeper_id "
            "WHERE t.direction=? ORDER BY t.count DESC LIMIT ?", (direction, limit))}
    return {"error": "unknown fantasy kind"}


def api_norms(q):
    metric = (q.get("metric") or ["scoring"])[0]
    if metric not in NORMS:
        return {"error": "unknown metric"}
    title, sql = NORMS[metric]
    rows = kb.query(sql)
    return {"title": title,
            "points": [{"x": int(r["season"]), "y": r["v"]} for r in rows if r["v"] is not None]}


def api_schema(q):
    t = (q.get("table") or [""])[0]
    if t:
        return {"table": t, "columns": kb.columns(t)}
    return {"tables": [{"name": n, "cols": len(kb.columns(n))} for n in kb.list_tables()]}


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NFL Guru</title>
<style>
 :root{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;
   --muted:#898781;--line:#e1e0d9;--border:rgba(11,11,11,.10);--series:#2a78d6;
   --good:#0ca30c;--crit:#d03b3b;--grid:#e1e0d9}
 @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
   --plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;
   --line:#2c2c2a;--border:rgba(255,255,255,.10);--series:#3987e5;--grid:#2c2c2a}}
 :root[data-theme="dark"]{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;
   --ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;--border:rgba(255,255,255,.10);
   --series:#3987e5;--grid:#2c2c2a}
 *{box-sizing:border-box} body{margin:0;background:var(--plane);color:var(--ink);
   font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
 header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;gap:14px;
   align-items:center;flex-wrap:wrap;position:sticky;top:0;background:var(--plane);z-index:5}
 h1{font-size:18px;margin:0;font-weight:800}
 .tabs{display:flex;gap:4px} .tabs button{background:transparent;border:1px solid transparent;
   color:var(--ink2);padding:6px 14px;border-radius:8px;font:inherit;cursor:pointer}
 .tabs button.on{background:var(--ink);color:var(--plane);font-weight:700}
 .spacer{flex:1} a.link{color:var(--series);font-size:12px;text-decoration:none;margin-left:10px}
 button.b{background:var(--surface);border:1px solid var(--border);color:var(--ink);
   padding:7px 12px;border-radius:8px;font:inherit;cursor:pointer}
 button.b:hover{border-color:var(--muted)}
 .wrap{padding:18px 20px;max-width:1050px;margin:0 auto}
 .panel{display:none} .panel.on{display:block}
 textarea,input,select{background:var(--surface);border:1px solid var(--border);color:var(--ink);
   border-radius:8px;padding:8px 10px;font:14px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
 input,select{font-family:inherit}
 textarea{width:100%;min-height:70px}
 .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}
 label.ck{display:inline-flex;gap:5px;align-items:center;color:var(--ink2);font-size:13px}
 table{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
 th,td{text-align:left;padding:5px 9px;border-bottom:1px solid var(--line);white-space:nowrap}
 th{color:var(--muted);text-transform:uppercase;font-size:11px;letter-spacing:.04em}
 td{font-variant-numeric:tabular-nums}
 .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin:10px 0}
 .stat{font-size:22px;font-weight:800;font-variant-numeric:tabular-nums}
 .muted{color:var(--muted);font-size:12px} .err{color:var(--crit);font-size:13px}
 .two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
 .chips button{margin:2px 4px 2px 0}
 svg{width:100%;height:340px;background:var(--surface);border:1px solid var(--border);border-radius:12px}
 .axis{stroke:var(--grid);stroke-width:1} .tick{fill:var(--muted);font-size:10px}
 .series{fill:none;stroke:var(--series);stroke-width:2}
 .dot{fill:var(--series)} @media(max-width:720px){.two{grid-template-columns:1fr}}
</style></head><body>
<header>
  <h1>NFL Guru</h1>
  <div class="tabs">
    <button data-tab="query" class="on" onclick="tab('query')">Query</button>
    <button data-tab="betting" onclick="tab('betting')">Betting</button>
    <button data-tab="fantasy" onclick="tab('fantasy')">Fantasy</button>
    <button data-tab="norms" onclick="tab('norms')">Norms</button>
  </div>
  <span class="spacer"></span>
  <span class="muted">read-only · nflverse + Sleeper</span>
  <a class="link" href="http://127.0.0.1:8789/" target="_blank">Injuries ↗</a>
  <a class="link" href="http://127.0.0.1:8787/" target="_blank">Picks ↗</a>
  <button class="b" onclick="theme()" title="light/dark">◐</button>
</header>
<div class="wrap">
  <div class="panel on" id="p-query">
    <div class="muted">Write read-only SQL, or ask me in chat and I'll write it. Schema:
      <span id="schema"></span></div>
    <textarea id="sql">SELECT season, ROUND(AVG(home_score+away_score),1) ppg
FROM games WHERE game_type='REG' GROUP BY season ORDER BY season</textarea>
    <div class="row"><button class="b" onclick="runsql()">Run</button>
      <span class="chips" id="samples"></span></div>
    <div id="qout"></div>
  </div>

  <div class="panel" id="p-betting">
    <div class="row">
      <label>Team <input id="bteam" value="KC" size="4"></label>
      <label>Since <input id="bsince" value="2006" size="5"></label>
      <span id="bflags"></span>
      <button class="b" onclick="runbet()">Go</button>
    </div>
    <div class="two"><div class="card" id="bats"></div><div class="card" id="bou"></div></div>
  </div>

  <div class="panel" id="p-fantasy">
    <div class="row">
      <label>Pos <select id="fpos"><option>QB</option><option selected>RB</option>
        <option>WR</option><option>TE</option></select></label>
      <label>Season <input id="fseason" value="2024" size="5"></label>
      <button class="b" onclick="runfan('leaders')">PPR leaders</button>
      <button class="b" onclick="runfan('usage')">Usage</button>
    </div>
    <div id="fout"></div>
    <div class="two">
      <div class="card"><b style="color:var(--good)">▲ Trending adds</b><div id="tadd"></div></div>
      <div class="card"><b style="color:var(--crit)">▼ Trending drops</b><div id="tdrop"></div></div>
    </div>
  </div>

  <div class="panel" id="p-norms">
    <div class="row"><select id="nmetric" onchange="runnorm()">
      <option value="scoring">Scoring / game</option>
      <option value="home_win">Home win %</option>
      <option value="fav_cover">Home favorite cover %</option>
      <option value="pass_rate">Pass-play rate %</option>
      <option value="plays">Plays / game</option>
    </select><span class="muted" id="ntitle"></span></div>
    <svg id="chart" viewBox="0 0 900 340" preserveAspectRatio="none"></svg>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
function tab(t){document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.tab===t));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('on',p.id==='p-'+t));
  if(t==='fantasy'&&!$('tadd').innerHTML){loadTrending();runfan('leaders');}
  if(t==='norms'&&!$('chart').innerHTML)runnorm();
  if(t==='betting'&&!$('bats').innerHTML)runbet();}
function theme(){const e=document.documentElement,c=e.getAttribute('data-theme');
  const d=c?c==='dark':matchMedia('(prefers-color-scheme:dark)').matches;e.setAttribute('data-theme',d?'light':'dark');
  if($('p-norms').classList.contains('on'))runnorm();}
function esc(x){return(x==null?'':(''+x)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function tableHTML(cols,rows){return '<table><thead><tr>'+cols.map(c=>`<th>${esc(c)}</th>`).join('')+
  '</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(v=>`<td>${esc(v)}</td>`).join('')+'</tr>').join('')+
  `</tbody></table><div class="muted">${rows.length} row(s)</div>`;}

async function runsql(){const r=await fetch('/api/query?sql='+encodeURIComponent($('sql').value));
  const d=await r.json();$('qout').innerHTML=d.error?`<div class="err">${esc(d.error)}</div>`:
    tableHTML(d.columns,d.rows);}
const SAMPLES={'Scoring by era':"SELECT season, ROUND(AVG(home_score+away_score),1) ppg FROM games WHERE game_type='REG' GROUP BY season ORDER BY season",
 'Dome vs outdoor totals':"SELECT roof, ROUND(AVG(home_score+away_score),1) ppg, COUNT(*) n FROM games WHERE game_type='REG' GROUP BY roof ORDER BY ppg DESC",
 'Trending adds + value':"SELECT f.full_name, f.position, f.team, f.search_rank, t.count FROM trending t JOIN fantasy_value f ON t.sleeper_id=f.sleeper_id WHERE t.direction='add' ORDER BY t.count DESC LIMIT 15"};
function loadSamples(){$('samples').innerHTML=Object.keys(SAMPLES).map(k=>`<button class="b" onclick="$('sql').value=SAMPLES['${k}'.replace(/'/g,String.fromCharCode(39))];runsql()">${k}</button>`).join(' ');}
async function loadSchema(){const d=await(await fetch('/api/schema')).json();
  $('schema').textContent=(d.tables||[]).map(t=>`${t.name}(${t.cols})`).join('  ·  ');}

const BFLAGS=['home','away','div','fav','dog','rest'];
function loadFlags(){$('bflags').innerHTML=BFLAGS.map(f=>`<label class="ck"><input type="checkbox" id="bf_${f}">${f}</label>`).join(' ');}
async function runbet(){const fl=BFLAGS.map(f=>`${f}=`+($('bf_'+f).checked?1:0)).join('&');
  const d=await(await fetch(`/api/report?team=${$('bteam').value}&since=${$('bsince').value}&${fl}`)).json();
  const a=d.ats,o=d.ou,na=a.w+a.l,no=o.o+o.u;
  $('bats').innerHTML=`<div class="muted">${esc(d.team)} ATS since ${d.since}</div>`+
    `<div class="stat">${a.w}-${a.l}-${a.p}</div><div class="muted">${na?(100*a.w/na).toFixed(1):'—'}% cover</div>`;
  $('bou').innerHTML=`<div class="muted">${esc(d.team)} Over/Under since ${d.since}</div>`+
    `<div class="stat">${o.o} O / ${o.u} U / ${o.p} P</div><div class="muted">${no?(100*o.o/no).toFixed(1):'—'}% over</div>`;}

async function runfan(kind){const d=await(await fetch(`/api/fantasy?kind=${kind}&pos=${$('fpos').value}&season=${$('fseason').value}`)).json();
  const rows=d.rows||[];if(!rows.length){$('fout').innerHTML='<div class="muted">no rows</div>';return;}
  const cols=Object.keys(rows[0]);$('fout').innerHTML=tableHTML(cols,rows.map(r=>cols.map(c=>r[c])));}
async function loadTrending(){for(const [dir,el] of [['add','tadd'],['drop','tdrop']]){
  const d=await(await fetch(`/api/fantasy?kind=trending&direction=${dir}&limit=15`)).json();
  const rows=d.rows||[];const cols=['player','pos','team','rank','count'];
  $(el).innerHTML=tableHTML(cols,rows.map(r=>cols.map(c=>r[c])));}}

async function runnorm(){const m=$('nmetric').value;const d=await(await fetch('/api/norms?metric='+m)).json();
  $('ntitle').textContent=d.title||'';drawChart($('chart'),d.points||[]);}
function drawChart(svg,pts){const W=900,H=340,pad=44;svg.innerHTML='';
  if(!pts.length)return;const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
  const ylo=y0-(y1-y0)*0.1||0,yhi=y1+(y1-y0)*0.1||1;
  const sx=v=>pad+(v-x0)/((x1-x0)||1)*(W-pad*1.3);
  const sy=v=>H-pad-(v-ylo)/((yhi-ylo)||1)*(H-pad*1.6);
  const ns='http://www.w3.org/2000/svg';const add=(t,a)=>{const e=document.createElementNS(ns,t);
    for(const k in a)e.setAttribute(k,a[k]);svg.appendChild(e);return e;};
  add('line',{x1:pad,y1:H-pad,x2:W-pad*0.3,y2:H-pad,class:'axis'});
  add('line',{x1:pad,y1:pad*0.5,x2:pad,y2:H-pad,class:'axis'});
  for(let i=0;i<=4;i++){const yv=ylo+(yhi-ylo)*i/4;const yy=sy(yv);
    add('line',{x1:pad,y1:yy,x2:W-pad*0.3,y2:yy,stroke:'var(--grid)','stroke-width':i?0.5:0});
    const t=add('text',{x:pad-6,y:yy+3,'text-anchor':'end',class:'tick'});t.textContent=yv.toFixed(1);}
  [x0,Math.round((x0+x1)/2),x1].forEach(xv=>{const t=add('text',{x:sx(xv),y:H-pad+14,'text-anchor':'middle',class:'tick'});t.textContent=xv;});
  add('path',{class:'series',d:pts.map((p,i)=>(i?'L':'M')+sx(p.x).toFixed(1)+' '+sy(p.y).toFixed(1)).join(' ')});
  pts.forEach(p=>{const c=add('circle',{cx:sx(p.x),cy:sy(p.y),r:2.5,class:'dot'});
    const ti=document.createElementNS(ns,'title');ti.textContent=p.x+': '+p.y;c.appendChild(ti);});}

loadSamples();loadSchema();loadFlags();runsql();
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
            if u.path == "/healthz":
                return self._send(200, "ok", "text/plain")
            if u.path == "/api/query":
                return self._send(200, json.dumps(api_query((q.get("sql") or [""])[0])))
            if u.path == "/api/report":
                return self._send(200, json.dumps(api_betting(q)))
            if u.path == "/api/fantasy":
                return self._send(200, json.dumps(api_fantasy(q)))
            if u.path == "/api/norms":
                return self._send(200, json.dumps(api_norms(q)))
            if u.path == "/api/schema":
                return self._send(200, json.dumps(api_schema(q)))
            if u.path == "/" or u.path.startswith("/index"):
                return self._send(200, PAGE, "text/html; charset=utf-8")
        except Exception as e:  # noqa: BLE001
            return self._send(502, json.dumps({"error": str(e)}))
        return self._send(404, "not found", "text/plain")


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"NFL Guru dashboard at {url}  (Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
