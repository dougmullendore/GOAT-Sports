"""Checks that the feeds are read correctly and that the site builds, using saved copies of
ESPN's feeds (tests/fixtures; index.json says which file is which): one day of last season
for each league, with two box scores each, and what the feeds held on October 10, 2026,
before either season had begun.

Run with:  python tests/run_local.py
"""
import datetime as dt
import json
import os
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
os.environ["FETCH_CACHE"] = str(FIXTURES)

from pipeline import config, espn, odds, players, run, teams, web  # noqa: E402

ILLINOIS, INDIANA, GAME = "356", "84", 401825518         # Illinois 71, Indiana 51
KNICKS, SPURS, NBA_GAME = "18", "24", 401810723          # Knicks 114, Spurs 89
DAYS = {"college": "20260215", "nba": "20260301"}


def league(name):
    config.use(name)


def day_games(name):
    league(name)
    doc = web.get_json(config.DAY.format(day=DAYS[name]))
    return {g["id"]: g for g in (espn.parse_event(e, DAYS[name]) for e in doc["events"]) if g}


def last_season(name, state: Path):
    """Stored data as it stood on one day of last season, built from the saved feeds."""
    league(name)
    now = dt.datetime(2026, 3, 16, 12, tzinfo=dt.timezone.utc)
    games = list(day_games(name).values())
    run.write_json(state / "scoreboard.json", {"season": 2026, "first": "2025-11-03", "last": "2026-04-06",
                                               "days": {DAYS[name]: {"read": "2026-03-16", "games": games}}})
    run.write_json(state / "fbs.json", espn.parse_standings(web.get_json(config.STANDINGS.format(season=2026))))
    if config.POLL_TYPE:
        polls = espn.parse_rankings(web.get_json(config.RANKINGS))
        run.write_json(state / "polls.json", {"season": 2026, **{k: {v["date"]: v} for k, v in polls.items()}})
    run.update_boxes(state, now)
    run.update_rosters(state, now)
    run.update_careers(state, now)
    return now


def test_a_college_day_is_read():
    try:
        games = day_games("college")
        g = games[GAME]
        assert g["state"] == "final" and g["date"] == "2026-02-15" and g["day"] == "20260215" and g["kind"] == 2
        assert (g["away"]["id"], g["away"]["name"], g["away"]["score"]) == (INDIANA, "Indiana", 51)
        assert (g["home"]["id"], g["home"]["name"], g["home"]["score"], g["home"]["lines"]) == (ILLINOIS, "Illinois", 71, [38, 33])
        extra = next(g for g in games.values() if len(g["home"]["lines"]) == 3)          # went to overtime
        assert sum(extra["home"]["lines"]) == extra["home"]["score"]
        assert len(games) > 25
    finally:
        league("college")


def test_an_nba_day_is_read():
    try:
        games = day_games("nba")
        g = games[NBA_GAME]
        assert g["state"] == "final" and (g["away"]["name"], g["away"]["score"]) == ("Spurs", 89)
        assert (g["home"]["id"], g["home"]["score"], g["home"]["lines"]) == (KNICKS, 114, [22, 29, 29, 34])
        assert len(games) == 11
    finally:
        league("college")


def test_the_season_and_the_days_before_it():
    try:
        assert espn.parse_season(web.get_json(config.SCOREBOARD)) == (2027, "2026-11-01", "2027-04-07")
        league("nba")
        season, first, last = espn.parse_season(web.get_json(config.SCOREBOARD))
        assert (season, last) == (2027, "2027-06-26")
        doc = web.get_json(config.DAY.format(day="20261020"))
        opening = [g for g in (espn.parse_event(e, "20261020") for e in doc["events"]) if g]
        assert opening and all(g["state"] == "upcoming" and g["kind"] == 2 and g["start"] for g in opening)
        assert any(g.get("tv") for g in opening)
    finally:
        league("college")


