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
    url = next(u for u in index if "/athletes/" in u)
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


def test_the_wording_file_is_complete():
    words = run.read_words()
    assert words["nav.games"] == "Games" and "{poll}" in words["games.lede"]
