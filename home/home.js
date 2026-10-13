/* GOAT Sports, the front page: each league's games on one day, and a door to each sport. No libraries. */
(function () {
  "use strict";
  // ---- games under way go to the top of whatever list they are in, and move there when one starts ----
  function liveFirst(ol) {
    var kids = Array.prototype.slice.call(ol.children), ref = null, i;
    function on(li) { return li.classList && li.classList.contains("game") && li.classList.contains("on"); }
    for (i = 0; i < kids.length; i++) if (!on(kids[i])) { ref = kids[i]; break; }
    if (!ref) return;
    for (i = kids.indexOf(ref) + 1; i < kids.length; i++) if (on(kids[i])) ol.insertBefore(kids[i], ref);
  }
  function listsIn(node, found) {
    if (!node || node.nodeType !== 1) return;
    if (node.matches && node.matches("ol.games")) found.push(node);
    else if (node.matches && node.matches("li.game") && node.parentNode) found.push(node.parentNode);
    Array.prototype.forEach.call(node.querySelectorAll("ol.games"), function (ol) { found.push(ol); });
  }
  if (window.MutationObserver) new MutationObserver(function (list) {
    var lists = [];
    list.forEach(function (m) { Array.prototype.forEach.call(m.addedNodes, function (n) { listsIn(n, lists); }); });
    lists.filter(function (ol, i) { return lists.indexOf(ol) === i; }).forEach(liveFirst);
  }).observe(document.documentElement, { childList: true, subtree: true });

  var $ = function (id) { return document.getElementById(id); };
  var data = null, shown = null;
  // home.json carries the days around today, with their live scores; every other day of every season is in
  // schedule/<year>-<month>.json, read the first time the calendar reaches that month
  var months = {};
  function monthOf(d) { return d.slice(0, 7); }
  function inWindow(d) { return !data.window || !data.months || (d > data.window[0] && d < data.window[1]); }
  function needMonths(days) {
    if (!data.months) return;
    var want = {};
    days.forEach(function (d) { [addDays(d, -1), d, addDays(d, 1)].forEach(function (x) { if (!inWindow(x)) want[monthOf(x)] = 1; }); });
    Object.keys(want).forEach(function (m) {
      if (months[m] || data.months.indexOf(m) < 0) return;
      months[m] = "loading";
      fetch("schedule/" + m + ".json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (doc) { months[m] = doc.leagues || {}; draw(); })
        .catch(function () { months[m] = "failed"; draw(); });
    });
  }
  // whether a day's games are all to hand: in home.json, or in months already read (or that do not exist)
  function known(d) {
    if (inWindow(d)) return true;
    return [addDays(d, -1), d, addDays(d, 1)].every(function (x) { var m = monthOf(x); return inWindow(x) || !data.months || data.months.indexOf(m) < 0 || (months[m] && months[m] !== "loading"); });
  }
  // a league's games on a day
  function gamesOn(lg, d) {
    if (inWindow(d)) return lg.games.filter(function (g) { return dayOf(g) === d; });
    var out = [];
    [addDays(d, -1), d, addDays(d, 1)].forEach(function (x) {
      var m = months[monthOf(x)];
      if (m && typeof m === "object") (m[lg.key] || []).forEach(function (g) { if (dayOf(g) === d && out.indexOf(g) < 0) out.push(g); });
    });
    return out;
  }
  // the next day after d that a league has a game, among the days to hand
  function nextFor(lg, d) {
    var days = lg.games.map(dayOf);
    Object.keys(months).forEach(function (m) { var x = months[m]; if (x && typeof x === "object") (x[lg.key] || []).forEach(function (g) { days.push(dayOf(g)); }); });
    var found = days.filter(function (x) { return x > d; }).sort()[0];
    return found || (lg.next && lg.next > d ? lg.next : null);
  }

  // ---- the reader's own choices, kept in this browser: the leagues left off the page ----
  var HIDE_KEY = "goat-home-hidden", hidden = {};
  try { (JSON.parse(localStorage.getItem(HIDE_KEY) || "[]") || []).forEach(function (k) { hidden[k] = 1; }); } catch (e) {}
  function keepHidden() { try { localStorage.setItem(HIDE_KEY, JSON.stringify(Object.keys(hidden))); } catch (e) {} }
  // a long league shows its first games and a button for the rest; a league opened in full stays open
  var SHORT = 8, opened = {};
  // a score that changes is read out to screen readers
  var sayBox = null;
  function say(words) {
    if (!sayBox) {
      sayBox = document.createElement("p");
      sayBox.className = "sr"; sayBox.setAttribute("role", "status"); sayBox.setAttribute("aria-live", "polite");
      document.body.appendChild(sayBox);
    }
    sayBox.textContent = words;
  }

  // ---- black or white: the page follows the device until the reader inverts it, and remembers that ----
  var THEME_KEY = "goat-theme";
  function lightNow() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t) return t === "light";
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches);
  }
  function setTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
    var b = $("invert");
    if (b) b.setAttribute("aria-pressed", String(t === "light"));
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t === "light" ? "#ffffff" : "#000000");
  }
  try { var kept = localStorage.getItem(THEME_KEY); if (kept === "light" || kept === "dark") document.documentElement.setAttribute("data-theme", kept); } catch (e) {}


  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) {
      if (attrs[k] == null || attrs[k] === false) continue;
      if (k === "text") n.textContent = attrs[k];
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function iso(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function day(s) { var p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2], 12); }
  function addDays(s, n) { var d = day(s); d.setDate(d.getDate() + n); return iso(d); }
  function long(s) { return day(s).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }); }
  var today = iso(new Date());
  // a game belongs to the day it starts on where the reader is, when its start time is known
  function dayOf(g) { return g.start ? iso(new Date(g.start * 1000)) : g.date; }

  var ICON = {
    hockey: '<path d="M6 2.5l9.2 13.2c.7 1 1.6 1.5 2.8 1.5h3.5"/><path d="M18 2.5L8.8 15.7c-.7 1-1.6 1.5-2.8 1.5H2.5"/><ellipse cx="12" cy="21.3" rx="2.7" ry="1.1"/>',
    volleyball: '<circle cx="12" cy="12" r="10"/><path d="M11.1 7.1a16.55 16.55 0 0 1 10.9 4"/><path d="M12 12a12.6 12.6 0 0 1-8.7 5"/><path d="M16.8 13.6a16.55 16.55 0 0 1-9 7.5"/><path d="M20.7 17a12.8 12.8 0 0 0-8.7-5 13.3 13.3 0 0 1 0-10"/><path d="M6.3 3.8a16.55 16.55 0 0 0 1.9 11.5"/>',
    football: '<path d="M3.6 20.4c-1.2-5.600 1.100-11.600 6.200-14.700 3.100-1.900 7.100-2.500 10.600-2.100.400 3.500-.200 7.500-2.100 10.600-3.100 5.100-9.100 7.400-14.700 6.200z"/><path d="M9.200 14.800l5.600-5.600"/><path d="M10.300 11.300l2.400 2.400"/><path d="M12.300 9.300l2.400 2.400"/>',
    basketball: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3v18"/><path d="M5.6 5.6c2.6 1.9 2.6 10.9 0 12.8"/><path d="M18.4 5.6c-2.6 1.9-2.6 10.9 0 12.8"/>',
    baseball: '<g style="fill:var(--c);stroke:var(--c)" stroke-linejoin="round" stroke-linecap="round"><path d="M5.2 19.3l6.3-6.2c2-2 4-2.8 5.4-4.2l3.4-3a1.5 1.5 0 0 0-2.2-2.200l-3 3.400c-1.4 1.4-2.2 3.4-4.2 5.400l-6.2 6.300z" stroke-width=".8" transform="translate(0 -2.2)"/><path d="M5.2 19.3l6.3-6.2c2-2 4-2.8 5.4-4.2l3.4-3a1.5 1.5 0 0 0-2.2-2.200l-3 3.400c-1.4 1.4-2.2 3.4-4.2 5.400l-6.2 6.300z" stroke-width=".8" transform="translate(24 -2.2) scale(-1 1)"/><path d="M3.6 16l2.2 2.200M20.4 16l-2.2 2.2" stroke-width="1.5"/><circle cx="12" cy="20.2" r="2.5" stroke="none"/></g>'
  };
  var LEAGUE_LOGO = { nfl: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png", nba: "https://a.espncdn.com/i/teamlogos/leagues/500/nba.png",
    mlb: "https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png", nhl: "https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png" };
  function sportIcon(sport) {
    var box = el("span", { "class": "mark icon", "aria-hidden": "true" });
    box.innerHTML = '<svg viewBox="0 0 24 24">' + (ICON[sport] || "") + "</svg>";
    return box;
  }
  function leagueMark(lg) {
    var url = LEAGUE_LOGO[lg.key];
    if (!url) return sportIcon(lg.sport);
    var img = el("img", { src: url, alt: "", loading: "lazy", decoding: "async" }), box = el("span", { "class": "mark", "aria-hidden": "true" }, [img]);
    img.addEventListener("error", function () { if (box.parentNode) box.parentNode.replaceChild(sportIcon(lg.sport), box); });
    return box;
  }
  // what each sport's line at the foot of the page says, and the pages behind it
  var DOORS = {
    hockey: ["NHL", "Every game with its betting line, standings, expected goals, line combinations and playoff odds.",
      [["Games", "#/"], ["Standings", "#/standings"], ["Teams", "#/teams"], ["Players", "#/players"], ["Lines", "#/lines"], ["Playoffs", "#/odds"]]],
    volleyball: ["Women's college, LOVB and MLV", "The top 25's games day by day, the AVCA poll and the GOAT ranking, and a card for every Division I player.",
      [["Games", "#/"], ["Rankings", "#/rankings"], ["Teams", "#/teams"], ["Players", "#/players"], ["LOVB", "lovb/"], ["MLV", "mlv/"]]],
    football: ["The NFL and college", "Games week by week with their betting lines, NFL standings, the AP poll, the GOAT rankings, team stats and a card for every player.",
      [["Games", "#/"], ["Standings", "#/rankings"], ["Teams", "#/teams"], ["Players", "#/players"], ["College", "../"]]],
    basketball: ["The NBA and men's college", "Games day by day with their betting lines, NBA standings, the AP poll, the GOAT rankings, team stats and a card for every player.",
      [["Games", "#/"], ["Standings", "#/rankings"], ["Teams", "#/teams"], ["Players", "#/players"], ["College", "../"]]],
    baseball: ["MLB", "Every game with the probable starters and the betting line, standings, team stats and a card for every hitter and pitcher.",
      [["Games", "#/"], ["Standings", "#/rankings"], ["Teams", "#/teams"], ["Players", "#/players"]]]
  };

  function logo(lg, id, name) {
    var url = lg.logos && lg.logos[id] ? lg.logos[id] : lg.logo && id ? lg.logo.replace("{team}", encodeURIComponent(id)) : null;
    if (!url) {
      var a = (lg.abbr || {})[id];
      if (!a) return null;
      return el("span", { "class": "logo badge", style: a[1] ? "--team:" + a[1] : null, "aria-hidden": "true" }, [el("span", { text: a[0] })]);
    }
    var img = el("img", { src: url, alt: "", loading: "lazy", decoding: "async" });
    var box = el("span", { "class": "logo", "aria-hidden": "true" }, [img]);
    img.addEventListener("error", function () { box.style.visibility = "hidden"; });
    return box;
  }
  var ONE = { games: "game", matches: "match" };
  function pct(home) { var n = Math.min(99, Math.max(1, Math.round(home * 100))); return [(100 - n) + "%", n + "%"]; }
  function ordinal(n) { var s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  // A team's number: its place in the poll or in the standings. A college team outside the poll carries
  // its place in the GOAT ranking instead (26 and up), and its tag is outlined rather than filled.
  function rankOf(lg, n) {
    if (!n) return null;
    var goat = !!lg.poll && n > 25;
    return { n: n, goat: goat, words: goat ? n + " in the GOAT ranking" : lg.poll ? "ranked " + n + " in the " + lg.poll : ordinal(n) + " in the standings" };
  }
  // the key under a league's name: what its numbers are, and why a list has no chances of winning
  function keyOf(lg, games) {
    var bits = [], numbered = games.some(function (g) { return g.away[2] || g.home[2]; });
    if (numbered) bits.push(lg.poll ? "Numbers are places in the " + lg.poll + (games.some(function (g) { return (g.away[2] || 0) > 25 || (g.home[2] || 0) > 25; })
      ? "; an outlined number is a place in this site's GOAT ranking, for a team the poll leaves out." : ".") : "Numbers are places in the league standings.");
    var ahead = games.filter(function (g) { return g.state === "upcoming"; });
    if (lg.sport === "volleyball" && ahead.length && !ahead.some(function (g) { return g.p != null; })) bits.push("No chances of winning are worked out for these " + lg.unit + ".");
    if (lg.sport === "volleyball" && games.some(function (g) { return g.p != null && g.state !== "final"; })) bits.push("No sportsbook offers lines on these matches; the percentages are this site's own chance of winning.");
    return bits.join(" ");
  }

  // a drawn arrow, one stroke weight with the rules
  function arrow() {
    var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg"), p = document.createElementNS(ns, "path");
    svg.setAttribute("class", "arrow"); svg.setAttribute("viewBox", "0 0 14 10"); svg.setAttribute("aria-hidden", "true");
    p.setAttribute("d", "M0 5H13M9 1l4 4-4 4"); p.setAttribute("fill", "none"); p.setAttribute("stroke", "currentColor"); p.setAttribute("stroke-width", "1");
    svg.appendChild(p);
    return svg;
  }
  function row(lg, g) {
    var fin = g.state === "final", live = g.state === "live";
    var as = g.away[3], hs = g.home[3], scored = (fin || live) && as != null && hs != null;
    var awayWon = fin && scored && as > hs, homeWon = fin && scored && hs > as;
    var t = g.start ? new Date(g.start * 1000) : null;
    var note = g.state === "other" ? (g.note ? g.note.charAt(0).toUpperCase() + g.note.slice(1) : "Not played") : "";
    var when = fin ? "Final" : live ? "" : note ? note : t && !isNaN(t) ? t.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "Time not set";
    var tv = g.tv || [];
    function team(side, s, lost, won) {
      var r = rankOf(lg, s[2]);
      var kids = [logo(lg, s[0], s[1]), el("span", { "class": "name", text: s[1] }), r ? el("span", { "class": "rk" + (r.goat ? " goat" : ""), text: String(r.n) }) : null];
      if (side === "home") kids.reverse();
      return el("span", { "class": "team " + side + (lost ? " lost" : "") + (won ? " won" : "") }, kids);
    }
    function named(s) { var r = rankOf(lg, s[2]); return s[1] + (r ? " (" + r.words + ")" : ""); }
    var mid = scored
      ? el("span", { "class": "mid" }, [el("span", { "class": homeWon ? "l" : "", text: String(as) }), el("span", { "class": "dash", text: "–" }), el("span", { "class": awayWon ? "l" : "", text: String(hs) })])
      : g.line && g.line[0] && !fin
        ? el("span", { "class": "mid line" }, [el("span", { "class": "ln", text: g.line[0] }), g.line[1] != null ? el("span", { "class": "ou", text: "O/U " + g.line[1] }) : null])
      : g.p != null && !fin && lg.sport === "volleyball"
        ? el("span", { "class": "mid odds" }, [el("span", { "class": g.p > 0.5 ? "l" : "", text: pct(g.p)[0] }), el("span", { "class": "dash", text: "at" }), el("span", { "class": g.p < 0.5 ? "l" : "", text: pct(g.p)[1] })])
        : el("span", { "class": "mid at", text: "at" });
    // what a screen reader hears for the row: everything the row shows, in reading order
    var label = [live ? "Live" : when, named(g.away) + " at " + named(g.home),
      scored ? g.away[1] + " " + as + ", " + g.home[1] + " " + hs + (fin ? ", final" : "")
        : g.line && g.line[0] && !fin ? "Betting line: " + g.line[0] + (g.line[1] != null ? ", over/under " + g.line[1] : "")
        : g.p != null && !fin && lg.sport === "volleyball" ? "This site's chance of winning: " + g.away[1] + " " + pct(g.p)[0] + ", " + g.home[1] + " " + pct(g.p)[1] : "",
      !fin && !note && tv.length ? "Watch on " + tv.join(", ") : ""].filter(Boolean).join(". ");
    var more = fin || note ? "" : tv.length ? tv.join(", ") : "No broadcast listed";
    return el("li", { "class": "game" + (live ? " on" : "") + (flipped[key(lg, g)] ? " flip" : ""), "data-k": key(lg, g) }, [el("a", { "class": "row", href: lg.game + g.id, "aria-label": label }, [
      el("span", { "class": "when" }, live ? [el("span", { "class": "livetag" }, [el("span", { "class": "dot", "aria-hidden": "true" }), "Live"])] : [when]),
      team("away", g.away, homeWon, awayWon), mid, team("home", g.home, awayWon, homeWon),
      el("span", { "class": "more" + (tv.length ? "" : " none"), text: more })])]);
  }

  // ---- the leagues the reader wants: a list to tick, kept in this browser ----
  function picker() {
    var box = $("pick");
    if (!box) return;
    box.innerHTML = "";
    var shownCount = data.leagues.filter(function (lg) { return lg.ready && !hidden[lg.key]; }).length, ready = data.leagues.filter(function (lg) { return lg.ready; });
    var open = el("summary", { text: "Leagues" }, [shownCount < ready.length ? el("span", { "class": "count", text: shownCount + " of " + ready.length }) : null]);
    var list = el("fieldset", {}, [el("legend", { "class": "sr", text: "Leagues to show" })].concat(ready.map(function (lg) {
      return el("label", { "class": "s-" + lg.sport }, [el("input", { type: "checkbox", checked: !hidden[lg.key], onchange: function (ev) {
        if (ev.target.checked) delete hidden[lg.key]; else hidden[lg.key] = 1;
        keepHidden(); draw();
        var c = open.querySelector(".count"), n = ready.filter(function (x) { return !hidden[x.key]; }).length;
        if (c) c.remove();
        if (n < ready.length) open.appendChild(el("span", { "class": "count", text: n + " of " + ready.length }));
      } }), " " + lg.name]);
    })));
    box.appendChild(open);
    box.appendChild(list);
  }

  function draw() {
    var holder = $("today"), nav = $("nav"), jump = $("jump");
    holder.innerHTML = ""; nav.innerHTML = ""; jump.innerHTML = "";
    feed();
    if (!shown) shown = today;
    var all = [];
    for (var i = -7; i <= 7; i++) all.push(addDays(shown, i));
    needMonths(all);
    var label = shown === today ? "Today's games" : shown === addDays(today, 1) ? "Tomorrow's games" : shown === addDays(today, -1) ? "Yesterday's games" : "Games on " + long(shown);
    var h = $("h-day");
    h.textContent = "";
    h.appendChild(el("span", { "class": "sr", text: label + ", " }));
    h.appendChild(document.createTextNode(day(shown).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short",
      year: shown.slice(0, 4) !== today.slice(0, 4) ? "numeric" : undefined }).replace(/,/g, "")));
    document.title = label + " | GOAT Sports";
    $("goto").value = shown;
    // the calendar: fifteen days with the chosen one in the middle, each with its number of games;
    // the chosen day is inverted and today is marked. The arrows either side move it a week at a time.
    nav.className = "cal";
    var month = null;
    all.forEach(function (d) {
      var n = 0, dt = day(d), ready = known(d);
      if (ready) data.leagues.forEach(function (lg) { if (!hidden[lg.key]) n += gamesOn(lg, d).length; });
      var m = dt.toLocaleDateString(undefined, { month: "short" }), wd = dt.toLocaleDateString(undefined, { weekday: "short" });
      var b = el("button", { type: "button", "class": "calday" + (d === today ? " today" : ""), "aria-pressed": String(d === shown),
        "aria-label": long(d) + (d === today ? ", today" : "") + (ready ? ", " + n + (n === 1 ? " game" : " games") : ""), onclick: function () { shown = d; draw(); } }, [
        el("span", { "class": "wd", text: d === today ? "Today" : wd }), el("span", { "class": "dn", text: String(dt.getDate()) }),
        el("span", { "class": "mo", text: m !== month ? m : "" }), el("span", { "class": "gn", text: !ready ? "…" : n ? n + (n === 1 ? " game" : " games") : "No games" })]);
      month = m;
      nav.appendChild(b);
    });
    var on_ = nav.querySelector("[aria-pressed=\"true\"]");
    if (on_ && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = Math.max(0, on_.offsetLeft - nav.offsetLeft - Math.floor(nav.clientWidth / on_.offsetWidth / 2) * on_.offsetWidth);

    var total = 0, quiet = [], out = [], live = [], off = 0;
    data.leagues.forEach(function (lg) {
      var games = gamesOn(lg, shown);
      if (hidden[lg.key]) { off += games.length; return; }
      if (!games.length) { quiet.push(lg); return; }
      total += games.length;
      // a game under way first, then by start time
      games.sort(function (a, b) { return (b.state === "live") - (a.state === "live") || (a.start || 0) - (b.start || 0); });
      var on = games.filter(function (g) { return g.state === "live"; }).length;
      if (on) live.push([lg, on]);
      out.push([lg, games, on]);
    });
    // the three readouts in the masthead
    var liveN = 0;
    data.leagues.forEach(function (lg) { if (!hidden[lg.key]) lg.games.forEach(function (g) { if (g.state === "live") liveN++; }); });
    $("r-live").textContent = String(liveN);
    // the leagues of the day, each a link to its list
    out.forEach(function (x) {
      jump.appendChild(el("a", { href: "#lg-" + x[0].key }, [el("span", { text: x[0].name }), el("span", {}, [el("span", { "class": "n", text: x[1].length + (x[1].length === 1 ? " game" : " games") }),
        x[2] ? el("span", { "class": "on", title: x[2] + " under way" }, [el("span", { "class": "sr", text: ", " + x[2] + " under way" })]) : null])]));
    });
    jump.hidden = !out.length;

    out.forEach(function (x) {
      var lg = x[0], games = x[1];
      // how many places a rank is shaded over: the poll's 25, or every team of a league numbered by its standings
      var top = lg.ranked_only ? 25 : Math.max.apply(null, [25].concat(lg.games.map(function (g) { return Math.max(g.away[2] || 0, g.home[2] || 0); })));
      var long_ = games.length > SHORT && !opened[lg.key], first = long_ ? games.slice(0, SHORT) : games;
      var list = el("ol", { "class": "games" }, first.map(function (g) { return row(lg, g); }));
      var cols_ = el("div", { "class": "colhead", "aria-hidden": "true" }, [el("span", { text: "Time" }), el("span", { "class": "r", text: "Away" }),
        el("span", { "class": "c", text: games.some(function (g) { return g.line && g.line[0] && g.state !== "final"; }) ? "Line" : lg.sport === "volleyball" && games.some(function (g) { return g.p != null && g.state !== "final"; }) ? "Our chance" : "" }), el("span", { text: "Home" }), el("span", { "class": "r", text: "Watch" })]);
      var key = keyOf(lg, games);
      var sec = el("section", { "class": "lg s-" + lg.sport, id: "lg-" + lg.key, "data-top": top, "aria-labelledby": "h-" + lg.key }, [
        el("div", { "class": "lg-head" }, [leagueMark(lg),
          el("h2", { id: "h-" + lg.key }, [el("a", { href: lg.href, text: lg.name }), el("span", { "class": "kind", text: lg.label })]),
          el("a", { "class": "all", href: lg.href }, ["All " + lg.name + " " + lg.unit, arrow()])]),
        key ? el("p", { "class": "lg-key", text: key }) : null, cols_, list]);
      if (long_) {
        var more = el("button", { type: "button", "class": "morebtn", text: "Show all " + games.length + " " + lg.name + " " + lg.unit, onclick: function () {
          opened[lg.key] = 1;
          var rest = games.slice(SHORT).map(function (g) { return row(lg, g); });
          rest.forEach(function (li) { list.appendChild(li); });
          more.remove();
          var go = rest[0] && rest[0].querySelector("a");
          if (go) go.focus();
        } });
        sec.appendChild(el("p", { "class": "showall" }, [more]));
      }
      holder.appendChild(sec);
    });
    var ready_ = known(shown);
    // the day's count of games and leagues sits in the masthead beside the readouts; the line over the calendar only speaks while a month loads
    $("r-games").textContent = ready_ ? String(total) : "…";
    $("r-leagues").textContent = ready_ ? String(out.length) : "…";
    $("lede").textContent = ready_ ? "" : "Loading the games…";
    $("lede").hidden = ready_;
    if (!ready_) return;
    if (!total) holder.appendChild(el("p", { "class": "empty", text: off ? "No games on this day in the leagues you chose. " + off + (off === 1 ? " game is" : " games are") + " in leagues you have left off; choose leagues above to show them."
      : "No games are listed for this day. Try an earlier or later day." }));
    quiet.forEach(function (lg) {
      if (!lg.ready) return;
      var coming = nextFor(lg, shown);
      var what = (lg.ranked_only ? "No ranked " + lg.name.toLowerCase() + " " : "No " + lg.name + " ") + lg.unit;
      holder.appendChild(el("p", { "class": "quiet s-" + lg.sport }, [what + " on this day" + (coming ? "; the next are on " + long(coming) + ". " : ". "),
        el("a", { href: lg.href, text: lg.name })]));
    });
  }

  // ---- the feed: today's games under way, then today's finished ones, newest first, in every league shown;
  // it always holds today, whichever day the list below is on, and moves with every score read live ----
  var SHORT_NAME = { cfb: "NCAAF", cbb: "NCAAM", wvb: "NCAAW" };   // the college leagues, short enough for a feed card
  function feed() {
    var box = $("feed");
    if (!box) return;
    box.innerHTML = "";
    var on = [], done = [];
    data.leagues.forEach(function (lg) {
      if (hidden[lg.key]) return;
      lg.games.forEach(function (g) {
        if (dayOf(g) !== today || g.away[3] == null || g.home[3] == null) return;
        if (g.state === "live") on.push([lg, g]); else if (g.state === "final") done.push([lg, g]);
      });
    });
    on.sort(function (a, b) { return (a[1].start || 0) - (b[1].start || 0); });
    done.sort(function (a, b) { return (b[1].start || 0) - (a[1].start || 0); });
    var items = on.concat(done.slice(0, 16));
    box.hidden = !items.length;
    if (!items.length) return;
    function side(lg, s, won) {
      return el("span", { "class": "side" + (won ? " won" : "") }, [logo(lg, s[0], s[1]), el("span", { "class": "nm", text: s[1] }), el("span", { "class": "sc", text: String(s[3]) })]);
    }
    var list = el("ol", { "class": "ticks" }, items.map(function (x) {
      var lg = x[0], g = x[1], live = g.state === "live", as = g.away[3], hs = g.home[3];
      var status = live ? g.clock || "Live" : "Final";
      return el("li", { "class": "tick" + (live ? " on" : "") + (flipped[key(lg, g)] ? " flip" : "") }, [el("a", { href: lg.game + g.id,
        "aria-label": lg.name + ". " + (live ? "Live" + (g.clock ? ", " + g.clock : "") : "Final") + ". " + g.away[1] + " " + as + ", " + g.home[1] + " " + hs }, [
        el("span", { "class": "tk-top" }, [el("span", { text: SHORT_NAME[lg.key] || lg.name }), live ? el("span", { "class": "livetag" }, [el("span", { "class": "dot", "aria-hidden": "true" }), status]) : el("span", { text: status })]),
        side(lg, g.away, !live && as > hs), side(lg, g.home, !live && hs > as)])]);
    }));
    box.appendChild(el("div", { "class": "wrap feed-row" }, [
      el("h2", { "class": "feed-h", id: "feed-h" }, on.length
        ? [el("span", { "class": "livetag" }, [el("span", { "class": "dot", "aria-hidden": "true" }), "Live"]), el("span", { "class": "n", text: on.length + (on.length === 1 ? " game" : " games") + (done.length ? " · " + done.length + " final" : "") })]
        : [el("span", { text: "Scores" }), el("span", { "class": "n", text: "Today · " + done.length + " final" })]),
      list]));
  }

  // ---- the sports, one line each, with the pages behind them ----
  function cards() {
    var holder = $("cards");
    holder.innerHTML = "";
    data.sports.forEach(function (s) {
      var d = DOORS[s.key];
      if (!d) return;
      var name = el("a", { href: s.href }, [el("span", { text: s.name })]);
      holder.appendChild(el("li", { "class": "door s-" + s.key + (s.ready ? "" : " soon") }, [sportIcon(s.key),
        el("div", { "class": "door-id" }, [el("h3", {}, [name]),
          el("p", { text: d[0] + ". " + d[1] + (s.ready ? "" : " Being set up: its first update has not run yet.") })]),
        el("ul", { "class": "door-pages", "aria-label": s.name + " pages" }, d[2].map(function (p) { return el("li", {}, [el("a", { href: s.href + p[1], text: p[0] })]); }))]));
    });
  }

  // ---- scores as they happen ----
  // While a game is on, its score is read straight from ESPN's public scoreboard (the one each
  // sport's own page reads) every 20 seconds. The page's own list of games is read again every
  // minute, and whenever the page is come back to, so nothing on it goes stale while it is left open.
  var LIVE_MS = 20 * 1000, LIST_MS = 60 * 1000, liveTimer = null, listTimer = null, seen = {}, told = [], flipped = {};
  function key(lg, g) { return lg.key + " " + g.id; }
  function due(lg, g, t) {
    return g.f != null && g.start && g.state !== "final" && g.state !== "other" && !g.over && (g.state === "live" || (t >= g.start - 900 && t <= g.start + (lg.live_hours || 5) * 3600));
  }
  function espnSide(x) { return x.score === "" || x.score == null ? null : +x.score; }
  function readEvent(lg, e) {
    var c = (e.competitions || [{}])[0], type = (e.status || {}).type || {}, out = { id: String(e.id), state: type.state, done: !!type.completed, clock: type.shortDetail || "" };
    (c.competitors || []).forEach(function (x) {
      var side = x.homeAway === "home" ? "home" : "away", a = (x.team || {}).abbreviation || "";
      out[side] = espnSide(x);
      out[side + "Id"] = (lg.espn_abbr || {})[a] || a;
    });
    return out;
  }
  function apply(lg, g, r) {
    if (!r || (r.state !== "in" && r.state !== "post") || r.away == null || r.home == null) return false;
    if (r.state === "post" && !r.done) return false;                       // postponed or called off: the next update says which
    var flip = lg.key === "wvb" && g.e && g.e[1], away = flip ? r.home : r.away, home = flip ? r.away : r.home;
    var state = r.state === "post" ? "final" : "live", clock = state === "live" ? r.clock : "";
    if (g.state === state && g.away[3] === away && g.home[3] === home) { if (g.clock === clock) return false; g.clock = clock; return true; }
    g.clock = clock;
    g.state = state; g.away[3] = away; g.home[3] = home; g.over = state === "final";
    flipped[key(lg, g)] = 1;
    told.push(lg.name + ": " + g.away[1] + " " + away + ", " + g.home[1] + " " + home + (state === "final" ? ", final" : ""));
    seen[key(lg, g)] = { state: state, away: away, home: home, at: Date.now() };
    return true;
  }
  function pollLive() {
    clearTimeout(liveTimer);
    if (!data || document.hidden) return;                                  // picks up again when the page is shown
    var t = Date.now() / 1000, jobs = [];
    data.leagues.forEach(function (lg) {
      var want = {};
      (lg.games || []).forEach(function (g) { if (due(lg, g, t) && (lg.feeds || [])[g.f]) (want[g.f] = want[g.f] || []).push(g); });
      Object.keys(want).forEach(function (f) {
        jobs.push(fetch(lg.feeds[f], { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : { events: [] }; }).catch(function () { return { events: [] }; }).then(function (doc) {
          var byId = {}, byTeams = {}, changed = false;
          (doc.events || []).forEach(function (e) { var r = readEvent(lg, e); byId[r.id] = r; byTeams[r.awayId + "@" + r.homeId] = r; });
          want[f].forEach(function (g) {
            var r = lg.key === "nhl" ? byTeams[g.away[0] + "@" + g.home[0]] : lg.key === "wvb" ? byId[String((g.e || [])[0])] : byId[String(g.id)];
            if (apply(lg, g, r)) changed = true;
          });
          return changed;
        }));
      });
    });
    Promise.all(jobs).then(function (results) {
      if (results.some(Boolean)) draw();
      if (told.length) { say(told.join(". ")); told = []; }
      setTimeout(function () { flipped = {}; }, 1000);
      liveTimer = setTimeout(pollLive, LIVE_MS);
    });
  }
  function load(first) {
    clearTimeout(listTimer);
    if (!first && document.hidden) return;
    fetch("home.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      var fresh = !data || d.updated !== data.updated;
      if (fresh) {
        // a score read live in the last few minutes is newer than the list's; keep it until the list catches up
        d.leagues.forEach(function (lg) {
          (lg.games || []).forEach(function (g) {
            var s = seen[key(lg, g)];
            if (s && g.state !== "final" && Date.now() - s.at < 30 * 60 * 1000) { g.state = s.state; g.away[3] = s.away; g.home[3] = s.home; g.over = s.state === "final"; }
          });
        });
        data = d;
        var was = today;
        today = iso(new Date());
        if (shown === was) shown = today;                                   // left open overnight: "today" moves on
        var u = new Date(d.updated);
        $("foot-updated").textContent = "Updated " + (isNaN(u) ? d.updated : u.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })) + ".";
        $("r-updated").textContent = isNaN(u) ? "–" : u.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
        draw();
        if (!$("cards").firstChild) { cards(); picker(); }       // also after a first load that failed
      }
      if (first) pollLive();
    }).catch(function () {
      if (first) {
        var lede = $("lede");
        lede.hidden = false;
        lede.textContent = "The games could not be loaded. ";
        lede.appendChild(el("button", { type: "button", "class": "morebtn", text: "Try again", onclick: function () { lede.textContent = "Loading the games…"; load(true); } }));
      }
    }).then(function () { listTimer = setTimeout(load, LIST_MS); });
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { load(!data); pollLive(); } });
  $("back").addEventListener("click", function () { if (data) { shown = addDays(shown || today, -7); draw(); } });
  $("ahead").addEventListener("click", function () { if (data) { shown = addDays(shown || today, 7); draw(); } });
  $("goto").addEventListener("change", function (ev) { if (data && /^\d{4}-\d{2}-\d{2}$/.test(ev.target.value)) { shown = ev.target.value; draw(); } });
  $("invert").addEventListener("click", function () { setTheme(lightNow() ? "dark" : "light"); });
  $("invert").setAttribute("aria-pressed", String(lightNow()));
  load(true);
})();
