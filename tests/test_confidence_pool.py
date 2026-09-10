import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ConfidencePoolTests(unittest.TestCase):
    def test_expected_points_and_validation(self):
        subprocess.run(['node', '-e', r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const code = fs.readFileSync('docs/confidence-pool.js', 'utf8').split('// Browser wiring')[0];
vm.runInThisContext(code);
assert.equal(poolTotal([{probability:'70',points:'10'}], 10).expected, 7);
assert.equal(poolTotal([{probability:'0',points:'1'}], 1).expected, 0);
assert.ok(poolTotal([], 0).error);
assert.ok(poolTotal([], NaN).error);
assert.equal(poolTotal([{probability:'',points:'1'}], 1).complete, false);
assert.equal(poolTotal([{probability:'101',points:'1'}], 1).error.length > 0, true);
assert.equal(poolTotal([{probability:'Infinity',points:'1'}], 1).error.length > 0, true);
assert.equal(poolTotal([{probability:'60',points:'1'},{probability:'70',points:'1'}],2).error.length > 0,true);
assert.equal(poolTotal([{probability:'60',points:'1.5'}], 2).error.length > 0,true);
assert.deepEqual(assignPoolPoints(['90','55','70']), [3,1,2]);
assert.deepEqual(assignPoolPoints(['70','70']), [1,2]);
assert.throws(() => assignPoolPoints(['','70']));
assert.equal(poolTotal([{probability:'60',points:'1'},{probability:'70',points:'2'}],2).complete,true);
'''], cwd=ROOT, check=True)


if __name__ == '__main__':
    unittest.main()
