"""Localhost Injury Report dashboard — a browser view of injuries.py.

Two views, rendered from the SAME data injuries.py produces so the dashboard and
CLI can never disagree:

  1. Team grid — all 32 teams, worst-first, each showing its injury load. Click one.
  2. Team view — a football-field formation diagram (offense / defense / both)
     with each starter placed at his position; injured starters light up by
     severity and are clickable for the detail. Plus the injury list for that side.

The render is a self-contained HTML page fetching JSON endpoints — the same shape
a future public page on postgameoutlet.com would use, fed by the daily artifact.

Bound to 127.0.0.1 only, on its own port (pick sheet=8787, team workspace=8788).

Run:
    python3 injury_server.py            # open the dashboard
    python3 injury_server.py --no-open

Endpoints:
    GET /                          -> dashboard page
    GET /api/grid?refresh=0        -> all 32 teams with injury counts (worst-first)
    GET /api/team?abbr=SF&refresh=0 -> one team: injuries + offense/defense starters
    GET /healthz                   -> ok
"""

import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import injuries
import sleeper

HOST = "127.0.0.1"
PORT = 8789


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Injury Report — McCabe Method</title>
<style>
 :root{
   color-scheme:light;
   --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
   --line:#e1e0d9; --border:rgba(11,11,11,0.10);
   --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
   --off:#b23b3b; --def:#2f4a6b;
   --field1:#4f9b4f; --field2:#3c7d3c;
 }
 @media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
   color-scheme:dark;
   --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
   --line:#2c2c2a; --border:rgba(255,255,255,0.10);
 }}
 :root[data-theme="dark"]{
   color-scheme:dark;
   --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
   --line:#2c2c2a; --border:rgba(255,255,255,0.10);
 }
 *{box-sizing:border-box}
 body{margin:0;background:var(--plane);color:var(--ink);
   font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
 header{padding:14px 22px;border-bottom:1px solid var(--border);display:flex;gap:12px;
   align-items:center;flex-wrap:wrap;position:sticky;top:0;background:var(--plane);z-index:5}
 h1{font-size:18px;margin:0;font-weight:700}
 .fresh{color:var(--muted);font-size:12px}
 .spacer{flex:1}
 button{background:var(--surface);border:1px solid var(--border);color:var(--ink);
   padding:7px 11px;border-radius:8px;font-size:14px;font-family:inherit;cursor:pointer}
 button:hover{border-color:var(--muted)}
 .wrap{padding:18px 22px;max-width:1040px;margin:0 auto}
 /* grid */
 .teamgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
 .tcard{background:var(--surface);border:1px solid var(--border);border-radius:12px;
   padding:12px 14px;cursor:pointer;transition:border-color .12s}
 .tcard:hover{border-color:var(--muted)}
 .tcard .ab{font-size:20px;font-weight:800;letter-spacing:.02em}
 .tcard .nm{color:var(--ink2);font-size:12px;margin-bottom:8px}
 .tcard .st{font-size:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
 .dot{width:9px;height:9px;border-radius:50%;display:inline-block}
 .badge{font-size:11px;font-weight:700;border-radius:999px;padding:1px 7px;border:1px solid}
 .b-crit{color:var(--ink);background:rgba(208,59,59,.15);border-color:rgba(208,59,59,.55)}
 .b-clean{color:var(--muted);background:transparent;border-color:var(--border)}
 .b-clus{color:var(--ink);background:rgba(208,59,59,.15);border-color:rgba(208,59,59,.6)}
 /* team view */
 .topbar{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
 .topbar h2{margin:0;font-size:20px}
 .seg{display:inline-flex;border:1px solid var(--border);border-radius:9px;overflow:hidden}
 .seg button{border:none;border-radius:0;background:transparent;padding:6px 14px}
 .seg button.on{background:var(--ink);color:var(--plane);font-weight:700}
 .field{position:relative;width:100%;aspect-ratio:16/11;min-height:660px;border-radius:12px;overflow:hidden;
   background:repeating-linear-gradient(var(--field1) 0 8.33%,var(--field2) 8.33% 16.66%);
   border:1px solid var(--border);margin-bottom:6px}
 .field.offense,.field.defense{min-height:600px;aspect-ratio:16/10}
 .los{position:absolute;left:0;right:0;top:50%;height:2px;background:rgba(255,255,255,.85)}
 .hash{position:absolute;top:calc(50% - 7px);width:2px;height:14px;background:rgba(255,255,255,.7)}
 .stack{position:absolute;transform:translate(-50%,-50%);width:106px;text-align:center;
   background:rgba(10,20,10,.42);border-radius:8px;padding:3px 4px;backdrop-filter:blur(1px)}
 .stack.off{box-shadow:inset 0 0 0 1.5px rgba(178,59,59,.85)}
 .stack.def{box-shadow:inset 0 0 0 1.5px rgba(120,150,190,.85)}
 .field.both .stack{width:92px}
 .field.both .pl{font-size:9.5px}
 .stack .lbl{font-size:10px;font-weight:800;color:#fff;letter-spacing:.04em;margin-bottom:2px}
 .pl{font-size:10.5px;line-height:1.22;color:#eef0ee;white-space:normal;overflow:hidden;
   word-break:break-word;border-radius:4px;padding:1px 3px;cursor:pointer}
 .pl:hover{outline:1px solid rgba(255,255,255,.5)}
 .pl.sel{outline:2px solid #fff;outline-offset:1px}
 .pl.st{font-weight:700}
 .pl.crit{background:var(--critical);color:#fff;font-weight:700}
 .pl.serious{background:var(--serious);color:#141414;font-weight:700}
 .pl.watch{background:var(--warning);color:#141414;font-weight:700}
 .legend{color:var(--muted);font-size:12px;margin:8px 0 4px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
 .legend .k{display:inline-flex;gap:5px;align-items:center}
 .legend .chip{width:14px;height:10px;border-radius:3px;display:inline-block}
 .selcard{background:var(--surface);border:1px solid var(--border);border-radius:12px;
   padding:12px 16px;margin:8px 0 16px;min-height:20px}
 .selcard .nm{font-weight:700;font-size:16px}
 .selcard .meta{color:var(--ink2);font-size:13px;margin-top:2px}
 .ret{font-size:13px;margin-top:6px;font-weight:600;color:var(--ink)}
 .ret.season{color:var(--critical)}
 .ret .cap{font-weight:400;color:var(--muted)}
 .ret2{font-size:11.5px;color:var(--ink2);white-space:nowrap}
 .subhead{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin:14px 0 6px}
 .row{display:flex;gap:10px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--line)}
 .row:last-child{border-bottom:none}
 .pos{color:var(--ink2);font-weight:600;min-width:36px;font-size:13px;padding-top:2px}
 .who{flex:1}.nm2{font-weight:600}.det{color:var(--ink2);font-size:13px}
 .tags{margin-top:2px;display:flex;gap:6px;flex-wrap:wrap}
 .tag{font-size:11px;color:var(--ink2);background:var(--plane);border:1px solid var(--border);border-radius:999px;padding:1px 8px}
 .tag.warn{color:var(--ink);background:rgba(250,178,25,.16);border-color:rgba(250,178,25,.55)}
 .sev{display:inline-flex;gap:5px;align-items:center;font-size:12px;font-weight:700;border-radius:999px;padding:2px 9px;white-space:nowrap}
 .sev .g{font-size:10px}
 .sev-crit{color:var(--ink);background:rgba(208,59,59,.16);border:1px solid rgba(208,59,59,.55)}
 .sev-serious{color:var(--ink);background:rgba(236,131,90,.18);border:1px solid rgba(236,131,90,.6)}
 .sev-watch{color:var(--ink);background:rgba(250,178,25,.16);border:1px solid rgba(250,178,25,.55)}
 .empty{color:var(--muted);padding:14px 0}
 .hide{display:none}
</style></head><body>
<header>
  <h1 id="title">Injury Report</h1>
  <button id="back" class="hide" onclick="showGrid()">← all teams</button>
  <span class="fresh" id="fresh"></span>
  <span class="spacer"></span>
  <button onclick="reloadGrid(true)" id="refreshBtn">↻ refresh from Sleeper</button>
  <button onclick="toggleTheme()" title="light / dark">◐</button>
</header>
<div class="wrap">
  <div id="grid"></div>
  <div id="team" class="hide"></div>
</div>
<script>
const SEV_COLOR={crit:'#d03b3b',serious:'#ec835a',watch:'#fab219'};
// slot -> field coordinates (% left / % top). Offense bottom half, defense top half.
const COORD={
 LWR:[8,56],SWR:[21,61],RWR:[92,56],LT:[30,58],LG:[40,58],C:[50,58],RG:[60,58],RT:[70,58],
 TE:[80,60],QB:[50,73],FB:[40,80],RB:[60,84],HB:[60,84],
 LCB:[8,42],RCB:[92,42],NB:[22,37],CB:[9,42],
 LDE:[26,44],RDE:[74,44],DE:[50,44],LDT:[40,44],RDT:[60,44],NT:[50,44],DT:[46,44],DL:[50,44],
 LOLB:[30,33],ROLB:[70,33],MLB:[50,31],LILB:[42,32],RILB:[58,32],WLB:[36,33],SLB:[64,33],LB:[50,33],
 SS:[62,20],FS:[38,16],DB:[50,20]
};
let TEAM=null, SIDE='offense', SELECTED=null, FLAT=[];

function esc(x){return (x==null?'':(''+x)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function sevKey(s){return s>=5?'crit':s>=3?'serious':'watch';}
function sevGlyph(k){return k==='crit'?'⬤':k==='serious'?'◆':'▲';}
// "Undisclosed"/"Not Injury Related" are Sleeper filler, not real detail — drop them.
function clean(v){ if(!v)return ''; const b=(''+v).trim().toLowerCase();
  return (b==='undisclosed'||b==='not injury related'||b==='n/a')?'':(''+v).trim(); }
function detailText(i){ return [clean(i.body_part),clean(i.notes)].filter(Boolean).join('; '); }

async function reloadGrid(refresh){
  const btn=document.getElementById('refreshBtn');
  if(refresh){btn.textContent='↻ fetching…';btn.disabled=true;}
  const r=await fetch('/api/grid?refresh='+(refresh?1:0));
  const d=await r.json();
  btn.textContent='↻ refresh from Sleeper';btn.disabled=false;
  document.getElementById('fresh').textContent='source: Sleeper · '+(d.from_cache?'cached ':'fresh ')+(d.generated||'');
  window.__grid=d; renderGrid(d);
}
function renderGrid(d){
  const rows=(d.teams||[]).slice().sort((a,b)=>
    (b.clusters-a.clusters)||(b.severe_starters-a.severe_starters)||a.abbr.localeCompare(b.abbr));
  document.getElementById('grid').innerHTML='<div class="teamgrid">'+rows.map(t=>{
    const sp=n=>n+' starter'+(n===1?'':'s');
    let st;
    if(t.clusters) st=`<span class="badge b-clus">⚠ ${t.clusters} cluster${t.clusters>1?'s':''}</span>`+
       `<span class="badge b-crit">${sp(t.severe_starters)} out</span>`;
    else if(t.severe_starters) st=`<span class="dot" style="background:${SEV_COLOR.crit}"></span>`+
       `<span class="badge b-crit">${sp(t.severe_starters)} out</span>`;
    else st=`<span class="badge b-clean">clean</span>`;
    return `<div class="tcard" onclick="openTeam('${t.abbr}')"><div class="ab">${t.abbr}</div>`+
      `<div class="nm">${esc(t.name)}</div><div class="st">${st}</div></div>`;
  }).join('')+'</div>';
}

async function openTeam(abbr){
  const r=await fetch('/api/team?abbr='+abbr);
  TEAM=await r.json(); SIDE='both'; SELECTED=null;
  document.getElementById('grid').classList.add('hide');
  document.getElementById('team').classList.remove('hide');
  document.getElementById('back').classList.remove('hide');
  document.getElementById('title').textContent='Injury Report · '+abbr;
  renderTeam();
}
function showGrid(){
  document.getElementById('team').classList.add('hide');
  document.getElementById('grid').classList.remove('hide');
  document.getElementById('back').classList.add('hide');
  document.getElementById('title').textContent='Injury Report';
}
function setSide(s){SIDE=s;SELECTED=null;renderTeam();}

function renderTeam(){
  const t=TEAM; if(!t)return;
  // flat index of every player entry, so a clicked row can be looked up by data-i
  FLAT=[]; (t.offense||[]).concat(t.defense||[]).forEach(it=>(it.players||[]).forEach(p=>{
    p._slot=it.slot; p._i=FLAT.length; FLAT.push(p);}));
  const showOff=SIDE!=='defense', showDef=SIDE!=='offense';
  const maxDepth=SIDE==='both'?2:5;  // Both is a compact overview; single side shows full depth
  const stacks=[]
    .concat(showOff?(t.offense||[]).map(it=>stack(it,'off',maxDepth)):[])
    .concat(showDef?(t.defense||[]).map(it=>stack(it,'def',maxDepth)):[]).join('');
  const hashes=[20,40,60,80].map(x=>`<div class="hash" style="left:${x}%"></div>`).join('');
  const clusters=(t.clusters||[]).map(c=>
    `<div class="sev sev-crit" style="margin-right:8px">⚠ ${esc(c.group)} cluster: ${esc((c.players||[]).join(', '))}</div>`).join('');
  const listInj=(t.injuries||[]).filter(i=>{
    const g=grpOf(i.group); return SIDE==='both'||(SIDE==='offense'&&g==='off')||(SIDE==='defense'&&g==='def');});
  document.getElementById('team').innerHTML=`
    <div class="topbar">
      <h2>${esc(t.abbr)} <span style="color:var(--ink2);font-weight:500;font-size:15px">${esc(t.name||'')}</span></h2>
      <div class="seg">
        <button class="${SIDE==='both'?'on':''}" onclick="setSide('both')">Both</button>
        <button class="${SIDE==='offense'?'on':''}" onclick="setSide('offense')">Offense</button>
        <button class="${SIDE==='defense'?'on':''}" onclick="setSide('defense')">Defense</button>
      </div>
    </div>
    ${clusters?('<div style="margin-bottom:10px">'+clusters+'</div>'):''}
    <div class="field ${SIDE}">${hashes}<div class="los"></div>${stacks}</div>
    <div class="legend">
      <span class="k"><span class="dot" style="background:var(--off)"></span>offense</span>
      <span class="k"><span class="dot" style="background:var(--def)"></span>defense</span>
      <span class="k"><span class="chip" style="background:${SEV_COLOR.crit}"></span>IR/PUP</span>
      <span class="k"><span class="chip" style="background:${SEV_COLOR.serious}"></span>Out/Doubtful</span>
      <span class="k"><span class="chip" style="background:${SEV_COLOR.watch}"></span>Questionable</span>
      <span>starter listed first; click a player for the latest Sleeper update</span>
    </div>
    <div class="selcard" id="selcard">Click any player for their latest injury update from Sleeper.</div>
    <div class="subhead">${SIDE==='both'?'all':SIDE} injuries</div>
    <div id="injlist">${listInj.length?listInj.map(injRow).join(''):'<div class="empty">No injuries on this side.</div>'}</div>`;
}
function grpOf(g){return ['QB','RB','WR','TE','OL'].includes(g)?'off':'def';}
// keep first `max` in depth order, but always include any injured player deeper than that
function capDepth(players,max){
  const head=players.slice(0,max);
  const extra=players.slice(max).filter(p=>p.injury);
  return head.concat(extra);
}
function lastName(n){const s=(n||'').replace(/\s+(Jr\.?|Sr\.?|II|III|IV|V)$/,'').trim().split(' ');
  return s.length>1?s.slice(1).join(' '):s[0];}
function stack(item,side,maxDepth){
  const co=COORD[item.slot]; if(!co)return '';
  const rows=capDepth(item.players||[],maxDepth||5).map((p,idx)=>{
    const inj=p.injury; let cls='pl'+(idx===0?' st':''); let tag='';
    if(inj){const k=sevKey(inj.severity); cls+=' '+k; tag=' · '+esc(inj.status);}
    const dt=inj?(detailText(inj)||inj.status):'';
    return `<div class="${cls}" data-i="${p._i}" title="${esc(dt)}">${esc(p.name)}${tag}</div>`;
  }).join('');
  return `<div class="stack ${side}" style="left:${co[0]}%;top:${co[1]}%">`+
    `<div class="lbl">${esc(item.slot)}</div>${rows}</div>`;
}
function fmtUpdated(ms){ if(!ms)return ''; try{
  return new Date(ms).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
}catch(e){return '';} }
// "how long ago" from a ms-epoch Sleeper news_updated timestamp
function relTime(ms){ if(!ms)return ''; const s=(Date.now()-ms)/1000;
  if(s<90)return 'just now';
  const m=Math.round(s/60); if(m<60)return m+(m===1?' minute ago':' minutes ago');
  const h=Math.round(m/60); if(h<24)return h+(h===1?' hour ago':' hours ago');
  const d=Math.round(h/24); if(d<14)return d+(d===1?' day ago':' days ago');
  const w=Math.round(d/7); if(w<9)return w+(w===1?' week ago':' weeks ago');
  const mo=Math.round(d/30.4); if(mo<18)return mo+(mo===1?' month ago':' months ago');
  const y=Math.round(d/365); return y+(y===1?' year ago':' years ago'); }
function updatedLine(ms){ const rel=relTime(ms); if(!rel)return ''; const abs=fmtUpdated(ms);
  return ' · updated '+rel+(abs?' ('+abs+')':''); }
function roleLabel(r){return r==='EFFECTIVE'?'effective starter (promoted)':r==='STARTER'?'starter':
  r==='SHELVED'?'role unclear — verify':'backup';}
function pick(i){
  const p=FLAT[i]; if(!p)return;
  const card=document.getElementById('selcard'); if(!card)return;
  document.querySelectorAll('.pl.sel').forEach(el=>el.classList.remove('sel'));
  document.querySelectorAll('.pl[data-i="'+i+'"]').forEach(el=>el.classList.add('sel'));
  const inj=p.injury, u=p.update||{};
  if(inj){
    const k=sevKey(inj.severity), dt=detailText(inj), bits=[];
    if(dt)bits.push(dt);
    if(inj.practice)bits.push('practice: '+inj.practice);
    bits.push(roleLabel(inj.role));
    if(inj.ourlads_agree==='differs')bits.push('⚠ Ourlads has him at '+inj.ourlads);
    else if(inj.ourlads_agree==='absent')bits.push('not on Ourlads chart');
    const upd=updatedLine(inj.updated||u.updated);
    const rt=inj.return_est;
    const retHtml=rt?`<div class="ret${rt.season_ending?' season':''}">🩺 Est. return: ${esc(rt.eta)} `+
      `<span class="cap">· typical ${esc(rt.duration)} for ${esc(rt.label)}${rt.confidence==='rough'?' · rough (no body-part detail)':''}</span></div>`:'';
    card.innerHTML=`<div class="nm">${esc(p._slot)} · ${esc(p.name)} `+
      `<span class="sev sev-${k}"><span class="g">${sevGlyph(k)}</span>${esc(inj.status)}</span></div>`+
      `<div class="meta">${esc(bits.join(' · '))}${esc(upd)}</div>`+retHtml;
  } else {
    const upd=updatedLine(u.updated);
    const note=p.ourlads_note?(' · Ourlads note: '+esc(p.ourlads_note)):'';
    card.innerHTML=`<div class="nm">${esc(p._slot)} · ${esc(p.name)}</div>`+
      `<div class="meta">No active injury reported by Sleeper.${esc(upd)}${note}</div>`;
  }
}
function teamClick(e){const el=e.target.closest('.pl[data-i]'); if(el)pick(+el.getAttribute('data-i'));}
function injRow(i){
  const k=sevKey(i.severity);const dt=detailText(i);
  const role=i.role==='EFFECTIVE'?'effective starter (promoted)':i.role==='STARTER'?'starter':i.role==='SHELVED'?'role unclear — verify':'backup';
  const tags=[`<span class="tag">${role}</span>`];
  if(i.return_est)tags.push(`<span class="tag">🩺 ${esc(i.return_est.eta)}</span>`);
  if(i.ourlads_agree==='differs')tags.push(`<span class="tag warn">⚠ Ourlads: ${esc(i.ourlads)}</span>`);
  else if(i.ourlads_agree==='absent')tags.push(`<span class="tag warn">not on Ourlads chart</span>`);
  return `<div class="row"><div class="pos">${esc(i.position||i.dcp||'?')}</div><div class="who">`+
    `<span class="nm2">${esc(i.name)}</span> <span class="sev sev-${k}"><span class="g">${sevGlyph(k)}</span>${esc(i.status)}</span>`+
    (dt?` <span class="det">${esc(dt)}</span>`:'')+`<div class="tags">${tags.join('')}</div></div></div>`;
}
function toggleTheme(){const el=document.documentElement,cur=el.getAttribute('data-theme');
  const dark=cur?cur==='dark':matchMedia('(prefers-color-scheme:dark)').matches;
  el.setAttribute('data-theme',dark?'light':'dark');}
document.getElementById('team').addEventListener('click',teamClick);
reloadGrid();
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
        refresh = (q.get("refresh") or ["0"])[0] == "1"
        if u.path == "/healthz":
            return self._send(200, "ok", "text/plain")
        if u.path == "/api/grid":
            try:
                bundle = sleeper.get_players(force=refresh)
                return self._send(200, json.dumps({
                    "generated": bundle.get("fetched_at"),
                    "from_cache": bundle.get("from_cache"),
                    "teams": injuries.league_grid(bundle)}))
            except Exception as e:  # noqa: BLE001
                return self._send(502, json.dumps({"error": str(e)}))
        if u.path == "/api/team":
            abbr = (q.get("abbr") or [""])[0].upper()
            if abbr not in sleeper.NFL_ABBRS:
                return self._send(200, json.dumps({"error": "unknown team"}))
            try:
                bundle = sleeper.get_players(force=refresh)
                return self._send(200, json.dumps(injuries.team_detail(bundle, abbr)))
            except Exception as e:  # noqa: BLE001
                return self._send(502, json.dumps({"error": str(e)}))
        if u.path == "/" or u.path.startswith("/index"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        return self._send(404, "not found", "text/plain")


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Injury Report dashboard at {url}  (Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
