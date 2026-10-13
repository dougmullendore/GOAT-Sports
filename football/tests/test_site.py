"""Checks that the feeds are read correctly and that the site builds, using saved copies of
ESPN's feeds from October 10, 2026 (tests/fixtures; index.json says which file is which).

Run with:  python tests/run_local.py
"""
import datetime as dt
import json
import os
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
os.environ["FETCH_CACHE"] = str(FIXTURES)

from pipeline import cards, config, espn, goat, odds, players, run, teams, web  # noqa: E402

TEXAS, OKLAHOMA, GAME = "251", "201", 401856717          # Oklahoma 27, Texas 24 at the Cotton Bowl
NFL_GAME = 401872980                                     # Buccaneers 24, Cowboys 16
NOW = "2026-10-11T00:05:00+00:00"


def week6():
    doc = web.get_json(config.WEEK.format(season=2026, kind=2, week=6))
    return [g for g in (espn.parse_event(e, 2, 6) for e in doc["events"]) if g]


def test_the_calendar_and_a_week_are_read():
    season, weeks = espn.parse_calendar(web.get_json(config.SCOREBOARD))
    assert season == 2026
    assert weeks[0][:3] == [2, 1, "Week 1"] and [3, 1] in [w[:2] for w in weeks]
    games = {g["id"]: g for g in week6()}
    g = games[GAME]
    assert g["state"] == "final" and g["date"] == "2026-10-10" and g["week"] == [2, 6]
    assert (g["away"]["id"], g["away"]["name"], g["away"]["score"]) == (TEXAS, "Texas", 24)
    assert (g["home"]["id"], g["home"]["score"], g["home"]["lines"]) == (OKLAHOMA, 27, [0, 7, 3, 17])
    assert g.get("neutral") == 1 and g.get("conf") == 1
    states = {g["state"] for g in games.values()}
    assert {"final", "live", "upcoming"} <= states, states
    live = next(g for g in games.values() if g["state"] == "live")
    assert live["detail"] and live["away"]["score"] is not None
    ahead = next(g for g in games.values() if g["state"] == "upcoming")
    assert ahead["away"]["score"] is None and "lines" not in ahead["home"]


def test_a_game_without_a_kickoff_time_keeps_its_day():
    e = {"id": "1", "date": "2026-11-07T05:00Z", "status": {"type": {"name": "STATUS_SCHEDULED", "state": "pre"}},
         "competitions": [{"timeValid": False, "competitors": [
             {"homeAway": "home", "team": {"id": "251", "location": "Texas"}}, {"homeAway": "away", "team": {"id": "201", "location": "Oklahoma"}}]}]}
    g = espn.parse_event(e, 2, 10)
    assert g["date"] == "2026-11-07" and g["start"] is None
    e["competitions"][0]["timeValid"] = True
    e["date"] = "2026-11-08T04:00Z"                  # 9pm Saturday on the west coast
    assert espn.parse_event(e, 2, 10)["date"] == "2026-11-07"
    e["competitions"][0]["competitors"][0]["team"] = {"id": "-1", "location": "TBD"}
    assert espn.parse_event(e, 3, 1) is None         # a bowl whose teams are not chosen yet


def test_the_rankings_are_read():
    polls = espn.parse_rankings(web.get_json(config.RANKINGS))
    ap = polls["ap"]
    assert ap["date"] == "2026-10-04" and len(ap["rows"]) == 25
    assert ap["rows"][0] == {"rank": 1, "id": TEXAS, "name": "Texas", "prev": 1, "points": 1737, "votes": 61, "record": "4-0"}
    assert ap["rows"][-1]["prev"] is None            # new to the poll this week
    assert "usa" in polls and "fcs" not in polls


def test_the_conferences_are_read():
    fbs = espn.parse_standings(web.get_json(config.STANDINGS.format(season=2026)))
    assert len(fbs) == 138
    assert fbs[TEXAS]["conf"] == "SEC" and fbs[TEXAS]["rec"]["all"] == "4-1"
    assert {t["conf"] for t in fbs.values()} >= {"SEC", "Big Ten", "Sun Belt", "ACC", "Big 12"}
    assert sum(1 for t in fbs.values() if t["conf"] == "Sun Belt") == 14          # its two divisions fold into the conference


