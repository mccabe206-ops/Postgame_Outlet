"""Depth-chart view — localhost UI (port 8791).

A team's Ourlads starter->backup order with ESPN player photos + jersey numbers,
in two toggleable layouts:
  - List view: offense / defense / special / reserve columns, each position slot
    with its players in depth order (photo thumbnail + # + name).
  - Field view: a formation diagram (offense bottom, defense top) with the
    starter's photo placed at each slot and backups stacked beneath.

Data comes from depth_view.team_depth (Ourlads order + ESPN headshots). Read-only,
stdlib only. Lane-2 tool (testing branch) — never touches ratings or the site.

Endpoints:
  GET /                       -> the page
  GET /api/teams              -> all 32 abbrs
  GET /api/team?abbr=BUF&refresh=0  -> one team's depth chart with photos
"""
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import depth_view as DV

HOST = "127.0.0.1"
PORT = 8791

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Depth Charts · Power Ratings</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0e1116;--card:#171c24;--line:#273040;--ink:#e6edf3;--dim:#93a1b0;
  --off:#c8442e;--def:#2f5fa8;--field1:#4f9b4f;--field2:#3c7d3c;--accent:#4f9bff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px;flex-wrap:wrap}
h1{font-size:18px;margin:0}
.sub{color:var(--dim);font-size:12px}
a.xlink{color:var(--accent);font-size:12px;text-decoration:none}
button{font:inherit;cursor:pointer}
.teamgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(64px,1fr));gap:8px;padding:16px 20px}
.tbtn{background:var(--card);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:9px 0;font-weight:700;letter-spacing:.5px}
.tbtn:hover{border-color:var(--accent)}
.tbtn.on{border-color:var(--accent);background:#12233f}
.bar{padding:10px 20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;border-bottom:1px solid var(--line)}
.toggle{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.toggle button{background:var(--card);border:0;color:var(--dim);padding:6px 14px}
.toggle button.on{background:#12233f;color:var(--ink)}
.refresh{background:var(--card);border:1px solid var(--line);color:var(--dim);border-radius:8px;padding:6px 12px}
#view{padding:16px 20px}
/* list view */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:820px){.cols{grid-template-columns:1fr}}
.sec h2{font-size:13px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px;color:var(--dim)}
.sec.off h2{color:var(--off)}.sec.def h2{color:var(--def)}
.slot{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin-bottom:8px}
.slot .lbl{font-weight:700;font-size:11px;color:var(--dim);letter-spacing:.5px;margin-bottom:6px}
.plrow{display:flex;align-items:center;gap:9px;padding:3px 0}
.plrow .rank{width:16px;color:var(--dim);font-size:11px;text-align:center;flex:none}
.ph{width:34px;height:34px;border-radius:50%;background:#0b0e13;object-fit:cover;flex:none;border:1px solid var(--line)}
.ph.avatar{display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--dim);font-weight:700}
.plrow.starter .nm{font-weight:700}
.plrow .nm{font-size:13px}
.plrow .jer{color:var(--dim);font-size:11px;margin-left:auto;flex:none}
.tag{font-size:9.5px;color:var(--dim);border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:6px}
/* field view */
.field{position:relative;width:100%;max-width:960px;margin:0 auto;aspect-ratio:16/12;min-height:640px;
  border-radius:12px;overflow:hidden;border:1px solid var(--line);
  background:repeating-linear-gradient(var(--field1) 0 8.33%,var(--field2) 8.33% 16.66%)}
.los{position:absolute;left:0;right:0;top:50%;height:2px;background:rgba(255,255,255,.5)}
.stack{position:absolute;transform:translate(-50%,-50%);text-align:center;width:76px}
.stack .slotlbl{font-size:9px;font-weight:700;color:#fff;text-shadow:0 1px 2px #000;margin-bottom:2px}
.pl{display:flex;flex-direction:column;align-items:center;margin-bottom:2px}
.pl img,.pl .avatar{width:30px;height:30px;border-radius:50%;border:2px solid #fff;object-fit:cover;background:#0b0e13}
.pl.off img,.pl.off .avatar{border-color:var(--off)}
.pl.def img,.pl.def .avatar{border-color:var(--def)}
.pl.bk img,.pl.bk .avatar{width:20px;height:20px;opacity:.72;border-width:1px}
.pl .avatar{display:flex;align-items:center;justify-content:center;font-size:9px;color:#cfd8e3;font-weight:700}
.pl .pn{font-size:9px;color:#fff;text-shadow:0 1px 2px #000;max-width:76px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pl .pn .num{color:#ffd479}
.legend{color:var(--dim);font-size:11px;padding:6px 20px 20px;text-align:center}
.msg{color:var(--dim);padding:20px}
</style></head><body>
<header>
  <h1>Depth Charts</h1>
  <span class="sub" id="src">Ourlads order · ESPN photos</span>
  <a class="xlink" id="injLink" href="http://127.0.0.1:8789/" target="_blank">↗ injury dashboard</a>
  <a class="xlink" href="http://127.0.0.1:8786/" target="_blank">↗ hub</a>
</header>
<div class="teamgrid" id="teams"></div>
<div class="bar" id="bar" style="display:none">
  <strong id="teamName"></strong>
  <span class="toggle">
    <button id="tList" class="on" onclick="setView('list')">List</button>
    <button id="tField" onclick="setView('field')">Field</button>
  </span>
  <span class="toggle">
    <button id="sBoth" class="on" onclick="setSide('both')">Both</button>
    <button id="sOff" onclick="setSide('offense')">Offense</button>
    <button id="sDef" onclick="setSide('defense')">Defense</button>
  </span>
  <button class="refresh" id="refreshBtn" onclick="loadTeam(ABBR,true)">↻ refresh depth</button>
  <span class="sub" id="fresh"></span>
</div>
<div id="view"><div class="msg">Pick a team above.</div></div>
<div class="legend" id="legend"></div>
<script>
// slot -> field coordinates (% left / % top). Offense bottom half, defense top.
const COORD={
 LWR:[9,60],SWR:[24,64],RWR:[91,60],LT:[31,60],LG:[41,60],C:[50,60],RG:[59,60],RT:[69,60],
 TE:[80,62],QB:[50,73],FB:[41,80],RB:[59,84],HB:[59,84],
 LCB:[9,40],RCB:[91,40],CB:[9,40],NB:[24,36],
 LDE:[27,45],RDE:[73,45],DE:[38,45],NT:[50,45],LDT:[42,45],DT:[60,45],RDT:[62,45],
 LOLB:[30,32],ROLB:[70,32],MLB:[50,30],LILB:[42,31],RILB:[58,31],WLB:[36,32],SLB:[64,32],LB:[50,32],
 SS:[62,18],FS:[38,14],DB:[50,18]
};
let ABBR=null, VIEW='list', SIDE='both', DATA=null;
function esc(x){return (x==null?'':(''+x)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function titleCase(s){return (s||'').toLowerCase().replace(/\b([a-z])/g,m=>m.toUpperCase());}
function initials(nm){const p=(nm||'').trim().split(/\s+/);return ((p[0]||'')[0]||'')+((p[p.length-1]||'')[0]||'');}
function avatar(p,cls){const nm=titleCase(p.name);
  if(p.photo)return `<img class="ph ${cls||''}" src="${esc(p.photo)}" alt="${esc(nm)}" `+
    `onerror="this.outerHTML='<span class=\\'ph avatar ${cls||''}\\'>'+${JSON.stringify(esc(initials(p.name)))}+'</span>'">`;
  return `<span class="ph avatar ${cls||''}">${esc(initials(p.name))}</span>`;}

async function loadTeams(){
  const r=await fetch('/api/teams'); const d=await r.json();
  const g=document.getElementById('teams'); g.innerHTML='';
  d.teams.forEach(ab=>{const b=document.createElement('button');b.className='tbtn';b.textContent=ab;
    b.id='tb-'+ab; b.onclick=()=>loadTeam(ab,false); g.appendChild(b);});
}
async function loadTeam(ab,refresh){
  ABBR=ab;
  document.querySelectorAll('.tbtn').forEach(x=>x.classList.toggle('on',x.id==='tb-'+ab));
  const btn=document.getElementById('refreshBtn'); if(refresh){btn.textContent='↻ fetching…';btn.disabled=true;}
  document.getElementById('view').innerHTML='<div class="msg">loading…</div>';
  const r=await fetch('/api/team?abbr='+encodeURIComponent(ab)+'&refresh='+(refresh?1:0));
  const d=await r.json(); btn.textContent='↻ refresh depth';btn.disabled=false;
  if(!d.ok){document.getElementById('view').innerHTML='<div class="msg">'+esc(d.message||'error')+'</div>';return;}
  DATA=d; document.getElementById('bar').style.display='flex';
  document.getElementById('teamName').textContent=d.abbr+' · '+(d.name||'');
  document.getElementById('fresh').textContent='depth '+(d.from_cache?'cached':'fresh')+
    (d.fetched_at?' '+d.fetched_at:'')+(d.unmatched?(' · '+d.unmatched+' w/o photo'):'');
  render();
}
function setView(v){VIEW=v;document.getElementById('tList').classList.toggle('on',v==='list');
  document.getElementById('tField').classList.toggle('on',v==='field');render();}
function setSide(s){SIDE=s;
  document.getElementById('sBoth').classList.toggle('on',s==='both');
  document.getElementById('sOff').classList.toggle('on',s==='offense');
  document.getElementById('sDef').classList.toggle('on',s==='defense');render();}

function render(){ VIEW==='field'?renderField():renderList(); }

function plrowHtml(p){
  const tags=[]; if(p.note)tags.push(esc(p.note));
  return `<div class="plrow ${p.order===1?'starter':''}">`+
    `<span class="rank">${p.order}</span>`+avatar(p)+
    `<span class="nm">${esc(titleCase(p.name))}</span>`+
    (tags.length?`<span class="tag">${tags.join(' · ')}</span>`:'')+
    `<span class="jer">${p.jersey!=null&&p.jersey!==''?'#'+esc(p.jersey):''}</span></div>`;
}
function sectionHtml(title,cls,groups){
  if(!groups||!groups.length)return '';
  const slots=groups.map(g=>`<div class="slot"><div class="lbl">${esc(g.slot)}</div>`+
    g.players.map(plrowHtml).join('')+`</div>`).join('');
  return `<div class="sec ${cls}"><h2>${esc(title)}</h2>${slots}</div>`;
}
function renderList(){
  const d=DATA; const showOff=SIDE!=='defense', showDef=SIDE!=='offense';
  let left='', right='';
  if(showOff)left=sectionHtml('Offense','off',d.offense);
  if(showDef)right=sectionHtml('Defense','def',d.defense);
  const extra=(SIDE==='both')?(sectionHtml('Special Teams','', d.special)+sectionHtml('Reserve / IR','', d.reserve)):'';
  document.getElementById('view').innerHTML=
    `<div class="cols"><div>${left}${(SIDE==='both'||SIDE==='offense')?'':''}</div><div>${right}</div></div>`+
    (extra?`<div class="cols" style="margin-top:2px">${extra}</div>`:'');
  document.getElementById('legend').textContent='';
}
function stackHtml(g,cls){
  const co=COORD[g.slot]; if(!co)return '';
  const rows=g.players.slice(0,3).map((p,i)=>{const nm=titleCase(p.name).split(' ').slice(-1)[0];
    return `<div class="pl ${cls} ${i>0?'bk':''}">${avatar(p,'')}`+
      `<span class="pn">${i===0?'<span class=num>'+(p.jersey!=null&&p.jersey!==''?'#'+esc(p.jersey)+' ':'')+'</span>':''}${esc(nm)}</span></div>`;}).join('');
  return `<div class="stack" style="left:${co[0]}%;top:${co[1]}%"><div class="slotlbl">${esc(g.slot)}</div>${rows}</div>`;
}
function renderField(){
  const d=DATA; const showOff=SIDE!=='defense', showDef=SIDE!=='offense';
  const stacks=[]
    .concat(showOff?d.offense.map(g=>stackHtml(g,'off')):[])
    .concat(showDef?d.defense.map(g=>stackHtml(g,'def')):[]).join('');
  document.getElementById('view').innerHTML=`<div class="field"><div class="los"></div>${stacks}</div>`;
  document.getElementById('legend').innerHTML=
    'Starter shown large at each position; up to two backups stacked beneath. '+
    'Special teams &amp; reserves are in the List view. Depth order: Ourlads · photos: ESPN.';
}
// deep-link: ?q=BUF (or ?team=) auto-selects a team on load
(async function(){
  await loadTeams();
  const p=new URLSearchParams(location.search); const q=(p.get('q')||p.get('team')||'').trim();
  if(q) loadTeam(q.toUpperCase(),false);
})();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/teams":
            return self._send(200, json.dumps({"teams": DV.all_abbrs()}))
        if u.path == "/api/team":
            abbr = (q.get("abbr") or [""])[0]
            refresh = (q.get("refresh") or ["0"])[0] == "1"
            try:
                return self._send(200, json.dumps(DV.team_depth(abbr, refresh=refresh)))
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "message": str(e)}))
        return self._send(404, json.dumps({"ok": False, "message": "not found"}))


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"Depth Charts serving at {url}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
