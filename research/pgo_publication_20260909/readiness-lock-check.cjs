const assert=require('node:assert/strict'); let now=Date.parse('2026-09-09T23:19:59Z'); let timers=[]; const nodes=[{dataset:{weeklyCutoff:'2026-09-09T23:20:00Z'}},{dataset:{weeklyCutoff:'2026-09-10T23:20:00Z'}}]; Date.now=()=>now; global.document={querySelectorAll:()=>nodes,querySelector:()=>nodes[0]};global.setTimeout=(fn,delay)=>timers.push({fn,delay});
function updateWeeklyLocks() {
  const now = Date.now();
  let next = now + 60000;
  document.querySelectorAll('[data-weekly-cutoff]').forEach(node => {
    const cutoff = Date.parse(node.dataset.weeklyCutoff);
    node.textContent = now >= cutoff ? 'Locked' : 'Draft';
    if (cutoff > now) next = Math.min(next, cutoff);
  });
  if (document.querySelector('[data-weekly-cutoff]')) setTimeout(updateWeeklyLocks, Math.max(1, next - now));
}
updateWeeklyLocks();

assert.deepEqual(nodes.map(x=>x.textContent),['Draft','Draft']);assert.equal(timers.at(-1).delay,1000);now=Date.parse('2026-09-09T23:20:00Z');timers.at(-1).fn();assert.deepEqual(nodes.map(x=>x.textContent),['Locked','Draft']);now=Date.parse('2026-09-10T00:21:00Z');timers.at(-1).fn();assert.deepEqual(nodes.map(x=>x.textContent),['Locked','Draft']);console.log('PASS: exact issued JS before, at and after cutoff; next game remains Draft');