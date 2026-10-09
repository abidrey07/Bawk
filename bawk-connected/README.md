# Bawk: connected local practice

## Use it

1. Double-click `website/Start-Bawk.command`. Keep its Terminal window open.
2. Open http://localhost:8765 on this Mac.
3. Create a supervisor account or sign in, then add a client, enter the client name, type a goal, and add questions.
4. Add/remove choices and mark the correct answer. Save a draft or **Save & assign to client**.
5. Select **Pair iOS app**. In the app, tap **Connect to supervisor** and enter the code.
   - iOS Simulator: server address `http://127.0.0.1:8765`.
   - Physical iPhone: same Wi-Fi as this Mac; use `http://<Mac-local-IP>:8765` and allow local network access. The Mac firewall may need to allow Python.
6. The client name and assigned sets appear after connecting or refreshing. Feed me is disabled when no sets are available, during loading, or after a connection failure.
7. Completed practice contributes to **Goals & independence** at the top of the website. Select a goal and press Refresh to see the last seven days. Individual response lists are no longer displayed.

Published sets are fixed so the client receives exactly what the supervisor approved. Drafts remain editable. New sets can be made for repeat practice.

Multiple-choice feedback uses the supervisor's answer key; open-ended answers are saved for supervisor review. No AI calls are made. Open-ended answers support a microphone button with editable speech-to-text. Microphone and speech permission are requested on first use; typing remains available if permission is denied. AI feedback remains future work.

## Local scope

This connects the app and website through a server on this Mac. It is not a cloud deployment. The Mac must remain on, and an iPhone must be on its local network. Pairing codes expire in ten minutes and are single-use. Device tokens are stored in iOS Keychain; only token hashes are stored on the server. The supervisor page is restricted to this Mac, and clients receive no answer keys.

The local bridge uses HTTP and is intended for development with test clients. Before handling real clinical records or remote clients, deploy the API behind HTTPS with production identity and access controls. An AI key alone does not provide that deployment.

Client data persists in `website/data/bawk.sqlite3` and is excluded from Git. Back up that database to preserve names, sets, and results. The old source files are backed up in `connection-backups` before installation.

## Verification

`python3 -m unittest discover -s tests -p test_bridge.py -v` (use `integration-tests` in the installed project).

Tests cover creating/editing/publishing sets, pairing and replay prevention, client isolation, hidden answer keys, renamed clients, removed-choice validation, open-ended review, saved responses, and duplicate-submission prevention. The iOS app also builds with the simulator SDK.

## Animated meadow

The home screen now includes a native vector meadow with wildflowers, clover, and leafy plants. The chicken wanders between random destinations and pauses to glance, stretch, or peck at decorative seeds. These animations do not change practice progress or the feeding score. Reduce Motion uses a static scene. Animation pauses when the app is inactive or a connection/practice sheet is open.

The cream background fills the connection footer and bottom safe area. The home content scrolls on shorter screens.

Run movement checks with `python3 tests/check_meadow.py` from this folder. These check randomized routes across cycle boundaries, movement bounds, continuous turning, planted feet during stationary actions, and returning to walking after each action.


## Shop and unlimited practice

All assigned sets remain playable after completion. Feed me opens practice again; rewards decrease per completed attempt of the same set: 30, 15, 10, 7, 6, 5, then gradually toward a minimum of one seed. Award totals are stored on the server and retries do not duplicate rewards. Existing rewards are preserved during migration. A fresh round starts without the prior round's answers or hints. Leaving an unfinished round preserves its progress, including whether a hint was shown. Completion requests use a round ID so retrying after a connection problem does not create another completion or reward.

The shop offers a party hat, Yankees hat, Thug Life glasses, 2026 glasses, volcanic terrain, and blue grass with glowing flowers and berry plants. Purchases use earned seeds. Owned items can be equipped again without paying. Purchases and equipped items are saved per client on this device; they do not sync across devices. Hats and glasses use separate slots, so one of each can be worn together; terrain replaces the meadow. Native artwork is shared between individual item previews and the equipped scene.

## Goals dashboard

Client goals form a horizontal row at the top of the planning column. Select a goal for its last-seven-days independence percentage and daily graph. Dates follow the browser's local calendar, including today. Each daily percentage counts first-try correct multiple-choice answers divided by scored answers across completed rounds for that goal, including earlier versions of its sets. A wrong answer triggers an in-app hint and marks that question as prompted for that round. Open-ended answers and legacy responses without independence data are excluded. Missing days appear as 0% dots on the daily graph, with a no-data label to distinguish them from recorded 0% results. Lines connect all seven daily dots; hover or focus a dot for the date and percentage. The headline uses the same weighted calculation across all seven days; it does not average the daily percentages.

This is an in-app performance measure, not a measure of help given outside the app. Previous completion records are preserved during database migration.


## Automatic practice priority

Feed me automatically refreshes and opens the assigned set with the fewest completed practice rounds. Clients do not choose sets. Equal counts favor the least recently completed set, then original assignment order. Incomplete rounds resume with their existing progress and do not increase the completed-round count. Each completed replay moves its set back in priority; assigned sets remain available indefinitely.


## Time-based fullness

The fed bar decreases continuously by 5 percentage points per 30 minutes (10 per hour), down to zero. It uses fractional values and updates every second with a smooth transition while visible. The server stores a fullness level and timestamp per client; the app also caches the last value and timestamp, allowing elapsed time to be applied immediately after reopening, even before a connection succeeds. No background timer is required. Completing a practice round adds 20 points, capped at 100. Retrying submission does not feed twice. The chicken keeps its earned growth stage as fullness declines. Existing clients start from their previous displayed fullness when this update is first applied.

## Client details and family prototype