def test_each_day_and_when_it_is_read_again():
    assert run.each_day("2026-02-27", "2026-03-02") == ["20260227", "20260228", "20260301", "20260302"]
    today = dt.date(2026, 3, 1)
    assert run.day_is_due("20260301", "2026-03-01", today)          # today: on every run
    assert run.day_is_due("20260228", "2026-02-28", today)          # yesterday: its late games
    assert run.day_is_due("20260305", None, today)                  # never read
    assert not run.day_is_due("20260110", "2026-01-12", today)      # long over and read since
    assert run.day_is_due("20260420", "2026-02-01", today)          # far ahead, read a month ago


def test_the_poll_and_the_standings():
    try:
        polls = espn.parse_rankings(web.get_json(config.RANKINGS))
        ap = polls["ap"]
        assert ap["name"] == "AP Top 25" and ap["season"] == 2026 and len(ap["rows"]) >= 25
        assert ap["rows"][0]["name"] == "Michigan" and ap["rows"][0]["record"] == "37-3"
        table = espn.parse_standings(web.get_json(config.STANDINGS.format(season=2026)))
        assert len(table) >= config.MIN_TEAMS
        ill = table[ILLINOIS]
        assert (ill["name"], ill["conf"], ill["w"], ill["l"], ill["rec"]["conf"]) == ("Illinois", "Big Ten", 28, 9, "15-5")
        assert espn.parse_standings(web.get_json(config.STANDINGS.format(season=2027))) == {}      # nothing yet for the new season
        league("nba")
        table = espn.parse_standings(web.get_json(config.STANDINGS.format(season=2026)))
        assert len(table) == 30
        ny = table[KNICKS]
        assert (ny["name"], ny["place"], ny["conf"], ny["group"], ny["w"], ny["l"], ny["seed"]) == ("Knicks", "New York", "Atlantic", "East", 53, 29, 3)
        assert ny["rec"]["home"] == "30-10" and ny["logo"].startswith("https://")
        assert {t["group"] for t in table.values()} == {"East", "West"} and len({t["conf"] for t in table.values()}) == 6
    finally:
        league("college")


def test_a_box_score_is_read():
    try:
        league("nba")
        box = espn.parse_summary(web.get_json(config.SUMMARY.format(game=NBA_GAME)))
        assert box["status"] == "F" and box["home_id"] == KNICKS and box["away_id"] == SPURS
        t = dict(zip(espn.TEAM, box["team"]["home"]))
        assert (t["fgm"], t["fga"], t["tpm"], t["reb"], t["ast"], t["to"]) == (43, 97, 17, 54, 27, 14)
        at = {c: 5 + i for i, c in enumerate(espn.COLS)}
        rows = box["players"]["home"]
        og = next(r for r in rows if r[1] == "OG Anunoby")
        assert og[3] == "F" and og[4] == 1 and (og[at["min"]], og[at["pts"]], og[at["fgm"]], og[at["fga"]], og[at["pm"]]) == (35, 12, 5, 11, 16)
        assert sum(r[at["pts"]] for r in rows) == 114 and sum(r[4] for r in rows) == 5
        assert sum(r[at["pts"]] for r in box["players"]["away"]) == 89
        league("college")
        box = espn.parse_summary(web.get_json(config.SUMMARY.format(game=GAME)))
        assert box["home_id"] == ILLINOIS and sum(r[at["pts"]] for r in box["players"]["home"]) == 71
        assert dict(zip(espn.TEAM, box["team"]["away"]))["fga"] == 49
    finally:
        league("college")


def test_a_roster_and_a_career_are_read():
    try:
        league("nba")
        roster = espn.parse_roster(web.get_json(config.ROSTER.format(team=KNICKS)))
        assert len(roster) >= 13
        name, number, pos, height, weight, years, home, photo, college = roster["3136195"]
        assert name == "Karl-Anthony Towns" and pos == "C" and height > 80 and college == "Kentucky"
        career = espn.parse_career(web.get_json(config.CAREER.format(player="3136195")))
        title, heads, seasons, total = career[0]
        assert "Averages" in title and heads[0] == "GP" and "PTS" in heads
        assert seasons[0][:3] == ["2015-16", "MIN", "82"] and len(total) == len(heads)
        league("college")
        roster = espn.parse_roster(web.get_json(config.ROSTER.format(team=ILLINOIS)))
        assert len(roster) >= 10 and all(len(p) >= 8 and p[0] for p in roster.values())
        assert {players.position(p[2]) for p in roster.values()} <= {"G", "F", "C", None}
    finally:
        league("college")


