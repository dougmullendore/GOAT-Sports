# GOAT Baseball

The baseball part of GOAT Sports: Major League Baseball, built from the same
pages as the NBA and NFL sites.

- The page: `https://dougmullendore.github.io/GOAT-Sports/baseball/`
- Every path below is inside this `baseball/` folder.

## What the site shows

- **Games** (first page): three days at a time; opened on today, they are
  today, tomorrow and yesterday. Games still to come show the start time in
  the reader's own time zone, the probable starting pitchers, the channel and
  each team's chance of winning; finished ones show the score, the winning and
  losing pitchers and a link to the box score. A menu narrows the list to one
  team's whole season.
- **Standings**: by division, by league (in ESPN's playoff seeding, with a
  line under the sixth team), all 30 teams, or the GOAT ranking.
- **Teams**: a sortable table (with a division menu): record, runs for and
  against, batting average, on-base percentage, slugging and OPS, home runs
  and steals per game, earned run average, WHIP, strikeouts and walks per
  nine innings, opponents' batting average, errors, the site's rating and
  strength of schedule.
- **Players**: every hitter and pitcher, ranked by Impact. Choosing hitters
  or pitchers (or one position) swaps in that group's own columns.

Each team has a page (`#/team/<id>`), each game has one (`#/game/<id>`: the
line score by inning with runs, hits and errors, chance of winning, the
betting line, a team comparison, and both teams' batting and pitching lines)
and each player has a card (`#/player/<id>`).

There is no poll: every team is numbered by its place in the league standings
(share of games won, then wins, then runs scored less runs allowed; the
league's own tie-breakers are not worked through). Spring training and the
all-star game are not listed. Playoff games are listed, with the series score,
but the season's team and player numbers are the regular season's.

## Player Impact

Impact is runs above average: how many more runs a player has been worth this
season than an average regular in his job would have been in the same playing
time (`pipeline/players.py`).

- **Hitters**: +0.54 runs for a single, double or triple, +1.40 for a home
  run, +0.31 for a walk and -0.26 for an out, less what an average regular at
  his position (catcher, infielder, outfielder or designated hitter) makes in
  the same number of trips to the plate. Shown in four parts.
- **Pitchers**: the earned runs an average regular starter or reliever gives
  up while getting the same number of outs, less the earned runs he gave up.

A regular hitter has come to the plate 1.5 times for each game his team has
played; a regular starter has pitched half an inning per team game and a
regular reliever a fifth of one. Only regulars are ranked and given percentiles.

What it cannot see: ESPN's box score does not say which hits were doubles or
triples, who was hit by a pitch or who stole a base, so every hit short of a
home run counts the same and fielding and baserunning count for nothing. It
does not adjust for the ballpark or the opponent. Batting average, on-base
percentage, slugging and earned run average on the site are ESPN's own season
figures, which do count everything.

## Chance of winning

`pipeline/odds.py`: one rating per team, in runs, moved a little after every
game. One baseball game says very little, so ratings move slowly and no game
is far from even: tested on 9,908 games from 2022 to 2025, the favorite won
57.0% (the home team wins 52.9%). The starting pitchers are not taken into
account. `ratings/seed.json` holds where teams finished 2025.

## Where the numbers come from

ESPN's public feeds, with no key: the scoreboard one day at a time, each
game's box score, team rosters, standings, and each player's career.
`pipeline/config.py` has every address and setting.

The schedule is read a day at a time: today and the days around it on every
run, every other day about once a week. Box scores are read once a game is
over, and again for two days in case of corrections; at most 500 are read on
one run (a baseball box score is large), so a first run late in a season
catches up over several runs, newest games first. Until it has, team stats
and Impact cover only the games read so far.

During games, a run every 5 minutes reads only the days with a game on and
their box scores, and the page itself reads ESPN's scoreboard every 20 seconds
for the score.

## Changing the wording

`site/words.txt` holds the wording of every page. Edit it on GitHub and the
site rebuilds.

## Trying it without GitHub

    python tests/run_local.py                      # the checks, from saved copies of the feeds
    python -m pipeline.run ../state/baseball ../dist/baseball
