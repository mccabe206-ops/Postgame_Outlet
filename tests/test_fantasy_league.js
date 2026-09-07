'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const PGOLeague = require('../fantasy_league.js');

const COMPONENTS = [
  'passing_yards', 'passing_tds', 'passing_interceptions',
  'passing_2pt_conversions', 'rushing_yards', 'rushing_tds',
  'rushing_2pt_conversions', 'receptions', 'receiving_yards',
  'receiving_tds', 'receiving_2pt_conversions', 'special_teams_tds',
  'fumbles_lost_total'
];

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed += 1;
  } catch (error) {
    error.message = name + ': ' + error.message;
    throw error;
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function profile(overrides = {}) {
  const value = clone(PGOLeague.DEFAULT_PROFILE);
  const {slots, scoring, ...root} = overrides;
  Object.assign(value, root);
  if (overrides.slots) value.slots = {...value.slots, ...overrides.slots};
  if (overrides.scoring) {
    value.scoring = {...value.scoring, ...overrides.scoring};
  }
  return value;
}

function components(overrides = {}) {
  return Object.fromEntries(COMPONENTS.map(name => [name, overrides[name] || 0]));
}

function player(id, position, points, extra = {}) {
  return {id, position, points, ...extra};
}

test('exports the browser and Node API with frozen defaults', () => {
  assert.deepEqual(Object.keys(PGOLeague).sort(), [
    'DEFAULT_PROFILE', 'HALF_PPR', 'PRESETS', 'rankLeague',
    'scorePlayer', 'validateProfile'
  ]);
  assert.deepEqual(Object.keys(PGOLeague.HALF_PPR).sort(), [
    ...COMPONENTS, 'te_reception_bonus', 'wr_reception_bonus'
  ].sort());
  assert.deepEqual(Object.keys(PGOLeague.PRESETS), ['STANDARD', 'HALF_PPR', 'PPR']);
  assert.equal(PGOLeague.DEFAULT_PROFILE.teams, 12);
  assert.deepEqual(PGOLeague.DEFAULT_PROFILE.slots, {
    QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0
  });
  assert.equal(PGOLeague.HALF_PPR.receptions, 0.5);
  assert.equal(PGOLeague.PRESETS.STANDARD.receptions, 0);
  assert.equal(PGOLeague.PRESETS.PPR.receptions, 1);
  assert.ok(Object.isFrozen(PGOLeague.DEFAULT_PROFILE));
  assert.ok(Object.isFrozen(PGOLeague.DEFAULT_PROFILE.slots));
  assert.ok(Object.isFrozen(PGOLeague.DEFAULT_PROFILE.scoring));
  assert.ok(Object.isFrozen(PGOLeague.PRESETS));
});

test('defines a browser-global const without CommonJS', () => {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(require.resolve('../fantasy_league.js'), 'utf8'), context);
  assert.equal(vm.runInContext('typeof PGOLeague.rankLeague', context), 'function');
});

test('validateProfile returns a detached normalized copy', () => {
  const input = profile({name: '  Home League  '});
  const validated = PGOLeague.validateProfile(input);
  assert.equal(validated.name, 'Home League');
  assert.notStrictEqual(validated, input);
  assert.notStrictEqual(validated.slots, input.slots);
  assert.notStrictEqual(validated.scoring, input.scoring);
  assert.equal(input.name, '  Home League  ');
});

test('validateProfile rejects missing and extra keys at every level', () => {
  for (const [level, key] of [
    ['profile', 'version'], ['slots', 'RB'], ['scoring', 'passing_yards']
  ]) {
    const value = profile();
    delete (level === 'profile' ? value : value[level])[key];
    assert.throws(() => PGOLeague.validateProfile(value), /keys/i);
  }
  for (const level of ['profile', 'slots', 'scoring']) {
    const value = profile();
    (level === 'profile' ? value : value[level]).surprise = 1;
    assert.throws(() => PGOLeague.validateProfile(value), /keys/i);
  }
  assert.throws(() => PGOLeague.validateProfile(null), /profile/i);
  assert.throws(() => PGOLeague.validateProfile([]), /profile/i);
});

