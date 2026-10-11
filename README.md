# GOAT Sports

Five sports sites in one: football (the NFL and college), basketball (the NBA
and men's college), MLB baseball, NHL hockey and women's volleyball (college,
LOVB and MLV). One front page lists the day's games in every league, and a
bar across the top of every page switches between the sports, in that order.

You do not need to run anything. GitHub does it all on a schedule.

- The site: `https://dougmullendore.github.io/GOAT-Sports/`
- Volleyball: `…/GOAT-Sports/volleyball/` (LOVB and MLV under
  `volleyball/lovb/` and `volleyball/mlv/`), hockey: `…/GOAT-Sports/hockey/`,
  football: `…/GOAT-Sports/football/` (the NFL under `football/nfl/`),
  basketball: `…/GOAT-Sports/basketball/` (the NBA under `basketball/nba/`),
  baseball: `…/GOAT-Sports/baseball/`

## How it is put together

Each sport is a site of its own that happens to live in the same repository.

| Folder | What it is |
| --- | --- |
| `volleyball/` | GOAT Volleyball: its code (`pipeline/`), its pages (`site/`), its tests and its own README, which covers college, LOVB and MLV |
| `hockey/` | GOAT Hockey, the same way |
| `football/` | GOAT Football, the same way; its README covers college and the NFL |
| `basketball/` | GOAT Basketball, the same way; its README covers men's college and the NBA |
| `baseball/` | GOAT Baseball (MLB), the same way |
| `home/` | The front page (`index.html`, `home.js`, `home.css`) and the bar's stylesheet (`sports.css`) |
| `tools/assemble.py` | Joins the sports into one site: writes the bar into every page and builds the front page's list of games |
| `tools/run_sport.sh` | Updates one sport; the workflow calls it once for each |
| `.github/workflows/update.yml` | The schedule |

Each sport's README says what its pages show, where its numbers come from and
how its ratings work. Nothing in one sport's folder depends on another's, so a
change to football cannot break hockey.

Two side branches hold what the job produces, each with a folder for each sport:

- `state`: what is stored between runs (`state/volleyball/`, `state/hockey/`,
  `state/football/`, `state/basketball/`, `state/baseball/`), including `status.json` and `logs/last_run.log` for each.
- `gh-pages`: the finished site.

## When it updates

`.github/workflows/update.yml` tells GitHub when to run. All times are Central
and about right; GitHub's scheduled runs are often a few minutes late.

| When | What it does |
| --- | --- |
| Every day about 5:47am and 11:47am | Every sport, in full |
| Every night about 11:47pm | Every sport but hockey, so the night's results are in by morning |
| Every night about 3:17am | Every sport but volleyball, once the late games out west are over |
| Monday about 4pm | Volleyball and basketball, to look for the new AVCA and AP top 25 |
| Monday about 9pm | Volleyball again, in case its poll came out late |
| Sunday about 2:23pm and 6:23pm | Football, to look for the new AP top 25 |
| Every 5 minutes, 11am to 2am | Live scores and box scores: each sport looks whether one of its games is on, and stops within seconds when none is |
| Every 5 minutes on Sunday mornings from about 8am, September to February | The same, for the NFL games played in Europe |
| Whenever the code changes, or you press **Run workflow** on the **Actions** tab | Every sport's checks, then everything, straight away |

A run updates the sports one after another. If one sport fails, the others are
still updated and published; the run shows red on the Actions tab and GitHub
emails you, and the failed sport keeps the pages it had. Only the sports that
were rebuilt are published again, so a 5-minute run during a hockey game does
not touch the other sports' pages.

## The front page

`home/` is the page at the top of the site. It reads `home.json`, which
`tools/assemble.py` writes on every run from each sport's own data: the games
from two days back to ten days ahead, for the NFL, college football (games with
a team in the AP top 25), the NBA, college basketball (the same; every game
until the season's first poll is out), MLB, the NHL, college volleyball (matches
with a team in the AVCA top 25), LOVB and MLV, in that order (`LEAGUES` in
`tools/assemble.py`; the order of the bar is `SPORTS` there). A college team
outside the poll carries its number in that sport's GOAT ranking, as on the
sport's own pages. Scores there are as of the last update; each sport's own
pages have the live scores.

## Adding a sport

1. Give it a folder with `pipeline/` (run as `python -m pipeline.run <state> <out>`),
   `site/` and `tests/run_local.py`, like the others.
2. Add it to `SPORTS` and `LEAGUES` at the top of `tools/assemble.py`, and to the
   door list in `home/home.js`.
3. Add a step for it in `.github/workflows/update.yml`, next to the others, and
   its folder to the `paths` list there.

## Turning the website on

One-time setup in the repository's **Settings**:

**Settings → Pages → Build and deployment → Source: "Deploy from a branch"**,
then choose branch `gh-pages` and folder `/ (root)`, and save.

## Good to know

- Hockey and volleyball were moved here from their own repositories
  (github.com/dougmullendore/Hockey and /Volleyball) with their history and
  their stored data. Those repositories still run on their own schedule until
  they are archived (repository **Settings → General → Archive this
  repository**), which is worth doing once this site is the one you use, so
  the same feeds are not read twice.
- GitHub switches off scheduled jobs in a repository with no activity for 60
  days. Each run switches the job back on.
- Run a sport's tests with `cd <sport> && python tests/run_local.py`.

Not affiliated with or endorsed by the NCAA, the AVCA, LOVB, MLV, the NHL, the
NFL, ESPN, the Associated Press or any team or school.
