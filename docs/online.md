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
   every minute, always on): each new submission is replayed with the code of its
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

## The verified games, and the 'top' bot

Every verified game is kept: the verifier uploads its recording to the
GitHub pre-release `recordings-YYYY-Www` of its week (public, never the
"latest" release the updater looks at), named
`<difficulty>-<score>-<id>.json.gz`. A recording holds the seed, the version,
the settings, the upgrades and every key with its time: no personal data
besides the name typed at game over.

Every Monday `.github/workflows/community-bot.yml` runs
`tools/fit_community.py`: it downloads the best 12 ADVENTURE games of the last
4 weeks, measures them with the code of their version (`tools/fit_bot.py`) and
commits `src/sim/top_profile.json`. The bot profile **top** plays like them:

```bash
python3 game.py --bot top
```

```bash
python3 tools/simulate.py --bot top
```

## Maintenance

Actions → Online → Run workflow (Actions → Community bot → Run workflow fits
the top bot now):

- `verify`: start a watch now (one is always running: it checks every minute and restarts itself);
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
