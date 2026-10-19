// SPEC-261 R1: build id do bundle web = <sha curto>+<AAAAMMDDhhmm UTC>.
// Fonte do sha: VERCEL_GIT_COMMIT_SHA > GIT_SHA > `git rev-parse` local > "dev".
import { execSync } from 'node:child_process';

const SHA_RE = /^[0-9a-f]{7,40}$/;

function gitShaLocal() {
  return execSync('git rev-parse HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString();
}

function pad(n) { return String(n).padStart(2, '0'); }

export function computeBuildId(env = process.env, now = new Date(), git = gitShaLocal) {
  let sha = '';
  for (const raw of [env.VERCEL_GIT_COMMIT_SHA, env.GIT_SHA]) {
    const candidate = String(raw || '').trim().toLowerCase();
    if (SHA_RE.test(candidate)) { sha = candidate; break; }
  }
  if (!sha) {
    try {
      const candidate = String(git() || '').trim().toLowerCase();
      if (SHA_RE.test(candidate)) sha = candidate;
    } catch { /* sem git: "dev" */ }
  }
  const stamp = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}`
    + `${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}`;
  return `${sha ? sha.slice(0, 7) : 'dev'}+${stamp}`;
}
