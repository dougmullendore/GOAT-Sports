"""Checks that the feeds are read correctly and that the site builds, using saved copies of
ESPN's feeds (tests/fixtures; index.json says which file is which): September 26, 2026, a day
late in the regular season, with two box scores, and October 10 and 11, in the playoffs.

Run with:  python tests/run_local.py
"""
import datetime as dt
import json
import os
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
os.environ["FETCH_CACHE"] = str(FIXTURES)

from pipeline import cards, config, espn, odds, players, run, teams, web  # noqa: E402

METS, NATIONALS, GAME = "21", "20", 401817091            # Mets 7, Nationals 1
DAY = "20260926"


def games_of(day):
    doc = web.get_json(config.DAY.format(day=day))
    return {g["id"]: g for g in (espn.parse_event(e, day) for e in doc["events"]) if g}


def box():
    return espn.parse_summary(web.get_json(config.SUMMARY.format(game=GAME)))


def stored(state: Path):
    """Stored data as it stood on the evening of October 10, built from the saved feeds."""
    now = dt.datetime(2026, 10, 11, 2, 30, tzinfo=dt.timezone.utc)
    days = {d: {"read": "2026-10-10", "games": list(games_of(d).values())} for d in (DAY, "20261010", "20261011")}
    run.write_json(state / "scoreboard.json", {"season": 2026, "first": "2026-02-19", "last": "2026-11-12", "days": days})
    run.write_json(state / "fbs.json", espn.parse_standings(web.get_json(config.STANDINGS.format(season=2026))))
    run.update_boxes(state, now)
    run.update_rosters(state, now)
    run.update_careers(state, now)
    return now


def test_a_day_is_read():
    games = games_of(DAY)
    g = games[GAME]
    assert g["state"] == "final" and g["date"] == "2026-09-26" and g["kind"] == 2
    assert (g["away"]["id"], g["away"]["name"], g["away"]["score"], g["away"]["lines"]) == (METS, "Mets", 7, [0, 0, 0, 0, 0, 0, 4, 1, 2])
    assert (g["home"]["id"], g["home"]["name"], g["home"]["score"]) == (NATIONALS, "Nationals", 1)
    assert g["extra"] == [[10, 1], [3, 1]]                       # hits and errors, away then home
    assert g["wp"] == ["4717899", "D. Nunez"] and g["lp"][1] == "J. Irvin"
    assert len(games) == 13 and all(x["kind"] == 2 for x in games.values())


def test_the_playoffs_and_a_game_still_to_come():
    live = next(iter(games_of("20261010").values()))
    assert live["kind"] == 3 and live["round"] == "ALDS - Game 5" and live["series"] == "Series tied 2-2"
    assert live["state"] == "live" and live["detail"] and live["extra"][1] == [5, 0]
    ahead = next(iter(games_of("20261011").values()))
    assert ahead["state"] == "upcoming" and ahead["away"]["score"] is None and "extra" not in ahead
    assert ahead["away"]["sp"][1] and ahead["home"]["sp"][1] and ahead["tv"]         # the probable starters


def test_the_season():
    season, first, last = espn.parse_season(web.get_json(config.SCOREBOARD))
    assert (season, first, last) == (2026, "2026-02-19", "2026-11-12")
    assert len(run.each_day(first, last)) == 267


def test_the_standings():
    table = espn.parse_standings(web.get_json(config.STANDINGS.format(season=2026)))
    assert len(table) == 30
    ny = table["10"]
    assert (ny["name"], ny["place"], ny["conf"], ny["group"], ny["w"], ny["l"]) == ("Yankees", "New York", "AL East", "AL", 93, 68)
    assert ny["rec"]["home"] == "46-34" and ny["rec"]["div"] == "29-22" and ny["rec"]["conf"] == "66-47" and ny["gb"] == "4.5"
    assert (ny["pf"], ny["pa"], ny["seed"]) == (739, 601, 4) and ny["logo"].startswith("https://")
    assert {t["group"] for t in table.values()} == {"AL", "NL"} and len({t["conf"] for t in table.values()}) == 6


def test_innings():
    assert [espn.outs(x) for x in ("6.2", "9.0", "0.1", "", None, "7")] == [20, 27, 1, 0, 0, 21]
    assert [players.innings(x) for x in (20, 27, 1, 0)] == ["6.2", "9.0", "0.1", "0.0"]