def test_a_box_score_is_read():
    box = espn.parse_summary(web.get_json(config.SUMMARY.format(game=GAME)))
    assert box["status"] == "F" and box["away_id"] == TEXAS and box["home_id"] == OKLAHOMA
    away = dict(zip(espn.TEAM, box["team"]["away"]))
    assert (away["yds"], away["pyds"], away["ryds"], away["cmp"], away["att"], away["car"]) == (382, 260, 122, 19, 31, 32)
    assert (away["c3"], away["a3"], away["pen"], away["penyds"], away["to"], away["top"]) == (3, 14, 8, 61, 2, 29 * 60 + 29)
    assert away["drives"] >= 10 and away["scores"] == 5 and away["tds"] == 4
    passing = box["players"]["away"]["passing"]
    assert passing == [["4870906", "Arch Manning", "16", 19, 31, 260, 3, 2]]
    half = [r for r in box["players"]["home"]["defensive"] if r[1] == "Owen Heinecke"][0]
    assert half[3 + espn.CATS["defensive"].index("tfl")] == 2.5
    kick = box["players"]["away"]["kicking"][0]
    assert kick[3:5] == [1, 2] and kick[6:8] == [3, 3]            # one of two field goals, three of three extra points
    assert all(r[0].isdigit() for part in box["players"]["away"].values() for r in part)      # no "Team" rows
    assert len(box["scoring"]) == 9 and box["scoring"][-1][5:] == [24, 27] and box["scoring"][0][2] == "away"


def test_a_roster_and_a_career_are_read():
    roster = espn.parse_roster(web.get_json(config.ROSTER.format(team=TEXAS)))
    assert roster["4870906"][:3] == ["Arch Manning", "16", "QB"] and roster["4870906"][3] == 76 and roster["4870906"][7] == 1
    index = json.loads((FIXTURES / "index.json").read_text())
    url = next(u for u in index if "/athletes/" in u and "college-football" in u)
    career = espn.parse_career(web.get_json(url))
    assert career and all(len(row) == 2 + len(part[1]) for part in career for row in part[2])
    assert all(isinstance(part[2][0][0], int) for part in career)


def test_the_odds_follow_results():
    assert abs(odds.chance(5, 5, True) - 0.5) < 1e-9
    assert odds.chance(5, 5) > 0.5 and odds.chance(20, 0) > 0.85 > odds.chance(0, 0)
    games = [{"id": 1, "date": "2026-09-05", "start": 1, "state": "final", "home": {"id": "a", "score": 35}, "away": {"id": "b", "score": 7}},
             {"id": 2, "date": "2026-09-12", "start": 2, "state": "upcoming", "home": {"id": "b", "score": None}, "away": {"id": "a", "score": None}}]
    rating, pregame = odds.rate(games, {"a": 0.0, "b": 0.0}, {"a", "b"})
    assert rating["a"] > 0 > rating["b"] and abs(rating["a"] + rating["b"]) < 1e-9
    assert pregame == {1: odds.chance(0, 0)}
    # a school from the division below starts well under an FBS team, and is not pulled up toward FBS over the summer
    rating, _ = odds.rate(games, {"a": 10.0, "c": -30.0, "d": -40.0}, {"a"})
    assert rating["b"] < -20


def test_head_to_head_lifts_a_team_over_the_one_it_beat():
    def final(i, home, hs, away, vs):
        return {"id": i, "date": f"2026-09-{i:02d}", "start": i, "state": "final", "home": {"id": home, "score": hs}, "away": {"id": away, "score": vs}}
    games = [final(1, "a", 20, "b", 17), final(2, "b", 30, "c", 0), final(3, "a", 10, "d", 7), final(4, "c", 3, "d", 21)]
    out = goat.rank(games, {"a": 1.0, "b": 1.2, "c": -1.0, "d": 0.0}, {"a", "b", "c", "d"}, {"b": 1, "a": 2})
    assert out["order"].index("a") < out["order"].index("b")
    assert goat.contradictions(out["order"], games, {"a", "b"}) == 0 and goat.contradictions(["b", "a"], games, {"a", "b"}) == 1


