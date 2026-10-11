"""Every setting in one place.

The job builds two copies of the site: men's college basketball (the settings
as written below) and the NBA (the same settings with the changes listed under
NBA at the bottom of this file). `use("nba")` switches to the NBA's,
`use("college")` back.
"""

SITE_NAME = "GOAT Basketball"
LEAGUE = "college"        # which copy is being built: "college" or "nba"
LEAGUE_NAME = "College"
ALL_NAME = "Division I"   # what "every team" is called
STATE_FOLDER = ""         # the league's folder inside this sport's stored data
SITE_FOLDER = ""          # and inside the site
LEAGUE_TABS = [["nba", "NBA"], ["", "College"]]      # the tabs at the top of every page, the pro league first: folder, label
COLOURS = ("#c2410c", "#c2410c")                     # the sport's one colour, for the college pages and the NBA's alike
SEASON_SPANS_YEARS = True                            # a season is named "2026-27"

# The ranking that decides which teams' games are listed first: the AP Top 25.
# Every ranking ESPN carries is read on each full run, so there is no day to
# wait for. Before the preseason poll is out there is no top 25: the pages show
# all of Division I until it comes.
POLL_NAME = "AP Top 25"
POLL_TYPE = "ap"          # None for a league with no poll: its teams are numbered by the standings instead
POLL_SIZE = 25
MIN_TEAMS = 300           # the standings must list at least this many teams to be believed
OTHER_POLLS = {"usa": "Coaches Poll"}     # ESPN's type: the button's label

# A game belongs to the day it tips off on the west coast, so a late game in
# Hawaii still counts as that evening's.
GAME_TIMEZONE = "America/Los_Angeles"

# ESPN's public feeds (the ones behind espn.com's own pages).
SITE_API = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/"
SCOREBOARD = SITE_API + "scoreboard?limit=400&groups=50"                   # today, and the season's dates
DAY = SITE_API + "scoreboard?dates={day}&limit=400&groups=50"              # one day (YYYYMMDD); the page reads live scores from it too
RANKINGS = SITE_API + "rankings"
SUMMARY = SITE_API + "summary?event={game}"
ROSTER = SITE_API + "teams/{team}/roster"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/basketball/mens-college-basketball/standings?season={season}&group=50"
CAREER = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/mens-college-basketball/athletes/{player}/stats"
GAME_PAGE = "https://www.espn.com/mens-college-basketball/game/_/gameId/"
TEAM_NAME = "location"    # a team is called by its school ("Duke"); the NBA's by its nickname ("Celtics")
PERIODS = 2               # two halves; the NBA plays four quarters
GAME_MINUTES = 40

# The schedule is read a day at a time. On a full run a day is read again if it
# is close (from DAYS_BACK days ago to DAYS_AHEAD days ahead), and a day further
# ahead once every FAR_REFRESH_DAYS days; a day gone by is not read again.
DAYS_BACK = 2
DAYS_AHEAD = 7
FAR_REFRESH_DAYS = 7

BOX_REFRESH_DAYS = 2     # box scores this recent are read again: stats are corrected for a day or two
BOXES_PER_RUN = 1500     # at most this many box scores a run, newest first (a first run in mid-season catches up over a few)
LIVE_HOURS = 4           # a game is looked for on game-night runs for this long after tip-off

# Team logos and player photos are not stored here: the page shows them straight from ESPN.
# Set LOGO_URL to "" to show no logos, SHOW_PHOTOS to False to show no photos.
LOGO_URL = "https://a.espncdn.com/i/teamlogos/ncaa/500/{team}.png"
PHOTO_URL = "https://a.espncdn.com/i/headshots/mens-college-basketball/players/full/{player}.png"
SHOW_PHOTOS = True
ROSTER_REFRESH_DAYS = 7  # a team's roster (positions, height, class, hometown, photos) is read again after this many days
ROSTERS_PER_RUN = 400

# Career stats: each player's seasons as ESPN lists them, read once and again after his team's next game.
CAREERS_PER_RUN = 2500

# Players: a regular has played in at least 40% of his team's games (pipeline/players.py)
# and averages at least this many minutes in the games he plays.
REGULAR_MINUTES = 12
BIG_GAME = 25            # a game with this many points is counted on a player's card

