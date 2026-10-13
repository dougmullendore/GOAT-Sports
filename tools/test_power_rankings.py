"""Checks for tools/power_rankings.py (no network). Run with:  python -m tools.test_power_rankings"""
import sys

from . import power_rankings as pr

TEAMS = [(str(i), f"City{i} Team{i}", f"Team{i}") for i in range(1, 21)]


def page(rows, noise=""):
    return "<html><body>" + noise + "".join(f"<h2>{n}. <a>{name}</a></h2><p>Record: 3-1. Previous ranking: 7</p>" for n, name in rows) + "</body></html>"


def main() -> int:
    top = [(n, f"City{n} Team{n}") for n in range(1, 21)]
    assert pr.order(page(top), TEAMS) == [[n, str(n)] for n in range(1, 21)]                       # written top first
    assert pr.order(page(list(reversed(top))), TEAMS) == [[n, str(n)] for n in range(1, 21)]         # written from the bottom up
    # a scoreboard before the article ("1 Team9 ... 3 Team4") does not get into the ranking
    noise = "<div>1 Team9 24 3 Team4 17</div>"
    assert pr.order(page(top, noise), TEAMS)[:2] == [[1, "1"], [2, "2"]]
    # a site that writes "Rank 6, up 4, Team6"
    ranked = "".join(f"<div>Rank {n}</div><div>up {n % 3} </div><h3>City{n} Team{n}</h3>" for n in range(1, 21))
    assert pr.order(ranked, TEAMS, "rank") == [[n, str(n)] for n in range(1, 21)]
    assert pr.when("2026-10-13 09:00:00 UTC").isoformat() == "2026-10-13T09:00:00+00:00"
    assert pr.when("2026-10-13T00:24:05-04:00").utcoffset().total_seconds() == -4 * 3600
    print("PASS tools.power_rankings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
