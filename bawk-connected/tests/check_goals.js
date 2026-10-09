// Run with: TZ=America/Los_Angeles node tests/check_goals.js
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../website/dist/app.js'), 'utf8');
const aggregate = source.slice(source.indexOf('function goalDays('), source.indexOf('function renderGoals('));
const now = new Date(2026, 8, 23, 23, 59, 59);
const stamp = day => new Date(2026, 8, day, 12).getTime() / 1000;
const context = { Date, now, clientId: 'a', workspace: {
  sets: [{ id: 's', client_id: 'a', goal_id: 'g' }, { id: 'other', client_id: 'a', goal_id: 'other' }],
  responses: [
    { client_id: 'a', set_id: 's', created: stamp(23), results: [{ independent: true }, { independent: false }, {}] },
    { client_id: 'a', set_id: 's', created: stamp(23), results: [{ independent: true }] },
    { client_id: 'a', set_id: 's', created: stamp(16), results: [{ independent: true }] },
    { client_id: 'a', set_id: 'other', created: stamp(23), results: [{ independent: false }] },
    { client_id: 'other', set_id: 's', created: stamp(23), results: [{ independent: false }] }
  ]
}};
vm.createContext(context);
vm.runInContext(aggregate + '; output = goalDays("g", now);', context);
assert.equal(context.output.length, 7);
assert.equal(context.output[0].date.getDate(), 17);
assert.equal(context.output[0].percent, null);
assert.equal(context.output[6].percent, 66.7);
assert.equal(context.output[6].scored, 3);
assert.equal(context.output[6].sessions, 2);
assert.equal(context.output[6].unscored, 1);
// One second before and exactly at the beginning/end of the local seven-day window.
context.workspace.responses = [new Date(2026, 8, 16, 23, 59, 59), new Date(2026, 8, 17), new Date(2026, 8, 23, 23, 59, 59), new Date(2026, 8, 24)].map(date => ({
  client_id: 'a', set_id: 's', created: date.getTime() / 1000, results: [{ independent: true }]
}));
vm.runInContext('output = goalDays("g", now);', context);
assert.equal(context.output[0].scored, 1);
assert.equal(context.output[6].scored, 1);
assert.equal(context.output.reduce((sum, day) => sum + day.scored, 0), 2);
console.log('PASS: 7-day range, missing-day gaps, weighted repeated practices, goal/client filtering, unscored exclusion, and local midnight boundaries.');
