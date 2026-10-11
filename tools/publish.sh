#!/usr/bin/env bash
# Publish the site. Run from the top folder, after the sports have built their pages into dist/.
#
# The pages of a sport that was rebuilt replace the ones published; the other sports' pages stay
# as they are. The front page and the bar across the top are redone every time.
set -euo pipefail
if [ "${BY_HAND:-0}" = 0 ] && ! ls dist/*/index.html >/dev/null 2>&1; then
  echo "no sport was rebuilt, so the published site stays as it is"; exit 0
fi
rm -rf pub
set +e
git ls-remote --exit-code --heads "$REPO_URL" gh-pages >/dev/null 2>&1
found=$?
set -e
if [ "$found" -eq 0 ]; then
  git clone --quiet --depth 1 --branch gh-pages "$REPO_URL" pub
elif [ "$found" -eq 2 ]; then
  mkdir pub && git -C pub init -q -b gh-pages
else
  echo "The repository could not be reached, so the site was not published."; exit 1
fi
mkdir -p dist
if [ "${BY_HAND:-0}" = 1 ]; then python -m tools.test_assemble; fi
python -m tools.assemble dist pub
cd pub
git config user.name "goat-sports-bot"
git config user.email "goat-sports-bot@users.noreply.github.com"
git add -A
# One commit with no history, so the branch does not grow over the season. Files that
# have not changed are already on GitHub and are not uploaded again.
commit=$(git commit-tree "$(git write-tree)" -m "Site build $(date -u +%FT%TZ)")
git push -q -f "$REPO_URL" "$commit:refs/heads/gh-pages"
