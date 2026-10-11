"""Prop Board — verify pasted prop claims + compare free market prices (+ model edges).

A localhost page like the other hub tools (Lane 2, `testing` only), four tabs:
  Verify    — paste a post (X sheet, text); each claim is graded TRUE/FALSE/record with
              caveats: games played of team games, thin margins, injury, market price.
  Markets   — Kalshi / Polymarket / DraftKings / FanDuel quotes side by side per player.
  Edge      — model P(over) vs the best usable price; "no edge" by default.
  Sources   — running track record of every account you've verified.

Read-only against ratings/site. Writes only gitignored files under data/props/.

Run:
    python3 prop_server.py            # opens http://127.0.0.1:8793
    python3 prop_server.py --no-open
"""

import json
import os
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import props_markets
import props_verify

HOST = "127.0.0.1"
PORT = 8793
SOURCES_PATH = os.path.join(props_markets.PROPS_DIR, "sources.json")
_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _load_sources():
    try:
        with open(SOURCES_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"accounts": {}}


def _save_sources(d):
    os.makedirs(os.path.dirname(SOURCES_PATH), exist_ok=True)
    tmp = SOURCES_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, SOURCES_PATH)


def _model():
    try:
        import props_model
        return props_model.prob_for_claim
    except Exception:  # noqa: BLE001 — model is optional until calibrated
        return None


def api_verify(body):
    text = body.get("text") or ""
    tw = int(body.get("through_week") or 99)
    res = props_verify.verify(text, through_week=tw,
                              assume_perfect=bool(body.get("perfect")), model=_model())
    acct = (body.get("source") or "").strip().lstrip("@")
    if acct:
        with _LOCK:
            d = _load_sources()
            a = d["accounts"].setdefault(acct, {"claims": []})
            for v in res:
                if v["verdict"] in ("unparsed",):
                    continue
                a["claims"].append({"at": _now(), "text": v["text"], "kind": v["kind"],
                                    "verdict": v["verdict"],
                                    "price": (v.get("price") or {}).get("p"),
                                    "player_id": (v.get("resolved") or {}).get("player_id"),
                                    "stat": v.get("market") if v["kind"] == "player"
                                    else v.get("stat"),
                                    "line": v.get("line"), "side": v.get("side"),
                                    "graded": None})
            _save_sources(d)
    return {"results": res}


def api_markets(q):
    snap = props_markets.latest_snapshot()
    if not snap:
        return {"fetched_at": None, "rows": [], "status": {}}
    ev = (q.get("event") or [""])[0].upper()
    pl = (q.get("player") or [""])[0].lower()
    mk = (q.get("market") or [""])[0]
    only = (q.get("usable") or ["1"])[0] == "1"
    rows = [r for r in snap["rows"]
            if (not ev or (r.get("event_key") or "") == ev)
            and (not pl or pl in r["player"].lower())
            and (not mk or r["market"] == mk)
            and (r["usable"] or not only)]
    events = sorted({r.get("event_key") for r in snap["rows"] if r.get("event_key")})
    return {"fetched_at": snap["fetched_at"], "status": snap.get("status", {}),
            "events": events, "rows": rows[:3000]}


def api_refresh(body):
    srcs = ["kalshi", "polymarket"] + (["oddsapi"] if body.get("oddsapi") else [])
    logs = []
    snap = props_markets.pull(srcs, log=logs.append)
    return {"fetched_at": snap["fetched_at"], "status": snap["status"], "log": logs}


def api_sources():
    d = _load_sources()
    out = []
    for name, a in d["accounts"].items():
        cl = a.get("claims", [])
        judged = [c for c in cl if c["verdict"] in ("true", "false", "close")]
        graded = [c for c in cl if c.get("graded") in ("hit", "miss")]
        out.append({"account": name, "claims": len(cl),
                    "true_rate": (sum(c["verdict"] == "true" for c in judged) / len(judged))
                    if judged else None,
                    "graded": len(graded),
                    "hit_rate": (sum(c["graded"] == "hit" for c in graded) / len(graded))
                    if graded else None})
    return {"accounts": sorted(out, key=lambda x: -x["claims"])}


