#!/usr/bin/env bash
# Keep following the games that are on. Run from the top folder, at the end of a game-night run.
#
# GitHub is asked to start a game-night run every 5 minutes but in practice starts one about
# every 15. So a run that found a game on does not stop after one look: it looks again every
# FOLLOW_EVERY seconds (each sport's scores and box scores, then the site is published), until
# no game is on, a newer run is waiting to take over, or FOLLOW_PASSES more looks have been made.
set -uo pipefail
every="${FOLLOW_EVERY:-300}"
passes="${FOLLOW_PASSES:-5}"

if ! ls dist/*/index.html >/dev/null 2>&1; then
  echo "no game is on, so there is nothing to follow"; exit 0
fi

waiting() {     # is another run of this job waiting for this one to finish?
  local n
  n=$(gh api "repos/$GITHUB_REPOSITORY/actions/workflows/update.yml/runs?per_page=20" \
        --jq "[.workflow_runs[] | select(.status != \"completed\" and .id != $GITHUB_RUN_ID)] | length" 2>/dev/null) || return 1
  [ "${n:-0}" -gt 0 ]
}

last="${FOLLOW_SINCE:-$(date +%s)}"
for pass in $(seq 1 "$passes"); do
  while [ $(( $(date +%s) - last )) -lt "$every" ]; do
    if waiting; then echo "a newer run is waiting, so it carries on from here"; exit 0; fi
    sleep 30
  done
  last=$(date +%s)
  echo "::group::Look $pass of $passes at the games that are on"
  rm -rf dist pub
  for sport in hockey volleyball football basketball baseball; do
    (cd "$sport" && RUN_MODE=live BY_HAND=0 CHECK_POLL=0 ../tools/run_sport.sh "$sport") \
      || echo "::warning::$sport could not be updated on this look; its pages stay as they were"
  done
  tools/save_state.sh || echo "::warning::what was stored could not be saved on this look"
  if ! ls dist/*/index.html >/dev/null 2>&1; then
    echo "::endgroup::"
    echo "no game is on any more"; exit 0
  fi
  tools/publish.sh || echo "::warning::the site could not be published on this look"
  echo "::endgroup::"
done
echo "that was the last look of this run; the next run carries on"