def test_positions():
    assert [players.position(x) for x in ("PG", "SG", "G", "SF", "PF", "F", "C", "G-F", "F-C", "C-F", "", None)] == \
        ["G", "G", "G", "F", "F", "F", "C", "G", "F", "C", None, None]


def test_impact_adds_up_and_ranks_regulars():
    try:
        league("nba")
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            last_season("nba", state)
            sel = run.selection(state)
            boxes = run.read_json(state / "box.json", {})
            assert set(boxes) == {str(NBA_GAME), "401810733"}
            logs = {}
            rated = players.compute(sel["teams"], sel["all_games"], boxes, run.read_json(state / "rosters.json", {}), logs)
        keys = rated["metrics"]
        ps = rated["players"]
        assert rated["regulars"] and all(p["rank"] for p in ps if p["regular"]) and all(p["rank"] is None for p in ps if not p["regular"])
        for p in ps:                       # the four parts add up to the whole
            v = dict(zip(keys, p["v"]))
            assert abs(v["impact_g"] - (v["score"] + v["board"] + v["play"] + v["def"])) < 0.03, p["name"]
        # regulars at a position average out to nothing, weighted by minutes: that is what "over an average regular" means
        for pos in players.POSITIONS:
            grp = [p for p in ps if p["regular"] and p["pos"] == pos]
            if grp:
                assert abs(sum(p["impact"] for p in grp)) < 0.6, pos
        kat = next(p for p in ps if p["name"] == "Karl-Anthony Towns")
        assert kat["pos"] == "C" and kat["team_id"] == KNICKS and kat["gp"] == 1 and kat["tot"]["pts"] == 12 and kat["bio"]["col"] == "Kentucky"
        assert len(logs[kat["id"]][0]) == 6 + len(players.LOG) and logs[kat["id"]][0][5] == "W 114-89"
    finally:
        league("college")


def test_team_stats():
    try:
        league("nba")
        g = day_games("nba")[NBA_GAME]
        box = espn.parse_summary(web.get_json(config.SUMMARY.format(game=NBA_GAME)))
        ranked = [{"id": KNICKS, "name": "Knicks", "rank": 1}, {"id": SPURS, "name": "Spurs", "rank": 2}]
        out = teams.compute(ranked, [g], {str(NBA_GAME): box}, {KNICKS: 5.0, SPURS: 4.0})
        ny = next(t for t in out["teams"] if t["id"] == KNICKS)
        sa = next(t for t in out["teams"] if t["id"] == SPURS)
        assert (ny["w"], ny["l"], ny["ppg"], ny["opp_ppg"]) == (1, 0, 114.0, 89.0)
        assert 95 < ny["pace"] < 110 and ny["ortg"] > sa["ortg"] and abs(ny["net"] + sa["net"]) < 0.2
        assert abs(ny["efg"] - 100 * (43 + 0.5 * 17) / 97) < 0.06 and ny["power"] == 1
    finally:
        league("college")


def test_odds():
    assert abs(odds.chance(10, 10, neutral=True) - 0.5) < 1e-9
    assert odds.chance(10, 10) > 0.5 and odds.chance(20, 0) > odds.chance(10, 0) > odds.chance(0, 10)
    seed = odds.seed()
    assert seed["season"] == 2026 and len(seed["ratings"]) > 300
    try:
        league("nba")
        assert len(odds.seed()["ratings"]) == 30
    finally:
        league("college")


def test_the_words_file():
    words = run.read_words()
    for key in ("games.title", "games.title_fbs", "rankings.lede_nopoll", "nba.games_title", "nba.rankings_title"):
        assert words[key], key


def built(name, check):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            state, out = Path(tmp) / "state", Path(tmp) / "site"
            state.mkdir()
            now = last_season(name, state)
            info = run.build_site(state, out, now)
            check(info, out, json.loads((out / "data.json").read_text()))
    finally:
        league("college")


