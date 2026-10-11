"""Every setting in one place. This sport has one league: Major League Baseball."""

SITE_NAME = "GOAT Baseball"
LEAGUE = "mlb"
LEAGUE_NAME = "MLB"
ALL_NAME = "MLB"          # what "every team" is called
STATE_FOLDER = ""         # the league's folder inside this sport's stored data
SITE_FOLDER = ""          # and inside the site
LEAGUE_TABS = [["", "MLB"]]                          # one league, so no tabs are shown
COLOURS = ("#1e40af", "#1e40af")
SEASON_SPANS_YEARS = False                           # a season is named by its one year

# There is no poll: every team is numbered by its place in the league standings.
POLL_NAME = "MLB standings"
POLL_TYPE = None
POLL_SIZE = 30
MIN_TEAMS = 30            # the standings must list at least this many teams to be believed
OTHER_POLLS = {}

# A game belongs to the day it starts on the west coast, so a late game in
# Seattle still counts as that evening's.
GAME_TIMEZONE = "America/Los_Angeles"

# ESPN's public feeds (the ones behind espn.com's own pages).
SITE_API = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/"
SCOREBOARD = SITE_API + "scoreboard?limit=400"                   # today, and the season's dates
DAY = SITE_API + "scoreboard?dates={day}&limit=400"              # one day (YYYYMMDD); the page reads live scores from it too
RANKINGS = None
# Where scores are read from when ESPN cannot be: Yahoo's public scoreboard (pipeline/backup.py).
BACKUP = "mlb"
SUMMARY = SITE_API + "summary?event={game}"
ROSTER = SITE_API + "teams/{team}/roster"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings?season={season}&level=3"
CAREER = "https://site.web.api.espn.com/apis/common/v3/sports/baseball/mlb/athletes/{player}/stats"
GAME_PAGE = "https://www.espn.com/mlb/game/_/gameId/"
TEAM_NAME = "name"        # a team is called by its nickname ("Yankees")
PERIODS = 9               # innings

# The schedule is read a day at a time. On a full run a day is read again if it
# is close (from DAYS_BACK days ago to DAYS_AHEAD days ahead), and a day further
# ahead once every FAR_REFRESH_DAYS days; a day gone by is not read again.
DAYS_BACK = 2
DAYS_AHEAD = 7
FAR_REFRESH_DAYS = 7

BOX_REFRESH_DAYS = 2     # box scores this recent are read again: stats are corrected for a day or two
BOXES_PER_RUN = 1500     # at most this many box scores a run, newest first (a first run late in a season catches up over two)
LIVE_HOURS = 5           # a game is looked for on game-day runs for this long after the first pitch

# Team logos and player photos are not stored here: the page shows them straight from ESPN.
# Each team's logo address comes with the standings. Set SHOW_PHOTOS to False to show no photos.
LOGO_URL = ""
PHOTO_URL = "https://a.espncdn.com/i/headshots/mlb/players/full/{player}.png"
SHOW_PHOTOS = True
ROSTER_REFRESH_DAYS = 7  # a team's roster (positions, height, hometown, photos) is read again after this many days
ROSTERS_PER_RUN = 60

# Career stats: each player's seasons as ESPN lists them, read once and again after his team's next game.
CAREERS_PER_RUN = 1500

# Players (pipeline/players.py). A regular hitter comes to the plate at least this often
# for each game his team has played; a regular starting pitcher and a regular reliever
# get at least this many outs for each game their team has played.
REGULAR_PA = 1.5
REGULAR_OUTS_SP = 1.5
REGULAR_OUTS_RP = 0.6

# Odds: each team's chance of winning, from this site's own ratings (see
# pipeline/odds.py). These settings were chosen by testing on past results.
# Baseball teams are close to one another and one game says little, so
# ratings move slowly and no team is ever a heavy favorite.
ODDS_STEP = 0.01          # how far a rating moves per run of surprise, early in the season
ODDS_SETTLE = 10          # after about this many games the moves get smaller
ODDS_MIN_STEP = 0.01      # and never smaller than this
ODDS_KEEP = 0.9           # share of last season's rating (measured from its division's average) a team starts with
ODDS_HOME = 0.3           # home field, in the same units as a rating
ODDS_NEW = 0.0            # starting rating of a team with no history
ODDS_SOFT_CAP = 15.0      # a blowout counts for a little less than its full margin
ODDS_SCALE = 3.0          # how many rating units make a clear favorite
ODDS_TESTED = {"matches": 9908, "favorite_won": 0.570, "seasons": "2022 to 2025"}
ODDS_SEED = "seed.json"   # in ratings/: where teams finished the season before this site kept its own ratings

# The GOAT ranking (pipeline/goat.py) of every team: head to head first, then
# strength of schedule, place in the standings and record, in that order.
GOAT_WEIGHTS = (0.5, 0.3, 0.2)   # strength of schedule, standings, record (head to head comes first, see goat.py)
GOAT_HEAD_TO_HEAD = 0.15  # a head-to-head lead outweighs a score gap up to this size (scores run 0 to 1)
GOAT_REACH = 80           # how far up or down the order one move can take a team

# While a game is being played, the page itself re-reads ESPN's scoreboard this
# often (in seconds) and shows the score as it changes.
LIVE_SECONDS = 20

# Be polite to the servers.
FETCH_THREADS = 6
FETCH_RETRIES = 4
USER_AGENT = "Mozilla/5.0 (compatible; goat-sports/1.0)"

LEAGUES = ["mlb"]


def use(league: str) -> None:
    """There is one league, so there is nothing to switch."""
    if league != "mlb":
        raise ValueError(f"no such league: {league}")
