# GOAT Football

The college football part of GOAT Sports, modelled on the college volleyball
site: every FBS game week by week, the AP Top 25 and a GOAT ranking of all FBS
teams, team and player stats, and a page for every team, game and player. A
Top 25 / All FBS switch narrows any page to the ranked teams.

- The page: `https://dougmullendore.github.io/GOAT-Sports/football/`
- The NFL has a copy of the same site at `…/football/nfl/`, reached from the
  College / NFL tabs at the top of every page; see "The NFL" below.
- Every path below is inside this `football/` folder.

## What the site shows

- **Games** (first page): a week at a time, opening on this week. Games still
  to come show the kickoff time in the reader's own time zone, the channel and
  each team's chance of winning; finished ones show the score and link to the
  box score. A game between two ranked teams has a coloured edge. A menu
  narrows the list to one team's whole season.
- **Rankings**: the AP Top 25 with each team's record and how far it moved,
  and its results against the other 24 (Beat / Lost to). Buttons switch to the
  GOAT ranking, the coaches poll, and the playoff committee's ranking once it
  starts in November.
- **Teams**: a sortable table (with a conference menu): record, points for and
  against, yards per play for and against, passing and rushing yards, third
  downs, turnover margin, points per drive, the site's rating and strength of
  schedule.
- **Players**: every player with a number in a box score, ranked by Impact per
  game. Choosing a position swaps in that position's own columns.

Each team has a page (`#/team/<id>`: records, next five games and latest five
results, its stats with its place among the teams shown, and its players);
each game has one (`#/game/<id>`: score by quarter, chance of winning, the
betting line before kickoff, a team comparison, every scoring play, and both
box scores); each player has a card (`#/player/<id>`).

## The NFL

The NFL's pages are the college pages built a second time from the NFL's feeds
(`NFL` at the bottom of `pipeline/config.py` lists every setting that differs;
one run of the job does both leagues, college first). What is different:

- **No poll.** Every team is numbered by its place in the league standings, as
  on the hockey site: share of games won (a tie counts half), then wins, then
  points scored less points allowed. The league's own tie-breakers are not
  worked through. There is no Top 25 switch and there are no Beat / Lost to boxes.
- **Standings** take the place of Rankings: by division, by conference (in
  ESPN's playoff seeding, with a line under the seventh team), the whole
  league, or the GOAT ranking, which uses the same method with a team's place
  in the standings where college uses the AP poll.
- **Teams** go by nickname (Cowboys), and are grouped by division where
  college teams are grouped by conference.
- **Odds** have their own settings, fitted on 2020-2025: tested on 1,688
  games, the favorite won 64.3% (the home team wins 53.9%), and teams given 60
  to 70% won 69%. NFL teams are far closer to one another than college teams,
  so home field counts for 1.0 and ratings move less. `ratings/seed_nfl.json`
  holds where teams finished 2025.
- **Players**: the same Impact, against NFL regulars. Quarterback hits stand
  in for college's hurries. A card shows how long he has been in the league
  and his college. Career tables are ESPN's NFL regular seasons.
- **Stored data** is in the `nfl/` folder inside football's folder on the
  `state` branch; its stages show in `status.json` as "NFL schedule", "NFL
  standings" and so on.
- The wording is in the `nfl.` lines at the bottom of `site/words.txt`.

Not built for the NFL: a playoff bracket or playoff odds, the draft order,
injuries and depth charts, and preseason games.

## Where the numbers come from

Everything is read from ESPN's public feeds (the ones behind espn.com), by
`pipeline/espn.py`:

| What | Feed |
| --- | --- |
| Schedule, scores, channels, betting lines | the weekly scoreboard, one request for each week of the season |
| Rankings | the rankings feed (AP, coaches, playoff committee) |
| Which teams are FBS, conferences, home/away/conference records | the FBS standings |
| Box scores, scoring plays, drives | each game's summary |
| Positions, height, weight, class, hometown, photos | each team's roster, read again every 7 days |
| Career tables | each player's stats page |

A team is known by ESPN's number for it (Texas is 251), and a player by his
(`#/player/4870906`), so nothing has to be matched by name.

Logos and player photos are not stored here: the page shows them from ESPN.
Set `LOGO_URL = ""` or `SHOW_PHOTOS = False` in `pipeline/config.py` to show
none.

## Odds

Each game not yet played shows both teams' chance of winning, the favorite in
bold. These are the site's own estimate (`pipeline/odds.py`); the game's page
also shows the betting line, which is the bookmakers', for comparison.

- Every team has a rating that moves after each game by how far the margin
  was from what the ratings expected, quickly early in the season and slowly
  later. A blowout counts for a little less than its full margin. Home field
  is worth 3 rating units; at a neutral site (as ESPN marks it) it is left out.
- A team starts a season on 80% of where it finished the last one, measured
  from the average of its own division, so a school from outside FBS does not
  drift up toward FBS over the summer.
- Tested on 4,547 games from 2021 to 2025, always predicting from what was
  known beforehand: the favorite won 74.3% of the time (the home team wins
  63.0%), and the percentages were honest: teams given 70 to 80% won 73%, and
  teams given over 90% won 96%.
- `ratings/seed.json` holds where teams finished 2025, for this first season.
  After that, `ratings.json` on the `state` branch carries each season into
  the next. The settings are in `pipeline/config.py`.

## GOAT ranking

The same method as the volleyball site (`pipeline/goat.py`), over every FBS
team: head to head first (a team is ranked above one it has beaten unless the
other factors say the gap is wide), then strength of schedule, the AP poll and
record, weighted 0.5, 0.3 and 0.2 (`GOAT_WEIGHTS`). Everywhere on the site a
team's number is its AP rank, or, for an FBS team outside the poll, its place
from 26 on in GOAT order. A school from outside FBS shows NR and has no page.

## Players and Impact

Impact is points added over an average regular at the same position, from the
box scores (`pipeline/players.py`; the reasoning is at the top of that file).
A yard is worth 0.07 of a point; a touchdown counts as 20 more yards and a
turnover as 45 lost.

| Part | What counts |
| --- | --- |
| Passing | Yards, touchdowns and interceptions against the average quarterback on the same throws. The passer keeps 60%; receivers get the rest |
| Rushing | Yards and touchdowns against the position's average on the same carries |
| Receiving | 40% of his receiving yards and touchdowns beyond what the position's average regular gets from the same number of team passes |
| Defense | Tackles (0.10, solo 0.05 more), tackles for loss (1.0), sacks (0.6 more), hurries (0.3), passes defended (0.7), interceptions (3.0 plus return yards), fumbles recovered (1.5), touchdowns (4.0), beyond the position's average per game |
| Kicking and returns | Field goals and extra points against the average on the same kicks; punt yardage against the average punt; return yardage against the average return |
| Fumbles | Each fumble lost, as a turnover |

- **Positions** come from the team's roster, in nine groups: QB, RB, WR, TE,
  DL, LB, DB, K and P. A player missing from the roster is placed by his numbers.
- **A regular** has played in at least 40% of his team's games and carries a
  regular's load at his position (ten passes a team game for a quarterback,
  four carries for a running back, and so on: `WORKLOAD`). Only regulars are
  ranked and given percentiles.