def test_the_college_site_builds_in_season():
    def check(info, out, data):
        assert info["poll_date"] == "2026-04-07" and info["game_pages"] == 2 and info["players"] > 30
        assert data["site"] == "GOAT Basketball" and data["league"] == "" and not data["pro"] and not data["no_poll"] and data["numbered"]
        assert data["leagues"] == [["nba", "NBA"], ["", "College"]] and data["periods"] == 2 and data["season_label"] == "2025-26"
        assert len(data["poll"]["teams"]) == 25 and data["poll"]["teams"][0]["name"] == "Michigan"
        assert len(data["fbs"]) >= config.MIN_TEAMS and "{day}" in data["live_feed"]
        g = next(g for g in data["games"] if g["id"] == GAME)
        assert g["box"] and g["home"]["rank"] and 0 < g["p0"] < 1
        box = json.loads((out / "game" / f"{GAME}.json").read_text())
        assert len(box["team"]["home"]) == len(espn.TEAM) and box["players"]["home"][0][-1] in (0, 1)
        for name in ("players.json", "players_fbs.json", "teams.json", "teams_fbs.json", "index.html", "app.js", "styles.css", "icon-192.png"):
            assert (out / name).exists(), name
        everyone = json.loads((out / "players_fbs.json").read_text())
        assert everyone["metrics"][0] == "impact_g" and any(p["team_id"] == ILLINOIS for p in everyone["players"])
        assert (out / "cards" / f"{ILLINOIS}.json").exists()
        page = (out / "index.html").read_text()
        assert "app.js?v=" in page and 'id="leagues"' in page and "#c2410c" in page
    built("college", check)


def test_the_nba_site_builds_in_season():
    def check(info, out, data):
        assert info["poll_date"] is None and info["teams"] == 30 and info["game_pages"] == 2
        assert data["league"] == "nba" and data["pro"] and data["numbered"] and data["periods"] == 4
        assert [t["rank"] for t in data["poll"]["teams"]] == list(range(1, 31))
        assert len(data["standings"]) == 30 and data["standings"][0]["gb"] is not None and data["logos"][KNICKS].startswith("https://")
        assert len(data["goat"]["top"]) == 30
        assert not (out / "players.json").exists() and (out / "players_fbs.json").exists()
        cards = json.loads((out / "cards" / f"{KNICKS}.json").read_text())
        kat = cards["3136195"]
        assert kat["games"] and kat["career"] and kat["highs"]
        page = (out / "index.html").read_text()
        assert "#c2410c" in page                             # one colour for the whole sport
        assert "GOAT Basketball: NBA" in (out / "manifest.json").read_text()
    built("nba", check)


def test_a_whole_run_before_the_season():
    """October 10: no game has been played and there is no poll. Both sites still build."""
    os.environ["NOW"] = "2026-10-10T16:00:00+00:00"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            state, out = Path(tmp) / "state", Path(tmp) / "site"
            run.main(str(state), str(out))
            status = json.loads((state / "status.json").read_text())
            sites = {k: v for k, v in status["stages"].items() if k.endswith(" site")}
            assert set(sites) == {"College site", "NBA site"} and all(s["ok"] for s in sites.values()), status
            college = json.loads((out / "data.json").read_text())
            assert college["season"] == 2027 and college["season_label"] == "2026-27"
            assert college["no_poll"] and not college["numbered"] and college["poll"]["teams"] == []
            assert len(college["fbs"]) >= config.MIN_TEAMS            # last season's teams, until the new standings appear
            assert college["games"] and all(g["state"] == "upcoming" for g in college["games"])
            assert any("p" in g for g in college["games"])
            assert len(college["goat"]["top"]) >= config.MIN_TEAMS
            nba = json.loads((out / "nba" / "data.json").read_text())
            assert nba["pro"] and not nba["numbered"] and len(nba["standings"]) == 30
            assert all(t["w"] == 0 and t["l"] == 0 for t in nba["standings"])       # the warm-up games do not count
            assert nba["games"] and all("p" in g for g in nba["games"])
            assert (state / "nba" / "scoreboard.json").exists() and (state / "scoreboard.json").exists()
            # a game-night run with no game on does nothing and says so
            os.environ["RUN_MODE"] = "live"
            before = (out / "data.json").read_text()
            assert run.main(str(state), str(out)) == 0 and (out / "data.json").read_text() == before
    finally:
        os.environ.pop("NOW", None)
        os.environ.pop("RUN_MODE", None)
        league("college")

