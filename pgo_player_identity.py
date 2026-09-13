"""Strict, source-backed GSIS-to-PFR identities for future offensive inventories."""
import copy
import csv
from datetime import date, timedelta
import io
from pathlib import Path
import re

from pgo_season import require, utc
from pgo_season_rollover import source_bytes
from research.pgo_defensive_depth_candidate import evidence


URL = 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
REQUIRED_COLUMNS = (
    'gsis_id', 'pfr_id', 'display_name', 'first_name', 'common_first_name',
    'football_name', 'last_name', 'birth_date', 'esb_id', 'nfl_id',
    'smart_id', 'espn_id',
)
_GSIS = re.compile(r'00-\d{7}')
_PFR = re.compile(r"[A-Za-z0-9.'_\-]+")
_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_AUXILIARY = (
    ('esb_id', 'esb_id', 'ESB_ID_MISMATCH'),
    ('gsis_it_id', 'nfl_id', 'NFL_ID_MISMATCH'),
    ('smart_id', 'smart_id', 'SMART_ID_MISMATCH'),
    ('espn_id', 'espn_id', 'ESPN_ID_MISMATCH'),
)


def _text(value):
    return '' if value is None else str(value).strip()


def _gsis(row):
    value = _text(row.get('gsis_id'))
    return value if _GSIS.fullmatch(value) else ''


def _valid_date(value):
    value = _text(value)
    if not _DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _aliases(row):
    adapted = {key: _text(row.get(key)) for key in
               ('full_name', 'first_name', 'football_name', 'last_name')}
    names = {name for name in evidence.aliases(adapted) if name}
    names.discard(evidence.ch._normalize_player_name(adapted['last_name']))
    return names


def _provider_aliases(row):
    adapted = {
        'full_name': row.get('display_name'),
        'first_name': row.get('first_name'),
        'football_name': row.get('football_name'),
        'last_name': row.get('last_name'),
    }
    names = _aliases(adapted)
    common = evidence.ch._normalize_player_name(
        f"{_text(row.get('common_first_name'))} {_text(row.get('last_name'))}") \
        if _text(row.get('common_first_name')) and _text(row.get('last_name')) else ''
    if common:
        names.add(common)
    return names


def parse(raw):
    """Parse a full nflverse player table without repairing malformed rows."""
    try:
        text = raw.decode('utf-8')
    except (AttributeError, UnicodeDecodeError) as exc:
        raise ValueError('Player source must be UTF-8 bytes') from exc
    try:
        rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    except csv.Error as exc:
        raise ValueError('Invalid player CSV') from exc
    require(bool(rows), 'Missing player columns')
    header = rows[0]
    require(len(header) == len(set(header)), 'Duplicate player column')
    missing = sorted(set(REQUIRED_COLUMNS) - set(header))
    require(not missing, 'Missing player columns: ' + ', '.join(missing))
    result = []
    for values in rows[1:]:
        require(len(values) == len(header), 'Invalid player row width')
        result.append(dict(zip(header, values)))
    return result


def read_source(root, ref, checked_at, *, allow_stale=False):
    """Read a recent, byte-pinned player table from the season source archive."""
    require(isinstance(ref, dict) and ref.get('url') == URL, 'Player source URL differs')
    require(type(allow_stale) is bool, 'Invalid stale-source policy')
    require(all(ref.get(key) not in (None, '') for key in
                ('path', 'sha256', 'bytes', 'captured_at')),
            'Player source receipt is incomplete')
    root = Path(root).absolute()
    require(not root.is_symlink(), 'Invalid source root symlink')
    path = root / ref['path']
    current = path.parent
    while current != root:
        require(not current.is_symlink(), 'Invalid source parent symlink')
        require(current != current.parent, 'Invalid source path')
        current = current.parent
    checked = utc(checked_at)
    captured = utc(ref['captured_at'])
    require(captured <= checked, 'Player source captured after inventory check')
    require(allow_stale or checked - captured <= timedelta(hours=24),
            'Player source is older than 24 hours')
    if ref.get('published_at'):
        require(utc(ref['published_at']) <= captured,
                'Player source publication follows capture')
    raw = source_bytes(root, ref, checked_at)
    parse(raw)
    return raw