test('validateProfile enforces version, name, team, and slot rules', () => {
  for (const bad of [0, 2, true]) {
    assert.throws(() => PGOLeague.validateProfile(profile({version: bad})), /version/i);
  }
  for (const bad of ['', '   ', 'x'.repeat(61), 12]) {
    assert.throws(() => PGOLeague.validateProfile(profile({name: bad})), /name/i);
  }
  for (const bad of [1, 33, 2.5, true, NaN, Infinity]) {
    assert.throws(() => PGOLeague.validateProfile(profile({teams: bad})), /teams/i);
  }
  for (const field of ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPERFLEX']) {
    const limit = field === 'QB' || field === 'SUPERFLEX' ? 2 : 4;
    for (const bad of [-1, limit + 1, 0.5, true, NaN]) {
      const value = profile();
      value.slots[field] = bad;
      assert.throws(() => PGOLeague.validateProfile(value), new RegExp(field, 'i'));
    }
  }
  assert.throws(() => PGOLeague.validateProfile(profile({slots: {
    QB: 0, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0
  }})), /one lineup slot/i);
});

test('validateProfile enforces every scoring range and finite numeric type', () => {
  const ranges = {
    passing_yards: [0, 1], rushing_yards: [0, 1], receiving_yards: [0, 1],
    passing_tds: [0, 12], rushing_tds: [0, 12], receiving_tds: [0, 12],
    special_teams_tds: [0, 12], receptions: [0, 3],
    passing_interceptions: [-10, 0], fumbles_lost_total: [-10, 0],
    passing_2pt_conversions: [0, 6], rushing_2pt_conversions: [0, 6],
    receiving_2pt_conversions: [0, 6], te_reception_bonus: [0, 3], wr_reception_bonus: [0, 3]
  };
  const boundary = profile();
  for (const [field, [minimum, maximum]] of Object.entries(ranges)) {
    boundary.scoring[field] = maximum;
    for (const bad of [minimum - 1, maximum + 1, true, NaN, Infinity]) {
      const value = profile();
      value.scoring[field] = bad;
      assert.throws(() => PGOLeague.validateProfile(value), new RegExp(field, 'i'));
    }
  }
  assert.equal(PGOLeague.validateProfile(boundary).scoring.receptions, 3);
});

test('canonical half-PPR preserves the source scalar without components', () => {
  const points = 17.123456789;
  assert.strictEqual(PGOLeague.scorePlayer(player('p1', 'WR', points), profile()), points);
});

test('scorePlayer applies reception, passing TD, and TE-only premium deltas', () => {
  const stats = components({receptions: 8, passing_tds: 3});
  assert.equal(PGOLeague.scorePlayer(
    player('wr', 'WR', 20, {components: stats}),
    profile({scoring: {receptions: 1, passing_tds: 6}})
  ), 30);
  const premium = profile({scoring: {te_reception_bonus: 0.5}});
  assert.equal(PGOLeague.scorePlayer(player('te', 'TE', 20, {components: stats}), premium), 24);
  assert.equal(PGOLeague.scorePlayer(player('wr', 'WR', 20, {components: stats}), premium), 20);
});

test('scorePlayer uses all 13 anchor deltas', () => {
  const custom = profile({scoring: Object.fromEntries(
    COMPONENTS.map(name => [name, PGOLeague.HALF_PPR[name] + 0.25])
  )});
  const stats = components(Object.fromEntries(COMPONENTS.map(name => [name, 2])));
  assert.equal(PGOLeague.scorePlayer(player('all', 'RB', 10, {components: stats}), custom), 16.5);
});

