from pathlib import Path
import shutil
from datetime import datetime
import argparse
source = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description='Install Bawk updates into an existing local project, preserving backups.')
parser.add_argument('destination', type=Path, help='Existing Bawk project root')
root = parser.parse_args().destination.expanduser().resolve()
backup = root / 'connection-backups' / datetime.now().strftime('%Y%m%d-%H%M%S')
changes = {
    'Bawk/ContentView.swift': source/'ios/ContentView.swift',
    'Bawk/PracticeStore.swift': source/'ios/PracticeStore.swift',
    'Bawk/ChickenMeadow.swift': source/'ios/ChickenMeadow.swift',
    'Bawk.xcodeproj/project.pbxproj': source/'build-check/Bawk.xcodeproj/project.pbxproj',
    'BawkInfo.plist': source/'build-check/BawkInfo.plist',
    'website/dist/index.html': source/'website/dist/index.html',
    'website/dist/app.js': source/'website/dist/app.js',
    'website/dist/supervisor.js': source/'website/dist/supervisor.js',
    'website/dist/style.css': source/'website/dist/style.css',
    'website/server.py': source/'website/server.py',
    'website/Start-Bawk.command': source/'website/Start-Bawk.command',
    'integration-tests/test_bridge.py': source/'tests/test_bridge.py',
    'CONNECTED-PRACTICE.md': source/'README.md',
}
for swift in (source/'ios').glob('*.swift'):
    changes['Bawk/'+swift.name] = swift
changes['website/rbt.py'] = source/'website/rbt.py'
changes['website/notes.py'] = source/'website/notes.py'
for note_file in (source/'website/dist').glob('notes.*'):
    changes['website/dist/'+note_file.name] = note_file
for parent in (source/'website/dist').glob('parent.*'):
    changes['website/dist/'+parent.name] = parent
for relative, src in changes.items():
    target = root/relative
    if target.exists():
        old = backup/relative
        old.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, old)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
gitignore = root/'website/.gitignore'
existing = gitignore.read_text() if gitignore.exists() else ''
for line in ['data/', '__pycache__/', '.DS_Store']:
    if line not in existing.splitlines(): existing += '\n'+line
if gitignore.exists():
    (backup/'website').mkdir(parents=True, exist_ok=True)
    shutil.copy2(gitignore, backup/'website/.gitignore')
gitignore.write_text(existing.strip()+'\n')
print('Updated Bawk app and website. Backup:', backup)
