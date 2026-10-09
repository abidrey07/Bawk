"""Exercise the Swift tracing geometry with real drawn and empty/off-path input."""
from pathlib import Path
import subprocess, tempfile
source = (Path(__file__).resolve().parents[1] / 'ios/ContentView.swift').read_text()
model = source[source.index('struct TracePoint:'):source.index('struct TracingQuestionView:')]
checks = '''
for template in ["school", "letter_a", "number_2", "star"] {
    precondition(TraceDrawing().coverage(template: template) == 0)
    let offPath = TraceDrawing(strokes: [[TracePoint(x: 0, y: 0)]])
    precondition(offPath.coverage(template: template) < 0.1)
    let drawn = TraceDrawing.guide(template).map { stroke in
        zip(stroke, stroke.dropFirst()).flatMap { a,b in
            (0...100).map { i in
                let t = Double(i)/100
                return TracePoint(x: a.x+(b.x-a.x)*t, y: a.y+(b.y-a.y)*t)
            }
        }
    }
    precondition(TraceDrawing(strokes: drawn).coverage(template: template) == 1)
    precondition(TraceDrawing(strokes: [Array(drawn[0].prefix(5))]).coverage(template: template) < 0.75)
}
print("PASS: four tracing guides accept completed paths and reject blank, off-path and tiny strokes")
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'main.swift'
    path.write_text('import Foundation\n' + model + checks)
    subprocess.run(['/usr/bin/swift', '-module-cache-path', str(Path(directory)/'cache'), str(path)], check=True)
