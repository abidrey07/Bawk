"""Run the route's behavioral checks without launching the app."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'ios/ChickenMeadow.swift').read_text()
route = source[source.index('struct MeadowRoute {'):source.index('struct ChickenMeadowView: View {')]
checks = Path(__file__).with_name('MeadowRouteChecks.swift').read_text()
with tempfile.TemporaryDirectory(prefix='bawk-meadow-checks-') as directory:
    script = Path(directory) / 'main.swift'
    script.write_text('import Foundation\n' + route + '\n' + checks)
    subprocess.run(['xcrun', 'swift', '-module-cache-path', str(Path(directory) / 'cache'), str(script)], check=True)
