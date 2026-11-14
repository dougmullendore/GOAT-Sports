/* GOAT Sports, the front page: each league's games on one day, and a door to each sport. No libraries. */
(function () {
  "use strict";

  // ---- a team name too long for its row gives way to the team's abbreviation (CBJ for the Columbus Blue Jackets);
  // the full name stays in the tooltip and is what a screen reader says. Checked as rows arrive and when the window resizes. ----
  function fitName(n) {
    var full = n.getAttribute("data-full");
    if (!full) { full = n.textContent; n.setAttribute("data-full", full); }
    if (n.textContent !== full) { n.textContent = full; n.removeAttribute("title"); n.removeAttribute("aria-label"); }
    if (n.scrollWidth > n.clientWidth + 1) { n.textContent = n.getAttribute("data-abbr"); n.setAttribute("title", full); n.setAttribute("aria-label", full); }
  }
  function fitNames(root) { Array.prototype.forEach.call((root || document).querySelectorAll(".team .name[data-abbr]"), fitName); }
  if (window.MutationObserver) new MutationObserver(function (list) {
    list.forEach(function (m) { Array.prototype.forEach.call(m.addedNodes, function (n) { if (n.nodeType === 1 && (n.matches(".team .name[data-abbr]") || n.querySelector(".team .name[data-abbr]"))) fitNames(n); }); });
  }).observe(document.documentElement, { childList: true, subtree: true });
  var fitTimer = null;
  window.addEventListener("resize", function () { clearTimeout(fitTimer); fitTimer = setTimeout(function () { fitNames(); }, 120); });
  // ---- games under way go to the top of whatever list they are in, and move there when one starts ----
  function liveFirst(ol) {
    var kids = Array.prototype.slice.call(ol.children), ref = null, i;
    function on(li) { return li.classList && li.classList.contains("game") && li.classList.contains("live"); }
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
  // ---- the button at the foot of the page goes back to the top ----
  (function () {
    var b = document.getElementById("totop");
    if (!b) return;
    b.addEventListener("click", function () {
      var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: still ? "auto" : "smooth" });
      var first = document.querySelector(".skip") || document.body;
      try { first.focus({ preventScroll: true }); } catch (e) {}
    });
  })();
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

  // ---- black or white: the page follows the device; a choice kept from the old Invert button is let go ----
  try { localStorage.removeItem("goat-theme"); } catch (e) {}


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
    // a college poll's numbers, or a pro league's places in its standings
    if (!n) return null;
    var standings = !lg.poll || /standings$/i.test(lg.poll), goat = !standings && n > 25;
    if (goat) return null;              // a place in the GOAT ranking, for a team the poll leaves out: hidden for now
    return { n: n, goat: goat, words: goat ? n + " in the GOAT ranking" : standings ? ordinal(n) + " in the " + (lg.poll || "standings") : "ranked " + n + " in the " + lg.poll };
  }
  // the key under a league's name: why a list has no chances of winning (the rankings go without a note)
  function keyOf(lg, games) {
    var bits = [];
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
      // the logos sit in the middle, beside the line; the names on the outside
      var kids = [r ? el("span", { "class": "rk" + (r.goat ? " goat" : ""), text: String(r.n) }) : null, el("span", { "class": "name", text: s[1], "data-abbr": s[4] && s[4] !== s[1] ? s[4] : null }), logo(lg, s[0], s[1])];
      if (side === "home") kids.reverse();
      return el("span", { "class": "team " + side + (lost ? " lost" : "") + (won ? " won" : "") }, kids);
    }
    function named(s) { var r = rankOf(lg, s[2]); return s[1] + (r ? " (" + r.words + ")" : ""); }
    var mid = scored
      ? el("span", { "class": "mid" }, [el("span", { "class": homeWon ? "l" : "", text: String(as) }), el("span", { "class": "dash", text: "–" }), el("span", { "class": awayWon ? "l" : "", text: String(hs) })])
      : g.line && g.line[0] && !fin
        ? el("span", { "class": "mid line" }, [el("span", { "class": "ln", text: g.line[0] })])
      : g.p != null && !fin && lg.sport === "volleyball"
        ? el("span", { "class": "mid odds" }, [el("span", { "class": g.p > 0.5 ? "l" : "", text: pct(g.p)[0] }), el("span", { "class": "dash", text: "at" }), el("span", { "class": g.p < 0.5 ? "l" : "", text: pct(g.p)[1] })])
        : el("span", { "class": "mid at", text: "at" });
    // what a screen reader hears for the row: everything the row shows, in reading order
    var label = [live ? "Live" : when, named(g.away) + " at " + named(g.home),
      scored ? g.away[1] + " " + as + ", " + g.home[1] + " " + hs + (fin ? ", final" : "")
        : g.line && g.line[0] && !fin ? "Betting line: " + g.line[0] + (g.line[1] != null ? ", over/under " + g.line[1] : "")
        : g.p != null && !fin && lg.sport === "volleyball" ? "This site's chance of winning: " + g.away[1] + " " + pct(g.p)[0] + ", " + g.home[1] + " " + pct(g.p)[1] : "",
      !fin && !note && tv.length ? "Watch on " + tv.join(", ") : ""].filter(Boolean).join(". ");
    var more = fin || note ? "" : tv.join(", ");
    return el("li", { "class": "game" + (live ? " live" : "") + (flipped[key(lg, g)] ? " flip" : ""), "data-k": key(lg, g) }, [el("a", { "class": "row", href: lg.game + g.id, "aria-label": label }, [
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
    $("goto-val").textContent = day(shown).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
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
      jump.appendChild(el("a", { href: "#lg-" + x[0].key }, [el("span", { text: x[0].name }), el("span", {}, [el("span", { "class": "n" }, [String(x[1].length), el("span", { "class": "sr", text: x[1].length === 1 ? " game" : " games" })]),
        x[2] ? el("span", { "class": "on", title: x[2] + " under way" }, [el("span", { "class": "sr", text: ", " + x[2] + " under way" })]) : null])]));
    });
    jump.hidden = !out.length;

    out.forEach(function (x) {
      var lg = x[0], games = x[1];
      // how many places a rank is shaded over: the poll's 25, or every team of a league numbered by its standings
      var top = lg.ranked_only ? 25 : Math.max.apply(null, [25].concat(lg.games.map(function (g) { return Math.max(g.away[2] || 0, g.home[2] || 0); })));
      // every game of the day is listed, however many there are
      var list = el("ol", { "class": "games" }, games.map(function (g) { return row(lg, g); }));
      var key = keyOf(lg, games);
      var sec = el("section", { "class": "lg s-" + lg.sport, id: "lg-" + lg.key, "data-top": top, "aria-labelledby": "h-" + lg.key }, [
        el("div", { "class": "lg-head" }, [leagueMark(lg),
          el("h2", { id: "h-" + lg.key }, [el("a", { href: lg.href, text: lg.name }), el("span", { "class": "kind", text: lg.label })]),
          el("a", { "class": "all", href: lg.href }, ["All " + lg.name + " " + lg.unit, arrow()])]),
        key ? el("p", { "class": "lg-key", text: key }) : null,
        // which side is which, right over the games: over the columns on a wide screen, a note on a phone
        el("div", { "class": "hahead", "aria-hidden": "true" }, [el("span"), el("span", { "class": "ha away", text: "Away" }), el("span"), el("span", { "class": "ha home", text: "Home" }), el("span")]),
        list]);
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
      // the league's name goes to its page; the next day with its games opens that day here, at its list
      var name = el("a", { "class": "lgname", href: lg.href, text: lg.name });
      var go = coming ? el("button", { type: "button", "class": "date", text: long(coming), onclick: function () {
        shown = coming; draw();
        var sec = $("lg-" + lg.key);
        if (sec) sec.scrollIntoView({ block: "start" });
      } }) : null;
      holder.appendChild(el("p", { "class": "quiet s-" + lg.sport }, [el("span", {}, [lg.ranked_only ? "No ranked " : "No ", name, " " + lg.unit + " on this day" + (coming ? "; the next are on " : ". "), go, coming ? ". " : null])]));     // (the league named once, in the sentence)
    });
  }

  // ---- the sports, one line each, with the pages behind them ----
  function cards() {
    var holder = $("cards");
    if (!holder) return;                                      // (the front page no longer lists the sports at its foot)
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
        if ($("r-updated")) $("r-updated").textContent = isNaN(u) ? "–" : u.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
        draw();
        if (!$("pick").firstChild) picker();                    // also after a first load that failed
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
  // ---- the Date button opens a month of days to jump to: this site's own, the same in every browser ----
  (function () {
    var btn = $("goto"), box = $("goto-box"), pop = null, month = null, focusDay = null;
    function close(back) {
      if (!pop) return;
      pop.remove(); pop = null;
      btn.setAttribute("aria-expanded", "false");
      document.removeEventListener("mousedown", outside, true);
      if (back) btn.focus();
    }
    function outside(ev) { if (pop && !box.contains(ev.target)) close(false); }
    function first(m) { return m + "-01"; }
    function shiftMonth(m, by) { var p = m.split("-"), d = new Date(+p[0], +p[1] - 1 + by, 1, 12); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2); }
    function pick(d) { close(true); if (data && d !== shown) { shown = d; draw(); } }
    function render() {
      pop.innerHTML = "";
      var start = day(first(month)), title = start.toLocaleDateString(undefined, { month: "long", year: "numeric" });
      function arrow(by, words, d) {
        var b = el("button", { type: "button", "class": "gp-step", "aria-label": words, onclick: function () { month = shiftMonth(month, by); focusDay = first(month); render(); } });
        b.innerHTML = '<svg viewBox="0 0 10 14" aria-hidden="true"><path d="' + d + '"/></svg>';
        return b;
      }
      pop.appendChild(el("div", { "class": "gp-head" }, [arrow(-1, "Previous month", "M8 1L2 7l6 6"), el("b", { "class": "gp-title", text: title, "aria-live": "polite" }), arrow(1, "Next month", "M2 1l6 6-6 6")]));
      var grid = el("div", { "class": "gp-grid", role: "grid", "aria-label": title });
      // the week starts on Sunday
      for (var w = 0; w < 7; w++) grid.appendChild(el("span", { "class": "gp-wd", "aria-hidden": "true", text: new Date(2023, 0, 1 + w, 12).toLocaleDateString(undefined, { weekday: "narrow" }) }));
      for (var pad = 0; pad < start.getDay(); pad++) grid.appendChild(el("span", { "class": "gp-pad" }));
      var d = first(month);
      while (d.slice(0, 7) === month) {
        (function (d) {
          var b = el("button", { type: "button", "class": "gp-day" + (d === today ? " today" : ""), "aria-pressed": String(d === shown), tabindex: d === focusDay ? "0" : "-1",
            "aria-label": long(d) + (d === today ? ", today" : ""), "data-d": d, onclick: function () { pick(d); } }, [String(day(d).getDate())]);
          grid.appendChild(b);
        })(d);
        d = addDays(d, 1);
      }
      pop.appendChild(grid);
      pop.appendChild(el("div", { "class": "gp-foot" }, [el("button", { type: "button", "class": "gp-today", text: "Today", onclick: function () { pick(today); } })]));
      var f = grid.querySelector('[data-d="' + focusDay + '"]');
      if (f) f.focus({ preventScroll: true });
    }
    function open() {
      month = (shown || today).slice(0, 7); focusDay = shown || today;
      pop = el("div", { "class": "gp", id: "goto-pop", role: "dialog", "aria-label": "Choose a day" });
      box.appendChild(pop);
      btn.setAttribute("aria-expanded", "true");
      document.addEventListener("mousedown", outside, true);
      render();
    }
    btn.addEventListener("click", function () { if (pop) close(true); else open(); });
    box.addEventListener("keydown", function (ev) {
      if (!pop) return;
      if (ev.key === "Escape") { ev.preventDefault(); close(true); return; }
      var on = document.activeElement && document.activeElement.getAttribute("data-d");
      if (!on) return;
      var by = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[ev.key];
      if (by) {
        ev.preventDefault();
        focusDay = addDays(on, by);
        if (focusDay.slice(0, 7) !== month) month = focusDay.slice(0, 7);
        render();
      }
    });
  })();
  load(true);
})();