def built(tmp):
    state, out = Path(tmp) / "state", Path(tmp) / "out"
    os.environ["NOW"] = NOW
    os.environ.pop("RUN_MODE", None)
    code = run.main(str(state), str(out))
    return code, state, out


def test_the_site_is_built():
    with tempfile.TemporaryDirectory() as tmp:
        code, state, out = built(tmp)
        status = json.loads((state / "status.json").read_text())
        assert code == 0 and status["ok"], status
        data = json.loads((out / "data.json").read_text())
        assert data["season"] == 2026 and data["poll"]["date"] == "2026-10-04" and data["poll"]["through"] == "2026-10-03"
        assert [t["id"] for t in data["poll"]["teams"]][:1] == [TEXAS] and len(data["poll"]["teams"]) == 25
        assert len(data["fbs"]) == 138 and len(data["goat"]["top"]) == 138
        assert set(data["nr"].values()) == set(range(26, 139))            # every unranked FBS team has its own number
        g = next(g for g in data["games"] if g["id"] == GAME)
        assert g["away"]["rank"] == 1 and g["home"]["rank"] is None and g["box"] == 1 and 0.5 < 1 - g["p0"] < 1
        assert any("p" in x and "tv" in x for x in data["games"] if x["state"] == "upcoming")
        assert "usa" in data["polls"] and data["polls"]["usa"]["label"] == "Coaches Poll"
        page = (out / "index.html").read_text()
        assert "app.js?v=" in page and "styles.css?v=" in page
        game = json.loads((out / "game" / f"{GAME}.json").read_text())
        assert game["status"] == "F" and game["players"]["away"]["passing"][0][-1] == 1      # Manning has a card
        roster = json.loads((out / "players_fbs.json").read_text())
        manning = next(p for p in roster["players"] if p["id"] == "4870906")
        assert manning["pos"] == "QB" and manning["team_id"] == TEXAS and manning["tot"]["pyds"] == 260 and manning["ph"] == 1
        assert manning["bio"]["ht"] == "6-4" and "tkl" not in manning["tot"]
        ranked = json.loads((out / "players.json").read_text())
        assert {p["team_id"] for p in ranked["players"]} <= {t["id"] for t in data["poll"]["teams"]}
        card = json.loads((out / "cards" / f"{TEXAS}.json").read_text())["4870906"]
        assert card["games"][0][:6] == [GAME, "2026-10-10", OKLAHOMA, "Oklahoma", 0, "L 24-27"]
        assert card["highs"][0][:2] == ["Passing yards", 260]
        table = json.loads((out / "teams_fbs.json").read_text())
        texas = next(t for t in table["teams"] if t["id"] == TEXAS)
        assert texas["conf"] == "SEC" and texas["games"] == 1 and texas["ypp"] == round(382 / 63, 2) and texas["to_margin"] == -2.0
        # a second run reads nothing it already has, except the last few days' box scores
        assert json.loads((state / "ratings.json").read_text())["2026"]
        # the NFL's copy, in its own folder inside the college pages
        nfl = json.loads((out / "nfl" / "data.json").read_text())
        assert nfl["league"] == "nfl" and nfl["pro"] and len(nfl["fbs"]) == 32 and len(nfl["standings"]) == 32
        assert [t["rank"] for t in nfl["poll"]["teams"]] == list(range(1, 33)) and nfl["nr"] == {}
        assert nfl["standings"][0]["w"] >= nfl["standings"][-1]["w"] and len(nfl["logos"]) == 32
        g = next(g for g in nfl["games"] if g["id"] == NFL_GAME)
        assert (g["away"]["name"], g["away"]["score"], g["home"]["name"], g["home"]["score"]) == ("Buccaneers", 24, "Cowboys", 16)
        assert g["box"] == 1 and g["away"]["rank"] and g["home"]["rank"]
        assert all("beat" not in t for t in nfl["goat"]["top"]) and len(nfl["goat"]["top"]) == 32
        assert (out / "nfl" / "players_fbs.json").exists() and not (out / "nfl" / "players.json").exists()
        assert 'content="#0a1224"' in (out / "nfl" / "index.html").read_text() and 'content="#0a1224"' in page      # one colour for the whole sport
        assert (out / "nfl" / "icon.svg").read_text() == (out / "icon.svg").read_text()
        assert (state / "nfl" / "box.json").exists() and not (state / "nfl" / "polls.json").exists()
        assert {"NFL schedule", "NFL standings", "NFL site"} <= set(status["stages"]) and "NFL rankings" not in status["stages"]
        assert config.LEAGUE == "college"                 # the settings are put back when the run ends