def api_edge(q):
    try:
        import props_model
    except Exception as e:  # noqa: BLE001
        return {"ready": False, "why": f"model not built yet ({e.__class__.__name__})"}
    return props_model.edge_board(event=(q.get("event") or [""])[0],
                                  market=(q.get("market") or [""])[0])


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Prop Board</title>
<style>
 :root{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;
   --muted:#898781;--line:#e1e0d9;--border:rgba(11,11,11,.10);--series:#2a78d6;
   --good:#0ca30c;--crit:#d03b3b;--warn:#b7791f}
 @media (prefers-color-scheme:dark){:root{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;
   --ink:#fff;--ink2:#c3c2b7;--line:#2c2c2a;--border:rgba(255,255,255,.10);--series:#3987e5}}
 *{box-sizing:border-box} body{margin:0;background:var(--plane);color:var(--ink);
   font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
 header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;gap:14px;
   align-items:center;flex-wrap:wrap;position:sticky;top:0;background:var(--plane);z-index:5}
 h1{font-size:18px;margin:0;font-weight:800}
 .tabs{display:flex;gap:4px} .tabs button{background:transparent;border:1px solid transparent;
   color:var(--ink2);padding:6px 14px;border-radius:8px;font:inherit;cursor:pointer}
 .tabs button.on{background:var(--ink);color:var(--plane);font-weight:700}
 main{padding:16px 20px;max-width:1200px} .pane{display:none} .pane.on{display:block}
 textarea{width:100%;min-height:170px;font:13px ui-monospace,monospace;padding:10px;
   border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--ink)}
 input,select{font:inherit;padding:6px 8px;border:1px solid var(--border);border-radius:8px;
   background:var(--surface);color:var(--ink)}
 button.b{background:var(--ink);color:var(--plane);border:0;padding:8px 14px;border-radius:8px;
   font:inherit;font-weight:700;cursor:pointer} button.alt{background:var(--surface);
   color:var(--ink);border:1px solid var(--border);font-weight:500}
 .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:10px 0}
 .card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
   padding:10px 12px;margin:8px 0} .v{font-weight:800;margin-right:6px}
 .true{color:var(--good)} .false{color:var(--crit)} .close,.record{color:var(--warn)}
 .unverifiable,.unparsed{color:var(--muted)} .log{font:12px ui-monospace,monospace;color:var(--ink2)}
 .cv{font-size:13px;color:var(--ink2);margin:2px 0 0 18px} .note{color:var(--muted);font-size:13px}
 table{border-collapse:collapse;width:100%;font-size:13px} th,td{padding:5px 8px;
   border-bottom:1px solid var(--line);text-align:left} th{color:var(--ink2);font-weight:600}
 td.n{text-align:right;font-variant-numeric:tabular-nums} .thin{color:var(--muted)}
</style></head><body>
<header><h1>Prop Board</h1><div class="tabs" id="tabs"></div></header>
<main>
<section class="pane" id="p-verify">
 <p class="note">Paste a post (one claim per line). Claims are graded against this season's
 box scores. TRUE ≠ good bet — read the caveats.</p>
 <textarea id="vt" placeholder="Xavier Hutchinson Over 29.5 Rec Yds 4/4&#10;TYLER SHOUGH 250+ PASS YARDS&#10;EAGLES ALLOW MOST RUSH TDS TO QB"></textarea>
 <div class="row">
  <label>Account <input id="vs" placeholder="@PropsEdge" size="14"></label>
  <label>As of week <input id="vw" type="number" min="1" max="22" size="3" placeholder="all"></label>
  <label><input id="vp" type="checkbox"> sheet claims 100% / every game</label>
  <button class="b" onclick="verify()">Verify</button></div>
 <div id="vout"></div>
