'use strict';

const PGOLeague = (() => {
  const POSITIONS = ['QB', 'RB', 'WR', 'TE'];
  const COMPONENTS = [
    'passing_yards', 'passing_tds', 'passing_interceptions',
    'passing_2pt_conversions', 'rushing_yards', 'rushing_tds',
    'rushing_2pt_conversions', 'receptions', 'receiving_yards',
    'receiving_tds', 'receiving_2pt_conversions', 'special_teams_tds',
    'fumbles_lost_total'
  ];
  const SLOT_NAMES = [...POSITIONS, 'FLEX', 'SUPERFLEX'];

  const HALF_PPR = Object.freeze({
    passing_yards: 0.04,
    passing_tds: 4,
    passing_interceptions: -2,
    passing_2pt_conversions: 2,
    rushing_yards: 0.1,
    rushing_tds: 6,
    rushing_2pt_conversions: 2,
    receptions: 0.5,
    receiving_yards: 0.1,
    receiving_tds: 6,
    receiving_2pt_conversions: 2,
    special_teams_tds: 6,
    fumbles_lost_total: -2,
    te_reception_bonus: 0
  });
  const PRESETS = Object.freeze({
    STANDARD: Object.freeze({...HALF_PPR, receptions: 0}),
    HALF_PPR,
    PPR: Object.freeze({...HALF_PPR, receptions: 1})
  });
  const DEFAULT_PROFILE = Object.freeze({
    version: 1,
    name: '12-Team Half-PPR',
    teams: 12,
    slots: Object.freeze({
      QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0
    }),
    scoring: HALF_PPR
  });

  const PROFILE_KEYS = ['version', 'name', 'teams', 'slots', 'scoring'];
  const SCORING_RANGES = {
    passing_yards: [0, 1],
    rushing_yards: [0, 1],
    receiving_yards: [0, 1],
    passing_tds: [0, 12],
    rushing_tds: [0, 12],
    receiving_tds: [0, 12],
    special_teams_tds: [0, 12],
    receptions: [0, 3],
    passing_interceptions: [-10, 0],
    fumbles_lost_total: [-10, 0],
    passing_2pt_conversions: [0, 6],
    rushing_2pt_conversions: [0, 6],
    receiving_2pt_conversions: [0, 6],
    te_reception_bonus: [0, 3]
  };
  const SCORING_KEYS = Object.keys(SCORING_RANGES);

  function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function requireKeys(value, expected, label) {
    if (!isObject(value)) throw new TypeError(label + ' must be an object');
    const actual = Object.keys(value).sort();
    const wanted = [...expected].sort();
    if (actual.length !== wanted.length || actual.some((key, i) => key !== wanted[i])) {
      throw new TypeError(label + ' keys must be exactly: ' + wanted.join(', '));
    }
  }

  function requireNumber(value, minimum, maximum, label) {
    if (typeof value !== 'number' || !Number.isFinite(value)
        || value < minimum || value > maximum) {
      throw new RangeError(label + ' must be a finite number from '
        + minimum + ' to ' + maximum);
    }
  }

  function validateProfile(profile) {
    requireKeys(profile, PROFILE_KEYS, 'Profile');
    if (profile.version !== 1) throw new RangeError('Profile version must be 1');
    if (typeof profile.name !== 'string') throw new TypeError('Profile name must be text');
    const name = profile.name.trim();
    if (name.length < 1 || name.length > 60) {
      throw new RangeError('Profile name must contain 1 to 60 characters');
    }
    if (!Number.isInteger(profile.teams) || profile.teams < 2 || profile.teams > 32) {
      throw new RangeError('Profile teams must be an integer from 2 to 32');
    }
    requireKeys(profile.slots, SLOT_NAMES, 'Profile slots');
    for (const slot of SLOT_NAMES) {
      const maximum = slot === 'QB' || slot === 'SUPERFLEX' ? 2 : 4;
      if (!Number.isInteger(profile.slots[slot])
          || profile.slots[slot] < 0 || profile.slots[slot] > maximum) {
        throw new RangeError(slot + ' slots must be an integer from 0 to ' + maximum);
      }
    }
    if (!SLOT_NAMES.some(slot => profile.slots[slot] > 0)) {
      throw new RangeError('Profile must have at least one lineup slot');
    }
    requireKeys(profile.scoring, SCORING_KEYS, 'Profile scoring');
    for (const [field, [minimum, maximum]] of Object.entries(SCORING_RANGES)) {
      requireNumber(profile.scoring[field], minimum, maximum, field);
    }
    return {
      version: 1,
      name,
      teams: profile.teams,
      slots: {...profile.slots},
      scoring: {...profile.scoring}
    };
  }

  function validatePlayer(player) {
    if (!isObject(player)) throw new TypeError('Player must be an object');
    if (typeof player.id !== 'string' || !player.id.trim()) {
      throw new TypeError('Player id must be nonempty text');
    }
    if (!POSITIONS.includes(player.position)) {
      throw new RangeError('Player position must be QB, RB, WR, or TE');
    }
    if (typeof player.points !== 'number' || !Number.isFinite(player.points)) {
      throw new TypeError('Player points must be a finite number');
    }
    if (Object.prototype.hasOwnProperty.call(player, 'inactive')
        && typeof player.inactive !== 'boolean') {
      throw new TypeError('Player inactive must be a boolean');
    }
  }

  function isCanonical(scoring) {
    return SCORING_KEYS.every(field => scoring[field] === HALF_PPR[field]);
  }

  function scoreValidated(player, profile) {
    validatePlayer(player);
    if (player.inactive === true) return 0;
    if (isCanonical(profile.scoring)) return player.points;
    requireKeys(player.components, COMPONENTS, 'Player components');
    let score = player.points;
    for (const field of COMPONENTS) {
      const value = player.components[field];
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        throw new TypeError(field + ' component must be a finite number');
      }
      const weight = profile.scoring[field]
        + (field === 'receptions' && player.position === 'TE'
          ? profile.scoring.te_reception_bonus : 0);
      score += (weight - HALF_PPR[field]) * value;
    }
    if (!Number.isFinite(score)) throw new RangeError('Player score must be finite');
    return score;
  }

  function scorePlayer(player, profile) {
    return scoreValidated(player, validateProfile(profile));
  }

  function compareId(left, right) {
    return left.id < right.id ? -1 : left.id > right.id ? 1 : 0;
  }

  function compareScore(left, right) {
    return right.score - left.score || compareId(left, right);
  }

  function rankLeague(players, profile) {
    if (!Array.isArray(players)) throw new TypeError('Players must be an array');
    const validated = validateProfile(profile);
    const seen = new Set();
    const rows = players.map(player => {
      const score = scoreValidated(player, validated);
      if (seen.has(player.id)) throw new TypeError('Duplicate player id: ' + player.id);
      seen.add(player.id);
      return {...player, score, value: null, rank: 0};
    });
    const remaining = new Set(rows);
    const reserve = (eligible, count, label) => {
      const candidates = rows.filter(row => remaining.has(row) && eligible(row))
        .sort(compareScore);
      if (candidates.length < count) {
        return 'League value unavailable: cannot fill ' + count + ' ' + label + ' slots';
      }
      candidates.slice(0, count).forEach(row => remaining.delete(row));
      return null;
    };

    let unavailableReason = null;
    for (const position of POSITIONS) {
      const count = validated.teams * validated.slots[position];
      if (count) {
        unavailableReason = reserve(row => row.position === position, count, position);
        if (unavailableReason) break;
      }
    }
    if (!unavailableReason && validated.slots.FLEX) {
      unavailableReason = reserve(
        row => row.position !== 'QB',
        validated.teams * validated.slots.FLEX,
        'FLEX'
      );
    }
    if (!unavailableReason && validated.slots.SUPERFLEX) {
      unavailableReason = reserve(
        () => true,
        validated.teams * validated.slots.SUPERFLEX,
        'SUPERFLEX'
      );
    }

    const baselines = {QB: null, RB: null, WR: null, TE: null};
    const isRelevant = position => (
      validated.slots[position] > 0
      || (position !== 'QB' && validated.slots.FLEX > 0)
      || validated.slots.SUPERFLEX > 0
    ) && rows.some(row => row.position === position);
    if (!unavailableReason) {
      for (const position of POSITIONS.filter(isRelevant)) {
        const replacement = rows.filter(
          row => remaining.has(row) && row.position === position
        ).sort(compareScore)[0];
        if (!replacement) {
          unavailableReason = 'League value unavailable: no '
            + position + ' replacement remains after filling starters';
          break;
        }
        baselines[position] = replacement.score;
      }
    }

    if (unavailableReason) {
      for (const position of POSITIONS) baselines[position] = null;
      rows.sort(compareScore);
    } else {
      for (const row of rows) {
        if (baselines[row.position] !== null) {
          row.value = row.score - baselines[row.position];
        }
      }
      rows.sort((left, right) => {
        if (left.value === null) return right.value === null ? compareScore(left, right) : 1;
        if (right.value === null) return -1;
        return right.value - left.value || compareId(left, right);
      });
    }
    rows.forEach((row, index) => { row.rank = index + 1; });
    return {rows, baselines, unavailableReason};
  }

  return Object.freeze({
    DEFAULT_PROFILE, HALF_PPR, PRESETS, validateProfile, scorePlayer, rankLeague
  });
})();

if (typeof module !== 'undefined' && module.exports) module.exports = PGOLeague;