def test_a_game_night_run_stops_when_no_game_is_on():
    with tempfile.TemporaryDirectory() as tmp:
        code, state, out = built(tmp)
        assert code == 0
        import shutil
        shutil.rmtree(out)
        os.environ["RUN_MODE"] = "live"
        try:
            os.environ["NOW"] = "2026-10-12T15:00:00+00:00"            # Monday morning: nothing on
            assert run.main(str(state), str(out)) == 0 and not out.exists()
            os.environ["NOW"] = NOW                                    # Saturday evening: games under way
            assert run.live_now(state, dt.datetime.fromisoformat(NOW)) == ["2-6"]
            run.main(str(state), str(out))         # the saved files hold no box score of a game under way, so that stage fails
            stages = json.loads((state / "status.json").read_text())["stages"]
            assert stages["scores now"]["ok"] and stages["site"]["ok"] and (out / "data.json").exists()
        finally:
            os.environ.pop("RUN_MODE", None)


def test_players_are_rated_against_their_position():
    games = week6()
    boxes = {str(GAME): {"date": "2026-10-10", **espn.parse_summary(web.get_json(config.SUMMARY.format(game=GAME)))}}
    rosters = {TEXAS: {"players": espn.parse_roster(web.get_json(config.ROSTER.format(team=TEXAS)))}}
    teams_ = [{"id": TEXAS, "name": "Texas", "rank": 1}, {"id": OKLAHOMA, "name": "Oklahoma", "rank": None}]
    logs = {}
    rated = players.compute(teams_, games, boxes, rosters, logs)
    by = {p["name"]: p for p in rated["players"]}
    qb = by["Arch Manning"]
    assert qb["pos"] == "QB" and qb["regular"] and qb["gp"] == 1
    assert by["John Mateer"]["pos"] == "QB"                          # no roster given for Oklahoma: worked out from his numbers
    assert by["Owen Heinecke"]["pos"] in ("DL", "LB")
    v = dict(zip(rated["metrics"], qb["v"]))
    assert v["cmp_pct"] == round(100 * 19 / 31, 2) and v["ypa"] == round(260 / 31, 2)
    # the two quarterbacks are measured against each other: the one with more adjusted yards a throw is above average
    other = dict(zip(rated["metrics"], by["John Mateer"]["v"]))
    assert (v["aya"] > other["aya"]) == (v["pass"] > other["pass"])
    line = logs["4870906"][0]
    assert line[:6] == [GAME, "2026-10-10", OKLAHOMA, "Oklahoma", 0, "L 24-27"] and line[6:11] == [19, 31, 260, 3, 2]
    extra = cards.one(logs["4870906"], qb, [], {OKLAHOMA})
    assert extra["ranked"]["gp"] == 1 and extra["ranked"]["w"] == 0
    stats = teams.compute(teams_, games, boxes, {TEXAS: 5.0, OKLAHOMA: 2.0})
    assert [t["w"] for t in stats["teams"]] == [0, 1] and stats["through"] == "2026-10-10"