- **Percentiles** on a card compare a player with regulars at his own position
  and only on jobs he does.

What it cannot do: it sees only the box score, so it knows nothing about
blocking, coverage or who was on the field, and it does not adjust for the
opponent. Offensive linemen have no numbers in a box score and are not listed.
The values in points are my own reasonable choices, not fitted to anything.

Each card also shows season highs, his games against teams now in the top 25,
his career, and every game this season (`pipeline/cards.py`, one file per team
in `cards/`).

### Career tables

The career tables are ESPN's own, with a line for every school a player has
played for (`pipeline/careers.py`, kept in `careers.json` on the `state`
branch). A player's page is read once and again after each of his team's
games, at most 2,500 players a run, ranked teams first; with about 7,500
players in FBS box scores the first pass takes a day or so, and until then a
card says his earlier seasons have not been read yet.

## Live scores and box scores

- While a game is on, the page itself re-reads ESPN's scoreboard for that week
  every 30 seconds and updates the score, the clock and the score by quarter.
  This happens in the reader's browser.
- Team and player stats for a game under way are fetched by the GitHub job on
  its 5-minute runs, which also rebuild the pages when a game ends.

## When it updates

The schedule is in the workflow all the sports share (see the README at the top
of the repository). For football: four full runs a day, two more on Sunday
afternoon for the new AP poll (every full run reads the rankings, so a poll
that comes out late is picked up by the next one), and the 5-minute runs while
a game is on.

A full run reads: the 17 weeks of the schedule, the rankings, the standings,
the box scores it does not have yet and the last three days' again, the
rosters more than a week old, and up to 2,500 careers.

## A new season

Nothing needs doing. When ESPN's scoreboard says a new season has started, the
schedule, box scores and ratings start again from it, and each team begins on
80% of where it finished. Player stats stay empty until the first games.

## Changing the wording

All the site's headings, intro lines, notes, button labels and the footer are
in `site/words.txt`, one `name = words` line each, as on the other sites. A
broken line stops the football update and leaves the old pages up.

## Where things are

| Path | What it is |
| --- | --- |
| `pipeline/config.py` | Every setting |
| `pipeline/espn.py` | Reads ESPN's feeds: schedule, rankings, standings, box scores, rosters, careers |
| `pipeline/odds.py` | Rates every team from results and turns two ratings into a chance of winning |
| `pipeline/goat.py` | The GOAT ranking |
| `pipeline/players.py` | Rates the players and works out percentiles |
| `pipeline/teams.py` | Team stats |
| `pipeline/cards.py` | Each card's extras |
| `pipeline/careers.py` | Reads and keeps career tables |
| `pipeline/web.py` | Downloads, with retries |
| `pipeline/run.py` | The job |
| `site/` | The page itself (plain HTML, CSS and JavaScript, no build step) |
| `tests/` | Saved copies of the feeds from October 10, 2026, with checks that they are read correctly |
| `ratings/seed.json`, `ratings/seed_nfl.json` | Where teams finished 2025, college and NFL |

Run the tests with `cd football && python tests/run_local.py`.

## Not built

- Conference standings as a page of their own (the records are on team pages
  and in the Teams table).
- A playoff bracket or playoff odds.
- Anything from the play-by-play beyond drives: no expected points, success
  rate or win-probability chart.
- Injuries, depth charts, recruiting and transfers.
- Earlier seasons' games and team stats.

Not affiliated with or endorsed by ESPN, the NCAA, the NFL, the Associated Press or any school or team.