# ------------------------------------------------------ the backup scoreboard --
def test_scores_come_from_the_backup_when_the_feed_is_down():
    import json as _json
    from pipeline import backup, web as _web
    now = dt.datetime(2026, 10, 11, 1, 0, tzinfo=dt.timezone.utc)
    start = int(now.timestamp()) - 3 * 3600

    def game(gid, away, home, state, a=None, h=None, when=start):
        return {"id": gid, "date": "2026-10-10", "start": when, "state": state,
                "away": {"id": away[1], "name": away[0], "abbr": away[1], "score": a},
                "home": {"id": home[1], "name": home[0], "abbr": home[1], "score": h}}

    def games():
        return [game(1, ("Reds", "CIN"), ("Blues", "STL"), "live", 1, 1),          # on when the feed went down
                game(2, ("Greens", "GRN"), ("Golds", "GLD"), "upcoming"),           # listed the other way round by Yahoo
                game(3, ("Reds", "CIN"), ("Blues", "STL"), "final", 9, 9),          # over: never touched
                game(4, ("Nobody", "NOB"), ("Nowhere", "NWH"), "upcoming"),         # not on Yahoo: left alone
                game(5, ("Greys", "GRY"), ("Pinks", "PNK"), "upcoming", when=start + 9 * 86400)]   # not due yet
    teams = {f"x.t.{i}": {"first_name": city, "last_name": name, "full_name": f"{city} {name}", "abbr": abbr}
             for i, (city, name, abbr) in enumerate([("Cincinnati", "Reds", "CIN"), ("St. Louis", "Blues", "STL"),
                                                     ("Greenville", "Greens", "GRN"), ("Goldsboro", "Golds", "GLD")])}
    when = "Sat, 10 Oct 2026 22:00:00 +0000"
    doc = {"service": {"scoreboard": {"teams": teams, "games": {
        "a": {"start_time": when, "status_type": "status.type.final", "status_display_name": "Final", "current_period_id": "4",
              "away_team_id": "x.t.0", "home_team_id": "x.t.1", "total_away_points": "3", "total_home_points": "2"},
        "b": {"start_time": when, "status_type": "status.type.in_progress", "status_display_name": "2nd", "current_period_id": "2",
              "away_team_id": "x.t.3", "home_team_id": "x.t.2", "total_away_points": "7", "total_home_points": "0"}}}}}
    asked, real = [], _web.get_bytes

    def up(url, *a, **k):
        asked.append(url)
        return _json.dumps(doc).encode()

    def down(url, *a, **k):
        raise _web.FetchError("down")
    try:
        _web.get_bytes = up
        g = games()
        assert backup.patch(g, now, "x", log=lambda m: None) == {"days": 1, "changed": 2}
        assert len(asked) == 1 and "leagues=x&date=2026-10-10" in asked[0]
        assert (g[0]["state"], g[0]["away"]["score"], g[0]["home"]["score"]) == ("final", 3, 2)
        assert (g[1]["state"], g[1]["away"]["score"], g[1]["home"]["score"]) == ("live", 0, 7)
        assert (g[2]["home"]["score"], g[3]["state"], g[4]["state"]) == (9, "upcoming", "upcoming")
        g = games()
        assert run.from_backup(g, now, True, "day") == 2 and not any("backup" in x for x in g)
        assert g[1]["detail"] == "2nd" and "detail" not in g[0]
        _web.get_bytes = down
        assert run.from_backup(games(), now, False, "day") == 0          # part of the feed was read: carry on
        try:
            run.from_backup(games(), now, True, "day")
            raise AssertionError("with nothing read from either, the stage must fail")
        except RuntimeError:
            pass
        try:
            run.from_backup(games()[2:3], now, True, "day")             # nothing to look up is not a reading
            raise AssertionError("with nothing read, the stage must fail")
        except RuntimeError:
            pass
    finally:
        _web.get_bytes = real