def test_a_career_is_read_again_after_the_next_game():
    from pipeline import careers
    seen = []
    real = web.get_many
    web.get_many = lambda urls, tries=None: [(u, {"categories": []}, seen.append(u)) for u in urls]
    try:
        stored, kickoff = {}, 1_000_000
        quiet = lambda msg: None
        careers.update(stored, [("1", kickoff)], kickoff + 2 * 3600, quiet)          # read during the game
        careers.update(stored, [("1", kickoff)], kickoff + 9 * 3600, quiet)          # so read again once it is over
        careers.update(stored, [("1", kickoff)], kickoff + 30 * 3600, quiet)         # and then left alone
        assert len(seen) == 2 and stored["players"]["1"]["t"] == kickoff + 9 * 3600
        careers.update(stored, [("2", kickoff)], kickoff + 40 * 3600, quiet)         # a player no longer wanted is dropped
        assert list(stored["players"]) == ["2"]
    finally:
        web.get_many = real


def test_the_nfl_feeds_are_read():
    config.use("nfl")
    try:
        season, weeks = espn.parse_calendar(web.get_json(config.SCOREBOARD))
        assert season == 2026 and [w[:3] for w in weeks][17:] == [[2, 18, "Week 18"], [3, 1, "Wild Card"], [3, 2, "Divisional Round"],
                                                                 [3, 3, "Conference Championship"], [3, 4, "Super Bowl"]]
        teams_ = espn.parse_standings(web.get_json(config.STANDINGS.format(season=2026)))
        assert len(teams_) == 32 and len({t["conf"] for t in teams_.values()}) == 8 and {t["group"] for t in teams_.values()} == {"AFC", "NFC"}
        bills = teams_["2"]
        assert (bills["name"], bills["place"], bills["conf"], bills["w"], bills["l"], bills["t"], bills["pf"], bills["pa"]) == ("Bills", "Buffalo", "AFC East", 3, 1, 0, 127, 107)
        assert bills["rec"]["home"] == "2-1" and bills["rec"]["away"] == "1-0" and bills["rec"]["div"] == "0-1" and bills["logo"].endswith("buf.png")
        order = run.league_order(teams_)
        assert teams_[order[0]]["l"] == 0 and teams_[order[-1]]["w"] == 0
        box = espn.parse_summary(web.get_json(config.SUMMARY.format(game=NFL_GAME)))
        assert box["status"] == "F" and set(box["players"]["home"]) >= {"passing", "rushing", "receiving", "defensive"}
        hits = sum(r[3 + espn.CATS["defensive"].index("hur")] for side in ("home", "away") for r in box["players"][side]["defensive"])
        assert hits > 0                                   # quarterback hits stand in for college's hurries
        roster = espn.parse_roster(web.get_json(config.ROSTER.format(team=6)))
        someone = next(iter(roster.values()))
        assert len(someone) == 9 and any(p[8] for p in roster.values()) and any(p[5] == "Rookie" for p in roster.values())
        assert {p[5] for p in roster.values()} - {"Rookie", ""} and all("season" in p[5] or p[5] in ("Rookie", "") for p in roster.values())
    finally:
        config.use("college")


def test_a_tie_is_not_a_loss():
    game = {"id": 1, "date": "2026-09-13", "start": 1, "state": "final", "home": {"id": "a", "score": 20}, "away": {"id": "b", "score": 20}}
    table = teams.compute([{"id": "a", "name": "A", "rank": 1}, {"id": "b", "name": "B", "rank": 2}], [game], {}, {"a": 0.0, "b": 0.0})
    assert [(t["w"], t["l"], t["t"]) for t in table["teams"]] == [(0, 0, 1), (0, 0, 1)]
    rating, pregame = odds.rate([game], {"a": 1.0, "b": 0.0}, {"a", "b"})
    assert pregame == {} and rating["a"] > rating["b"]            # a tie moves no rating


def test_the_wording_file_is_complete():
    words = run.read_words()
    assert words["nav.games"] == "Games" and "{poll}" in words["games.lede"]
    assert words["nfl.nav_rankings"] == "Standings"
    # every NFL line stands in for a line the college pages have
    assert all(k.split(".", 1)[1].replace("_", ".", 1) in words for k in words if k.startswith("nfl."))

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