# Odds: each team's chance of winning, from this site's own ratings (see
# pipeline/odds.py). These settings were chosen by testing on past results.
ODDS_STEP = 0.2           # how far a rating moves per point of surprise, early in the season
ODDS_SETTLE = 3           # after about this many games the moves get smaller
ODDS_MIN_STEP = 0.05      # and never smaller than this
ODDS_KEEP = 0.9           # share of last season's rating (measured from its division's average) a team starts with
ODDS_HOME = 3.0           # home court, in the same units as a rating
ODDS_NEW = -28.0          # starting rating of a school from outside Division I with no history
ODDS_SOFT_CAP = 40.0      # a blowout counts for a little less than its full margin
ODDS_SCALE = 6.0          # how many rating units make a clear favorite
ODDS_TESTED = {"matches": 18835, "favorite_won": 0.742, "seasons": "2023-24 to 2025-26"}
ODDS_SEED = "seed.json"   # in ratings/: where teams finished the season before this site kept its own ratings

# The GOAT ranking (pipeline/goat.py) of every Division I team: head to head
# first, then strength of schedule, the AP poll and record, in that order.
GOAT_WEIGHTS = (0.5, 0.2, 0.2)   # the poll (or ESPN's power ranking, or the standings), strength of schedule, strength of record
GOAT_CURVE = 2            # strength of record: how much more a win over a top team counts than one over a middling team
GOAT_LOSS = 0.25          # strength of record: the least any loss costs, even to the best team (a win over the best team is worth 1)
GOAT_HEAD_TO_HEAD = 0.1   # head to head, the last tenth: having the better of a team outweighs a score gap up to this size (scores run 0 to 0.9)
GOAT_REACH = 80           # how far up or down the order one move can take a team

# While a game is being played, the page itself re-reads ESPN's scoreboard this
# often (in seconds) and shows the score as it changes.
LIVE_SECONDS = 20

# Be polite to the servers.
FETCH_THREADS = 6
FETCH_RETRIES = 4
USER_AGENT = "Mozilla/5.0 (compatible; goat-sports/1.0)"


# ---------------------------------------------------------------- the NBA --
# What is different for the NBA's copy of the site. There is no poll: every team is numbered by
# its place in the league standings, as on the hockey site.
# ESPN's power rankings stand in for a poll in a pro league (pipeline/power.py): the league as ESPN's addresses write it.
POWER = None
POWER_ABBR = {}             # ESPN's short names for teams where they differ from the ones used here
# Wikidata's name for the kind of player id this league uses; players' social media pages are looked up by it (pipeline/social.py).
SOCIAL_IDS = None             # none for college basketball
# Where scores are read from when ESPN cannot be: Yahoo's public scoreboard (pipeline/backup.py).
BACKUP = "ncaab"
_NBA_API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/"
NBA = {
    "LEAGUE": "nba", "LEAGUE_NAME": "NBA", "ALL_NAME": "the NBA", "STATE_FOLDER": "nba", "SITE_FOLDER": "nba",
    "POLL_NAME": "NBA standings", "POLL_TYPE": None, "POLL_SIZE": 30, "MIN_TEAMS": 30, "OTHER_POLLS": {},
    "SITE_API": _NBA_API, "BACKUP": "nba", "POWER": "nba", "SOCIAL_IDS": "P3685",
    "SCOREBOARD": _NBA_API + "scoreboard?limit=400",
    "DAY": _NBA_API + "scoreboard?dates={day}&limit=400",
    "RANKINGS": None,
    "SUMMARY": _NBA_API + "summary?event={game}",
    "ROSTER": _NBA_API + "teams/{team}/roster",
    "STANDINGS": "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings?season={season}&level=3",
    "CAREER": "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{player}/stats",
    "GAME_PAGE": "https://www.espn.com/nba/game/_/gameId/",
    "TEAM_NAME": "name", "PERIODS": 4, "GAME_MINUTES": 48,
    "LOGO_URL": "",          # each team's logo address comes with the standings
    "PHOTO_URL": "https://a.espncdn.com/i/headshots/nba/players/full/{player}.png",
    "REGULAR_MINUTES": 15, "BIG_GAME": 30,
    "ODDS_STEP": 0.05, "ODDS_SETTLE": 10, "ODDS_MIN_STEP": 0.02, "ODDS_KEEP": 0.7, "ODDS_HOME": 2.0, "ODDS_NEW": 0.0,
    "ODDS_SOFT_CAP": 50.0, "ODDS_SCALE": 7.0,
        "ODDS_TESTED": {"matches": 5267, "favorite_won": 0.657, "seasons": "2022-23 to 2025-26"}, "ODDS_SEED": "seed_nba.json",
}
LEAGUES = ["college", "nba"]
_COLLEGE = {k: globals()[k] for k in NBA}


def use(league: str) -> None:
    """Switch every setting to one league's."""
    globals().update(_COLLEGE)
    if league == "nba":
        globals().update(NBA)
    elif league != "college":
        raise ValueError(f"no such league: {league}")
