from pathlib import Path
import subprocess,tempfile
s=(Path(__file__).resolve().parents[1] / 'ios/PracticeStore.swift').read_text()
model=s[s.index('struct HungerAnchor:'):s.index('private enum DeviceKeychain')]
checks='''
let start = Date(timeIntervalSince1970: 10000)
let anchor = HungerAnchor(level: 80, recordedAt: start)
precondition(anchor.value(at: start.addingTimeInterval(900)) == 77.5)
precondition(anchor.value(at: start.addingTimeInterval(1800)) == 75)
precondition(abs(anchor.value(at: start.addingTimeInterval(1)) - (80 - 5.0/1800)) < 0.000001)
precondition(anchor.value(at: start.addingTimeInterval(100000)) == 0)
precondition(anchor.value(at: start.addingTimeInterval(-100)) == 80)
let data = try JSONEncoder().encode(anchor)
let restored = try JSONDecoder().decode(HungerAnchor.self, from: data)
precondition(restored.value(at: start.addingTimeInterval(3600)) == 70)
print("PASS: smooth decay, closed-app elapsed time, bounds, timestamp persistence")
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'main.swift';p.write_text('import Foundation\n'+model+checks)
    subprocess.run(['/usr/bin/swift','-module-cache-path','/private/tmp/bawk-hunger-module-cache',str(p)],check=True)
