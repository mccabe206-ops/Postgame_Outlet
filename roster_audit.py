"""One-off roster audit: cross-check ESPN (live) vs nflverse (KB 2026) team
assignments across all 32 teams and print ONLY discrepancies. Third-source
resolution (PFF/web) is done by hand on the flagged conflicts.

Team-assignment accuracy is the target (the DJ Moore CHI->BUF class of error),
not full 53-man depth. Match key = normalized full name.
"""
import re, sqlite3, os, sys
import rosters
import team_view as TV

KB = os.path.join(os.path.dirname(__file__), "data", "nfl_kb", "nfl.sqlite")

# canonical abbreviation map (fold source-specific spellings to one)
CANON = {"LA": "LAR", "WSH": "WAS", "WFT": "WAS", "OAK": "LV", "SD": "LAC",
         "STL": "LAR", "JAC": "JAX", "LAR": "LAR", "WAS": "WAS", "AZ": "ARI"}
def canon(a): return CANON.get(a, a)

SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.I)
def norm(n):
    n = n.lower().replace(".", "").replace("'", "").replace("-", " ")
    n = SUFFIX.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

# coarse position group so same-name DIFFERENT players (e.g. DeVonta Smith WR-PHI
# vs DeVonta Smith DB-CAR) don't get matched to each other
PG = {"QB":"QB","RB":"RB","HB":"RB","FB":"RB","WR":"WR","TE":"TE",
      "C":"OL","G":"OL","T":"OL","OL":"OL","OT":"OL","OG":"OL","LT":"OL","RT":"OL","LG":"OL","RG":"OL",
      "DE":"DL","DT":"DL","NT":"DL","DL":"DL","EDGE":"DL","ED":"DL","DI":"DL",
      "LB":"LB","ILB":"LB","OLB":"LB","MLB":"LB","LOLB":"LB","ROLB":"LB","WLB":"LB",
      "CB":"DB","S":"DB","SS":"DB","FS":"DB","DB":"DB","SAF":"DB",
      "K":"ST","P":"ST","LS":"ST","PK":"ST"}
def pg(pos): return PG.get((pos or "").upper(), "OTH")
def key(name, pos): return (norm(name), pg(pos))

# ---- nflverse (KB 2026): latest row per player ----
con = sqlite3.connect(KB)
nfl = {}   # (norm_name, posgroup) -> (team, pos, full_name, wk)
for full, team, pos, wk in con.execute(
        "SELECT full_name, team, position, COALESCE(week,0) FROM rosters "
        "WHERE season=2026 AND full_name IS NOT NULL AND team IS NOT NULL"):
    k = key(full, pos)
    prev = nfl.get(k)
    if prev is None or wk >= prev[3]:
        nfl[k] = (canon(team), pos, full, wk)
con.close()

# ---- ESPN (live): all 32, active + IR/suspended = "on this team" ----
espn = {}  # norm_name -> (team, pos, status, full_name)
idx = TV.espn_team_index()
GROUPS = ("offense", "defense", "specialTeam", "injuredReserveOrOut", "suspended")
errs = []
for name, meta in idx.items():
    r = rosters.fetch_roster(name)
    if "error" in r:
        errs.append(name); continue
    ab = canon(r["abbr"])
    for g in GROUPS:
        for p in r["groups"].get(g, []):
            espn[key(p["name"], p.get("pos"))] = (ab, p.get("pos"), p.get("status"), p["name"])
if errs:
    print("ESPN fetch errors:", errs, file=sys.stderr)

# ---- diff: team-assignment conflicts (same name+posgroup, different team) ----
conflicts = []
for k, (et, epos, est, ename) in espn.items():
    if k in nfl:
        nt, npos, nfull, _ = nfl[k]
        if et != nt:
            conflicts.append((ename, epos, et, nt, est))

print(f"\n=== ESPN teams fetched: {len(idx)-len(errs)}/32 | ESPN players: {len(espn)} | nflverse players: {len(nfl)} ===")
SKILL = {"QB", "RB", "HB", "FB", "WR", "TE"}
skill = [c for c in conflicts if (c[1] or "") in SKILL]
print(f"\n=== TOTAL team-assignment conflicts: {len(conflicts)} | SKILL-position (QB/RB/WR/TE): {len(skill)} ===")
print("\n--- SKILL-POSITION CONFLICTS (resolve these with a 3rd source) ---")
for ename, epos, et, nt, est in sorted(skill, key=lambda x: (x[1] or "", x[0])):
    print(f"  {ename:26} {epos or '?':4}  ESPN={et:4} nflverse={nt:4}  (ESPN status: {est})")
print("\n--- ALL OTHER CONFLICTS (mostly depth/OL/DB churn) ---")
for ename, epos, et, nt, est in sorted([c for c in conflicts if (c[1] or '') not in SKILL], key=lambda x: (x[1] or "", x[0])):
    print(f"  {ename:26} {epos or '?':4}  ESPN={et:4} nflverse={nt:4}  (ESPN status: {est})")