def test_a_box_score_is_read():
    b = box()
    assert b["status"] == "F" and b["home_id"] == NATIONALS and b["away_id"] == METS
    t = dict(zip(espn.TEAM, b["team"]["away"]))
    assert (t["ab"], t["r"], t["h"], t["d"], t["hr"], t["bb"], t["k"], t["hbp"], t["tb"], t["lob"]) == (36, 7, 10, 1, 3, 4, 8, 1, 20, 15)
    assert (t["outs"], t["ph"], t["er"], t["pk"], t["e"]) == (27, 3, 1, 14, 1)
    at = {c: 5 + i for i, c in enumerate(espn.COLS)}
    rows = {r[1]: r for r in b["players"]["away"]}
    soto = rows["Juan Soto"]
    assert soto[3] == "LF" and soto[4] == 1 and (soto[at["bo"]], soto[at["ab"]], soto[at["h"]], soto[at["k"]]) == (2, 4, 2, 1)
    assert (soto[at["avg"]], soto[at["obp"]], soto[at["slg"]]) == (278, 397, 522) and soto[at["pn"]] == 0
    sub = rows["Nick Morabito"]
    assert sub[4] == 0 and sub[at["bo"]] == 2                    # came in for Soto, in his place in the order
    tong, nunez = rows["Jonah Tong"], rows["Dedniel Nunez"]
    assert tong[3] == "SP" and tong[4] == 1 and (tong[at["pn"]], tong[at["outs"]], tong[at["er"]], tong[at["pk"]], tong[at["pc"]], tong[at["era"]]) == (1, 15, 1, 9, 87, 382)
    assert nunez[2] == "W" and nunez[3] == "RP" and nunez[at["pn"]] == 2 and rows["Nate Lavender"][2] == "H"
    batters = [r for r in b["players"]["away"] if r[at["bo"]]]
    assert sum(r[at["ab"]] for r in batters) == 36 and sum(r[at["h"]] for r in batters) == 10 and sum(r[at["hr"]] for r in batters) == 3
    assert sum(r[at["outs"]] for r in b["players"]["away"]) == 27
    assert sum(r[4] for r in batters) == 9


def test_a_roster_and_a_career_are_read():
    roster = espn.parse_roster(web.get_json(config.ROSTER.format(team=METS)))
    assert len(roster) >= 26
    name, number, pos, height, weight, years, home, photo, hands = roster["36969"]
    assert name == "Juan Soto" and pos in ("LF", "RF") and height > 60 and "season" in years and hands == "L/L"
    assert {players.group(p[2]) for p in roster.values()} <= set(players.POSITIONS)
    career = espn.parse_career(web.get_json(config.CAREER.format(player="36969")))
    assert [c[0] for c in career][:1] == ["Career Batting"] and all(c[0].startswith(("Career", "Postseason")) for c in career)
    title, heads, seasons, total = career[0]
    assert heads[:4] == ["GP", "AB", "R", "H"] and seasons[0][:2] == ["2018", "WSH"] and len(total) == len(heads)


def rated(state):
    sel = run.selection(state)
    logs = {}
    out = players.compute(sel["teams"], sel["all_games"], run.read_json(state / "box.json", {}), run.read_json(state / "rosters.json", {}), logs)
    return out, logs


def test_impact_is_runs_above_average():
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp)
        stored(state)
        out, logs = rated(state)
    keys = out["metrics"]
    by = {p["name"]: p for p in out["players"]}
    soto = by["Juan Soto"]
    v = dict(zip(keys, soto["v"]))
    assert soto["group"] == "OF" and soto["team_id"] == METS and soto["tot"]["ab"] == 4 and soto["bio"]["bt"] == "Bats/throws L/L"
    assert (v["avg"], v["obp"], v["slg"], v["ops"]) == (0.278, 0.397, 0.522, 0.919)          # ESPN's season figures
    assert v["pit"] is None and abs(v["impact_t"] - (v["hit"] + v["power"] + v["walk"] + v["out"])) < 0.03
    tong = by["Jonah Tong"]
    v = dict(zip(keys, tong["v"]))
    assert tong["group"] == "SP" and v["hit"] is None and abs(v["impact_t"] - v["pit"]) < 0.01 and v["era"] == 3.82 and v["ip_g"] == 5.0
    assert tong["tot"]["outs"] == 15 and tong["tot"]["gs_p"] == 1 and by["Dedniel Nunez"]["tot"]["w"] == 1 and by["Nate Lavender"]["tot"]["hld"] == 1
    # the playoffs are not counted: only the two regular-season box scores
    assert sum(t["games"] for t in out["teams"]) == 4
    # regular hitters at a position, and regular pitchers in a role, add up to nothing
    for grp in players.POSITIONS:
        mine = [p for p in out["players"] if p["regular"] and p["group"] == grp]
        if len(mine) >= players.MIN_POOL:
            assert abs(sum(p["impact"] for p in mine)) < 0.6, grp
    ranked = [p for p in out["players"] if p["regular"]]
    assert [p["rank"] for p in ranked] == list(range(1, len(ranked) + 1))
    assert all(a["impact"] >= b["impact"] for a, b in zip(ranked, ranked[1:]))
    line = logs[tong["id"]][0]
    assert len(line) == 6 + len(players.LOG) + 1 and line[5] == "W 7-1"
    extras = cards.build(out, logs, {}, set())[METS]
    assert extras[tong["id"]]["highs"][0][:2] == ["Strikeouts", 9] and ["Innings", 5.0] in [h[:2] for h in extras[tong["id"]]["highs"]]
    assert extras[soto["id"]]["marks"] == [["multi-hit games", 1]]


