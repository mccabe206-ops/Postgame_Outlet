"""Build the production refresh path into an isolated, private preview directory."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import generate_site as site
import pgo_comparison as comparison
from release_ratings import atomic_write_text

rows = site.load_teams(site.load_prior())
site.build_html.qb_data = site.load_qbs({row['team']: row['rating'] for row in rows})
base = site.build_html(rows, site.load_config())
published = comparison.PUBLIC_OUTPUT.read_text(encoding='utf-8')
page = comparison.refresh_mccabe_page(base, published)
page = comparison.pgo_current_board.add_current_board(page)
assert comparison._extract_published_fantasy_panel(published) == comparison._extract_published_fantasy_panel(
    comparison.strip_current_injury_notes(page))
assert page.count('id="tab-fantasy"') == 1
destination = ROOT / 'output/opening-night/site'
atomic_write_text(destination / 'index.html', page)
shutil.copyfile(ROOT / 'docs/pgo-theme.css', destination / 'pgo-theme.css')
print(json.dumps(dict(output=str(destination / 'index.html'),
    html_sha256=hashlib.sha256((destination / 'index.html').read_bytes()).hexdigest(),
    css_sha256=hashlib.sha256((destination / 'pgo-theme.css').read_bytes()).hexdigest(),
    current_injury_note_count=page.count('<!-- CURRENT INJURY NOTE -->'),
    saved_fantasy_panel_unchanged_after_removing_current_annotations=True), indent=2))
