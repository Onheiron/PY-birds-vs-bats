// BVB: starts the leaderboards' verifier when a game is waiting (docs/online.md).
//
// A Cloudflare Worker (free plan) with a Cron Trigger, every 2 minutes: it asks Firestore
// whether a submission is pending (the rules allow exactly that query, nothing more) and, if
// one is, starts the GitHub workflow online.yml (action verify), unless one is already
// queued or running. The workflow replays the games and updates the leaderboards in about
// a minute, then stops.
//
// Secret of the Worker (Settings > Variables and Secrets): GITHUB_TOKEN, a fine-grained
// GitHub token for this repository only, with "Actions: Read and write".
// Opening the Worker's URL only says whether a game is waiting (it starts nothing).

const PROJECT = 'birds-vs-bats';
const API_KEY = 'AIzaSyAmAn2UPtoFXJMniP9d68juw-OC4KmGHmE'; // the game's public web key
const REPO = 'Onheiron/PY-birds-vs-bats';
const WORKFLOW = 'online.yml';

async function pending() {
  const query = {
    structuredQuery: {
      from: [{ collectionId: 'submissions' }],
      where: { fieldFilter: { field: { fieldPath: 'status' }, op: 'EQUAL', value: { stringValue: 'pending' } } },
      limit: 1,
    },
  };
  const url = `https://firestore.googleapis.com/v1/projects/${PROJECT}/databases/(default)/documents:runQuery?key=${API_KEY}`;
  const reply = await fetch(url, { method: 'POST', body: JSON.stringify(query) });
  if (!reply.ok) throw new Error(`Firestore ${reply.status}: ${await reply.text()}`);
  const rows = await reply.json();
  return rows.some((row) => row.document);
}

async function github(env, method, path, body) {
  const reply = await fetch(`https://api.github.com/repos/${REPO}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'bvb-verifier-worker',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!reply.ok) throw new Error(`GitHub ${reply.status}: ${await reply.text()}`);
  return reply.status === 204 ? null : reply.json();
}

async function busy(env) {
  for (const status of ['queued', 'in_progress']) {
    const runs = await github(env, 'GET', `/actions/workflows/${WORKFLOW}/runs?status=${status}&per_page=1`);
    if (runs.total_count > 0) return true;
  }
  return false;
}

async function check(env) {
  if (!(await pending())) return 'no game waiting';
  if (await busy(env)) return 'a game is waiting: the verifier is already on it';
  await github(env, 'POST', `/actions/workflows/${WORKFLOW}/dispatches`, { ref: 'main', inputs: { action: 'verify' } });
  return 'a game is waiting: verifier started';
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(check(env).then(console.log));
  },
  async fetch() {
    return new Response((await pending()) ? 'a game is waiting\n' : 'no game waiting\n');
  },
};