Click the three-dot button beside a client to open their details in the left column: first name, last name, date of birth, caregiver 1, caregiver 2, and address. Creating a client still requires only a name. Optional fields can be saved or cleared later. Existing names are initially split at the first space and can be corrected in the form. App pairing is beneath these details. The child app only receives the display name, not address, birthday, or caregiver information.

Open http://localhost:8765/parent.html for the **Family nest** prototype. It offers an overview, selectable goal charts, and sample home activities in a distinct green/cream/lavender design. All family information and progress there are fictional. It has no parent authentication, live client connection, or messaging yet.

## Fullness and appearance

The meadow chicken now reflects current fullness independently of earned growth. Above 75% it looks bright; at 75%, 50%, 25%, and 0% it becomes progressively more hunched and tired, with drooping wings, localized dirt blotches, small muted bruises, and scuff marks while keeping its original feather color. Feeding restores its condition. The home scene and shop previews use the same fullness value, including with Reduce Motion enabled. Run `python3 tests/check_condition.py` to verify boundaries and feeding recovery.

## Game settings

Use the gear in the home screen’s upper-right corner to select System, Light, or Dark appearance; enable or mute sound effects; adjust chime volume with buttons or a slider; and reduce chicken movement. Preferences persist on this device. A sample sound previews the volume used when opening the shop or starting practice. The home background includes soft orange accents, and cards adapt to dark appearance.


## Supervisor accounts and profile

Each supervisor has an email/password account and sees only their own clients, goals, sets, and results. The first supervisor account created on this Mac receives existing clients; subsequent accounts start empty. Existing device pairings continue to work. The website remains local to this Mac; email addresses are sign-in identifiers, with no email verification or email-based password recovery.

The upper-right profile menu displays a circular photo (initials until one is added), the supervisor name, and a dropdown arrow. Profile settings allow a name/photo update and password change with the current password. JPEG/PNG photos are cropped and resized locally. Passwords use salted PBKDF2 hashes; session tokens are stored hashed, expire after seven days, and are revoked on sign-out. A password change also revokes other sessions.

The greeting uses the browser's local time and updates every minute: morning 05:00–11:59, afternoon 12:00–16:59, evening 17:00–04:59. Run `node tests/check_supervisor.js` for the time boundaries; the bridge tests cover account lifecycle, expired sessions, initial migration, and cross-supervisor access denial.

Supervisor names are stored as separate `first_name` and `last_name` fields. Greetings use the entire first name; `fullName(person)` joins both fields for profile display. Multi-word names are preserved. On migration, an older combined name is retained intact in the first-name field with an empty last name; supervisors can correct the two fields in Profile settings without an automatic split.

### Managing goals and problem sets
Saved problem sets are grouped in expandable goal sections. Delete problem set removes only that set from active practice; Delete goal removes the goal and all its sets from active practice. Both actions ask for confirmation. Historical responses, progress, earned completion counts, and chicken hunger are preserved. Deleted goals and sets cannot receive new practice submissions.


## October 2026 client, supervisor, and RBT update

Open `build-check/Bawk.xcodeproj` in Xcode to run the iOS app. The first screen selects Client practice or RBT sessions. The source of truth is `ios/`; run `python3 sync-ios.py` after editing it to update the build project.

Supervisors can author tracing questions using four templates: chicken to school, letter A, number 2, and a star. The app captures normalized strokes and uses path coverage as practice guidance. Tracing submissions remain unscored for supervisor review; coverage is not a clinical mastery judgment. Seven new shop assets include a crown, explorer hat, flower crown, heart glasses, aviators, a sunset meadow, and a snowy meadow. Existing owned items stay owned, and prices apply only to new purchases.

Goals include editable mastery criteria. Mark mastered archives the goal and pauses its assigned practice without erasing history; archived goals can be reviewed and restored. Client removal is a soft deletion: device access and RBT assignments are revoked, historical records remain, and open RBT sessions are closed with an explicit draft-retention message.

In the supervisor client details, expand RBT device access, enter the provider details, select assigned clients, and generate a ten-minute one-use code. Pair the RBT iOS view using that code and the same local server address. RBT credentials are separate from client credentials and grant access only to assigned clients.

Start session opens a timer and per-goal Independent, Prompted, and No response counters. Drafts save every 20 seconds and can be saved manually. A saved active session resumes after reopening. Review session note provides the supplied fill-in template, measured percentages, dates, duration rounded to a quarter hour, and descriptive 15-minute units. Enter actual observations; unfilled fields say Not documented. Submitting archives the note and returns to the client list. The supervisor reviews submitted notes and trial counts under Session note history. Retries cannot submit twice or change an archived note.

Practice response data and RBT trial data are displayed separately to avoid conflating independent practice with staff-collected trials. This remains a local prototype; cloud deployment, production identity and access controls, and billing validation are outside this update.

Run `python3 -m unittest discover -s tests -p 'test_*.py' -v` for API integration tests. Additional model checks: `python3 tests/check_shop.py`, `python3 tests/check_tracing.py`, and compile/run `ios/RBTModels.swift` with `tests/RBTNoteChecks.swift`. JavaScript checks use `node tests/check_portals.js`, `node tests/check_goals.js`, and `node tests/check_supervisor.js`.


## Session note archive

Use **Session note history** immediately below the client list to open the dedicated archive page. It includes submitted RBT notes and notes recorded for BCBAs or student analysts. Selecting a client before opening the archive filters it to that client; filters can also show all clients or one author role. Closed cases remain available for historical review.

**Write session note** records the active client, author role/name, session start/end, and narrative. The signed-in supervisor account is retained as the recorder, including when entering a student analyst's note. These are supervisor-managed records, not separate student analyst logins or verified credentials. Submission archives an immutable note; retries do not create duplicates.