def resolve(roster, players):
    """Return a detached roster and fail-closed identity result for each canonical GSIS."""
    require(isinstance(roster, list) and all(isinstance(row, dict) for row in roster),
            'Roster must be a list of rows')
    require(isinstance(players, list) and all(isinstance(row, dict) for row in players),
            'Players must be a list of rows')
    enriched = copy.deepcopy(roster)
    roster_by_gsis = {}
    roster_pfr_owners = {}
    for index, row in enumerate(roster):
        gsis = _gsis(row)
        if not gsis:
            enriched[index]['pfr_id'] = ''
            continue
        require(gsis not in roster_by_gsis, 'Duplicate roster GSIS')
        roster_by_gsis[gsis] = (index, row)
        pfr = _text(row.get('pfr_id'))
        if pfr:
            roster_pfr_owners.setdefault(pfr, set()).add(gsis)

    provider_by_gsis = {}
    provider_pfr_rows = {}
    for index, row in enumerate(players):
        gsis = _gsis(row)
        if gsis:
            provider_by_gsis.setdefault(gsis, []).append(row)
        pfr = _text(row.get('pfr_id'))
        if pfr:
            provider_pfr_rows.setdefault(pfr, []).append((index, gsis))

    records = {}
    for gsis, (index, current) in roster_by_gsis.items():
        current_pfr = _text(current.get('pfr_id'))
        reasons, aliases = [], []
        status, qualified = 'MISSING', None

        if current_pfr and not _PFR.fullmatch(current_pfr):
            reasons.append('PFR_INVALID')
        elif current_pfr and len(roster_pfr_owners[current_pfr]) != 1:
            reasons.append('DUPLICATE_ROSTER_PFR')
        else:
            candidates = provider_by_gsis.get(gsis, [])
            if len(candidates) > 1:
                reasons.append('DUPLICATE_PROVIDER_GSIS')
            elif not candidates:
                if current_pfr:
                    owners = provider_pfr_rows.get(current_pfr, [])
                    if len(owners) > 1:
                        reasons.append('DUPLICATE_PROVIDER_PFR')
                    elif owners and owners[0][1] != gsis:
                        reasons.append('PROVIDER_PFR_OWNER_MISMATCH')
                    else:
                        status, qualified = 'ROSTER', current_pfr
                else:
                    reasons.append('PROVIDER_NOT_FOUND')
            else:
                provider = candidates[0]
                provider_pfr = _text(provider.get('pfr_id'))
                roster_names, provider_names = _aliases(current), _provider_aliases(provider)
                name_ok = bool(roster_names and provider_names and roster_names & provider_names)
                if not roster_names or not provider_names:
                    if not current_pfr:
                        reasons.append('NAME_MISSING')
                elif not name_ok:
                    reasons.append('NAME_MISMATCH')

                roster_dob, provider_dob = _text(current.get('birth_date')), _text(provider.get('birth_date'))
                dob_ok = bool(_valid_date(roster_dob) and _valid_date(provider_dob)
                              and roster_dob == provider_dob)
                if not roster_dob or not provider_dob:
                    if not current_pfr:
                        reasons.append('DOB_MISSING')
                elif not _valid_date(roster_dob) or not _valid_date(provider_dob):
                    reasons.append('DOB_INVALID')
                elif not dob_ok:
                    reasons.append('DOB_MISMATCH')

                for roster_field, provider_field, reason in _AUXILIARY:
                    left, right = _text(current.get(roster_field)), _text(provider.get(provider_field))
                    if left and right and left != right:
                        reasons.append(reason)

                if current_pfr and provider_pfr and current_pfr != provider_pfr:
                    reasons.append('PROVIDER_PFR_MISMATCH')
                if provider_pfr and not _PFR.fullmatch(provider_pfr):
                    reasons.append('PFR_INVALID')
                candidate_pfr = provider_pfr or current_pfr
                if candidate_pfr:
                    roster_owners = roster_pfr_owners.get(candidate_pfr, set())
                    if roster_owners and roster_owners != {gsis}:
                        reasons.append('ROSTER_PFR_OWNER_MISMATCH')
                    owners = provider_pfr_rows.get(candidate_pfr, [])
                    if len(owners) > 1:
                        reasons.append('DUPLICATE_PROVIDER_PFR')
                    elif owners and owners[0][1] != gsis:
                        reasons.append('PROVIDER_PFR_OWNER_MISMATCH')
                elif not current_pfr:
                    reasons.append('PROVIDER_PFR_MISSING')

                contradictions = [reason for reason in reasons if not reason.endswith('_MISSING')]
                if contradictions:
                    status = 'CONFLICT'
                elif current_pfr:
                    status, qualified = 'ROSTER', current_pfr
                elif not reasons:
                    status, qualified = 'PROVIDER', provider_pfr
                if qualified and name_ok and dob_ok:
                    aliases = sorted(provider_names)

        if reasons and status != 'CONFLICT' and any(not reason.endswith('_MISSING')
                                                    and reason != 'PROVIDER_NOT_FOUND'
                                                    for reason in reasons):
            status = 'CONFLICT'
        if status in ('MISSING', 'CONFLICT'):
            qualified, aliases = None, []
        enriched[index]['pfr_id'] = qualified or ''
        if qualified:
            enriched[index]['_usage_identity_aliases'] = aliases
        records[gsis] = {
            'pfr_id': qualified, 'status': status,
            'reasons': list(dict.fromkeys(reasons)), 'aliases': aliases,
        }
    return enriched, records
