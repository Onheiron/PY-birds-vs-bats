# Online leaderboards

Free, with no server of our own: Firebase on the free plan (Auth and Firestore,
no Cloud Functions) and a GitHub Actions workflow that verifies the games.

## How it works

1. **Account** (`src/services/online.py`): the first time, the game signs in
   to Firebase Auth anonymously with the project's public web key (`online`
   in config.yml) and keeps the refresh token in `~/.bvb/account.json`. No
   password, no e-mail; the identity belongs to that computer.
2. **Sending a game**: at game over, the game's recording (seed, version,
   settings, every key; `src/engine/recorder.py`) is sent to Firestore as a
   *submission*, its bytes in `parts` of at most 700 KB, with the score and
   level the player reached and the name typed at game over.
3. **Verification** (`tools/verify_runs.py`, `.github/workflows/online.yml`,
   every 15 minutes): each new submission is replayed with the code of its
   version (the git tag `v<version>`) and the official configuration. Only
   when the replay ends with the same level and score does the game enter the
   leaderboards; the submission is marked verified or rejected (with why).
4. **Leaderboards**: `boards/<period>-<difficulty>` documents (`all`,
   `month-YYYY-MM`, `week-YYYY-Www`), each with the best run of each player,
   the best 100. TITLE > LEADERBOARDS shows them for the difficulty chosen.

The Firestore rules (`firestore.rules`) let a player only add their own
submissions and parts and set their own name; the leaderboards are read-only
for everyone and written by the verifier with the service account (the
secret `FIREBASE_SERVICE_ACCOUNT`, never in the game).

SETTINGS > ONLINE turns it off: nothing is sent or read. Bot games, the
simulator and the tests never go online (`BVB_OFFLINE`).

## Maintenance

Actions → Online → Run workflow:

- `verify`: verify now (it also runs every 15 minutes);
- `rules`: deploy `firestore.rules`;
- `wipe`: delete every document (a fresh start).

## Limits

- The upgrades a game was played with come from the player's profile, which
  is on their computer: a forged profile is not caught (the game itself is).
- Games played with a custom configuration (`--config`) replay differently
  and are rejected.
- Steam (when the game is on the store): its own leaderboards and
  achievements through the Steam API, and the Steam identity checked by the
  verifier with the Publisher Web API key.
