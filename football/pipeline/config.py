"""Every setting in one place."""

SITE_NAME = "GOAT Football"

# The ranking that decides which teams' games are listed first: the AP Top 25.
# Every ranking ESPN carries is read on each full run, so there is no day to
# wait for; the others listed here get a button of their own on the Rankings
# page when they have come out (the playoff committee's starts in November).
POLL_NAME = "AP Top 25"
POLL_TYPE = "ap"
POLL_SIZE = 25
OTHER_POLLS = {"cfp": "Playoff Ranking", "usa": "Coaches Poll"}     # ESPN's type: the button's label

# A game belongs to the day it kicks off on the west coast, so a late kickoff in
# Hawaii still counts as Saturday's.
GAME_TIMEZONE = "America/Los_Angeles"

# ESPN's public feeds (the ones behind espn.com's own pages).
SITE_API = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/"
SCOREBOARD = SITE_API + "scoreboard?groups=80&limit=400"                      # this week, and the season's calendar
WEEK = SITE_API + "scoreboard?dates={season}&seasontype={kind}&week={week}&groups=80&limit=400"   # one week; the page reads live scores from it too
RANKINGS = SITE_API + "rankings"
SUMMARY = SITE_API + "summary?event={game}"
ROSTER = SITE_API + "teams/{team}/roster"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/football/college-football/standings?season={season}&group=80"
CAREER = "https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/{player}/stats"
GAME_PAGE = "https://www.espn.com/college-football/game/_/gameId/"
FBS_GROUP = 80
# If ESPN's calendar cannot be read: the weeks of a normal season (kind 2 is the regular season, 3 the bowls).
DEFAULT_WEEKS = [[2, w, f"Week {w}"] for w in range(1, 16)] + [[3, 1, "Bowls"], [3, 999, "Playoff"]]

BOX_REFRESH_DAYS = 3     # box scores this recent are read again: stats are corrected for a day or two
LIVE_HOURS = 6           # a game is looked for on game-night runs for this long after kickoff

# Team logos and player photos are not stored here: the page shows them straight from ESPN.
# Set LOGO_URL to "" to show no logos, SHOW_PHOTOS to False to show no photos.
LOGO_URL = "https://a.espncdn.com/i/teamlogos/ncaa/500/{team}.png"
PHOTO_URL = "https://a.espncdn.com/i/headshots/college-football/players/full/{player}.png"
SHOW_PHOTOS = True
ROSTER_REFRESH_DAYS = 7  # a team's roster (positions, height, class, hometown, photos) is read again after this many days

# Career stats: each player's seasons as ESPN lists them, read once and again after his team's next game.
CAREERS_PER_RUN = 2500

# Odds: each team's chance of winning, from this site's own ratings (see
# pipeline/odds.py). These settings were chosen by testing on 2021-2025 results.
ODDS_STEP = 0.2           # how far a rating moves per point of surprise, early in the season
ODDS_SETTLE = 3           # after about this many games the moves get smaller
ODDS_MIN_STEP = 0.06      # and never smaller than this
ODDS_KEEP = 0.8           # share of last season's rating (measured from its division's average) a team starts with
ODDS_HOME = 3.0           # home field, in the same units as a rating
ODDS_NEW = -32.0          # starting rating of a school from outside FBS with no history
ODDS_SOFT_CAP = 60.0      # a blowout counts for a little less than its full margin
ODDS_SCALE = 9.0          # how many rating units make a clear favorite
ODDS_TESTED = {"matches": 4547, "favorite_won": 0.743, "seasons": "2021 to 2025"}

# The GOAT ranking (pipeline/goat.py) of every FBS team: head to head
# first, then strength of schedule, the AP poll and record, in that order.
GOAT_WEIGHTS = (0.5, 0.3, 0.2)   # strength of schedule, AP poll, record (head to head comes first, see goat.py)
GOAT_HEAD_TO_HEAD = 0.15  # a head-to-head win outweighs a score gap up to this size (scores run 0 to 1)
GOAT_REACH = 80           # how far up or down the order one move can take a team

# While a game is being played, the page itself re-reads ESPN's scoreboard this
# often (in seconds) and shows the score as it changes.
LIVE_SECONDS = 30

# Be polite to the servers.
FETCH_THREADS = 6
FETCH_RETRIES = 4
USER_AGENT = "Mozilla/5.0 (compatible; goat-sports/1.0)"
