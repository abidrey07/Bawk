const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../website/dist/supervisor.js'), 'utf8');
const greeting = source.slice(source.indexOf('function greetingFor'), source.indexOf('function updateGreeting'));
const context = {}; vm.createContext(context); vm.runInContext(greeting, context);
for (const [hour, minute, expected] of [[0,0,'evening'],[4,59,'evening'],[5,0,'morning'],[11,59,'morning'],[12,0,'afternoon'],[16,59,'afternoon'],[17,0,'evening'],[23,59,'evening']]) {
  assert.equal(context.greetingFor(new Date(2026,9,2,hour,minute)), `Good ${expected}`);
}
console.log('PASS: local-time greeting at every boundary, noon and midnight.');

assert.equal(context.fullName({first_name:'Mary Jane',last_name:'de la Cruz'}), 'Mary Jane de la Cruz');
assert.equal(context.fullName({first_name:'Mary Jane',last_name:''}), 'Mary Jane');
const node = { textContent:'' };
context.$ = () => node;
context.supervisor = { first_name:'Mary Jane', last_name:'de la Cruz' };
vm.runInContext(source.slice(source.indexOf('function updateGreeting'), source.indexOf('function showAvatar')), context);
context.updateGreeting();
assert.match(node.textContent, /^Good (morning|afternoon|evening), Mary Jane$/);
console.log('PASS: multi-word first names remain intact in greetings; full-name helper supports multi-word surnames and empty last names.');
