"""Run the actual Swift wardrobe model against isolated disposable client IDs."""
from pathlib import Path
import subprocess
import tempfile
source = (Path(__file__).resolve().parents[1] / 'ios/ContentView.swift').read_text()
model = source[source.index('struct ChickenShopItem:'):source.index('struct ChickenShopView:')]
checks = r'''
@main struct Checks {
 @MainActor static func main() {
  let client = "test-" + UUID().uuidString
  let other = "test-" + UUID().uuidString
  defer { for id in [client, other] { UserDefaults.standard.removeObject(forKey: "bawkWardrobe.\(id)") } }
  let wardrobe = ChickenWardrobe()
  wardrobe.load(clientID: client)
  let party = ChickenShopItem.all[0], cap = ChickenShopItem.all[1], glasses = ChickenShopItem.all[2], terrain = ChickenShopItem.all[4]
  wardrobe.choose(party, earned: 0)
  precondition(!wardrobe.owns(party) && wardrobe.spent == 0)
  wardrobe.choose(party, earned: 2000)
  precondition(wardrobe.hat == "party" && wardrobe.spent == 150)
  wardrobe.choose(cap, earned: 2000)
  wardrobe.choose(glasses, earned: 2000)
  wardrobe.choose(terrain, earned: 2000)
  precondition(wardrobe.hat == "yankees" && wardrobe.glasses == "thug" && wardrobe.terrain == "volcanic" && wardrobe.spent == 940)
  wardrobe.choose(cap, earned: 2000)
  precondition(wardrobe.hat.isEmpty && wardrobe.spent == 940)
  wardrobe.choose(party, earned: 2000)
  precondition(wardrobe.hat == "party" && wardrobe.spent == 940)
  let restored = ChickenWardrobe(); restored.load(clientID: client)
  precondition(restored.hat == "party" && restored.glasses == "thug" && restored.terrain == "volcanic" && restored.spent == 940)
  restored.load(clientID: other)
  precondition(restored.hat.isEmpty && restored.spent == 0 && !restored.owns(party))
  print("Shop checks passed: affordability, purchases, slot replacement, combinations, free re-equip, persistence, client isolation")
 }
}
'''
with tempfile.TemporaryDirectory(prefix='bawk-shop-checks-') as directory:
    root = Path(directory).resolve()
    script = root / 'checks.swift'
    script.write_text('import Foundation\nimport Combine\n' + model + checks)
    subprocess.run(['xcrun', 'swiftc', '-parse-as-library', '-module-cache-path', str(root/'cache'), str(script), '-o', str(root/'checks')], check=True)
    subprocess.run([str(root/'checks')], check=True)
