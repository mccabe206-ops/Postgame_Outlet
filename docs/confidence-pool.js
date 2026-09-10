'use strict';
function poolTotal(rows, size) {
  if (!Number.isInteger(size) || size < 1 || size > 32 || rows.length > size) return {error:'Choose a slate size from 1 to 32.'};
  let expected = 0, entered = 0;
  const used = new Set();
  for (const row of rows) {
    const pText = String(row.probability).trim(), cText = String(row.points).trim();
    const p = Number(pText), c = Number(cText);
    if (pText && (!Number.isFinite(p) || p < 0 || p > 100)) return {error:'Win chances must be between 0% and 100%.'};
    if (cText) {
      if (!Number.isInteger(c) || c < 1 || c > size) return {error:`Points must be whole numbers from 1 to ${size}.`};
      if (used.has(c)) return {error:'Use each confidence-point value only once.'};
      used.add(c);
    }
    if (!pText || !cText) continue;
    expected += c * p / 100;
    entered++;
  }
  return {expected, entered, complete:entered === size, error:''};
}
function assignPoolPoints(probabilities) {
  const ordered = probabilities.map((value, index) => {
    if (!String(value).trim() || !Number.isFinite(Number(value)) || Number(value) < 0 || Number(value) > 100)
      throw new Error('Enter a valid win chance for every game before assigning points.');
    return {p:Number(value), index};
  }).sort((a,b) => a.p - b.p || a.index - b.index);
  const result = [];
  ordered.forEach((row, index) => { result[row.index] = index + 1; });
  return result;
}
// Browser wiring
const body = document.getElementById('pool-games');
const output = document.getElementById('pool-output');
const sizeInput = document.getElementById('pool-size');
function updatePool() {
  if (Number(sizeInput.value) !== body.rows.length) { output.textContent = 'Choose a valid slate size before calculating.'; return; }
  const rows = [...body.rows].map(row => ({probability:row.querySelector('.probability').value,points:row.querySelector('.points').value}));
  const total = poolTotal(rows, body.rows.length);
  output.textContent = total.error || `${total.complete ? 'Expected pool points' : 'Partial expected pool points'}: ${total.expected.toFixed(2)} (${total.entered} of ${body.rows.length} games entered).`;
}
function resizePool() {
  const size = Number(sizeInput.value);
  if (!Number.isInteger(size) || size < 1 || size > 32) { output.textContent = 'Choose a slate size from 1 to 32.'; return; }
  while (body.rows.length > size) body.deleteRow(-1);
  while (body.rows.length < size) {
    const n = body.rows.length + 1, row = body.insertRow();
    row.innerHTML = `<th scope="row">${n}</th><td><input class="pick" aria-label="Selected team, game ${n}" placeholder="Team name" maxlength="80"></td><td><input class="probability" aria-label="Your win chance percent, game ${n}" type="number" min="0" max="100" step="any" inputmode="decimal"></td><td><input class="points" aria-label="Confidence points, game ${n}" type="number" min="1" max="${size}" step="1" inputmode="numeric"></td>`;
  }
  body.querySelectorAll('.points').forEach(input => { input.max = size; });
  updatePool();
}
body.addEventListener('input', event => {
  if (event.target.classList.contains('pick')) event.target.closest('tr').querySelector('.probability').value = '';
  updatePool();
});
sizeInput.addEventListener('change', resizePool);
document.getElementById('assign-points').addEventListener('click', () => {
  try {
    const points = assignPoolPoints([...body.querySelectorAll('.probability')].map(input => input.value));
    [...body.querySelectorAll('.points')].forEach((input,index) => { input.value = points[index]; });
    updatePool();
  } catch (error) { output.textContent = error.message; }
});
resizePool();
