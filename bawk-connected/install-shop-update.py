"""Install the shop/goal update into the existing Bawk project, preserving a backup."""
from pathlib import Path
from datetime import datetime
import shutil
import sqlite3

source = Path(__file__).resolve().parent
root = Path('/Users/abidreymagsambol/Bawk/Bawk')
changes = {
    'Bawk/ContentView.swift': 'ios/ContentView.swift',
    'Bawk/PracticeStore.swift': 'ios/PracticeStore.swift',
    'Bawk/ChickenMeadow.swift': 'ios/ChickenMeadow.swift',
    'website/server.py': 'website/server.py',
    'website/dist/app.js': 'website/dist/app.js',
    'website/dist/supervisor.js': 'website/dist/supervisor.js',
    'website/dist/index.html': 'website/dist/index.html',
    'website/dist/style.css': 'website/dist/style.css',
    'website/dist/parent.html': 'website/dist/parent.html',
    'website/dist/parent.js': 'website/dist/parent.js',
    'website/dist/parent.css': 'website/dist/parent.css',
    'integration-tests/test_bridge.py': 'tests/test_bridge.py',
    'CONNECTED-PRACTICE.md': 'README.md',
}
backup = root / 'connection-backups' / datetime.now().strftime('shop-%Y%m%d-%H%M%S-%f')
for relative, origin in changes.items():
    if not (source / origin).is_file():
        raise SystemExit(f'Missing update file: {origin}')
backup.mkdir(parents=True)
data = root / 'website/data/bawk.sqlite3'
if data.exists():
    with sqlite3.connect(data) as src, sqlite3.connect(backup / 'bawk.sqlite3') as dst:
        src.backup(dst)
for relative, origin in changes.items():
    target = root / relative
    if target.exists():
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / origin, target)
print('Installed Bawk app and website updates. Backup:', backup)
