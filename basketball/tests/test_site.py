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

# ------------------------------------------------- social media pages on cards --
def test_social_links_are_read_and_put_on_cards(tmp_path=None):
    from pipeline import social
    row = lambda pid, **names: {"id": {"value": pid}, **{k: {"value": v} for k, v in names.items()}}
    doc = {"results": {"bindings": [row("101", instagram="some.player_1", twitter="SomePlayer"), row("101", instagram="second.account"),
                                    row("102", tiktok="@dancer"), row("103", twitter="not a name"), row("", instagram="nobody")]}}
    found = social.parse(doc)
    assert found == {"101": {"instagram": "https://www.instagram.com/some.player_1", "twitter": "https://x.com/SomePlayer"},
                     "102": {"tiktok": "https://www.tiktok.com/@dancer"}}
    assert "wdt:P1234 ?id" in social.query("P1234") and "P2003" in social.query("P1234")
    state = Path(tmp_path or tempfile.mkdtemp())
    today = dt.date(2026, 10, 11)
    old_ids, old_fetch = getattr(config, "SOCIAL_IDS", None), social.fetch
    try:
        config.SOCIAL_IDS = "P1234"
        asked = []
        social.fetch = lambda url: (asked.append(url), json.dumps(doc).encode())[1]
        assert social.update(state, today, lambda m: None) == {"read": True, "players": 2}
        assert social.update(state, today + dt.timedelta(days=3), lambda m: None)["read"] is False and len(asked) == 1     # read once a week
        def down(url):
            raise OSError("down")
        social.fetch = down
        again = social.update(state, today + dt.timedelta(days=8), lambda m: None)                  # cannot be read: the stored list stays
        assert again == {"read": False, "players": 2, "failed": True}
        players = [{"id": 101, "bio": {"ht": "6-2"}}, {"id": "102"}, {"id": "999", "bio": {}}]
        assert social.add(state, players) == 2
        assert players[0]["bio"]["ht"] == "6-2" and players[0]["bio"]["social"]["twitter"] == "https://x.com/SomePlayer"
        assert players[1]["bio"]["social"] == {"tiktok": "https://www.tiktok.com/@dancer"} and "social" not in players[2]["bio"]
    finally:
        config.SOCIAL_IDS, social.fetch = old_ids, old_fetch

# ----------------------------------------------- ESPN's power rankings (pro leagues) --
def test_espn_power_rankings_are_found_and_read(tmp_path=None):
    from pipeline import power, web as _web
    def hit(i, name, date, league="xyz"):
        return {"displayName": name, "date": date, "link": {"web": f"https://www.espn.com/{league}/story/_/id/{i}/slug"}}
    search = {"results": [{"contents": [hit(11, "XYZ Power Rankings: Week 3", "2026-10-06T15:00:00Z"), hit(12, "XYZ Power Rankings: Week 2", "2026-09-29T15:00:00Z"),
                                        hit(13, "XYZ Future Power Rankings: three years out", "2026-10-08T15:00:00Z"),
                                        hit(14, "XYZ survivor power rankings", "2026-10-09T15:00:00Z"), hit(15, "ABC Power Rankings", "2026-10-10T15:00:00Z", "abc"),
                                        hit(16, "Trade grades", "2026-10-10T15:00:00Z")]}]}
    assert [a["id"] for a in power.candidates(search, "xyz")] == ["11", "12"]            # newest first; the look-alikes are left out
    def story(order):
        return {"headlines": [{"story": "".join(f'<h2>{i}. <a data-x="1" href="https://www.espn.com/xyz/team/_/name/{a.lower()}/the-{a.lower()}">{n}</a> (1-0)</h2><p>words</p>'
                                                for i, (a, n) in enumerate(order, 1))}]}
    teams = {"1": ["AAA", "Alpha Aces", "Aces"], "2": ["BBB", "Beta Bears", "Bears"], "3": ["CCC", "Gamma Cats", "Cats"]}
    old_abbr = getattr(config, "POWER_ABBR", {})
    old_power, real = getattr(config, "POWER", None), _web.get_bytes
    try:
        config.POWER_ABBR, config.POWER = {"GC": "CCC"}, "xyz"
        good = [("BBB", "Beta Bears"), ("GC", "Gamma Cats"), ("ZZZ", "Alpha Aces")]            # one by ESPN's other short name, one by its name
        assert power.parse_story(story(good))[0] == (1, "BBB", "Beta Bears")
        assert power.match(power.parse_story(story(good)), teams) == {"2": 1, "3": 2, "1": 3}
        assert power.match(power.parse_story(story(good[:2])), teams) is None                      # a team missing: not used
        assert power.match(power.parse_story(story(good + [("QQQ", "Nobody")])), teams) is None  # a team that is not in the league
        state = Path(tmp_path or tempfile.mkdtemp())
        now = dt.datetime(2026, 10, 11, 12, 0, tzinfo=dt.timezone.utc)
        pages = {"search": search, "11": story(good[:2]), "12": story(good)}                       # the newest article cannot be read in full
        def fake(url, *a, **k):
            key = "search" if "search" in url else url.rsplit("/", 1)[1]
            return json.dumps(pages[key]).encode()
        _web.get_bytes = fake
        got = power.update(state, now, teams, lambda m: None)
        assert got["read"] and got["newest"] == "XYZ Power Rankings: Week 2"
        kept = power.stored(state, teams)
        assert kept["ranks"] == {"2": 1, "3": 2, "1": 3} and kept["published"].startswith("2026-09-29")
        assert power.stored(state, {"1", "2"}) == {}                                              # the league has changed: not used
        def down(url, *a, **k):
            raise OSError("down")
        _web.get_bytes = down
        assert power.update(state, now, teams, lambda m: None)["failed"] and power.stored(state, teams)["ranks"]["2"] == 1
    finally:
        config.POWER_ABBR, config.POWER, _web.get_bytes = old_abbr, old_power, real

