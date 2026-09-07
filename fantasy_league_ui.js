(() => {
  const panel = document.querySelector('#panel-fantasy');
  if (!panel) return;
  const body = panel.querySelector('#fantasy-rows');
  const form = panel.querySelector('#fantasy-league-form');
  const status = panel.querySelector('#fantasy-league-status');
  if (!body || !form || !status) return;
  const rows = [...body.rows];
  const viewButtons = [...panel.querySelectorAll('.fantasy-view-button')];
  const sortButtons = [...panel.querySelectorAll('.fantasy-sort')];
  const search = panel.querySelector('#fantasy-player-search');
  const team = panel.querySelector('#fantasy-team');
  const columns = panel.querySelector('#fantasy-columns');
  const count = panel.querySelector('#fantasy-result-count');
  const sortStatus = panel.querySelector('.fantasy-sort-status');
  const rankButton = panel.querySelector('.fantasy-sort[data-column="0"]');
  const profileSelect = panel.querySelector('#fantasy-profile-select');
  const presetSelect = panel.querySelector('#fantasy-scoring-preset');
  const storageKey = 'pgo.fantasy.leagues.v1';
  const clone = value => JSON.parse(JSON.stringify(value));
  const positionNames = {QB: 'QB', RB: 'RB', WR: 'WR', TE: 'TE', FLEX: 'FLEX', SUPERFLEX: 'Superflex'};
  const presetNames = {STANDARD: 'Standard', HALF_PPR: 'Half-PPR', PPR: 'Full PPR', CUSTOM: 'Custom scoring'};
  const componentNames = Object.keys(PGOLeague.HALF_PPR).filter(name => name !== 'te_reception_bonus').sort();
  const rowIds = rows.map(row => row.dataset.playerId);
  if (new Set(rowIds).size !== rows.length || rows.some(row =>
    !row.dataset.playerId || !['QB', 'RB', 'WR', 'TE'].includes(row.dataset.position)
    || !Number.isFinite(Number(row.dataset.basePoints))
    || Number(row.children[5].dataset.sort) !== Number(row.dataset.basePoints)
    || row.dataset.inactive !== String(row.children[13].dataset.sort.toLowerCase() === 'inactive'))) {
    status.textContent = 'League settings are unavailable because the player source data could not be validated.';
    return;
  }
  let scoring;
  let scoringNotice = '';
  try {
    scoring = JSON.parse(panel.querySelector('#fantasy-scoring-data').textContent);
    if (!scoring || typeof scoring !== 'object' || Array.isArray(scoring)
        || scoring.schema_version !== 1
        || typeof scoring.available !== 'boolean' || !scoring.players
        || typeof scoring.players !== 'object' || Array.isArray(scoring.players)
        || (!scoring.available && Object.keys(scoring.players).length)) {
      throw new Error('Invalid scoring payload');
    }
    if (scoring.available) {
      const payloadIds = Object.keys(scoring.players);
      if (payloadIds.length !== rowIds.length || payloadIds.some(id => !rowIds.includes(id))) {
        throw new Error('Invalid scoring population');
      }
      rows.forEach(row => {
        const player = scoring.players[row.dataset.playerId];
        if (!player || typeof player !== 'object' || Array.isArray(player)
            || Object.keys(player).sort().join(',') !== 'components,points,position'
            || player.position !== row.dataset.position
            || typeof player.points !== 'number' || !Number.isFinite(player.points)
            || player.points !== Number(row.dataset.basePoints)
            || !player.components || typeof player.components !== 'object'
            || Array.isArray(player.components)
            || Object.keys(player.components).sort().join(',') !== componentNames.join(',')
            || componentNames.some(name => typeof player.components[name] !== 'number'
              || !Number.isFinite(player.components[name]))) {
          throw new Error('Invalid scoring player');
        }
      });
    }
  } catch (_) {
    scoring = {available: false, players: {}};
    scoringNotice = 'Scoring adjustment data could not be validated. Original half-PPR is active; saved leagues remain stored.';
  }
  const players = rows.map(row => ({
    id: row.dataset.playerId, position: row.dataset.position,
    points: Number(row.dataset.basePoints), inactive: row.dataset.inactive === 'true',
    ...(scoring.available && scoring.players[row.dataset.playerId]
      ? {components: scoring.players[row.dataset.playerId].components} : {})
  }));
  let profiles = [clone(PGOLeague.DEFAULT_PROFILE)];
  let selected = 0;
  let activeProfile;
  let activeView = 'LEAGUE';
  let activeColumn = 0;
  let ascending = true;
  let leagueResult;
  let storageNotice = scoringNotice;
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw !== null) {
      const saved = JSON.parse(raw);
      if (!saved || Object.keys(saved).sort().join(',') !== 'profiles,selected,version' || saved.version !== 1
          || !Array.isArray(saved.profiles) || saved.profiles.length < 1 || saved.profiles.length > 20
          || !Number.isInteger(saved.selected) || saved.selected < 0 || saved.selected >= saved.profiles.length) {
        throw new Error('Invalid saved profiles');
      }
      profiles = saved.profiles.map(PGOLeague.validateProfile);
      selected = saved.selected;
    }
  } catch (_) {
    profiles = [clone(PGOLeague.DEFAULT_PROFILE)];
    selected = 0;
    storageNotice = 'Saved leagues could not be loaded. Default settings are active for this session.';
  }

  function presetFor(profile) {
    return Object.keys(PGOLeague.PRESETS).find(name =>
      Object.keys(PGOLeague.HALF_PPR).every(key => profile.scoring[key] === PGOLeague.PRESETS[name][key])) || 'CUSTOM';
  }

  function saveState(message) {
    try {
      localStorage.setItem(storageKey, JSON.stringify({version: 1, selected, profiles}));
      status.textContent = message + ' Saved in this browser.';
    } catch (_) {
      status.textContent = message + ' Browser storage is unavailable; these settings last for this session only.';
    }
  }

  function fillForm(profile) {
    profileSelect.replaceChildren(...profiles.map((value, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = value.name;
      return option;
    }));
    profileSelect.value = String(selected);
    form.elements.league_name.value = profile.name;
    form.elements.teams.value = profile.teams;
    Object.keys(profile.slots).forEach(key => { form.elements['slot_' + key].value = profile.slots[key]; });
    Object.keys(profile.scoring).forEach(key => { form.elements['score_' + key].value = profile.scoring[key]; });
    presetSelect.value = presetFor(profile);
  }

  function readForm() {
    const profile = {version: 1, name: form.elements.league_name.value,
      teams: Number(form.elements.teams.value), slots: {}, scoring: {}};
    Object.keys(PGOLeague.DEFAULT_PROFILE.slots).forEach(key => {
      profile.slots[key] = Number(form.elements['slot_' + key].value);
    });
    Object.keys(PGOLeague.HALF_PPR).forEach(key => {
      profile.scoring[key] = Number(form.elements['score_' + key].value);
    });
    return PGOLeague.validateProfile(profile);
  }

  function sortRows(column, direction, announce) {
    activeColumn = column;
    ascending = direction;
    const button = sortButtons.find(item => Number(item.dataset.column) === column);
    const numeric = button.dataset.kind === 'number';
    rows.sort((leftRow, rightRow) => {
      const leftRaw = leftRow.children[column].dataset.sort;
      const rightRaw = rightRow.children[column].dataset.sort;
      if (leftRaw === '' && rightRaw !== '') return 1;
      if (rightRaw === '' && leftRaw !== '') return -1;
      const difference = numeric ? Number(leftRaw) - Number(rightRaw) : leftRaw.localeCompare(rightRaw);
      return (ascending ? difference : -difference) || leftRow.dataset.playerId.localeCompare(rightRow.dataset.playerId);
    }).forEach(row => body.appendChild(row));
    sortButtons.forEach(item => item.closest('th').setAttribute('aria-sort', 'none'));
    button.closest('th').setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
    if (announce) sortStatus.textContent = button.textContent.trim() + ' sorted ' + (ascending ? 'ascending' : 'descending');
  }

  function applyFilters(resetRank) {
    const query = search.value.trim().toLowerCase();
    const allPositions = activeView === 'LEAGUE' || activeView === 'SUPERFLEX';
    const rankKey = activeView === 'LEAGUE' ? 'leagueRank'
      : activeView === 'SUPERFLEX' ? 'derivedAllRank'
      : activeView === 'FLEX' ? 'derivedFlexRank' : 'derivedPositionRank';
    rankButton.textContent = activeView === 'LEAGUE' ? (leagueResult.unavailableReason ? 'Pts#' : 'Lg#')
      : activeView === 'SUPERFLEX' ? 'Pts#' : activeView + '#';
    viewButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === activeView)));
    let visible = 0;
    rows.forEach(row => {
      const rank = row.dataset[rankKey] || '';
      row.children[0].textContent = rank || '—';
      row.children[0].dataset.sort = rank;
      const relevant = activeView !== 'LEAGUE' || leagueResult.unavailableReason || row.dataset.leagueValue !== '';
      const positionMatch = allPositions || (activeView === 'FLEX' && row.dataset.position !== 'QB') || row.dataset.position === activeView;
      row.hidden = !(relevant && positionMatch && row.dataset.player.includes(query) && (!team.value || row.dataset.team === team.value));
      if (!row.hidden) visible += 1;
    });
    if (resetRank) sortRows(0, true, false);
    count.textContent = visible + (visible === 1 ? ' player shown' : ' players shown');
  }

  function applyProfile(profile) {
    const next = PGOLeague.rankLeague(players, profile);
    activeProfile = profile;
    leagueResult = next;
    const derived = new Map(next.rows.map(row => [row.id, row]));
    const byPoints = [...next.rows].sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
    const ranks = new Map();
    const positions = {QB: 0, RB: 0, WR: 0, TE: 0};
    let flexRank = 0;
    byPoints.forEach((row, index) => ranks.set(row.id, {all: index + 1,
      position: ++positions[row.position], flex: row.position === 'QB' ? '' : ++flexRank}));
    rows.forEach(row => {
      const value = derived.get(row.dataset.playerId);
      const rank = ranks.get(row.dataset.playerId);
      row.dataset.derivedAllRank = rank.all;
      row.dataset.derivedPositionRank = rank.position;
      row.dataset.derivedFlexRank = rank.flex;
      row.dataset.leagueRank = value.rank;
      row.dataset.leagueValue = value.value === null ? '' : value.value;
      row.children[5].dataset.sort = value.score;
      row.children[5].textContent = value.score.toFixed(1);
      row.children[14].dataset.sort = row.dataset.leagueValue;
      row.children[14].textContent = value.value === null ? '—' : (value.value >= 0 ? '+' : '') + value.value.toFixed(1);
    });
    const preset = presetFor(profile);
    const format = presetNames[preset];
    const lineup = Object.entries(profile.slots).filter(([, number]) => number).map(([key, number]) => number + ' ' + positionNames[key]).join(' · ');
    panel.querySelector('#fantasy-profile-label').textContent = '— ' + profile.name;
    panel.querySelector('#fantasy-league-summary').textContent = profile.teams + ' teams · ' + format + ' · ' + lineup;
    panel.querySelector('#fantasy-table-caption').textContent = 'Eligible 2026 Week 1 projections scored for '
      + format + '; technical source columns retain original half-PPR values.';
    const summary = panel.querySelector('#fantasy-scoring-summary');
    summary.replaceChildren(document.createTextNode(preset === 'HALF_PPR'
      ? 'Original half-PPR projections. League value adjusts for your starting lineup.'
      : 'Experimental scoring adjustment to the half-PPR forecast. Custom scoring weights are scenarios; model status remains HOLD.'));
    if (scoring.available && scoring.receipt_url) {
      const link = document.createElement('a');
      link.href = scoring.receipt_url;
      link.textContent = 'Scoring methods and checks';
      link.target = '_blank'; link.rel = 'noopener noreferrer';
      summary.append(document.createTextNode(' '), link);
    }
    const baselineText = Object.entries(next.baselines).filter(([, number]) => number !== null)
      .map(([position, number]) => position + ' ' + number.toFixed(1)).join(' · ');
    panel.querySelector('#fantasy-replacement-summary').textContent = next.unavailableReason
      ? next.unavailableReason + ' Showing points order; league values are unavailable for this lineup.'
      : 'Replacement projections: ' + baselineText + ' points.';
    if (next.unavailableReason) summary.append(document.createTextNode(' ' + next.unavailableReason + ' League view uses points order.'));
    applyFilters(true);
  }

  function activateStoredProfile(index, source = profiles) {
    const stored = source[index];
    const fallback = !scoring.available && presetFor(stored) !== 'HALF_PPR';
    const profile = fallback
      ? {...clone(stored), scoring: {...PGOLeague.HALF_PPR}} : stored;
    applyProfile(profile);
    return {profile, notice: fallback
      ? 'Saved scoring adjustments for ' + stored.name + ' are unavailable on this board. Original half-PPR is active for this session; the saved league remains unchanged.'
      : ''};
  }

  function applyFromForm(asNew) {
    if (!form.reportValidity()) return;
    try {
      let profile = readForm();
      if (asNew) {
        if (profiles.length >= 20) throw new Error('You can save up to 20 leagues. Delete one before adding another.');
        const originalName = profile.name;
        let suffix = 2;
        while (profiles.some(value => value.name.toLowerCase() === profile.name.toLowerCase())) {
          profile = {...profile, name: originalName.slice(0, 52) + ' (' + suffix++ + ')'};
        }
      }
      applyProfile(profile);
      if (asNew) { profiles.push(profile); selected = profiles.length - 1; }
      else profiles[selected] = profile;
      fillForm(profile);
      saveState('League settings applied.');
    } catch (error) {
      status.textContent = error.message + ' Your active rankings and saved profile have not changed.';
    }
  }

  form.addEventListener('submit', event => { event.preventDefault(); applyFromForm(false); });
  panel.querySelector('#fantasy-profile-new').addEventListener('click', () => applyFromForm(true));
  panel.querySelector('#fantasy-profile-reset').addEventListener('click', () => {
    fillForm({...clone(PGOLeague.DEFAULT_PROFILE), name: profiles[selected].name});
    status.textContent = 'Default settings loaded into the form. Apply to update your league.';
  });
  panel.querySelector('#fantasy-profile-delete').addEventListener('click', () => {
    const remaining = profiles.filter((_, index) => index !== selected);
    if (!remaining.length) remaining.push(clone(PGOLeague.DEFAULT_PROFILE));
    try {
      const activated = activateStoredProfile(0, remaining);
      profiles = remaining;
      selected = 0;
      fillForm(activated.profile);
      saveState('League deleted. ' + activated.notice);
    } catch (error) {
      status.textContent = error.message + ' The league was not deleted.';
    }
  });
  profileSelect.addEventListener('change', () => {
    const nextIndex = Number(profileSelect.value);
    try {
      const activated = activateStoredProfile(nextIndex);
      selected = nextIndex;
      fillForm(activated.profile);
      saveState('League selected. ' + activated.notice);
    } catch (error) {
      profileSelect.value = String(selected);
      status.textContent = error.message;
    }
  });
  presetSelect.addEventListener('change', () => {
    const preset = PGOLeague.PRESETS[presetSelect.value];
    if (preset) Object.keys(preset).forEach(key => { form.elements['score_' + key].value = preset[key]; });
  });
  Object.keys(PGOLeague.HALF_PPR).forEach(key => form.elements['score_' + key].addEventListener('input', () => {
    presetSelect.value = 'CUSTOM';
  }));
  viewButtons.forEach(button => button.addEventListener('click', () => { activeView = button.dataset.view; applyFilters(true); }));
  sortButtons.forEach(button => button.addEventListener('click', () => {
    const column = Number(button.dataset.column);
    sortRows(column, column === activeColumn ? !ascending : ![5, 14].includes(column), true);
  }));
  search.addEventListener('input', () => applyFilters(false));
  team.addEventListener('change', () => applyFilters(false));
  columns.addEventListener('change', () => panel.classList.toggle('show-technical', columns.checked));
  const activated = activateStoredProfile(selected);
  fillForm(activated.profile);
  storageNotice = [storageNotice, activated.notice].filter(Boolean).join(' ');
  status.textContent = storageNotice;
})();
