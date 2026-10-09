"""Check visual thresholds, recovery after feeding, and out-of-range values."""
from pathlib import Path
import subprocess, tempfile
source = (Path(__file__).resolve().parents[1] / 'ios/ChickenMeadow.swift').read_text()
model = source[source.index('struct ChickenCondition {'):source.index('struct ChickenMeadowView: View {')]
checks = '''
for (level, expected) in [(100.0,0),(75.1,0),(75,1),(50.1,1),(50,2),(25.1,2),(25,3),(0.1,3),(0,4),(-1,4),(101,0)] {
    precondition(ChickenCondition(fedLevel: level).stage == expected)
}
precondition(ChickenCondition(fedLevel: 0).wear > ChickenCondition(fedLevel: 20).wear)
precondition(ChickenCondition(fedLevel: 20).wear > ChickenCondition(fedLevel: 40).wear)
print("PASS: condition thresholds, zero fullness, feeding recovery, bounds")
'''
with tempfile.TemporaryDirectory() as d:
    path = Path(d) / 'main.swift'
    path.write_text('import Foundation\n' + model + checks)
    subprocess.run(['/usr/bin/swift', '-module-cache-path', '/private/tmp/bawk-hunger-module-cache', str(path)], check=True)
