#!/usr/bin/env bash
# Store what the sports keep between runs (the `state` folder) on the `state` branch.
# Run from the top folder. The branch holds one commit, so it does not grow over the season.
set -euo pipefail
cd state
if [ -z "$(git status --porcelain)" ]; then echo "nothing new to store"; exit 0; fi
git config user.name "goat-sports-bot"
git config user.email "goat-sports-bot@users.noreply.github.com"
git add -A
if git rev-parse -q --verify HEAD >/dev/null; then
  git commit -q --amend -m "State as of $(date -u +%FT%TZ)" || true
else
  git commit -q -m "State as of $(date -u +%FT%TZ)"
fi
git push -q -f "$REPO_URL" HEAD:state
