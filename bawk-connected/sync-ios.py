from pathlib import Path
import shutil
root = Path(__file__).resolve().parent
for source in (root / 'ios').glob('*.swift'):
    shutil.copy2(source, root / 'build-check' / 'Bawk' / source.name)
print('Updated Xcode project sources from ios/.')
