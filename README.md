# Bawk

Bawk connects a native iOS client practice app and RBT session view with a local supervisor website.

## Current project

All current application code lives in [`bawk-connected/`](bawk-connected/README.md).

| Folder | Purpose |
| --- | --- |
| [`bawk-connected/ios/`](bawk-connected/ios/) | Canonical Swift source for client practice, the chicken shop, and RBT sessions |
| [`bawk-connected/build-check/`](bawk-connected/build-check/) | Runnable Xcode project and app assets |
| [`bawk-connected/website/`](bawk-connected/website/) | Python server, local SQLite storage, and supervisor website |
| [`bawk-connected/tests/`](bawk-connected/tests/) | API, interface, and app-model checks |

## Run the current version

1. Start the supervisor website with `python3 bawk-connected/website/server.py`, or double-click `bawk-connected/website/Start-Bawk.command` on macOS.
2. Open <http://localhost:8765> and sign in to your supervisor account.
3. Open `bawk-connected/build-check/Bawk.xcodeproj` in Xcode and run the Bawk scheme.
4. Choose **Client practice** or **RBT sessions**, then pair that view using the corresponding code from the supervisor website.

After editing files in `ios/`, run `python3 bawk-connected/sync-ios.py` to synchronize the Xcode project's sources before building.

See the [current setup and feature guide](bawk-connected/README.md) and [future roadmap](bawk-connected/ROADMAP.md). The current version is a local development prototype; the server Mac must remain running for connected practice and sessions. Client databases and credentials are excluded from the repository.

## Validation

```sh
python3 -m unittest discover -s bawk-connected/tests -p 'test_*.py' -v
```

Additional Swift and JavaScript checks are described in the current setup guide.

The retired February 2026 web/cloud scaffold has been removed from the current branch. It remains available in Git history.