test('WR reception bonus is separate from normal PPR and TE premium', () => {
  const stats = components({receptions: 8});
  for (const preset of Object.values(PGOLeague.PRESETS)) {
    const base = profile({scoring: preset});
    const bonus = profile({scoring: {...preset, wr_reception_bonus: 0.5}});
    for (const position of ['QB', 'RB', 'WR', 'TE']) {
      const row = player(position, position, 20, {components: stats});
      assert.equal(PGOLeague.scorePlayer(row, bonus) - PGOLeague.scorePlayer(row, base),
        position === 'WR' ? 4 : 0);
    }
  }
  const both = profile({scoring: {receptions: 1, wr_reception_bonus: 0.5, te_reception_bonus: 1}});
  assert.equal(PGOLeague.scorePlayer(player('wr', 'WR', 20, {components: stats}), both), 28);
  assert.equal(PGOLeague.scorePlayer(player('te', 'TE', 20, {components: stats}), both), 32);
  assert.equal(PGOLeague.scorePlayer(player('out', 'WR', 20, {inactive: true}), both), 0);
});

test('legacy saved profiles default WR bonus to zero and new profiles survive save/reload', () => {
  const legacy = profile({name: 'Existing league', teams: 10, scoring: {te_reception_bonus: 0.75}});
  delete legacy.scoring.wr_reception_bonus;
  const restored = PGOLeague.validateProfile(JSON.parse(JSON.stringify(legacy)));
  assert.deepEqual(restored, {...legacy, scoring: {...legacy.scoring, wr_reception_bonus: 0}});
  assert.equal(Object.hasOwn(legacy.scoring, 'wr_reception_bonus'), false);
  restored.scoring.wr_reception_bonus = 0.25;
  assert.deepEqual(PGOLeague.validateProfile(JSON.parse(JSON.stringify(restored))), restored);
  for (const invalid of [-0.1, 3.1, null, undefined, '0.5', Infinity, NaN, true]) {
    assert.throws(() => PGOLeague.validateProfile(profile({scoring: {wr_reception_bonus: invalid}})),
      /wr_reception_bonus/);
  }
});

test('UI still accepts the frozen 13-component payload after adding positional premiums', () => {
  const source = fs.readFileSync(require.resolve('../fantasy_league_ui.js'), 'utf8');
  const declaration = source.match(/const componentNames =[\s\S]*?;/)[0];
  const names = vm.runInNewContext(declaration + '\ncomponentNames;', {PGOLeague});
  assert.deepEqual([...names], [...COMPONENTS].sort());
});

test('scorePlayer rejects malformed players and incomplete custom components', () => {
  assert.throws(() => PGOLeague.scorePlayer(null, profile()), /player/i);
  assert.throws(() => PGOLeague.scorePlayer(player('', 'QB', 1), profile()), /id/i);
  assert.throws(() => PGOLeague.scorePlayer(player('x', 'K', 1), profile()), /position/i);
  for (const bad of [true, NaN, Infinity]) {
    assert.throws(() => PGOLeague.scorePlayer(player('x', 'QB', bad), profile()), /points/i);
  }
  assert.throws(() => PGOLeague.scorePlayer(
    player('x', 'QB', 1, {inactive: 'true'}), profile()
  ), /inactive/i);
  const custom = profile({scoring: {receptions: 1}});
  assert.throws(() => PGOLeague.scorePlayer(player('x', 'WR', 1), custom), /components/i);
  const missing = components();
  delete missing.receptions;
  assert.throws(() => PGOLeague.scorePlayer(
    player('x', 'WR', 1, {components: missing}), custom
  ), /component.*keys/i);
  assert.throws(() => PGOLeague.scorePlayer(
    player('x', 'WR', 1, {components: {...components(), extra: 0}}), custom
  ), /component.*keys/i);
  assert.throws(() => PGOLeague.scorePlayer(
    player('x', 'WR', 1, {components: components({receptions: Infinity})}), custom
  ), /receptions/i);
});

test('strictly verified inactive players score zero and remain in rankings', () => {
  const league = profile({teams: 2, slots: {
    QB: 1, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0
  }});
  const result = PGOLeague.rankLeague([
    player('q1', 'QB', 20), player('q2', 'QB', 10),
    player('q3', 'QB', 5), player('z', 'QB', 100, {inactive: true})
  ], league);
  assert.deepEqual(result.rows.map(row => [row.id, row.score]), [
    ['q1', 20], ['q2', 10], ['q3', 5], ['z', 0]
  ]);
  assert.deepEqual(result.rows.map(row => row.rank), [1, 2, 3, 4]);
});

