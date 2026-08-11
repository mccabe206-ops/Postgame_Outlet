"""Localhost-only pick-sheet server.

Serves an editable weekly pick sheet and saves Sean's picks (side + confidence)
back to a private, gitignored file. Bound to 127.0.0.1 so ONLY this machine can
reach it — it is not exposed to any network.

Run:
    python3 pick_server.py            # current week, opens browser
    python3 pick_server.py 3 2026     # explicit week/year
    python3 pick_server.py --no-open  # don't auto-open the browser

Endpoints:
    GET  /                     -> the editable sheet (HTML)
    GET  /api/sheet            -> sheet JSON
    POST /api/pick             -> {game_id, side, confidence} save one pick
    GET  /healthz              -> "ok"

Stdlib only (http.server). Stop with Ctrl-C or the agent stops the process.
"""

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import picks as P

HOST = "127.0.0.1"
PORT = 8787

_STATE = {"week": None, "year": None}


def _sheet():
    return P.build_sheet(week=_STATE["week"], year=_STATE["year"])


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>McCabe Picks — Week {week}</title>
<style>
 :root{{--bg:#0e1116;--card:#171c24;--line:#273040;--ink:#e6edf3;--dim:#93a1b0;
        --good:#2ea043;--bad:#e5534b;--accent:#3b82f6;--lock:#4b5563}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
   font:15px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}}
 header{{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;
   align-items:baseline;gap:14px;position:sticky;top:0;background:var(--bg);z-index:5}}
 h1{{font-size:19px;margin:0}} .sub{{color:var(--dim);font-size:13px}}
 #status{{margin-left:auto;font-size:13px;color:var(--dim)}}
 #saved{{font-size:13px;padding:3px 10px;border-radius:20px;margin-left:12px;
   background:#12331d;color:var(--good);border:1px solid #1c4a2b;opacity:0;
   transition:opacity .25s}}
 #saved.show{{opacity:1}} #saved.saving{{background:#2a2f0e;color:#d8c534;border-color:#4a4a1c}}
 table{{width:100%;border-collapse:collapse}}
 th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
 th{{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
 .num{{text-align:right;font-variant-numeric:tabular-nums}}
 .team-btn{{background:var(--card);border:1px solid var(--line);color:var(--ink);
   padding:6px 10px;border-radius:8px;cursor:pointer;font-size:14px;margin:2px 0}}
 .team-btn.sel{{border-color:var(--accent);background:#12233f;color:#fff;font-weight:600}}
 .team-btn:disabled{{opacity:.5;cursor:not-allowed}}
 .edge-pos{{color:var(--good)}} .edge-neg{{color:var(--bad)}}
 .locked td{{opacity:.55}} .lockchip{{font-size:11px;color:#fff;background:var(--lock);
   padding:2px 7px;border-radius:20px}}
 select.conf{{background:var(--card);border:1px solid var(--line);color:var(--ink);
   padding:5px 8px;border-radius:8px;font-size:14px}}
 select.conf:disabled{{opacity:.5;cursor:not-allowed}}
 .matchup{{font-weight:600}}
 footer{{padding:14px 22px;color:var(--dim);font-size:12px;border-top:1px solid var(--line)}}
</style></head><body>
<header>
  <h1>McCabe Picks</h1>
  <span class="sub">Week {week} · {season} · your line vs. ESPN market</span>
  <span id="status">loading…</span>
  <span id="saved"></span>
</header>
<table id="grid"><thead><tr>
  <th>Kickoff</th><th>Matchup</th><th class="num">My line</th>
  <th class="num">Market</th><th class="num">Edge</th>
  <th>My pick (side)</th><th>Confidence</th><th></th>
</tr></thead><tbody id="rows"></tbody></table>
<footer>Pick <b>exactly 5 games</b> and give each a <b>different</b> confidence (5 = most
confident … 1 = least). Picks are private (saved locally, gitignored). A game locks at its
kickoff — before then you can change that pick freely. Edge = market − my line.</footer>
<script>
const fmtSpread = (s, team) => s===null||s===undefined ? "—"
   : (s===0 ? "PK" : (s<0 ? team+" "+s : team+" +"+s));
let SHEET=null;
async function load(){{
  const r = await fetch('/api/sheet'); SHEET = await r.json();
  render();
}}
function render(){{
  const tb=document.getElementById('rows'); tb.innerHTML='';
  const MAX=SHEET.max_picks, WEIGHTS=SHEET.conf_weights;   // [1..5]
  const used=new Set(SHEET.used_confidence);                // weights already taken
  const picked=SHEET.picked_count;
  const poolFull = picked>=MAX;
  for(const g of SHEET.games){{
    const tr=document.createElement('tr'); if(g.locked) tr.className='locked';
    const edgeCls = g.edge>0?'edge-pos':(g.edge<0?'edge-neg':'');
    const isPicked = !!g.pick_side;
    // A team can be clicked if the game is unlocked AND (it's already one of my picks OR pool has room)
    const canPick = !g.locked && (isPicked || !poolFull);
    const dis = canPick ? '' : 'disabled';
    // Confidence dropdown: only weights not used by OTHER games (plus this game's own)
    const opts = ['<option value="">conf…</option>'].concat(
      WEIGHTS.slice().reverse().filter(w=> !used.has(w) || w===g.pick_confidence)
        .map(w=>`<option value="${{w}}" ${{g.pick_confidence===w?'selected':''}}>${{w}}${{w===5?' (max)':(w===1?' (min)':'')}}</option>`)
    ).join('');
    tr.innerHTML=`
      <td>${{g.kickoff_local}} ${{g.locked?'<span class=lockchip>LOCKED</span>':''}}</td>
      <td class="matchup">${{g.away}} @ ${{g.home}}</td>
      <td class="num">${{fmtSpread(g.my_spread, g.home)}}</td>
      <td class="num">${{g.market===null?'—':fmtSpread(g.market, g.home)}}</td>
      <td class="num ${{edgeCls}}">${{g.edge===null?'—':(g.edge>0?'+':'')+g.edge}}</td>
      <td>
        <button class="team-btn ${{g.pick_side==='away'?'sel':''}}" ${{g.pick_side==='away'?'':dis}}
          onclick="pick('${{g.game_id}}','away')">${{g.away}}</button>
        <button class="team-btn ${{g.pick_side==='home'?'sel':''}}" ${{g.pick_side==='home'?'':dis}}
          onclick="pick('${{g.game_id}}','home')">${{g.home}}</button>
      </td>
      <td><select class="conf" ${{(isPicked && !g.locked)?'':'disabled'}}
            onchange="conf('${{g.game_id}}',this.value)">${{opts}}</select></td>
      <td>${{isPicked?'<button class="team-btn" '+(g.locked?'disabled':'')+' onclick="clr(\\''+g.game_id+'\\')">clear</button>':''}}</td>`;
    tb.appendChild(tr);
  }}
  const remaining = MAX-picked;
  const missing = WEIGHTS.filter(w=>!used.has(w));
  let msg = `${{picked}}/${{MAX}} picked`;
  if(picked<MAX) msg += ` · ${{remaining}} to go`;
  const needConf = SHEET.games.filter(g=>g.pick_side && !g.pick_confidence).length;
  if(needConf) msg += ` · ${{needConf}} need a confidence`;
  if(picked===MAX && !needConf) msg = `✓ Complete — 5 picks, all rated`;
  document.getElementById('status').textContent = msg;
}}
function flagSaving(){{const s=document.getElementById('saved');
  s.textContent='Saving…'; s.className='show saving';}}
function flagSaved(){{const s=document.getElementById('saved');
  const t=new Date().toLocaleTimeString([], {{hour:'2-digit',minute:'2-digit'}});
  s.textContent='Saved ✓ '+t; s.className='show';
  clearTimeout(s._t); s._t=setTimeout(()=>{{s.classList.remove('show');}}, 2500);}}
function flagError(msg){{const s=document.getElementById('saved');
  s.textContent='⚠ '+(msg||'not saved'); s.className='show saving';}}
async function post(body){{
  flagSaving();
  try{{
    const r=await fetch('/api/pick',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify(body)}});
    const j=await r.json();
    if(!j.ok){{ flagError(j.message); alert(j.message||'could not save'); }}
    else {{ flagSaved(); }}
  }}catch(e){{ flagError('server offline'); }}
  await load();
}}
function pick(id,side){{const g=SHEET.games.find(x=>x.game_id===id);
  // toggle off if clicking the already-selected side
  if(g.pick_side===side){{ clr(id); return; }}
  post({{game_id:id,side:side,confidence:g.pick_confidence||''}});}}
function conf(id,v){{const g=SHEET.games.find(x=>x.game_id===id);
  if(!g.pick_side){{alert('Pick a side first');return;}}
  post({{game_id:id,side:g.pick_side,confidence:v||null}});}}
function clr(id){{post({{game_id:id,side:null}});}}
load(); setInterval(load, 60000);  // refresh lock states / lines each minute
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, "ok", "text/plain")
        if self.path.startswith("/api/sheet"):
            try:
                return self._send(200, json.dumps(_sheet()))
            except Exception as e:  # noqa: BLE001
                return self._send(502, json.dumps({"error": str(e)}))
        if self.path == "/" or self.path.startswith("/index"):
            try:
                s = _sheet()
            except Exception as e:  # noqa: BLE001
                return self._send(502, f"<h1>ESPN fetch failed</h1><pre>{e}</pre>", "text/html")
            html = PAGE.format(week=s["week"], season=s["season"])
            return self._send(200, html, "text/html; charset=utf-8")
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/pick":
            return self._send(404, "not found", "text/plain")
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, json.dumps({"ok": False, "message": "bad json"}))
        s = _sheet()
        idx = {g["game_id"]: g["kickoff"] for g in s["games"]}
        ok, msg = P.save_pick(s["season"], s["week"], body.get("game_id"),
                              body.get("side"), body.get("confidence"), idx)
        return self._send(200, json.dumps({"ok": ok, "message": msg}))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        _STATE["week"] = int(args[0])
    if len(args) > 1:
        _STATE["year"] = int(args[1])
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Pick sheet live at {url}  (Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