def test_team_stats():
    g = games_of(DAY)[GAME]
    ranked = [{"id": METS, "name": "Mets", "rank": 1}, {"id": NATIONALS, "name": "Nationals", "rank": 2}]
    out = teams.compute(ranked, [g], {str(GAME): box()}, {METS: 0.5, NATIONALS: -0.5})
    ny = next(t for t in out["teams"] if t["id"] == METS)
    dc = next(t for t in out["teams"] if t["id"] == NATIONALS)
    assert (ny["w"], ny["l"], ny["rpg"], ny["rapg"], ny["diff"]) == (1, 0, 7.0, 1.0, 6)
    assert ny["avg"] == round(10 / 36, 3) and ny["slg"] == round(20 / 36, 3) and ny["obp"] == round(15 / 41, 3)
    assert ny["era"] == 1.0 and ny["whip"] == round(4 / 9, 2) and ny["k9"] == 14.0 and ny["hr_g"] == 3.0
    assert dc["opp_avg"] == ny["avg"] and ny["power"] == 1 and dc["power"] == 2


def test_odds_are_never_far_from_even():
    assert abs(odds.chance(0, 0, neutral=True) - 0.5) < 1e-9 and 0.5 < odds.chance(0, 0) < 0.56
    seed = odds.seed()
    assert seed["season"] == 2025 and len(seed["ratings"]) == 30
    best, worst = max(seed["ratings"].values()), min(seed["ratings"].values())
    assert 0.6 < odds.chance(best, worst) < 0.8


def test_the_words_file():
    words = run.read_words()
    for key in ("games.title", "rankings.title", "rankings.note_conf", "players.note"):
        assert words[key], key


def test_the_site_builds():
    with tempfile.TemporaryDirectory() as tmp:
        state, out = Path(tmp) / "state", Path(tmp) / "site"
        state.mkdir()
        now = stored(state)
        info = run.build_site(state, out, now)
        data = json.loads((out / "data.json").read_text())
        assert info["teams"] == 30 and info["game_pages"] >= 2 and info["players"] > 40
        assert data["site"] == "GOAT Baseball" and data["league"] == "" and data["pro"] and data["numbered"] and data["periods"] == 9
        assert data["leagues"] == [["", "MLB"]] and data["season_label"] == "2026" and "{day}" in data["live_feed"]
        assert [t["rank"] for t in data["poll"]["teams"]] == list(range(1, 31)) and len(data["standings"]) == 30
        assert data["standings"][0]["w"] >= data["standings"][-1]["w"] and data["logos"]["10"].startswith("https://")
        g = next(g for g in data["games"] if g["id"] == GAME)
        assert g["box"] and 0.3 < g["p0"] < 0.7 and g["extra"] == [[10, 1], [3, 1]]
        ahead = next(g for g in data["games"] if g["state"] == "upcoming")
        assert 0.3 < ahead["p"] < 0.7 and ahead["home"]["sp"]
        page = json.loads((out / "game" / f"{GAME}.json").read_text())
        assert len(page["team"]["home"]) == len(espn.TEAM) and len(page["players"]["away"][0]) == 5 + len(espn.COLS) + 1
        for name in ("players_fbs.json", "teams_fbs.json", "index.html", "app.js", "styles.css", "icon-192.png", "manifest.json"):
            assert (out / name).exists(), name
        assert not (out / "players.json").exists()                  # no poll, so one list of players
        everyone = json.loads((out / "players_fbs.json").read_text())
        assert everyone["metrics"][0] == "impact_t" and any(p["team_id"] == METS for p in everyone["players"])
        soto = json.loads((out / "cards" / f"{METS}.json").read_text())["36969"]
        assert soto["games"] and soto["career"] and soto["highs"]
        html = (out / "index.html").read_text()
        assert "app.js?v=" in html and "#0a1224" in html and "GOAT Baseball" in html


def test_a_game_day_run_looks_only_while_a_game_is_on():
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp)
        stored(state)
        on = dt.datetime(2026, 10, 11, 2, 30, tzinfo=dt.timezone.utc)               # the ALDS game is in the eighth
        assert run.live_now(state, on) == ["20261010"]
        assert run.live_now(state, on - dt.timedelta(hours=9)) == []
        first_pitch = next(iter(games_of("20261011").values()))["start"]
        soon = dt.datetime.fromtimestamp(first_pitch - 600, dt.timezone.utc)
        assert "20261011" in run.live_now(state, soon)

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

