# GOAT Basketball

The basketball part of GOAT Sports: men's college basketball, built the way the
college football site is, and the NBA as a second copy of the same pages.

- College: `https://dougmullendore.github.io/GOAT-Sports/basketball/`
- NBA: `…/basketball/nba/`. The NBA is the first of the NBA / College tabs, and
  "Basketball" in the bar across the top opens it. The tabs are at the top of
  every page; see "The NBA" below.
- Every path below is inside this `basketball/` folder.

## What the site shows

- **Games** (first page): three days at a time; opened on today, they are
  today, tomorrow and yesterday. Games still to come show the tip-off time in
  the reader's own time zone, the channel and each team's chance of winning;
  finished ones show the score and link to the box score. A game between two
  ranked teams has a coloured edge. A menu narrows the list to one team's
  whole season.
- **Rankings**: the AP Top 25 with each team's record and how far it moved.
  Buttons switch to the coaches poll and to the GOAT ranking of all of
  Division I, which also lists each team's results against the rest of its
  top 25 (Beat / Lost to).
- **Teams**: a sortable table (with a conference menu): record, points for and
  against, offense, defense and net per 100 possessions, pace, effective field
  goal percentage for and against, turnover and offensive rebound rates, free
  throw rate, three-point shooting, the site's rating and strength of schedule.
- **Players**: every player in a box score, ranked by Impact per game.

A Top 25 / All D-I switch narrows any page to the ranked teams. Each team has a
page (`#/team/<id>`), each game has one (`#/game/<id>`: score by half, chance
of winning, the betting line, a team comparison and both box scores) and each
player has a card (`#/player/<id>`: Impact in four parts, shooting, season
totals and highs, his games against ranked teams, career and game by game).

**Before the season's first AP poll** (it comes out in October or November)
there is no top 25: every page shows all of Division I, the Rankings page shows
the GOAT ranking, which starts in the order teams finished last season, and
teams carry no numbers. The list of teams is last season's until ESPN's
standings for the new season fill in.

## The NBA

The NBA's pages are the college pages built a second time from the NBA's feeds
(`NBA` at the bottom of `pipeline/config.py` lists every setting that differs;
one run of the job does both leagues, college first). What is different:

- **No poll.** Every team is numbered by its place in the league standings:
  share of games won, then wins, then points scored less points allowed. The
  league's own tie-breakers are not worked through. There is no Top 25 switch
  and there are no Beat / Lost to boxes. Before opening night nobody has a
  number, and the records ESPN shows from the warm-up games are left out.
- **Standings** take the place of Rankings: by division, by conference (in
  ESPN's seeding, with a line under the sixth team for the playoffs and the
  tenth for the play-in), the whole league, or the GOAT ranking.
- **Teams** go by nickname (Knicks) and are grouped by division.
- **Warm-up games are not listed.** Playoff and play-in games are listed, with
  the series score, but a player's season numbers are the regular season's.
- **Odds** have their own settings, fitted on 2022-23 to 2025-26: tested on
  5,267 games, the favorite won 65.7%. `ratings/seed_nba.json` holds where
  teams finished 2025-26.
- A box score has plus-minus; a card shows how long he has been in the league
  and his college.

## Player Impact

Impact starts from game score, the box score rolled into one number that reads
like points:

    points + 0.4 x field goals made - 0.7 x field goals tried
    - 0.4 x free throws missed + 0.7 x offensive rebounds + 0.3 x defensive rebounds
    + steals + 0.7 x assists + 0.7 x blocks - 0.4 x fouls - turnovers

A player's Impact is his game score beyond what an average regular at his
position (guard, forward or center) puts up in the same minutes. It is shown in
four parts: scoring, rebounding, playmaking and defense. A regular has played
in at least 40% of his team's games and averages 12 minutes or more (15 in the
NBA); only regulars are ranked and given percentiles. It is a box-score
measure: it cannot see defense that leaves no number or who else was on the
floor, and it does not adjust for the opponent. `pipeline/players.py`.

## Chance of winning

`pipeline/odds.py`: one rating per team, in points. After each game the winner
gains and the loser gives up a share of how far the margin was from what the
ratings expected (large margins count for less and less). Ratings move faster
early in a season, and each new season starts from last season's, pulled toward
the conference average. College, fitted on 2023-24 to 2025-26: tested on 18,835
games, the favorite won 74.2%; home court is worth 3 points.
`ratings/seed.json` holds where teams finished 2025-26.

## GOAT ranking

`pipeline/goat.py`, for every Division I team and for the NBA. Four things
decide it:

1. **The poll (50%).** The AP poll for college: a ranked team gets credit for its
   place in it. For the NBA, ESPN's newest power ranking (`pipeline/power.py`),
   or the standings until one has been read.
2. **Strength of schedule (20%).** The average rating of the teams it has
   played (the ratings behind the odds), stretched to run from 0 for the
   easiest schedule to 1 for the hardest.
3. **Strength of record (20%).** Every win adds the quality of the team beaten,
   squared; every loss takes away a quarter, plus three quarters of how weak
   the team lost to was, squared. Quality is a team's place among all the
   teams by the ratings, from 0 (weakest) to 1 (strongest). So a win over a
   top team is worth far more than a win over a weak one, a loss to a weak
   team costs far more than a loss to a top one, and no loss is free. The
   totals are stretched to run from 0 to 1.
4. **Head to head (10%).** A team that has the better of another is ranked
   above it when the two are within 0.10 of each other on the first three
   (`GOAT_HEAD_TO_HEAD`). A lead counts once, however many games it is by.
   Results that form a circle cannot all be honored; the ranking keeps as
   many as it can.

The settings are `GOAT_WEIGHTS`, `GOAT_HEAD_TO_HEAD`, `GOAT_CURVE` and
`GOAT_LOSS` in `pipeline/config.py`. Every GOAT site uses this formula.

## Where the numbers come from

ESPN's public feeds, with no key: the scoreboard one day at a time, each
game's box score, team rosters, the AP and coaches polls, standings, and each
player's career. `pipeline/config.py` has every address and setting.

The season's schedule is read a day at a time: today and the days around it on
every run, every other day about once a week, so a first run reads the whole
season and later runs read little. Box scores are read once a game is over,
and again for two days in case of corrections; up to 1,500 are read on one
run, so a first run that starts mid-season catches up over a few runs.

During games, a run every 5 minutes reads only the days with a game on and
their box scores, and the page itself reads ESPN's scoreboard every 20 seconds
for the score.

## Changing the wording

`site/words.txt` holds the wording of every page; the lines starting `nba.` at
the bottom are the NBA's own. Edit it on GitHub and the site rebuilds.

## Trying it without GitHub

    python tests/run_local.py                      # the checks, from saved copies of the feeds
    python -m pipeline.run ../state/basketball ../dist/basketball