</section>
<section class="pane" id="p-markets">
 <div class="row"><select id="me"><option value="">All games</option></select>
  <select id="mm"><option value="">All markets</option></select>
  <input id="mp" placeholder="player" size="16">
  <label><input id="mu" type="checkbox" checked> usable only</label>
  <button class="alt b" onclick="markets()">Show</button>
  <button class="b" onclick="refresh(false)">Refresh Kalshi + Polymarket</button>
  <button class="alt b" onclick="refresh(true)" title="Spends Odds API credits">+ DK/FD (credits)</button></div>
 <div id="mstat" class="note"></div><div id="mout"></div>
</section>
<section class="pane" id="p-edge"><div id="eout" class="note">Loading…</div></section>
<section class="pane" id="p-sources"><div id="sout"></div></section>
</main>
<script>
const TABS=[["verify","Verify"],["markets","Markets"],["edge","Edge"],["sources","Sources"]];
const MK=["pass_yds","rush_yds","rec_yds","receptions","anytime_td","pass_tds","pass_ints"];
const $=id=>document.getElementById(id);
function el(t,c,x){const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e;}
function tab(k){for(const [n] of TABS){$('p-'+n).classList.toggle('on',n==k);$('t-'+n).classList.toggle('on',n==k);}
 if(k=='markets')markets(); if(k=='edge')edge(); if(k=='sources')sources(); location.hash=k;}
for(const [k,l] of TABS){const b=el('button',null,l);b.id='t-'+k;b.onclick=()=>tab(k);$('tabs').appendChild(b);}
for(const m of MK){const o=el('option',null,m);o.value=m;$('mm').appendChild(o);}
const pct=p=>p==null?'—':(100*p).toFixed(0)+'%';
async function post(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});return r.json();}
const MARK={true:'✅ TRUE',false:'❌ FALSE',close:'≈ CLOSE',record:'📋 RECORD',unverifiable:'⚠️ UNVERIFIABLE',unparsed:'· not a claim'};
async function verify(){
 $('vout').textContent='Checking…';
 const d=await post('/api/verify',{text:$('vt').value,source:$('vs').value,
   through_week:$('vw').value||99,perfect:$('vp').checked});
 $('vout').innerHTML='';
 for(const v of d.results){const c=el('div','card');
  const h=el('div');const s=el('span','v '+v.verdict,MARK[v.verdict]||v.verdict);h.appendChild(s);
  h.appendChild(el('span',null,v.text));c.appendChild(h);
  if(v.log&&v.log.length){c.appendChild(el('div','log',
    v.log.map(g=>`wk${g.week} ${g.value}${g.hit?'✓':'✗'}`).join('   ')+
    `   →  ${v.hits}/${v.games} played (${v.team_games} team games)`));}
  for(const x of (v.caveats||[])) c.appendChild(el('div','cv','• '+x));
  if(v.why) c.appendChild(el('div','cv','• '+v.why));
  if(v.model&&v.model.p!=null) c.appendChild(el('div','cv',`• model: ${pct(v.model.p)} (proj ${v.model.mean})`));
  $('vout').appendChild(c);}
}
async function markets(){
 const q=new URLSearchParams({event:$('me').value,market:$('mm').value,player:$('mp').value,usable:$('mu').checked?'1':'0'});
 const d=await (await fetch('/api/markets?'+q)).json();
 $('mstat').textContent=d.fetched_at?`Prices as of ${d.fetched_at} · `+Object.entries(d.status||{}).map(([k,v])=>`${k}: ${v.ok?v.usable+'/'+v.rows+' usable':'failed'}`).join(' · '):'No prices yet — Refresh.';
 if($('me').options.length<2) for(const e of d.events||[]){const o=el('option',null,e);o.value=e;$('me').appendChild(o);}
 const g={}; for(const r of d.rows){const k=r.player+'|'+r.market+'|'+r.line;(g[k]=g[k]||{player:r.player,market:r.market,line:r.line,ev:r.event_key,q:{}}).q[r.book]=r;}
 const books=['kalshi','polymarket','draftkings','fanduel'];
 const t=el('table');t.innerHTML='<tr><th>Player</th><th>Game</th><th>Market</th><th>Line</th>'+books.map(b=>`<th>${b}</th>`).join('')+'</tr>';
 Object.values(g).sort((a,b)=>a.player.localeCompare(b.player)||a.market.localeCompare(b.market)||a.line-b.line).slice(0,1500).forEach(x=>{
  const tr=el('tr');[x.player,x.ev||'',x.market,'o'+x.line].forEach(v=>tr.appendChild(el('td',null,v)));
  for(const b of books){const r=x.q[b];const td=el('td','n'+(r&&!r.usable?' thin':''),r?pct(r.p_fair):'');if(r)td.title=`bid ${r.p_bid} ask ${r.p_ask} liq ${r.liquidity}`;tr.appendChild(td);}
  t.appendChild(tr);}); $('mout').innerHTML='';$('mout').appendChild(t);
}
async function refresh(odds){$('mstat').textContent='Pulling…';const d=await post('/api/refresh',{oddsapi:odds});$('mstat').textContent=(d.log||[]).join(' | ');markets();}
async function edge(){const d=await (await fetch('/api/edge')).json();
 if(!d.ready){$('eout').textContent='Edge board not live yet: '+(d.why||'')+'. Leans only appear once the model is calibrated.';return;}
 $('eout').innerHTML='';const t=el('table');t.innerHTML='<tr><th>Player</th><th>Game</th><th>Market</th><th>Line</th><th>Model</th><th>Best price</th><th>Edge</th><th>Lean</th><th>Caveats</th></tr>';
 for(const r of d.rows){const tr=el('tr',r.lean?'':'thin');[r.player,r.event_key,r.market,'o'+r.line,pct(r.p_model),pct(r.p_market)+' '+r.best_book,(r.edge>0?'+':'')+(100*r.edge).toFixed(1),r.lean||'no edge',(r.caveats||[]).join('; ')].forEach(v=>tr.appendChild(el('td',null,v)));t.appendChild(tr);}
 $('eout').appendChild(t);}