test('rankLeague reserves dedicated slots then FLEX without double allocation', () => {
  const league = profile({teams: 2, slots: {
    QB: 0, RB: 1, WR: 1, TE: 1, FLEX: 1, SUPERFLEX: 0
  }});
  const players = [
    ...[30, 20, 18, 12, 5].map((score, i) => player('r' + i, 'RB', score)),
    ...[29, 19, 17, 11, 4].map((score, i) => player('w' + i, 'WR', score)),
    ...[10, 9, 8, 7, 3].map((score, i) => player('t' + i, 'TE', score))
  ];
  const result = PGOLeague.rankLeague(players, league);
  assert.equal(result.unavailableReason, null);
  assert.deepEqual(result.baselines, {QB: null, RB: 12, WR: 11, TE: 8});
  assert.equal(result.rows.find(row => row.id === 'r0').value, 18);
  assert.equal(result.rows.find(row => row.id === 'w0').value, 18);
});

test('SUPERFLEX changes QB replacement after unique starter allocation', () => {
  const players = [30, 28, 20, 15, 10].map((score, i) => player('q' + i, 'QB', score));
  const oneQb = PGOLeague.rankLeague(players, profile({teams: 2, slots: {
    QB: 1, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0
  }}));
  const superflex = PGOLeague.rankLeague(players, profile({teams: 2, slots: {
    QB: 1, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 1
  }}));
  assert.equal(oneQb.baselines.QB, 20);
  assert.equal(superflex.baselines.QB, 10);
  assert.equal(oneQb.rows.find(row => row.id === 'q0').value, 10);
  assert.equal(superflex.rows.find(row => row.id === 'q0').value, 20);
});

test('ties are ordered by stable player ID and irrelevant positions rank last', () => {
  const league = profile({teams: 2, slots: {
    QB: 1, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0
  }});
  const result = PGOLeague.rankLeague([
    player('b', 'QB', 10), player('a', 'QB', 10),
    player('c', 'QB', 0), player('z-rb', 'RB', 100),
    player('a-rb', 'RB', 50)
  ], league);
  assert.deepEqual(result.rows.map(row => row.id), ['a', 'b', 'c', 'z-rb', 'a-rb']);
  assert.equal(result.rows[3].value, null);
  assert.equal(result.baselines.RB, null);
});

test('rankLeague rejects duplicate identities without mutating input', () => {
  const league = profile({teams: 2, slots: {
    QB: 1, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0
  }});
  const players = [
    player('q1', 'QB', 3), player('q2', 'QB', 2), player('q3', 'QB', 1)
  ];
  const snapshot = clone(players);
  PGOLeague.rankLeague(players, league);
  assert.deepEqual(players, snapshot);
  assert.throws(() => PGOLeague.rankLeague([
    ...players, player('q1', 'QB', 0)
  ], league), /duplicate player id/i);
});

test('lineup exhaustion falls back to raw-score ranks with a clear reason', () => {
  const league = profile({teams: 2, slots: {
    QB: 2, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0
  }});
  const result = PGOLeague.rankLeague([
    player('q1', 'QB', 30), player('q2', 'QB', 20),
    player('q3', 'QB', 10), player('rb', 'RB', 100)
  ], league);
  assert.match(result.unavailableReason, /fill 4 QB slots/i);
  assert.deepEqual(result.rows.map(row => row.id), ['rb', 'q1', 'q2', 'q3']);
  assert.ok(result.rows.every(row => row.value === null));
  assert.deepEqual(result.baselines, {QB: null, RB: null, WR: null, TE: null});
});

test('missing replacement falls back instead of inventing zero', () => {
  const league = profile({teams: 2, slots: {
    QB: 2, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0
  }});
  const result = PGOLeague.rankLeague([
    player('q1', 'QB', 30), player('q2', 'QB', 20),
    player('q3', 'QB', 10), player('q4', 'QB', 0)
  ], league);
  assert.match(result.unavailableReason, /no QB replacement/i);
  assert.equal(result.baselines.QB, null);
  assert.ok(result.rows.every(row => row.value === null));
});

console.log('fantasy_league: ' + passed + ' tests passed');