# ----------------------------------------- the GOAT ranking stops with the regular season --
def test_the_goat_ranking_is_frozen_once_the_postseason_starts(tmp_path=None):
    state = Path(tmp_path or tempfile.mkdtemp())
    day = lambda d: dt.datetime(2026, 12, d, tzinfo=dt.timezone.utc)
    first = {"a": 1, "b": 2}
    assert run.frozen_credit(state, 2026, False, first, day(1)) == (first, None)            # regular season: follows the poll
    assert not (state / "goat_frozen.json").exists()
    assert run.frozen_credit(state, 2026, True, first, day(8)) == (first, "2026-12-08")      # the postseason starts: kept as it stands
    later = {"b": 1, "a": 2}
    assert run.frozen_credit(state, 2026, True, later, day(20)) == (first, "2026-12-08")     # a later poll changes nothing
    assert run.frozen_credit(state, 2027, False, later, day(21)) == (later, None)             # next season: follows the poll again
    assert run.frozen_credit(state, 2027, True, later, day(22)) == (later, "2026-12-22")      # and is frozen afresh

# -------------------------------------------- last season stays on show until the new one begins --
def test_last_season_is_shown_until_the_new_one_begins(tmp_path=None):
    state = Path(tmp_path or tempfile.mkdtemp())
    def game(gid, date, st, kind=2):
        return {"id": gid, "date": date, "start": None, "state": st, "note": "", "round": "", "day": date.replace("-", ""), "kind": kind,
                "away": {"id": "1", "name": "A", "abbr": "A", "score": 70 if st == "final" else None},
                "home": {"id": "2", "name": "B", "abbr": "B", "score": 80 if st == "final" else None}}
    feeds = {"20260110": [game(1, "2026-01-10", "final")], "20260111": [game(2, "2026-01-11", "final")],
             "20261101": [game(11, "2026-11-01", "upcoming")], "20261102": [game(12, "2026-11-02", "upcoming")]}
    seasons = {"now": (2027, "2026-11-01", "2026-11-02"), "20260115": (2026, "2026-01-10", "2026-01-11")}
    down = set()
    def get_json(url, *a, **k):
        key = url.split("dates=")[1][:8] if "dates=" in url else "now"
        if key in down:
            raise web.FetchError("down")
        return {"season_key": key}
    def get_many(urls, *a, **k):
        for u in urls:
            day = u.split("dates=")[1][:8]
            yield (u, None, web.FetchError("down")) if day in down else (u, {"events": feeds.get(day, [])}, None)
    real = (web.get_json, web.get_many, espn.parse_season, espn.parse_event)
    web.get_json, web.get_many = get_json, get_many
    espn.parse_season, espn.parse_event = (lambda doc: seasons[doc["season_key"]]), (lambda e, day: e)
    at = lambda m, d: dt.datetime(2026, m, d, 12, tzinfo=dt.timezone.utc)
    try:
        down.add("20260115")                                   # last season cannot be read: the coming season is shown, as before
        got = run.update_schedule(state, at(10, 11))
        assert (got["season"], got["showing_last_season"]) == (2027, False) and not (state / run.NEXT_SEASON).exists()
        down.clear()
        got = run.update_schedule(state, at(10, 12))           # three weeks before the first game: last season
        assert (got["season"], got["games"], got["showing_last_season"]) == (2026, 2, True)
        assert json.loads((state / "scoreboard.json").read_text())["season"] == 2026
        assert json.loads((state / run.NEXT_SEASON).read_text())["season"] == 2027
        run.write_json(state / "fbs.json", {"1": {"name": "A", "conf": "X", "rec": {}}, "2": {"name": "B", "conf": "X", "rec": {}}})
        sel = run.selection(state)
        assert sel["last_season"] and sel["next_first"] == "2026-11-01" and sel["season"] == 2026
        assert [(g["id"], g["state"], g.get("next")) for g in sel["all_games"]] == [(1, "final", None), (2, "final", None), (11, "upcoming", 1), (12, "upcoming", 1)]
        again = run.update_schedule(state, at(10, 20))          # nothing of last season is read twice
        assert again["showing_last_season"] and again["days"] == 0
        got = run.update_schedule(state, at(11, 1))             # the day of the first game: the new season takes over
        assert (got["season"], got["showing_last_season"]) == (2027, False) and not (state / run.NEXT_SEASON).exists()
        assert not run.selection(state)["last_season"] and len(run.selection(state)["all_games"]) == 2
    finally:
        web.get_json, web.get_many, espn.parse_season, espn.parse_event = real

