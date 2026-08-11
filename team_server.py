"""Localhost 'Update Ratings' workspace — per-team viewer.

A read-only browser page for ONE team at a time: current QB/Off/Def + total, the
live write-up, and the full season results (most recent first). Sean reads this,
then types his context to the agent in chat; the agent suggests a rating move and
drafts the write-up. The page is a display surface — the reasoning is the AI.

Bound to 127.0.0.1 only. Separate port from the pick sheet so both can run.

Run:
    python3 team_server.py "Buffalo Bills"        # open a team
    python3 team_server.py bills 2024             # team + season year
    python3 team_server.py --no-open "Bills"

Endpoints:
    GET /            -> workspace page (team selector + current team)
    GET /api/team?q=<team>&year=<yr>  -> team snapshot JSON
    GET /api/teams   -> list of all 32 team names (for the selector)
    GET /healthz     -> ok
"""

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import team_view as TV

HOST = "127.0.0.1"
PORT = 8788

_STATE = {"team": "Buffalo Bills", "year": None}


def _default_year():
    cfg = {}
    import csv
    p = os.path.join(TV.DATA, "config.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p, newline="")):
            cfg[r["key"]] = r["value"]
    return int(cfg.get("season", "2026"))


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Update Ratings — workspace</title>
<style>
 :root{{--bg:#0e1116;--card:#171c24;--line:#273040;--ink:#e6edf3;--dim:#93a1b0;
        --good:#2ea043;--bad:#e5534b;--accent:#3b82f6}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
   font:15px/1.45 -apple-system,Segoe UI,Roboto,sans-serif}}
 header{{padding:16px 22px;border-bottom:1px solid var(--line);display:flex;gap:14px;align-items:center}}
 h1{{font-size:18px;margin:0}} select{{background:var(--card);border:1px solid var(--line);
   color:var(--ink);padding:7px 10px;border-radius:8px;font-size:15px}}
 .wrap{{padding:20px 22px;max-width:900px}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}}
 .rat{{display:flex;gap:26px;flex-wrap:wrap;align-items:baseline}}
 .rat .b{{font-size:13px;color:var(--dim);text-transform:uppercase;letter-spacing:.04em}}
 .rat .v{{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}}
 .rat .tot .v{{color:var(--accent)}}
 .qbname{{color:var(--dim);font-size:14px;margin-top:2px}}
 .notes{{color:var(--dim);font-size:13px;margin-top:10px;font-style:italic}}
 table{{width:100%;border-collapse:collapse;font-size:14px}}
 th,td{{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
 th{{color:var(--dim);font-size:12px;text-transform:uppercase}}
 .W{{color:var(--good);font-weight:700}} .L{{color:var(--bad);font-weight:700}}
 .num{{text-align:right;font-variant-numeric:tabular-nums}}
 .recent{{outline:1px solid var(--accent);outline-offset:-1px}}
 h2{{font-size:13px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em;margin:2px 0 12px}}
 .writeup{{white-space:pre-wrap;font-size:14px;line-height:1.6}}
 .rec{{font-size:15px;color:var(--dim);margin-left:auto}}
 .hint{{padding:10px 14px;background:#12233f;border:1px solid #1c3a63;border-radius:10px;
   font-size:13px;color:#b9d2f5;margin-bottom:16px}}
 .thread{{border-left:3px solid var(--accent);padding:6px 12px;margin:8px 0;background:#10151d}}
 .thread .topic{{font-weight:600}} .thread .meta{{color:var(--dim);font-size:12px}}
 .thread .entry{{font-size:13px;color:#c8d3de;margin-top:3px}}
 .noopen{{color:var(--dim);font-size:13px}}
 details summary{{cursor:pointer;color:var(--dim);font-size:13px;text-transform:uppercase;
   letter-spacing:.05em;padding:4px 0}}
 .caveat{{color:var(--dim);font-size:12px;margin:6px 0 0}}
</style></head><body>
<header>
  <h1>Update Ratings</h1>
  <select id="team" onchange="pick(this.value)"></select>
  <select id="year" onchange="setYear(this.value)"></select>
  <span class="rec" id="rec"></span>
</header>
<div class="wrap">
  <div class="hint">Read the team below, then just tell me your take in chat — e.g.
    <i>"Bills are playing better than expected but Allen hasn't been sharp."</i>
    I'll suggest a QB/Off/Def move (up or down, by how much); you decide, and I'll draft
    the live write-up for your approval.</div>
  <div class="card">
    <div class="rat">
      <div><div class="b">QB</div><div class="v" id="qb">—</div></div>
      <div><div class="b">Offense</div><div class="v" id="off">—</div></div>
      <div><div class="b">Defense</div><div class="v" id="def">—</div></div>
      <div class="tot"><div class="b">Rating</div><div class="v" id="tot">—</div></div>
    </div>
    <div class="qbname" id="qbname"></div>
    <div class="notes" id="notes"></div>
  </div>
  <div class="card">
    <h2>Open items — memory (resurfaces until resolved)</h2>
    <div id="threads"></div>
  </div>
  <div class="card">
    <h2>Live write-up (shows on the site)</h2>
    <div class="writeup" id="writeup"></div>
  </div>
  <div class="card">
    <details>
      <summary>Season results (reference — grain of salt)</summary>
      <p class="caveat">Ratings are your forward-looking judgment, not computed from these.
        Prior games may matter when a situation is similar, but the future situation is often
        different — coaching, a player's prime, injuries, aging. Weigh, don't obey.</p>
      <table><thead><tr><th>Wk</th><th>Res</th><th>Matchup</th><th class="num">Score</th></tr></thead>
      <tbody id="results"></tbody></table>
    </details>
  </div>
</div>
<script>
let YEARS=[];
async function loadTeams(){{
  const r=await fetch('/api/teams'); const j=await r.json();
  const sel=document.getElementById('team'); sel.innerHTML='';
  j.teams.forEach(n=>{{const o=document.createElement('option');o.value=n;o.textContent=n;
    if(n===j.current)o.selected=true; sel.appendChild(o);}});
  const ys=document.getElementById('year'); ys.innerHTML='';
  j.years.forEach(y=>{{const o=document.createElement('option');o.value=y;o.textContent=y;
    if(y===j.year)o.selected=true; ys.appendChild(o);}});
  load(j.current, j.year);
}}
function pick(name){{const y=document.getElementById('year').value; load(name,y);}}
function setYear(y){{const n=document.getElementById('team').value; load(n,y);}}
async function load(name,year){{
  const r=await fetch('/api/team?q='+encodeURIComponent(name)+'&year='+year);
  const s=await r.json();
  if(s.error){{document.getElementById('rec').textContent=s.error;return;}}
  const f=x=>(x>0?'+':'')+x;
  document.getElementById('qb').textContent=f(s.qb);
  document.getElementById('off').textContent=f(s.off);
  document.getElementById('def').textContent=f(s.def);
  document.getElementById('tot').textContent=f(s.rating);
  document.getElementById('qbname').textContent='QB: '+s.qb_name;
  document.getElementById('notes').textContent=s.notes?('Notes: '+s.notes):'';
  document.getElementById('rec').textContent=s.record?('Record '+s.record+' · '+s.year):'';
  document.getElementById('writeup').textContent=s.writeup_md||'(no write-up yet)';
  // open items / memory
  const th=document.getElementById('threads'); th.innerHTML='';
  const open=(s.open_threads||[]);
  if(!open.length){{ th.innerHTML='<div class="noopen">No open items. Tell me something to track '+
    '(e.g. an injury to monitor) and it\\'ll stay here until you mark it resolved.</div>'; }}
  else open.forEach(t=>{{
    const last=(t.entries||[]).slice(-1)[0];
    const div=document.createElement('div'); div.className='thread';
    div.innerHTML=`<div class="topic">${{t.topic}}</div>`+
      `<div class="meta">open · ${{(t.entries||[]).length}} update(s)${{t.opened?' · since '+t.opened:''}}</div>`+
      (last?`<div class="entry">${{last.text}}</div>`:'');
    th.appendChild(div);
  }});
  const rc=(s.resolved_threads||[]).length;
  if(rc){{const d=document.createElement('div');d.className='noopen';
    d.style.marginTop='8px';d.textContent=`(${{rc}} resolved item${{rc>1?'s':''}} in history)`;th.appendChild(d);}}
  const tb=document.getElementById('results'); tb.innerHTML='';
  let firstFinal=true;
  s.results.forEach(g=>{{
    const tr=document.createElement('tr');
    const loc=g.home_away==='home'?'vs':'@';
    const sc=g.final?`${{g.team_score}}-${{g.opp_score}}`:(g.status||'').replace('STATUS_','');
    if(g.final&&firstFinal){{tr.className='recent';firstFinal=false;}}
    tr.innerHTML=`<td>${{g.week||''}}</td><td class="${{g.result||''}}">${{g.result||''}}</td>
      <td>${{loc}} ${{g.opponent}}</td><td class="num">${{sc}}</td>`;
    tb.appendChild(tr);
  }});
}}
loadTeams();
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
        if u.path == "/healthz":
            return self._send(200, "ok", "text/plain")
        if u.path == "/api/teams":
            rows = TV.load_ratings_rows()
            yr = _STATE["year"] or _default_year()
            # offer this season + a couple prior for looking back
            years = [yr, yr - 1, yr - 2]
            return self._send(200, json.dumps(
                {"teams": sorted(rows.keys()), "current": _STATE["team"],
                 "year": yr, "years": years}))
        if u.path == "/api/team":
            q = parse_qs(u.query)
            name = TV.resolve_team((q.get("q") or [""])[0])
            year = int((q.get("year") or [_default_year()])[0])
            if not name:
                return self._send(200, json.dumps({"error": "team not found"}))
            _STATE["team"] = name
            try:
                return self._send(200, json.dumps(TV.team_snapshot(name, year)))
            except Exception as e:  # noqa: BLE001
                return self._send(502, json.dumps({"error": str(e)}))
        if u.path == "/" or u.path.startswith("/index"):
            return self._send(200, PAGE.format(), "text/html; charset=utf-8")
        return self._send(404, "not found", "text/plain")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        _STATE["team"] = TV.resolve_team(args[0]) or args[0]
    if len(args) > 1:
        _STATE["year"] = int(args[1])
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Update-ratings workspace at {url}  (Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