async function sources(){const d=await (await fetch('/api/sources')).json();
 const t=el('table');t.innerHTML='<tr><th>Account</th><th>Claims</th><th>Claims true</th><th>Graded picks</th><th>Hit rate</th></tr>';
 for(const a of d.accounts){const tr=el('tr');[a.account,a.claims,pct(a.true_rate),a.graded,pct(a.hit_rate)].forEach(v=>tr.appendChild(el('td',null,v)));t.appendChild(tr);}
 $('sout').innerHTML='';if(!d.accounts.length)$('sout').textContent='No accounts yet — add an account name when you verify a post.';else $('sout').appendChild(t);}
tab((location.hash||'#verify').slice(1));
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

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/healthz":
                return self._send(200, "ok", "text/plain")
            if u.path == "/api/markets":
                return self._send(200, json.dumps(api_markets(q)))
            if u.path == "/api/sources":
                return self._send(200, json.dumps(api_sources()))
            if u.path == "/api/edge":
                return self._send(200, json.dumps(api_edge(q)))
            if u.path == "/" or u.path.startswith("/index"):
                return self._send(200, PAGE, "text/html; charset=utf-8")
        except Exception as e:  # noqa: BLE001
            return self._send(502, json.dumps({"error": str(e)}))
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/verify":
                return self._send(200, json.dumps(api_verify(self._body()), default=str))
            if u.path == "/api/refresh":
                return self._send(200, json.dumps(api_refresh(self._body())))
        except Exception as e:  # noqa: BLE001
            return self._send(502, json.dumps({"error": str(e)}))
        return self._send(404, "not found", "text/plain")


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Prop Board at {url}  (Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
