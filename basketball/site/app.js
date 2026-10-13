/* GOAT Basketball: one page, no libraries. Lists the games of the 25 ranked teams, or of all of
   Division I; the same page, in the site's nba/ folder, lists the NBA's. */
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
    list.forEach(function (m) {
      var was = {};
      Array.prototype.forEach.call(m.removedNodes, function (n) { if (isGame(n)) was[n.getAttribute("data-id")] = scoreOf(n); });
      Array.prototype.forEach.call(m.addedNodes, function (n) {
        listsIn(n, lists); explainAll(n); retry(n);
        var id = isGame(n) ? n.getAttribute("data-id") : null, now = id ? scoreOf(n) : "";
        if (id && was[id] != null && now && now !== was[id]) { var go = n.querySelector("a.go"); say(go ? go.getAttribute("aria-label") : n.textContent); }
      });
    });
    lists.filter(function (ol, i) { return lists.indexOf(ol) === i; }).forEach(liveFirst);
  }).observe(document.documentElement, { childList: true, subtree: true });

  // ---- a game's row opens its page through one link laid over the whole row. The team names in the row
  // stay links of their own, above it, so no link sits inside another. The link reads the whole line aloud. ----
  function rowLink(li) {
    var go = li.getAttribute("data-go");
    if (!go) return li;
    function said(n) { return n ? (n.getAttribute("aria-label") || n.textContent || "").replace(/\s+/g, " ").trim() : ""; }
    function side(t) {
      if (!t) return "";
      var rk = t.querySelector(".rk[aria-label]");
      return said(t.querySelector(".name")) + (rk ? " (" + rk.getAttribute("aria-label") + ")" : "");
    }
    var mid = li.querySelector(".mid"), sep = mid && /\bvs\b/.test(mid.textContent) ? " vs " : " at ";
    var words = [said(li.querySelector(".when")), side(li.querySelector(".team.away")) + sep + side(li.querySelector(".team.home")),
      mid && mid.getAttribute("aria-label") || "", said(li.querySelector(".more"))];
    li.insertBefore(el("a", { "class": "go", href: go, "aria-label": words.filter(Boolean).join(". ") }), li.firstChild);
    return li;
  }
  // ---- the explanations under lists and tables open from a "How to read this" line, so a page stays short
  // and its explanation stays one tap away. Notes side by side share one line. A note that holds a link
  // or a button (marked "keep") stays as it is. ----
  function explain(p) {
    if (!p.classList || !p.classList.contains("note") || p.classList.contains("keep") || !p.parentNode) return;
    if (p.parentNode.classList && p.parentNode.classList.contains("explain")) return;
    var before = p.previousElementSibling;
    if (before && before.classList.contains("explain")) { before.appendChild(p); return; }
    var box = document.createElement("details"), open = document.createElement("summary");
    box.className = "explain";
    open.textContent = (data && data.words && data.words["explain.open"]) || "How to read this";
    p.parentNode.insertBefore(box, p);
    box.appendChild(open);
    box.appendChild(p);
  }
  function explainAll(root) {
    if (!root || root.nodeType !== 1) return;
    explain(root);
    Array.prototype.forEach.call(root.querySelectorAll("p.note"), explain);
  }
  // the line that is always shown under this site's own chances of winning
  function keyline(g) {
    if (g && g.line && g.line[0]) return null;               // a game with a bookmaker's line says so beside the line
    return el("p", { "class": "keyline", text: W("games.odds_short") || "These percentages are this site's own estimate of each team's chance of winning, not betting lines." });
  }
  // ---- a score that changes is read out to screen readers ----
  var sayBox = null;
  function say(words) {
    if (!sayBox) {
      sayBox = document.createElement("p");
      sayBox.className = "sr"; sayBox.setAttribute("role", "status"); sayBox.setAttribute("aria-live", "polite");
      document.body.appendChild(sayBox);
    }
    sayBox.textContent = words;
  }
  function isGame(n) { return n && n.nodeType === 1 && n.matches && n.matches("li.game[data-id]"); }
  function scoreOf(li) {
    var m = li.querySelector(".mid"), w = li.querySelector(".when");
    if (!m || m.classList.contains("odds") || m.classList.contains("at")) return "";
    return m.textContent + (w && /final/i.test(w.textContent) ? " final" : "");
  }
  // ---- something that could not be loaded offers to try again ----
  function retry(root) {
    if (!root || root.nodeType !== 1) return;
    var all = root.matches && root.matches("p.empty") ? [root] : Array.prototype.slice.call(root.querySelectorAll("p.empty"));
    all.forEach(function (p) {
      if (!/Reload the page/.test(p.textContent) || p.querySelector("button")) return;
      p.appendChild(document.createTextNode(" "));
      p.appendChild(el("button", { type: "button", "class": "morebtn", text: "Try again", onclick: function () { location.reload(); } }));
    });
  }

  var $ = function (id) { return document.getElementById(id); };
  explainAll(document.querySelector("main"));       // the notes written into the page itself
  // ---- the calendar: a strip of days (or weeks), each with how many games it holds; the chosen one is
  // inverted and today is marked. It scrolls sideways a whole cell at a time. ----
  function calendar(items, chosen, pick, name) {
    var bar = el("nav", { "class": "cal", "aria-label": name || "Days" }), month = null;
    items.forEach(function (it) {
      var m = it.month || "";
      bar.appendChild(el("button", { type: "button", "class": "calday" + (it.today ? " today" : ""), "aria-pressed": String(it.key === chosen),
        "aria-label": it.label + (it.today ? ", today" : "") + ", " + it.n + (it.n === 1 ? " game" : " games"), onclick: function () { pick(it.key); } }, [
        el("span", { "class": "wd", text: it.top }), el("span", { "class": "mo", text: m !== month ? m : "" }),
        el("span", { "class": "dn", text: it.big }), el("span", { "class": "gn", text: it.n + (it.n === 1 ? " game" : " games") })]));
      month = m;
    });
    setTimeout(function () {
      var on = bar.querySelector('[aria-pressed="true"]');
      if (on && bar.scrollWidth > bar.clientWidth) bar.scrollLeft = Math.max(0, on.offsetLeft - bar.offsetLeft - Math.floor(bar.clientWidth / on.offsetWidth / 2) * on.offsetWidth);
    }, 0);
    return bar;
  }
  // one cell for each day that has a game
  function dayItems(games) {
    var n = {};
    games.forEach(function (g) { n[g.date] = (n[g.date] || 0) + 1; });
    return Object.keys(n).sort().map(function (d) {
      var t = day(d);
      return { key: d, top: d === today ? "Today" : t.toLocaleDateString(undefined, { weekday: "short" }), big: String(t.getDate()),
        month: t.toLocaleDateString(undefined, { month: "short" }), n: n[d], today: d === today, label: long(d) };
    });
  }
  // the day to show: the one asked for if it has games, otherwise the next day with games, otherwise the last
  function pickDay(items, want) {
    if (want && items.some(function (it) { return it.key === want; })) return want;
    var next = items.filter(function (it) { return it.key >= today; })[0];
    return (next || items[items.length - 1]).key;
  }

  // ---- betting lines: the sportsbook's line where there is one, read from ESPN ----
  function lineMid(g) {
    var l = g.line;
    return el("span", { "class": "mid line", "aria-label": "Betting line: " + l[0] + (l[1] != null ? ", over/under " + l[1] : "") }, [
      el("span", { "class": "ln", text: l[0] }), l[1] != null ? el("span", { "class": "ou", text: "O/U " + l[1] }) : null]);
  }
  function lineCard(g) {
    var l = g.line;
    return el("div", { "class": "gc-odds gc-lines" }, [
      el("span", { "class": "gc-lab", text: "Betting line" + (l[2] ? ", " + l[2] : "") }),
      el("div", { "class": "gc-linebig" }, [el("span", { text: l[0] }), l[1] != null ? el("span", { text: "Over/under " + l[1] }) : null]),
      linesNote([g])]);
  }
  function linesNote(games) {
    var from = (games.filter(function (g) { return g.line && g.line[2]; })[0] || {}).line;
    return el("p", { "class": "keyline", text: "Betting lines from " + (from ? from[2] : "a sportsbook") + ", read from ESPN. Lines move: check the sportsbook before you bet. " +
      "If you or someone you know has a gambling problem, call 1-800-GAMBLER." });
  }
  // this sport shows the sportsbook's betting lines in place of the site's own chances of winning
  // (volleyball has no betting lines, so it keeps the site's own chances)
  var LINES = true;
  var data = null, state = { day: null, team: null }, fbs = {};

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

  // ---- dates. A day is "YYYY-MM-DD". ----
  function iso(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function day(s) { var p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2], 12); }
  function addDays(s, n) { var d = day(s); d.setDate(d.getDate() + n); return iso(d); }
  function short(s) { return day(s).toLocaleDateString(undefined, { month: "short", day: "numeric" }); }
  function long(s) { return day(s).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }); }
  var today = iso(new Date());

  // A team's logo, shown from ESPN. With `name`, the logo stands in for the team's name,
  // so it carries the name for screen readers and on hover.
  function logo(teamId, cls, name) {
    var src = !teamId ? null : data.logos && data.logos[teamId] ? data.logos[teamId] : data.logo ? data.logo.replace("{team}", encodeURIComponent(teamId)) : null;
    if (!src) return name ? el("span", { text: name }) : null;
    var img = el("img", { src: src, alt: name || "", title: name || null, loading: "lazy", decoding: "async" });
    var pic = el("span", { "class": "logo " + (cls || "") }, [img]);
    img.addEventListener("error", function () {       // no logo for this team: show the name instead, or leave the space
      if (name) { pic.className = ""; pic.textContent = name; } else pic.style.visibility = "hidden";
    });
    return pic;
  }
  // A player's photo, shown from ESPN; his initials if there is none.
  function face(p, cls) {
    var initials = p.name.split(/\s+/).map(function (w) { return w.charAt(0); }).join("").slice(0, 2).toUpperCase();
    var box = el("span", { "class": "face " + (cls || ""), "aria-hidden": "true" }, [el("span", { text: initials })]);
    if (p.photo) {
      var img = el("img", { src: p.photo, alt: "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer" });
      img.addEventListener("load", function () { box.classList.add("has"); });
      img.addEventListener("error", function () { if (img.parentNode) img.parentNode.removeChild(img); });
      box.appendChild(img);
    }
    return box;
  }
  // A team's name as a link to its page. Teams from outside the league have no page.
  function teamA(id, name, cls) {
    return id && fbs[id] ? el("a", { "class": "tlink " + (cls || ""), href: "#/team/" + encodeURIComponent(id), text: name })
      : el("span", { "class": cls || "", text: name });
  }
  // The site's wording, from words.txt (see the top of that file). {name} is filled from `vars`.
  // A league's own copy of the site has its own lines there ("nba.games_title" for "games.title").
  function W(key, vars) {
    var ws = (data && data.words) || {}, own = data && data.league ? ws[data.league + "." + key.replace(".", "_")] : null;
    var s = own != null ? own : ws[key];
    if (s == null) return "";
    return s.replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] != null ? String(vars[k]) : m; });
  }
  // A pro league's copy of the site: there is no poll, so every team is "ranked", by the league
  // standings, and there is no Top 25 switch.
  function PRO() { return !!(data && data.pro); }
  // A college season before its first poll: there is no top 25 yet, so every page shows the whole division.
  function NOPOLL() { return !!(data && data.no_poll); }
  function ALL() { return (data && data.all_name) || "Division I"; }
  // ---- Top 25 or the whole division: one switch, remembered, used by every page that has it ----
  var SCOPE_KEY = "goat-scope-" + location.pathname.split("/").filter(Boolean).slice(-1)[0];
  var scope = "top25";
  try { if (localStorage.getItem(SCOPE_KEY) === "fbs") scope = "fbs"; } catch (e) {}
  function isAll() { return PRO() || NOPOLL() || scope === "fbs"; }
  // who a player is measured against, in words
  function POOL() { return PRO() ? "an average " + data.league_name + " regular" : isAll() ? "an average " + ALL() + " regular" : "an average top-25 regular"; }
  function rankOf(id) { for (var i = 0; i < data.poll.teams.length; i++) if (data.poll.teams[i].id === id) return data.poll.teams[i]; return null; }
  // the ending of a wording line's name: the "All" wording has its own lines; a pro league has one wording
  function FBS() { return !PRO() && isAll() ? "_fbs" : ""; }
  function setScope(s) { scope = s; try { localStorage.setItem(SCOPE_KEY, s); } catch (e) {} }
  function scopeSwitch(redraw, lockAll) {
    if (PRO() || NOPOLL()) return el("span", { "class": "noscope" });
    return el("div", { "class": "scope", role: "group", "aria-label": "Which teams" }, [["top25", W("scope.top25")], ["fbs", W("scope.fbs")]].map(function (o) {
      var on = lockAll ? o[0] === "fbs" : scope === o[0];      // a team outside the top 25 is always shown against the whole division
      return el("button", { type: "button", "aria-pressed": String(on), disabled: lockAll && o[0] === "top25",
        text: o[1], onclick: function () { if (!on) { setScope(o[0]); redraw(); } } });
    }));
  }
  function setHead(page, key) {      // a page's title and intro for the current switch
    var sec = $("page-" + page), h = sec && sec.querySelector("h1"), l = sec && sec.querySelector(".lede");
    if (h) h.textContent = W(key + ".title" + FBS());
    if (l && W(key + ".lede" + FBS())) l.textContent = W(key + ".lede" + FBS(), { poll: data.poll.name });
  }
  function ordinal(n) { var s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  // A team's number: its poll rank (or place in the standings), or for a team outside the poll
  // its place from 26 on in the GOAT ranking (data.nr), so no two teams share a number.
  // Before a season has a poll, or a game, there are no numbers to show.
  function shownRank(id, rank) { return !data.numbered ? null : rank || (id && data.nr && data.nr[id]) || null; }
  function rankTag(rank, id) {
    var n = shownRank(id, rank);
    if (!data.numbered) return el("span", { "class": "rk none" });
    return el("span", { "class": "rk" + (n ? "" : " nr") + (!PRO() && !rank && n ? " goat" : ""), role: PRO() && !n ? null : "img", text: n ? String(n) : "NR",
      "aria-label": PRO() ? (n ? ordinal(n) + " in the standings" : null) : rank ? "ranked " + rank : n ? "unranked, " + n + " by the GOAT ranking" : "not in " + ALL(),
      title: PRO() ? (n ? ordinal(n) + " in the " + data.league_name + " standings" : null) : !rank && n ? "Not in the AP poll; " + n + " by the GOAT ranking" : !n ? "Not in " + ALL() : null });
  }

  // ======================================================================================
  // What is particular to the sport: the numbers a player and a team have, and how they read.
  // ======================================================================================
  var POS_ONE = { G: "Guard", F: "Forward", C: "Center" };
  var POS_MANY = { G: "Guards", F: "Forwards", C: "Centers" };
  var fmt = {
    d1: function (v) { return v.toFixed(1); }, d2: function (v) { return v.toFixed(2); },
    s1: function (v) { return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1); },
    s2: function (v) { return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(2); },
    pct: function (v) { return v.toFixed(1) + "%"; },
    n: function (v) { return (Math.round(v * 10) / 10).toLocaleString("en-US"); }
  };
  var IMPACT_UNIT = "game", IMPACT_WORDS = "points of game score added";
  // a card's bars: key, label, what it means, format
  var CARD = [
    ["Impact, per game", [
      ["impact_g", "All of it", "Game score beyond what an average regular at his position puts up in the same minutes", fmt.s2],
      ["score", "Scoring", "Points, less 0.7 for each shot tried, plus 0.4 for each made, less 0.4 for each free throw missed", fmt.s2],
      ["board", "Rebounding", "Offensive rebounds at 0.7, defensive rebounds at 0.3", fmt.s2],
      ["play", "Playmaking", "Assists at 0.7, less turnovers", fmt.s2],
      ["def", "Defense", "Steals, blocks at 0.7, less fouls at 0.4", fmt.s2]]],
    ["Scoring", [
      ["pts_g", "Points per game", "", fmt.d1], ["fg_pct", "Field goal percentage", "", fmt.pct], ["tp_pct", "Three-point percentage", "", fmt.pct],
      ["ft_pct", "Free throw percentage", "", fmt.pct],
      ["efg", "Effective field goal percentage", "Field goal percentage with a three counted as one and a half baskets", fmt.pct],
      ["ts", "True shooting", "Points per shot, counting trips to the line: points divided by twice (field goals tried plus 0.44 of free throws tried)", fmt.pct]]],
    ["The rest of the game", [
      ["reb_g", "Rebounds per game", "", fmt.d1], ["ast_g", "Assists per game", "", fmt.d1], ["stl_g", "Steals per game", "", fmt.d1],
      ["blk_g", "Blocks per game", "", fmt.d1], ["to_g", "Turnovers per game", "Fewer is better, so a long bar means few turnovers", fmt.d1],
      ["ast_to", "Assists per turnover", "", fmt.d2], ["min_g", "Minutes per game", "", fmt.d1]]]
  ];
  var roster = null;
  function val(p, key) { return p.v[roster.metrics.indexOf(key)]; }
  function pctOf(p, key) { return p.pct[roster.metrics.indexOf(key)]; }
  function T(p, key) { return (p.tot || {})[key] || 0; }
  function per(a, b, nd) { return b ? (a / b).toFixed(nd == null ? 1 : nd) : ""; }
  function shot(m, a) { return a ? (100 * m / a).toFixed(1) : ""; }
  // A player's season in a line.
  function statLine(p) {
    if (!p.gp) return "";
    return per(T(p, "pts"), p.gp) + " pts, " + per(T(p, "reb"), p.gp) + " reb, " + per(T(p, "ast"), p.gp) + " ast" + (T(p, "fga") ? ", " + shot(T(p, "fgm"), T(p, "fga")) + "% FG" : "");
  }
  function avgCol(key, tkey, head, meaning) { return [key, head, meaning, function (p) { return val(p, key); }, fmt.d1, 1]; }
  function pctCol(key, need, head, meaning) { return [key, head, meaning, function (p) { return T(p, need) ? val(p, key) : null; }, fmt.d1, 1]; }
  // the players table: key, heading, meaning, getter, format, sorts high to low first
  var PCOLS = [
    ["rank", "#", "Rank by Impact per game among regulars", function (p) { return p.rank; }, function (v) { return String(v); }, 0],
    ["name", "Player", "", function (p) { return p.name; }, null, 0],
    ["team", "Team", "", function (p) { return p.team_rank; }, null, 0],
    ["pos", "Pos", "G Guard, F Forward, C Center", function (p) { return p.pos; }, function (v) { return v; }, 0],
    ["gp", "GP", "Games played", function (p) { return p.gp; }, function (v) { return String(v); }, 1],
    ["impact", "Impact", "Game score added this season over an average regular at his position", function (p) { return p.impact; }, fmt.s1, 1],
    ["impact_g", "Per game", "Impact per game played", function (p) { return val(p, "impact_g"); }, fmt.s2, 1],
    avgCol("min_g", "min", "Min", "Minutes per game"), avgCol("pts_g", "pts", "Pts", "Points per game"), avgCol("reb_g", "reb", "Reb", "Rebounds per game"),
    avgCol("ast_g", "ast", "Ast", "Assists per game"), avgCol("stl_g", "stl", "Stl", "Steals per game"), avgCol("blk_g", "blk", "Blk", "Blocks per game"),
    pctCol("fg_pct", "fga", "FG%", "Field goal percentage"), pctCol("tp_pct", "tpa", "3P%", "Three-point percentage"), pctCol("ft_pct", "fta", "FT%", "Free throw percentage")
  ];
  function pcols() { return PCOLS; }
  var POS_FILTER = Object.keys(POS_MANY).map(function (k) { return [k, POS_MANY[k]]; });
  // a card's season totals: label, the number
  function totalsOf(p) {
    function made(m, a) { return T(p, a) ? T(p, m) + "-" + T(p, a) : null; }
    return [["Games", p.gp], ["Starts", T(p, "gs") || null], ["Minutes", T(p, "min") || null], ["Points", T(p, "pts") || null], ["Field goals", made("fgm", "fga")],
      ["Three-pointers", made("tpm", "tpa")], ["Free throws", made("ftm", "fta")], ["Rebounds", T(p, "reb") || null], ["Offensive rebounds", T(p, "oreb") || null],
      ["Assists", T(p, "ast") || null], ["Steals", T(p, "stl") || null], ["Blocks", T(p, "blk") || null], ["Turnovers", T(p, "to") || null], ["Fouls", T(p, "pf") || null],
      ["Plus-minus", T(p, "pm") ? fmt.s1(T(p, "pm")).replace(".0", "") : null]].filter(function (x) { return x[1] != null; });
  }
  // a game line: [game, date, opponent id, opponent, at home, result] and then these, in this order
  var LOGK = ["min", "pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "ast", "stl", "blk", "to", "pf", "pm"];
  function at(r, k) { return r[6 + LOGK.indexOf(k)]; }
  function one(k, head, meaning) { return [head, meaning, function (r) { return at(r, k); }]; }
  function two(m, a, head, meaning) { return [head, meaning, function (r) { return at(r, m) + "-" + at(r, a); }]; }
  function logCols() {
    return [one("min", "Min", "Minutes"), one("pts", "Pts", "Points"), two("fgm", "fga", "FG", "Field goals made and tried"), two("tpm", "tpa", "3PT", "Three-pointers made and tried"),
      two("ftm", "fta", "FT", "Free throws made and tried"), one("reb", "Reb", "Rebounds"), one("ast", "Ast", "Assists"), one("stl", "Stl", "Steals"), one("blk", "Blk", "Blocks"),
      one("to", "TO", "Turnovers"), one("pf", "PF", "Fouls")];
  }
  // a game's box score. A row is [player id, name, number, position, started, ...numbers, has a card]
  var B = { min: 5, pts: 6, fgm: 7, fga: 8, tpm: 9, tpa: 10, ftm: 11, fta: 12, reb: 13, ast: 14, to: 15, stl: 16, blk: 17, oreb: 18, dreb: 19, pf: 20, pm: 21 };
  function boxCols() {
    var cols = [["Min", "Minutes", function (r) { return r[B.min]; }], ["Pts", "Points", function (r) { return r[B.pts]; }],
      ["FG", "Field goals made and tried", function (r) { return r[B.fgm] + "-" + r[B.fga]; }], ["3PT", "Three-pointers made and tried", function (r) { return r[B.tpm] + "-" + r[B.tpa]; }],
      ["FT", "Free throws made and tried", function (r) { return r[B.ftm] + "-" + r[B.fta]; }], ["Reb", "Rebounds", function (r) { return r[B.reb]; }],
      ["Ast", "Assists", function (r) { return r[B.ast]; }], ["Stl", "Steals", function (r) { return r[B.stl]; }], ["Blk", "Blocks", function (r) { return r[B.blk]; }],
      ["TO", "Turnovers", function (r) { return r[B.to]; }], ["PF", "Fouls", function (r) { return r[B.pf]; }]];
    if (PRO()) cols.push(["+/-", "The team's margin while he was on the floor", function (r) { return (r[B.pm] > 0 ? "+" : "") + r[B.pm]; }]);
    return cols;
  }
  function boxTables(rows, teamName, totals) {
    var cols = boxCols(), out = el("div", {});
    rows = (rows || []).slice().sort(function (a, b) { return (b[4] - a[4]) || (b[B.min] - a[B.min]) || (b[B.pts] - a[B.pts]); });   // starters first, then by minutes
    if (!rows.length) return out;
    var head = el("tr", {}, [el("th", { scope: "col", "class": "l", text: "#" }), el("th", { scope: "col", "class": "l", text: teamName })]
      .concat(cols.map(function (c) { return el("th", { scope: "col", title: c[1], text: c[0] }); })));
    var body = el("tbody", {}, rows.map(function (r) {
      var who = r[r.length - 1] ? el("a", { href: "#/player/" + encodeURIComponent(r[0]) }, [el("span", { text: r[1] })]) : el("span", { "class": "plain", text: r[1] });
      return el("tr", { "class": r[4] ? "starter" : "" }, [el("td", { "class": "l", text: r[2] || "" }), el("td", { "class": "l nm" }, [who, r[3] ? el("small", { "class": "bpos", text: " " + r[3] }) : null])]
        .concat(cols.map(function (c) { return el("td", { text: String(c[2](r)) }); })));
    }));
    var sum = [];
    for (var i = 0; i <= 21; i++) sum.push(0);
    rows.forEach(function (r) { for (var i = 5; i <= 20; i++) sum[i] += r[i] || 0; });
    sum[B.pm] = 0;
    var foot = el("tfoot", {}, [el("tr", {}, [el("td", {}), el("td", { "class": "l", text: "Team" })].concat(cols.map(function (c) { return el("td", { text: c[0] === "+/-" || c[0] === "Min" ? "" : String(c[2](sum)) }); })))]);
    out.appendChild(el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": teamName + " box score, scrolls sideways", style: "margin-top:10px" }, [
      el("table", { "class": "ptable btable" }, [el("thead", {}, [head]), body, foot])]));
    out.appendChild(el("p", { "class": "note", style: "margin-top:6px", text: "Starters are marked with a coloured edge." }));
    return out;
  }
  // team totals for a game, in the order the job writes them
  var TK = ["fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "oreb", "dreb", "ast", "stl", "blk", "to", "pf"];
  function teamTotals(arr) { var o = {}; TK.forEach(function (k, i) { o[k] = arr[i]; }); return o; }
  // the comparison on a game's card: label, away, home, how it is shown, higher is better, away's words, home's words
  function compareRows(A, H) {
    function pc(m, a) { return a ? m / a : null; }
    function show(v) { return (100 * v).toFixed(1) + "%"; }
    return [["Field goals", pc(A.fgm, A.fga), pc(H.fgm, H.fga), show, 1, A.fgm + "-" + A.fga, H.fgm + "-" + H.fga],
      ["Three-pointers", pc(A.tpm, A.tpa), pc(H.tpm, H.tpa), show, 1, A.tpm + "-" + A.tpa, H.tpm + "-" + H.tpa],
      ["Free throws", pc(A.ftm, A.fta), pc(H.ftm, H.fta), show, 1, A.ftm + "-" + A.fta, H.ftm + "-" + H.fta],
      ["Rebounds", A.reb, H.reb, String, 1], ["Offensive rebounds", A.oreb, H.oreb, String, 1], ["Assists", A.ast, H.ast, String, 1],
      ["Steals", A.stl, H.stl, String, 1], ["Blocks", A.blk, H.blk, String, 1], ["Turnovers", A.to, H.to, String, 0], ["Fouls", A.pf, H.pf, String, 0]];
  }
  // the heading over each period of a game's score
  function periodLabel(i, n) {
    var reg = data.periods || 4;
    if (i <= reg) return reg === 2 ? (i === 1 ? "1st" : "2nd") : String(i);
    return n - reg > 1 ? (i - reg) + "OT" : "OT";
  }
  function overtime(lines) { var extra = lines[0].length - (data.periods || 4); return extra > 0 ? "/" + (extra > 1 ? extra : "") + "OT" : ""; }
  function signed(v) { return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1); }
  // the teams table: key, heading, meaning, getter, format, sorts high to low first
  var TCOLS = [
    ["rank", "Rank", "AP poll rank, or place in the standings; college teams outside the poll are numbered from 26 in GOAT ranking order", function (t) { return shownRank(t.id, t.rank); }, String, 0],
    ["name", "Team", "", function (t) { return t.name; }, null, 0],
    ["conf", "Conf", "Conference; for the NBA, division", function (t) { return t.conf; }, function (v) { return v; }, 0],
    ["rec", "W-L", "Games won and lost", function (t) { return t.w + t.l ? t.w / (t.w + t.l) : null; }, null, 1],
    ["conf_rec", "In conf", "Record in conference games; for the NBA, in division games", function (t) { var p = (t.conf_rec || "").split("-"); return p.length === 2 && +p[0] + +p[1] ? +p[0] / (+p[0] + +p[1]) : null; }, null, 1],
    ["ppg", "PPG", "Points per game", function (t) { return t.ppg; }, fmt.d1, 1],
    ["opp_ppg", "Opp PPG", "Points allowed per game. Lower is better", function (t) { return t.opp_ppg; }, fmt.d1, 0],
    ["net", "Net", "Points scored less points allowed, per 100 possessions", function (t) { return t.net; }, signed, 1],
    ["ortg", "Off", "Points scored per 100 possessions", function (t) { return t.ortg; }, fmt.d1, 1],
    ["drtg", "Def", "Points allowed per 100 possessions. Lower is better", function (t) { return t.drtg; }, fmt.d1, 0],
    ["pace", "Pace", "Possessions per game", function (t) { return t.pace; }, fmt.d1, 1],
    ["efg", "eFG%", "Effective field goal percentage: a three counts as one and a half baskets", function (t) { return t.efg; }, fmt.d1, 1],
    ["opp_efg", "Opp eFG%", "Opponents' effective field goal percentage. Lower is better", function (t) { return t.opp_efg; }, fmt.d1, 0],
    ["tov", "TO%", "Turnovers per 100 possessions. Lower is better", function (t) { return t.tov; }, fmt.d1, 0],
    ["orb", "OReb%", "Share of its own misses the team rebounds", function (t) { return t.orb; }, fmt.d1, 1],
    ["ftr", "FT rate", "Free throws tried per 100 field goals tried", function (t) { return t.ftr; }, fmt.d1, 1],
    ["tp_pct", "3P%", "Three-point percentage", function (t) { return t.tp_pct; }, fmt.d1, 1],
    ["power", "Rating", "Where this site's rating (the one behind the odds) places the team in the league", function (t) { return t.power; }, String, 0],
    ["sos_rank", "SOS", "Strength of schedule among the teams shown: 1 is the hardest, by the average rating of the teams played", function (t) { return t.sos_rank; }, String, 0]
  ];
  // a team page's tiles: key, label, format, higher is better
  var TSTATS = [
    ["ppg", "Points per game", fmt.d1, 1], ["opp_ppg", "Points allowed per game", fmt.d1, 0], ["ortg", "Offense per 100 possessions", fmt.d1, 1],
    ["drtg", "Defense per 100 possessions", fmt.d1, 0], ["net", "Net per 100 possessions", signed, 1], ["pace", "Possessions per game", fmt.d1, 1],
    ["efg", "Effective field goal %", fmt.pct, 1], ["opp_efg", "Opponents' effective FG %", fmt.pct, 0], ["tp_pct", "Three-point %", fmt.pct, 1],
    ["ft_pct", "Free throw %", fmt.pct, 1], ["tov", "Turnovers per 100 possessions", fmt.d1, 0], ["opp_tov", "Turnovers forced per 100", fmt.d1, 1],
    ["orb", "Offensive rebound %", fmt.pct, 1], ["reb_g", "Rebounds per game", fmt.d1, 1], ["ast_g", "Assists per game", fmt.d1, 1]
  ];
  var POS_ORDER = ["G", "F", "C"];
  // the standings table of a pro league: heading, meaning, the cell
  function standCols() {
    function avg(t, k) { var n = t.w + t.l; return n ? (t[k] / n).toFixed(1) : ""; }
    return [["W", "Won", function (t) { return t.w; }, 1], ["L", "Lost", function (t) { return t.l; }],
      ["Pct", "Share of games won", function (t) { var n = t.w + t.l; return n ? (t.w / n).toFixed(3).replace(/^0/, "") : ".000"; }],
      ["GB", "Games behind the conference leader", function (t) { return t.gb || "–"; }],
      ["Home", "", function (t) { return (t.rec || {}).home || ""; }], ["Away", "", function (t) { return (t.rec || {}).away || ""; }],
      ["Div", "Record against its own division", function (t) { return (t.rec || {}).div || ""; }], ["Conf", "Record against its own conference", function (t) { return (t.rec || {}).conf || ""; }],
      ["PPG", "Points per game", function (t) { return avg(t, "pf"); }], ["Opp", "Points allowed per game", function (t) { return avg(t, "pa"); }],
      ["Diff", "Average margin", function (t) { var n = t.w + t.l; return n ? signed((t.pf - t.pa) / n) : ""; }],
      ["L10", "Record in the last ten games", function (t) { return (t.rec || {}).last10 || ""; }], ["Streak", "", function (t) { return (t.rec || {}).streak || ""; }]];
  }
  var STAND_CUTS = [6, 10];          // lines under the sixth team (the playoffs) and the tenth (the play-in)
  function groupTitle(g) { return /^(East|West)$/.test(g) ? g + "ern Conference" : g; }
  // ======================================================================================

  // ---- the rankings page ----
  var rankView = "poll", goatAll = false;
  // A team's results against the other ranked teams, in two boxes: "Beat" on the left, "Lost to" on the right.
  function versus(t) {
    function box(label, rows, cls) {
      var opps = rows.map(function (r) {
        return el("a", { "class": "opp", href: "#/team/" + encodeURIComponent(r[3]), title: r[1] }, [el("span", { "class": "n", text: String(r[0]) }), logo(r[3], "sm", r[1]), r[2] > 1 ? el("span", { "class": "x", text: "x" + r[2] }) : null]);
      });
      return el("span", { "class": "vsbox " + cls }, [el("b", { text: label }),
        el("span", { "class": "opps" }, opps.length ? opps : [el("span", { "class": "nil", text: W("rankings.none_yet") })])]);
    }
    return el("span", { "class": "vs" }, [box(W("rankings.beat"), t.beat || [], "beat"), box(W("rankings.lost_to"), t.lost || [], "lostto")]);
  }
  // ---- a pro league's standings, in place of a poll: by division, by conference, the whole league, or the GOAT ranking ----
  var standView = "div";
  // the GOAT ranking's opening line; it says so once the ranking has stopped for the season
  function goatLede() { return W("rankings.lede_goat") + ((data.goat || {}).frozen ? " " + W("rankings.frozen") : ""); }
  function drawStandings() {
    var ol = $("ranks"), bar = $("rank-sort"), head = $("ranks-head"), G = data.goat || {};
    ol.innerHTML = ""; bar.innerHTML = ""; head.innerHTML = ""; ol.hidden = true; head.hidden = true;
    $("goat-out").textContent = "";
    var old = $("pro-standings");
    if (old) old.parentNode.removeChild(old);
    [["div", "Division"], ["conf", W("rankings.button_conf")], ["league", "League"], ["goat", W("rankings.button_goat")]].forEach(function (o) {
      bar.appendChild(el("button", { type: "button", "aria-pressed": String(standView === o[0]), text: o[1], onclick: function () { standView = o[0]; drawStandings(); } }));
    });
    var rows = data.standings || [], holder = el("div", { id: "pro-standings" }), cols = standCols();
    function table(title, list, numbered, cuts) {
      var thead = el("thead", {}, [el("tr", {}, [el("th", { scope: "col", text: "#", title: numbered[1] }), el("th", { scope: "col", "class": "l", text: title })]
        .concat(cols.map(function (c) { return el("th", { scope: "col", title: c[1] || null, text: c[0] }); })))]);
      var body = el("tbody", {}, list.map(function (t, i) {
        return el("tr", { "class": cuts && cuts.indexOf(i) >= 0 ? "cut" : "" }, [el("td", { text: String(numbered[0](t, i)) }),
          el("td", { "class": "l" }, [el("span", { "class": "tcell" }, [logo(t.id), teamA(t.id, (t.place ? t.place + " " : "") + t.name)])])]
          .concat(cols.map(function (c) { return el("td", { "class": c[3] ? "strong" : "", text: String(c[2](t)) }); })));
      }));
      return el("div", { "class": "tablewrap standwrap", tabindex: "0", role: "region", "aria-label": title + " standings, scrolls sideways" }, [el("table", { "class": "ptable stand" }, [thead, body])]);
    }
    function group(key) { var seen = [], by = {}; rows.forEach(function (t) { if (!by[t[key]]) { by[t[key]] = []; seen.push(t[key]); } by[t[key]].push(t); }); return seen.sort().map(function (k) { return [k, by[k]]; }); }
    if (standView === "goat" && G.top) {
      var thead = el("thead", {}, [el("tr", {}, [["GOAT", "", "Place in this site's GOAT ranking"], ["Team", "l", ""], ["Record", "", ""], ["Standings", "", "Place in the league standings"]].concat(G.power ? [["ESPN", "", "Place in ESPN's newest power rankings (" + new Date(G.power.published).toLocaleDateString(undefined, { month: "long", day: "numeric" }) + ")"]] : []).concat([
        ["SOR", "", "Strength of record: a win counts for more the better the team beaten, a loss costs more the weaker the team lost to. 100 is the best in the league"],
        ["SOS", "", "Strength of schedule: how good the teams it has played are, on average. 100 is the hardest in the league"]]).map(function (c) { return el("th", { scope: "col", "class": c[1], title: c[2] || null, text: c[0] }); }))]);
      var body = el("tbody", {}, G.top.map(function (t) {
        var st = rows.filter(function (x) { return x.id === t.id; })[0] || {};
        return el("tr", {}, [el("td", {}, [el("span", { "class": "rk", text: String(t.rank) })]),
          el("td", { "class": "l" }, [el("span", { "class": "tcell" }, [logo(t.id), teamA(t.id, (st.place ? st.place + " " : "") + t.name)])]),
          el("td", { text: t.record || "" }), el("td", { text: t.poll == null || !data.numbered ? "–" : String(t.poll) }), ].concat(G.power ? [el("td", { text: t.power == null ? "–" : String(t.power) })] : []).concat([el("td", { text: String(Math.round(100 * t.factors[0])) }), el("td", { text: String(Math.round(100 * (t.factors[3] || 0))) })]));
      }));
      holder.appendChild(el("div", { "class": "tablewrap standwrap", tabindex: "0", role: "region", "aria-label": "GOAT ranking, scrolls sideways" }, [el("table", { "class": "ptable stand" }, [thead, body])]));
    } else if (standView === "league") {
      holder.appendChild(table(data.league_name, rows, [function (t) { return t.rank; }, "Place in the league"]));
    } else if (standView === "conf") {
      group("group").forEach(function (g) {
        var list = g[1].slice().sort(function (a, b) { return (a.seed || 99) - (b.seed || 99) || a.rank - b.rank; });
        holder.appendChild(table(groupTitle(g[0]), list, [function (t, i) { return t.seed || i + 1; }, "Seed as things stand"], STAND_CUTS));
      });
    } else {
      group("conf").forEach(function (g) {
        var list = g[1].slice().sort(function (a, b) { return a.rank - b.rank; });
        holder.appendChild(table(g[0], list, [function (t, i) { return i + 1; }, "Place in the division"]));
      });
    }
    ol.parentNode.insertBefore(holder, ol);
    $("rank-lede").textContent = standView === "goat" ? goatLede() : data.poll.through ? W("rankings.lede", { poll: data.poll.name, date: day(data.poll.through).toLocaleDateString(undefined, { month: "long", day: "numeric" }) }) : W("rankings.lede_before");
    $("rank-note").textContent = standView === "goat" ? W("rankings.note_goat") : standView === "conf" ? W("rankings.note_conf") : W("rankings.note");
    $("goat-note").textContent = "";
  }

  function drawRanks() {
    if (PRO()) return drawStandings();
    var ol = $("ranks"), bar = $("rank-sort"), head = $("ranks-head"), G = data.goat || {}, others = data.polls || {};
    if (NOPOLL()) rankView = "goat";
    else if (rankView !== "poll" && rankView !== "goat" && !others[rankView]) rankView = "poll";
    var goatView = rankView === "goat" && G.top, other = others[rankView];
    ol.innerHTML = ""; bar.innerHTML = ""; head.innerHTML = "";
    (NOPOLL() ? [] : [["poll", W("rankings.button_poll")]]).concat(Object.keys(others).map(function (k) { return [k, others[k].label]; })).concat([["goat", W("rankings.button_goat")]]).forEach(function (o) {
      bar.appendChild(el("button", { type: "button", "aria-pressed": String(rankView === o[0]), text: o[1], onclick: function () { rankView = o[0]; drawRanks(); } }));
    });
    (goatView ? ["GOAT", "Team", "Record", "AP"] : [other ? "#" : "AP", "Team", "Record", "Change"]).forEach(function (h) { head.appendChild(el("span", { text: h })); });
    // the Beat and Lost to boxes belong to the GOAT ranking only; on a wide screen they sit in the row, under these two headings
    if (goatView) {
      head.appendChild(el("span", { "class": "wide beat", text: W("rankings.beat") }));
      head.appendChild(el("span", { "class": "wide lostto", text: W("rankings.lost_to") }));
    }
    function teamLink(id, name) { return teamA(id, name, "nm"); }
    function pollRow(t, withBoxes) {
      var move = t.prev == null ? ["new", "up", "not ranked last week"] : t.prev > t.rank ? ["▲" + (t.prev - t.rank), "up", "up " + (t.prev - t.rank) + " from last week"]
        : t.prev < t.rank ? ["▼" + (t.rank - t.prev), "", "down " + (t.rank - t.prev) + " from last week"] : ["", "", ""];
      return el("li", {}, [el("span", { "class": "rk", text: String(t.rank) }), el("span", { "class": "who" }, [logo(t.id), teamLink(t.id, t.name)]), el("span", { "class": "rec", text: t.record || "" }),
        el("span", { "class": "mv " + move[1], text: move[0], "aria-label": move[2] || null }), withBoxes ? versus(t) : null]);
    }
    if (goatView) {
      (goatAll ? G.top : G.top.slice(0, 25)).forEach(function (t) {
        ol.appendChild(el("li", {}, [el("span", { "class": "rk", text: String(t.rank) }), el("span", { "class": "who" }, [logo(t.id), teamLink(t.id, t.name)]),
          el("span", { "class": "rec", text: t.record || "" }),
          el("span", { "class": "mv", text: t.poll == null ? "–" : String(t.poll), "aria-label": t.poll == null ? "not in the AP poll" : "AP poll " + t.poll }),
          versus(t)]));
      });
    } else if (other) other.teams.forEach(function (t) { ol.appendChild(pollRow(t, false)); });
    else data.poll.teams.forEach(function (t) { ol.appendChild(pollRow(t, false)); });
    function nice(d) { return day(d).toLocaleDateString(undefined, { month: "long", day: "numeric" }); }
    $("rank-lede").textContent = NOPOLL() ? W("rankings.lede_nopoll") : goatView ? goatLede() : other ? W("rankings.lede_other", { poll: other.name, date: nice(other.date) }) : W("rankings.lede", { poll: data.poll.name, date: nice(data.poll.date) });
    $("rank-note").textContent = goatView ? W("rankings.note_goat") : other ? W("rankings.note_other") : W("rankings.note");
    $("goat-note").textContent = !goatView ? "" : "Every " + ALL() + " team is ranked on four things: its place in the AP poll (50%), strength of schedule (20%: how good the teams it has played are, on average), strength of record (20%: a win counts for more the better the team beaten, a loss costs more the weaker the team lost to), and head to head (10%: a team is ranked above one it has the better of when the two are that close on the rest). " +
      "Before anyone has played, the order is last season's ratings. " +
      (NOPOLL() ? "" : "Elsewhere on the site, teams outside the poll are numbered from 26 in this order. Among the poll's 25 teams, the poll ranks a team below one it has beaten " + G.poll_wrong + " times; the GOAT ranking does " + G.goat_wrong + " times.");
    var out = $("goat-out");
    out.textContent = "";
    if (goatView && G.top.length > 25) out.appendChild(el("button", { type: "button", "class": "morebtn",
      text: goatAll ? W("rankings.show_top") : W("rankings.show_all", { n: G.top.length }), onclick: function () { goatAll = !goatAll; drawRanks(); } }));
  }

  // ---- one game ----
  // [away, home] chances as whole percentages that add up to 100; never shown as 0 or 100
  function pct(home) { var n = Math.min(99, Math.max(1, Math.round(home * 100))); return [(100 - n) + "%", n + "%"]; }
  function oddsNote() {
    var t = data.odds_tested;
    return " Percentages are each team's chance of winning, from this site's own ratings of results, opponents and home advantage; they are not betting lines." +
      (t ? " Tested on " + t.matches.toLocaleString("en-US") + " past games, the favorite won " + Math.round(t.favorite_won * 100) + "% of the time." : "");
  }
  function liveTag() { return el("span", { "class": "livetag" }, [el("span", { "class": "dot", "aria-hidden": "true" }), W("games.live")]); }
  function gameState(g) {     // the score and state now: from ESPN while the game is on (g.live), otherwise as stored
    var L = g.live;
    return { fin: L ? L.state === "post" : g.state === "final", live: L ? L.state === "in" : g.state === "live",
      as: L ? L.away : g.away.score, hs: L ? L.home : g.home.score, detail: L ? L.detail : g.detail,
      lines: L && L.lines ? L.lines : [g.away.lines || [], g.home.lines || []], extra: L ? L.extra : g.extra };
  }
  function row(g, dated) {      // `dated`: say which day, for a list that is not grouped by day
    var s = gameState(g), fin = s.fin, live = s.live, as = s.as, hs = s.hs, scored = (fin || live) && as != null && hs != null;
    var awayWon = fin && scored && as > hs, homeWon = fin && scored && hs > as;
    var t = g.start ? new Date(g.start * 1000) : null;
    var note = !g.live && g.state === "other" ? (g.note ? g.note.charAt(0).toUpperCase() + g.note.slice(1) : "Not played") : "";
    var when = fin ? "Final" + overtime(s.lines) : live ? s.detail || "In progress" : note ? note : t && !isNaN(t) ? t.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "Time not set";
    function team(side, x, lost, won) {
      var kids = [logo(x.id), teamA(x.id, x.name, "name"), rankTag(x.rank, x.id)];
      if (side === "home") kids.reverse();
      return el("span", { "class": "team " + side + (lost ? " lost" : "") + (won ? " won" : "") }, kids);
    }
    var mid = scored
      ? el("span", { "class": "mid", "aria-label": g.away.name + " " + as + ", " + g.home.name + " " + hs }, [
          el("span", { "class": "sa " + (homeWon ? "l" : "w"), text: String(as) }), el("span", { "class": "dash", text: "–" }), el("span", { "class": "sh " + (awayWon ? "l" : "w"), text: String(hs) })])
      : g.p != null && !fin
        // not started: each team's chance of winning, the favorite in bold
        ? el("span", { "class": "mid odds", "aria-label": g.away.name + " " + pct(g.p)[0] + ", " + g.home.name + " " + pct(g.p)[1] + " chance of winning" }, [
            el("span", { "class": "sa " + (g.p > 0.5 ? "l" : "w"), text: pct(g.p)[0] }), el("span", { "class": "dash", text: g.neutral ? "vs" : "at" }),
            el("span", { "class": "sh " + (g.p < 0.5 ? "l" : "w"), text: pct(g.p)[1] })])
        : el("span", { "class": "mid at", text: g.neutral ? "vs" : "at" });
    if (LINES && g.line && g.line[0] && (mid.classList.contains("at") || mid.classList.contains("odds"))) mid = lineMid(g);
    var more = [];
    if (g.round || g.series) more.push(el("span", { "class": "bowl", text: [g.round, g.series].filter(Boolean).join(": ") }));
    if (!fin && !note) {
      more.push(g.tv && g.tv.length ? el("span", { "class": "watch" }, [el("span", { "class": "sr", text: "Watch on " }), g.tv.join(", ")])
        : g.start ? el("span", { "class": "watch none", text: W("games.no_broadcast") }) : null);
    }
    var go = note && !fin && !live ? null : "#/game/" + g.id;       // the row itself opens the game: its preview, or its box score once it has started
    if (dated === true && !live) when = short(g.date) + (when === "Time not set" ? "" : " · " + when);
    var unplayed = !fin && !live && !note;
    return rowLink(el("li", { "class": "game" + (!PRO() && g.away.rank && g.home.rank ? " both" : "") + (live ? " on" : "") + (unplayed ? " ahead" : ""), "data-id": g.id, "data-dated": dated === true ? "" : null, "data-go": go }, [
      live ? el("span", { "class": "when live" }, [liveTag(), " " + (when === "In progress" ? "" : when)]) : el("span", { "class": "when", text: when }),
      team("away", g.away, homeWon, awayWon), mid, team("home", g.home, awayWon, homeWon),
      el("span", { "class": "more" }, more)]));
  }

  // ---- live scores ----
  // The site is rebuilt a few times a day, so while a game is on, the page reads
  // ESPN's public scoreboard itself and updates that game's row in place.
  var liveTimer = null, liveHooks = [];
  function dueGames(now) {       // games that could be under way: from 15 minutes before the start until some hours after
    var hours = data.live_hours || 4;
    return data.games.filter(function (g) {
      return g.start && g.state !== "final" && g.state !== "other" && !(g.live && g.live.state === "post") && now >= g.start - 900 && now <= g.start + hours * 3600;
    });
  }
  function readLive(e) {
    var c = (e.competitions || [{}])[0], st = (e.status || {}).type || {}, out = { state: st.state, detail: st.shortDetail || st.detail || "", lines: [[], []], extra: [null, null] };
    (c.competitors || []).forEach(function (x) {
      var i = x.homeAway === "home" ? 1 : 0;
      out[x.homeAway] = x.score === "" || x.score == null ? null : +x.score;
      out.lines[i] = (x.linescores || []).map(function (l) { return Math.round(l.value); });
      if (x.hits != null) out.extra[i] = [x.hits, x.errors];
    });
    return out;
  }
  function pollLive() {
    clearTimeout(liveTimer);
    if (!data.live_feed) return;
    var now = Date.now() / 1000, due = dueGames(now), every = (data.live_seconds || 30) * 1000;
    if (document.hidden) return;                       // picks up again when the tab is shown
    if (!due.length) {                                 // nothing on: look again when the next game is close
      var next = data.games.filter(function (g) { return g.start && g.state !== "final" && g.start - 900 > now; })
        .map(function (g) { return g.start - 900; }).sort(function (a, b) { return a - b; })[0];
      if (next) liveTimer = setTimeout(pollLive, Math.min(Math.max((next - now) * 1000, every), 6 * 3600 * 1000));
      showLiveNote(false);
      return;
    }
    var days = {};
    due.forEach(function (g) { days[g.day] = 1; });
    Promise.all(Object.keys(days).map(function (d) {
      return fetch(data.live_feed.replace("{day}", d), { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : { events: [] }; }).catch(function () { return { events: [] }; });
    })).then(function (docs) {
      var byId = {};
      docs.forEach(function (doc) { (doc.events || []).forEach(function (e) { byId[e.id] = e; }); });
      var anyLive = false;
      due.forEach(function (g) {
        var e = byId[g.id];
        if (!e) return;
        var live = readLive(e);
        if (live.state !== "in" && live.state !== "post") return;                // not started yet
        if (live.state === "in") anyLive = true;
        if (JSON.stringify(live) === JSON.stringify(g.live)) return;
        g.live = live;
        Array.prototype.forEach.call(document.querySelectorAll('.game[data-id="' + g.id + '"]'), function (li) { li.parentNode.replaceChild(row(g, li.hasAttribute("data-dated")), li); });
        liveHooks.forEach(function (fn) { fn(g); });
      });
      showLiveNote(anyLive);
    }).then(function () { liveTimer = setTimeout(pollLive, every); });
  }
  function showLiveNote(on) {
    var n = $("live-note");
    n.hidden = !on;
    if (on) n.textContent = "Live scores from ESPN, refreshed every " + (data.live_seconds || 30) + " seconds.";
  }
  document.addEventListener("visibilitychange", function () { if (data && !document.hidden) pollLive(); });

  function listInto(holder, games, newestFirst, asGiven) {
    var days = {}, order = [];
    games.forEach(function (g) { if (!days[g.date]) { days[g.date] = []; order.push(g.date); } days[g.date].push(g); });
    if (newestFirst) order.reverse();
    else if (!asGiven && order.indexOf(today) > 0) { order.splice(order.indexOf(today), 1); order.unshift(today); }   // today's games first
    order.forEach(function (d) {
      holder.appendChild(el("h3", { "class": "day" + (d === today ? " today" : ""), text: (d === today ? "Today, " : d === addDays(today, 1) ? "Tomorrow, " : d === addDays(today, -1) ? "Yesterday, " : "") + long(d) }));
      holder.appendChild(el("ol", { "class": "games" }, days[d].map(row)));
    });
  }

  // ---- the games page: three days at a time. Opened on today, they are today, tomorrow and yesterday. ----
  function draw() {
    var holder = $("list"), nav = $("nav"), head = $("h-list");
    holder.innerHTML = ""; nav.innerHTML = "";
    setHead("games", "games");
    var shown = isAll() ? data.games : data.games.filter(function (g) { return g.away.rank || g.home.rank; });
    var teamsHere = isAll() ? data.fbs.map(function (x) { var r = rankOf(x[0]); return { id: x[0], name: x[1], rank: shownRank(x[0], r && r.rank) }; })
        .sort(function (a, b) { return (a.rank || 9999) - (b.rank || 9999) || a.name.localeCompare(b.name); })
      : data.poll.teams;
    if (state.team && !teamsHere.some(function (x) { return x.id === state.team; })) state.team = null;
    nav.appendChild(scopeSwitch(draw));
    // which side is which: over the columns on a wide screen, beside the two lines on a phone
    holder.appendChild(el("div", { "class": "hahead", "aria-hidden": "true" }, [el("span"), el("span", { "class": "ha away", text: W("games.away") }),
      el("span"), el("span", { "class": "ha home", text: W("games.home") }), el("span")]));
    var pick = el("select", { id: "f-team", "aria-label": "Show one team", onchange: function () { state.team = pick.value || null; draw(); } },
      [el("option", { value: "", text: W("games.all_teams" + FBS()) })].concat(teamsHere.map(function (x) {
        return el("option", { value: x.id, text: (x.rank ? x.rank + ". " : "") + x.name, selected: x.id === state.team });
      })));
    nav.appendChild(pick);

    if (state.team) {
      var t = teamsHere.filter(function (x) { return x.id === state.team; })[0];
      var mine = data.games.filter(function (g) { return g.away.id === t.id || g.home.id === t.id; });
      head.innerHTML = "";
      head.appendChild(logo(t.id) || document.createTextNode(""));
      head.appendChild(document.createTextNode(" " + (t.rank && !PRO() ? "No. " + t.rank + " " : "") + t.name + ", whole season"));
      var next = mine.filter(function (g) { return g.state !== "final" && g.date >= today; }), done = mine.filter(function (g) { return g.state === "final" || g.date < today; });
      if (next.length) { holder.appendChild(el("p", { "class": "note", text: next.length + " still to play, " + done.length + " played." + oddsNote() })); listInto(holder, next); if (next.some(function (g) { return g.p != null; })) holder.appendChild(keyline()); }
      if (done.length) { holder.appendChild(el("h3", { "class": "day", text: "Already played, newest first" })); listInto(holder, done, true); }
      if (!mine.length) holder.appendChild(el("p", { "class": "empty", text: "No games are listed for " + t.name + " this season." }));
      return;
    }

    var days = shown.map(function (g) { return g.date; }).sort(), firstDay = days[0], lastDay = days[days.length - 1];
    if (!days.length) {
      head.textContent = "No games yet";
      holder.appendChild(el("p", { "class": "empty", text: NOPOLL() || isAll() ? "No games are listed yet this season." : "No ranked team has a game listed yet. Choose " + W("scope.fbs") + " to see every game." }));
      return;
    }
    // one day at a time, picked from the calendar: every day that has a game
    var items = dayItems(shown);
    state.day = pickDay(items, state.day);
    var mid = state.day, w = mid, end = mid, after = null;
    var games = shown.filter(function (g) { return g.date === mid; });
    head.textContent = (mid === today ? "Today, " : "") + long(mid);
    holder.insertBefore(calendar(items, mid, function (d) { state.day = d; draw(); }), holder.firstChild);
    if (!games.length) {
      holder.appendChild(el("p", { "class": "empty", text: (isAll() ? "No games" : "No ranked team has a game") + " on this day." +
        (after && mid <= today ? " The next " + (after === lastDay && days.length === 1 ? "game is" : "games are") + " on " + long(after) + "." : " Try earlier or later days.") }));
      return;
    }
    listInto(holder, games, false, true);
    var both = games.filter(function (g) { return g.away.rank && g.home.rank; }).length;
    if (PRO()) holder.appendChild(el("p", { "class": "note", text: games.length + (games.length === 1 ? " game" : " games") + " on this day. The visiting team is on the left, and the channel is on the right." + (data.numbered ? " Numbers are places in the league standings." : "") + " Choose a team to see its whole season." }));
    else holder.appendChild(el("p", { "class": "note", text: games.length + (games.length === 1 ? " game" : " games") + " on this day" + (both ? ", " + both + " of them between two ranked teams (marked with a coloured edge)" : "") +
      ". The visiting team is on the left, and the channel is on the right." + (data.numbered ? " Numbers are this week's AP rankings, also for earlier weeks; a team outside the poll is numbered from 26 by the GOAT ranking." : "") + " Choose a team to see its whole season." }));
    if (LINES && games.some(function (g) { return g.line && g.line[0] && g.state !== "final"; })) holder.appendChild(linesNote(games));
    if (games.some(function (g) { return g.p != null && g.state !== "final"; })) { var said = holder.lastElementChild; holder.insertBefore(keyline(), said && said.classList.contains("note") ? said : null); holder.appendChild(el("p", { "class": "note", text: oddsNote().trim() })); }
  }

  // ---- players ----
  var pstate = { pos: "", team: "", q: "", all: false, sort: "impact_g", dir: -1 };
  var rosters = {};
  function loadRoster(which) {     // players rated against the top 25, or against the whole league (a pro league has the one list)
    which = PRO() || NOPOLL() ? "fbs" : which || scope;
    if (rosters[which]) { roster = rosters[which]; return Promise.resolve(roster); }
    return fetch(which === "fbs" ? "players_fbs.json" : "players.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        d.players.forEach(function (p) {
          if (p.ph && data.photo) p.photo = data.photo.replace("{player}", encodeURIComponent(p.id));
          if (!p.pct) p.pct = [];
        });
        rosters[which] = d; roster = d; return d;
      });
  }
  function regularNote() {
    var w = roster.weights || {};
    return "A regular has played in at least " + Math.round(100 * (w.regular_games || 0.4)) + "% of his team's games" + (w.regular_words ? " " + w.regular_words : w.regular_minutes ? " and averages " + w.regular_minutes + " minutes or more" : "");
  }
  function drawPlayers() {
    var bar = $("p-filters"), holder = $("p-list");
    bar.innerHTML = ""; holder.innerHTML = "";
    setHead("players", "players");
    holder.appendChild(el("p", { "class": "empty", text: "Loading the players…" }));
    loadRoster().then(function () {
      bar.appendChild(scopeSwitch(function () { pstate.team = ""; pstate.limit = 200; drawPlayers(); }));
      function pick(label, value, options, set) {
        var s = el("select", { "aria-label": label, onchange: function () { set(s.value); pstate.limit = 200; table(); } },
          options.map(function (o) { return el("option", { value: o[0], text: o[1], selected: o[0] === value }); }));
        return s;
      }
      bar.appendChild(pick("Position", pstate.pos, [["", "All positions"]].concat(POS_FILTER), function (v) {
        pstate.pos = v;
        if (!pcols(v).some(function (c) { return c[0] === pstate.sort; })) { pstate.sort = "impact_g"; pstate.dir = -1; }
      }));
      bar.appendChild(pick("Team", pstate.team, [["", W("games.all_teams" + FBS())]].concat(roster.teams.slice().sort(function (a, b) { return (shownRank(a.id, a.rank) || 9999) - (shownRank(b.id, b.rank) || 9999) || a.name.localeCompare(b.name); })
        .map(function (t) { var n = shownRank(t.id, t.rank); return [t.id, (n ? n + ". " : "") + t.name]; })), function (v) { pstate.team = v; }));
      var q = el("input", { type: "search", placeholder: "Find a player", "aria-label": "Find a player", value: pstate.q, oninput: function () { pstate.q = q.value; pstate.limit = 200; table(); } });
      bar.appendChild(q);
      var chk = el("input", { type: "checkbox", id: "p-all", checked: pstate.all, onchange: function () { pstate.all = chk.checked; table(); } });
      bar.appendChild(el("label", { "class": "check", "for": "p-all" }, [chk, " Include part-time players"]));

      function table() {
        holder.innerHTML = "";
        if (!roster.players.length) { holder.appendChild(el("p", { "class": "empty", text: W("players.none_yet") })); return; }
        var cols = pcols(pstate.pos), needle = pstate.q.trim().toLowerCase(), col = cols.filter(function (c) { return c[0] === pstate.sort; })[0] || cols[6];
        var rows = roster.players.filter(function (p) {
          return (pstate.all || p.regular || needle) && (!pstate.pos || posMatch(p, pstate.pos)) && (!pstate.team || p.team_id === pstate.team) &&
            (!needle || p.name.toLowerCase().indexOf(needle) >= 0);
        }).sort(function (a, b) {
          var x = col[3](a), y = col[3](b);
          if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
          return typeof x === "string" ? pstate.dir * x.localeCompare(y) : pstate.dir * (x - y);
        });
        if (!rows.length) { holder.appendChild(el("p", { "class": "empty", text: "No player matches. Clear the search or choose all positions." })); return; }
        var head = el("tr", {}, cols.map(function (c) {
          var on = col[0] === c[0];
          return el("th", { scope: "col", "class": c[0] === "name" || c[0] === "team" ? "l" : "", "aria-sort": on ? (pstate.dir > 0 ? "ascending" : "descending") : null }, [
            el("button", { type: "button", title: c[2] || null, text: c[1] + (on ? (pstate.dir > 0 ? " ▲" : " ▼") : ""),
              onclick: function () { if (on) pstate.dir = -pstate.dir; else { pstate.sort = c[0]; pstate.dir = c[5] ? -1 : 1; } table(); } })]);
        }));
        var total = rows.length, limit = pstate.limit || 200;
        rows = rows.slice(0, limit);
        var body = el("tbody", {}, rows.map(function (p) {
          return el("tr", {}, cols.map(function (c) {
            if (c[0] === "name") return el("td", { "class": "l nm" }, [el("a", { href: "#/player/" + encodeURIComponent(p.id) }, [el("span", { text: p.name })])]);
            if (c[0] === "team") return el("td", { "class": "l" }, [el("span", { "class": "tcell tm" }, [logo(p.team_id), teamA(p.team_id, p.team)])]);
            var v = c[3](p);
            return el("td", { "class": (c[0] === "impact_g" ? "strong " : "") + (col[0] === c[0] ? "sorted" : ""), text: v == null ? (c[0] === "rank" ? "–" : "") : c[4](v) });
          }));
        }));
        holder.appendChild(el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": "Players table, scrolls sideways" }, [
          el("table", { "class": "ptable pltable" }, [el("thead", {}, [head]), body])]));
        if (total > rows.length) holder.appendChild(el("p", { "class": "more" }, [el("button", { type: "button", "class": "morebtn", text: "Show " + Math.min(400, total - rows.length) + " more of " + total,
          onclick: function () { pstate.limit = limit + 400; table(); } })]));
        holder.appendChild(el("p", { "class": "note", text: total.toLocaleString("en-US") + " players" + (roster.through ? ", through games of " + short(roster.through) : "") +
          ". " + regularNote() + "; only regulars are ranked. Choose a name for his card, or a column heading to sort." }));
        holder.appendChild(el("p", { "class": "note", text: W("players.note" + FBS()) }));
      }
      table();
    }).catch(function () {
      holder.innerHTML = "";
      holder.appendChild(el("p", { "class": "empty", text: "The players could not be loaded. Reload the page to try again." }));
    });
  }
  function posMatch(p, pos) { return p.pos === pos || (p.group && p.group === pos); }

  // His height, weight, class and hometown, from his team's roster.
  function bioLine(b) {
    if (!b) return null;
    var bits = [];
    if (b.ht) { var h = b.ht.split("-"); bits.push(h[0] + "′" + h[1] + "″"); }
    if (b.wt) bits.push(b.wt + " lb");
    if (b.bt) bits.push(b.bt);
    if (b.yr) bits.push(b.yr);
    if (b.home) bits.push(b.home);
    if (b.col) bits.push(b.col);
    return bits.length ? el("p", { "class": "pc-bio", text: bits.join(" · ") }) : null;
  }

  // ---- a card's extras, from cards/<team>.json: season highs, against ranked teams, career, every game ----
  var cardFiles = {};
  function loadCards(team) {
    if (!cardFiles[team]) cardFiles[team] = fetch("cards/" + encodeURIComponent(team) + ".json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
    cardFiles[team].catch(function () { delete cardFiles[team]; });
    return cardFiles[team];
  }
  function cardExtras(box, p) {
    loadCards(p.team_id).then(function (file) {
      var c = file[p.id];
      box.innerHTML = "";
      if (!c) return;
      function opp(id, name) { return el("span", { "class": "tcell tm" }, [rankTag((rankOf(id) || {}).rank, id), logo(id), teamA(id, name)]); }
      if (c.highs.length) {
        var highs = el("section", { "class": "pc-sec" }, [el("h2", { text: "Season highs" }),
          el("dl", { "class": "totals highs" }, c.highs.map(function (h) {
            return el("div", {}, [el("dt", { text: h[0] }), el("dd", { text: fmt.n(h[1]) }),
              el("a", { "class": "hwhen", href: "#/game/" + h[5], text: "vs " + h[3] + ", " + short(h[4]) })]);
          }))]);
        if (c.marks && c.marks.length) highs.appendChild(el("p", { "class": "pc-secnote", text: c.marks.map(function (m) { return m[1] + " " + (m[1] === 1 ? m[0].replace(/s$/, "") : m[0]); }).join(", ") + "." }));
        box.appendChild(highs);
      }
      var cols = logCols(p);
      if (c.ranked) {
        var R = c.ranked, row0 = [0, 0, 0, 0, 0, 0].concat(R.tot);
        var splits = [["Games", R.gp], ["Team's record", R.w + "-" + (R.gp - R.w)]].concat(cols.map(function (k) { return [k[1] || k[0], k[2](row0)]; }));
        box.appendChild(el("section", { "class": "pc-sec" }, [el("h2", { text: "Against ranked teams" }),
          el("p", { "class": "pc-secnote", text: "His games this season against teams now in the top 25, added up." }),
          el("dl", { "class": "totals" }, splits.map(function (x) { return el("div", {}, [el("dt", { text: x[0] }), el("dd", { text: String(x[1]) })]); }))]));
      }
      // his career, as ESPN lists it: one table for each kind of number
      var car = el("section", { "class": "pc-sec" }, [el("h2", { text: "Career" })]);
      (c.career || []).forEach(function (part) {
        var head = el("tr", {}, [el("th", { scope: "col", "class": "l", text: "Season" }), el("th", { scope: "col", "class": "l", text: "Team" })]
          .concat(part[1].map(function (h) { return el("th", { scope: "col", text: h }); })));
        var body = part[2].map(function (s) {
          return el("tr", { "class": String(s[0]) === String(data.season_label || data.season) ? "now" : "" }, [el("th", { scope: "row", "class": "l", text: String(s[0]) }), el("td", { "class": "l", text: s[1] })]
            .concat(s.slice(2).map(function (v) { return el("td", { text: v }); })));
        });
        var foot = part[3] && part[3].length ? el("tfoot", {}, [el("tr", {}, [el("th", { scope: "row", "class": "l", text: "Career" }), el("td", { "class": "l" })]
          .concat(part[3].map(function (v) { return el("td", { text: v }); })))]) : null;
        car.appendChild(el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": p.name + " career " + part[0].toLowerCase() + ", scrolls sideways" }, [
          el("table", { "class": "ptable btable cartable" }, [el("caption", { text: part[0] }), el("thead", {}, [head]), el("tbody", {}, body), foot])]));
      });
      car.appendChild(el("p", { "class": "note", text: (c.career || []).length ? W("players.career_note") : W("players.career_wait") }));
      box.appendChild(car);
      if (c.games.length) {
        var all = false, log = el("section", { "class": "pc-sec" }, [el("h2", { text: "Game by game" })]);
        var table = function () {
          while (log.childNodes.length > 1) log.removeChild(log.lastChild);
          var rows = all ? c.games : c.games.slice(0, 10);
          var lhead = el("tr", {}, [el("th", { scope: "col", "class": "l", text: "Date" }), el("th", { scope: "col", "class": "l", text: "Opponent" }), el("th", { scope: "col", "class": "l", text: "Result" })]
            .concat(cols.map(function (k) { return el("th", { scope: "col", title: k[1] || null, text: k[0] }); })));
          var body = el("tbody", {}, rows.map(function (r) {
            return el("tr", {}, [el("td", { "class": "l", text: short(r[1]) }), el("td", { "class": "l" }, [el("span", { "class": "tcell tm" }, [r[4] ? "vs" : "at"].concat([opp(r[2], r[3])]))]),
              el("td", { "class": "l" }, [el("a", { href: "#/game/" + r[0], "class": "res " + (r[5].charAt(0) === "W" ? "w" : "l"), text: r[5] || "Box score" })])]
              .concat(cols.map(function (k) { return el("td", { text: String(k[2](r)) }); })));
          }));
          log.appendChild(el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": p.name + " game by game, scrolls sideways" }, [
            el("table", { "class": "ptable tptable logtable" }, [el("thead", {}, [lhead]), body])]));
          if (c.games.length > 10) log.appendChild(el("p", { "class": "more" }, [el("button", { type: "button", "class": "morebtn",
            text: all ? "Show the latest 10 only" : "Show all " + c.games.length + " games", onclick: function () { all = !all; table(); } })]));
        };
        table();
        box.appendChild(log);
      }
    }).catch(function () {
      box.innerHTML = "";
      box.appendChild(el("p", { "class": "empty", text: "His games and career could not be loaded." }));
    });
  }

  // ---- links to a player's own pages (Instagram, X, TikTok), where they are known ----
  var SOCIAL = { instagram: ["Instagram", "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 8.2a3.2 3.2 0 1 1 0-6.4 3.2 3.2 0 0 1 0 6.4zM17.3 5.5a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4zM7.5 2h9A5.5 5.5 0 0 1 22 7.5v9a5.5 5.5 0 0 1-5.5 5.5h-9A5.5 5.5 0 0 1 2 16.5v-9A5.5 5.5 0 0 1 7.5 2zm0 1.8A3.7 3.7 0 0 0 3.8 7.5v9a3.7 3.7 0 0 0 3.7 3.7h9a3.7 3.7 0 0 0 3.7-3.7v-9a3.7 3.7 0 0 0-3.7-3.7z"],
    twitter: ["X", "M17.8 3h3.1l-6.8 7.7L22 21h-6.2l-4.9-6.4L5.3 21H2.2l7.2-8.3L1.8 3h6.4l4.4 5.8L17.8 3zm-1.1 16.2h1.7L7.4 4.7H5.6l11.1 14.5z"],
    tiktok: ["TikTok", "M16.6 2h-3.3v13.4a2.9 2.9 0 1 1-2.9-2.9c.3 0 .6 0 .9.1V9.2a6.3 6.3 0 1 0 5.3 6.2V8.6a7.9 7.9 0 0 0 4.4 1.4V6.7a4.6 4.6 0 0 1-4.4-4.7z"] };
  function socialLinks(b, name) {
    if (!b || !b.social) return null;
    var out = Object.keys(SOCIAL).filter(function (k) { return b.social[k]; }).map(function (k) {
      var a = el("a", { href: b.social[k], target: "_blank", rel: "noopener noreferrer", title: name + " on " + SOCIAL[k][0], "aria-label": name + " on " + SOCIAL[k][0] });
      a.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="' + SOCIAL[k][1] + '"/></svg>';
      return a;
    });
    return out.length ? el("p", { "class": "pc-social" }, out) : null;
  }

  function drawCard(id) {
    var holder = $("card");
    holder.innerHTML = "";
    // his team is not known until the players are loaded: look in the whole league first
    loadRoster("fbs").then(function (all) {
      var q = all.players.filter(function (x) { return x.id === id; })[0];
      if (!q) { holder.appendChild(el("p", { "class": "empty", text: "There is no card for that player. He may not have played yet this season." })); return; }
      var ranked = !!rankOf(q.team_id);
      return loadRoster(ranked ? scope : "fbs").then(function () {
        var p = roster.players.filter(function (x) { return x.id === id; })[0] || q;
        holder.appendChild(el("div", { "class": "nav filters" }, [scopeSwitch(function () { drawCard(id); }, !ranked)]));
        if (!ranked && !PRO() && !NOPOLL()) holder.appendChild(el("p", { "class": "note", text: "His team is not in the top 25, so he is measured against all of " + ALL() + "." }));
        document.title = p.name + " | " + data.site;
        var kind = p.group || p.pos, many = POS_MANY[kind] || "players", nPos = roster.pos_regulars[kind] || 0;
        var art = el("article", { "class": "pcard" });
        art.appendChild(el("header", { "class": "pc-head" }, [
          face(p, "big"),
          el("div", { "class": "pc-id" }, [
            el("h1", { text: p.name }),
            el("p", { "class": "pc-team" }, [logo(p.team_id), teamA(p.team_id, p.team), p.team_rank && data.numbered ? el("span", { text: PRO() ? " (" + ordinal(p.team_rank) + " in the standings)" : " (ranked " + p.team_rank + ")" }) : null]),
            el("p", { text: (p.num != null ? "No. " + p.num + ", " : "") + (POS_ONE[p.pos] || p.pos) }),
            bioLine(p.bio),
            el("p", { "class": "pc-sub", text: p.gp + (p.gp === 1 ? " game" : " games") + (statLine(p) ? ": " + statLine(p) : "") }), socialLinks(p.bio, p.name)]),
          el("div", { "class": "pc-rank" }, p.regular ? [
            el("b", { text: ordinal(p.rank) }), el("span", { text: "of " + roster.regulars.toLocaleString("en-US") + " regulars" }),
            el("span", { text: ordinal(p.pos_rank) + " of " + nPos + " " + many })] : [
            el("b", { text: "–" }), el("span", { text: "Not ranked: too little playing time so far" })])
        ]));
        art.appendChild(el("p", { "class": "pc-impact" }, [el("b", { text: fmt.s1(p.impact) }), " " + IMPACT_WORDS + " this season, ", el("b", { text: fmt.s2(val(p, "impact_g")) }), " per " + IMPACT_UNIT + "."]));
        CARD.forEach(function (sec) {
          var rows = sec[1].filter(function (m) { return pctOf(p, m[0]) != null; });
          if (!rows.length) return;
          var box = el("section", { "class": "pc-sec" }, [el("h2", { text: sec[0] })]);
          if (sec === CARD[0]) box.appendChild(el("p", { "class": "pc-secnote", text: "Against " + POOL() + " at his position." }));
          rows.forEach(function (m) {
            var pc = pctOf(p, m[0]), v = val(p, m[0]);
            box.appendChild(el("div", { "class": "prow", title: m[2] || null }, [
              el("span", { "class": "plabel", text: m[1] }),
              el("span", { "class": "ptrack", role: "img", "aria-label": m[1] + ": " + ordinal(pc) + " percentile" }, [
                el("i", { "class": pc >= 67 ? "hi" : pc >= 34 ? "mid" : "lo", style: "width:" + Math.max(pc, 2) + "%" })]),
              el("b", { "class": "ppct", text: String(pc) }),
              el("span", { "class": "pval", text: v == null ? "" : m[3](v) })]));
          });
          art.appendChild(box);
        });
        if (!p.regular) art.appendChild(el("p", { "class": "note", text: "Percentiles are given only to regulars. " + regularNote() + "." }));
        var totals = totalsOf(p);
        if (totals.length) art.appendChild(el("section", { "class": "pc-sec" }, [el("h2", { text: "Season totals" }),
          el("dl", { "class": "totals" }, totals.map(function (x) { return el("div", {}, [el("dt", { text: x[0] }), el("dd", { text: typeof x[1] === "number" ? fmt.n(x[1]) : String(x[1]) })]); }))]));
        var extra = el("div", { "class": "pc-extra" }, [el("p", { "class": "empty", text: "Loading his games and career…" })]);
        art.appendChild(extra);
        cardExtras(extra, p);
        art.appendChild(el("p", { "class": "note", text: "The number beside each bar is his percentile among " + many + " who play regularly " + (PRO() ? "in " + ALL() : scope === "fbs" || !ranked || NOPOLL() ? "in " + ALL() : "for a top-25 team") + " and do that job: 90 means better than 90% of them. The tick marks the middle." +
          (roster.through ? " Through games of " + short(roster.through) + "." : "") }));
        var defs = [];
        CARD.forEach(function (sec) { sec[1].forEach(function (m) { if (m[2] && pctOf(p, m[0]) != null) defs.push(el("div", {}, [el("dt", { text: m[1] }), el("dd", { text: m[2] + "." })])); }); });
        if (defs.length) art.appendChild(el("details", { "class": "defs" }, [el("summary", { text: "What each line measures" }), el("dl", {}, defs)]));
        holder.appendChild(art);
      });
    }).catch(function () {
      holder.appendChild(el("p", { "class": "empty", text: "The card could not be loaded. Reload the page to try again." }));
    });
  }

  // ---- the teams page: each team's stats, from box scores ----
  var tstate = { sort: "rank", dir: 1, conf: "" };
  var teamSets = {};
  function loadTeams(which) {      // the ranked 25, or the whole league (a pro league has the one table)
    which = PRO() || NOPOLL() ? "fbs" : which || scope;
    if (teamSets[which]) return Promise.resolve(teamSets[which]);
    return fetch(which === "fbs" ? "teams_fbs.json" : "teams.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { teamSets[which] = d; return d; });
  }
  function drawTeams() {
    var holder = $("t-list");
    holder.innerHTML = "";
    setHead("teams", "teams");
    holder.appendChild(el("p", { "class": "empty", text: "Loading the team stats…" }));
    loadTeams().then(function (d) {
      if (!data.numbered && tstate.sort === "rank") { tstate.sort = "power"; tstate.dir = 1; }
      function table() {
        holder.innerHTML = "";
        var confs = {};
        d.teams.forEach(function (t) { if (t.conf) confs[t.conf] = 1; });
        if (tstate.conf && !confs[tstate.conf]) tstate.conf = "";
        var pick = el("select", { "aria-label": "Conference", onchange: function () { tstate.conf = pick.value; table(); } },
          [el("option", { value: "", text: W("teams.all_conferences") })].concat(Object.keys(confs).sort().map(function (c) { return el("option", { value: c, text: c, selected: c === tstate.conf }); })));
        holder.appendChild(el("div", { "class": "nav filters" }, [scopeSwitch(drawTeams), pick]));
        var cols = TCOLS.filter(function (c) { return data.numbered || c[0] !== "rank"; });
        var col = cols.filter(function (c) { return c[0] === tstate.sort; })[0] || cols[0];
        var rows = d.teams.filter(function (t) { return !tstate.conf || t.conf === tstate.conf; }).sort(function (a, b) {
          var x = col[3](a), y = col[3](b);
          if (x == null && y == null) return (a.power || 999) - (b.power || 999); if (x == null) return 1; if (y == null) return -1;
          return (typeof x === "string" ? tstate.dir * x.localeCompare(y) : tstate.dir * (x - y)) || (a.power || 999) - (b.power || 999);
        });
        var head = el("tr", {}, cols.map(function (c) {
          var on = col[0] === c[0];
          var label = PRO() && c[0] === "conf" ? "Div" : PRO() && c[0] === "conf_rec" ? "In div" : c[1];
          return el("th", { scope: "col", "class": c[0] === "name" || c[0] === "conf" ? "l" : "", "aria-sort": on ? (tstate.dir > 0 ? "ascending" : "descending") : null }, [
            el("button", { type: "button", title: c[2] || null, text: label + (on ? (tstate.dir > 0 ? " ▲" : " ▼") : ""),
              onclick: function () { if (on) tstate.dir = -tstate.dir; else { tstate.sort = c[0]; tstate.dir = c[5] ? -1 : 1; } table(); } })]);
        }));
        var body = el("tbody", {}, rows.map(function (t) {
          return el("tr", {}, cols.map(function (c) {
            var cls = col[0] === c[0] ? "sorted" : "";
            if (c[0] === "rank") return el("td", { "class": cls }, [rankTag(t.rank, t.id)]);
            if (c[0] === "name") return el("td", { "class": "l " + cls }, [el("span", { "class": "tcell" }, [logo(t.id), teamA(t.id, t.name)])]);
            if (c[0] === "conf") return el("td", { "class": "l " + cls, text: t.conf || "" });
            if (c[0] === "rec") return el("td", { "class": cls, text: t.w + "-" + t.l + (t.t ? "-" + t.t : "") });
            if (c[0] === "conf_rec") return el("td", { "class": cls, text: t.conf_rec || "" });
            var v = c[3](t);
            return el("td", { "class": cls, text: v == null ? "" : c[4](v) });
          }));
        }));
        holder.appendChild(el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": "Team stats table, scrolls sideways" }, [
          el("table", { "class": "ptable ttable" }, [el("thead", {}, [head]), body])]));
        holder.appendChild(el("p", { "class": "note", text: (d.through ? "Through games of " + short(d.through) + ". " : "") +
          W("teams.note" + FBS()) }));
      }
      table();
    }).catch(function () {
      holder.innerHTML = "";
      holder.appendChild(el("p", { "class": "empty", text: "The team stats could not be loaded. Reload the page to try again." }));
    });
  }

  // ---- a game's own page: the score by period (ESPN, live) and both teams' box scores ----
  var gameTimers = [];
  function stopGame() { gameTimers.forEach(clearTimeout); gameTimers = []; liveHooks = []; }
  function scoreLine(g) {
    var s = gameState(g), t = g.start ? new Date(g.start * 1000) : null;
    function team(x, n, other) {
      var won = s.fin && n != null && n > other, lost = s.fin && n != null && n < other;
      return el("div", { "class": "gc-team" + (won ? " won" : "") + (lost ? " lost" : "") }, [logo(x.id, "gc"),
        el("div", { "class": "gc-name" }, [rankTag(x.rank, x.id), teamA(x.id, x.name)]),
        el("b", { "class": "gc-sets", text: n == null ? (s.fin || s.live ? "–" : "") : String(n) })]);
    }
    var mid = s.fin ? "Final" + overtime(s.lines) : s.live ? "" : (t && !isNaN(t) ? t.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "");
    return el("div", { "class": "gc-score" }, [team(g.away, s.as, s.hs), el("div", { "class": "gc-mid" }, s.live ? [liveTag(), el("div", { text: s.detail || "" })] : [el("span", { text: mid })]), team(g.home, s.hs, s.as)]);
  }
  function periodTable(g) {
    var s = gameState(g), a = s.lines[0], h = s.lines[1], n = Math.max(a.length, h.length, data.periods || 4);
    if (!a.length && !h.length) return null;
    var head = el("tr", {}, [el("th", { scope: "col", "class": "l", text: s.live ? (s.detail || "Live") : "" })]);
    for (var i = 1; i <= n; i++) head.appendChild(el("th", { scope: "col", text: periodLabel(i, n) }));
    var tails = lineTails(g, s);
    tails.forEach(function (x) { head.appendChild(el("th", { scope: "col", "class": x[2] ? "tot" : "", text: x[0] })); });
    function line(mine, x, i) {
      var cells = [];
      for (var k = 0; k < n; k++) cells.push(el("td", { text: mine[k] == null ? "" : String(mine[k]) }));
      return el("tr", {}, [el("th", { scope: "row", "class": "l" }, [el("span", { "class": "stm" }, [rankTag(x.rank, x.id), logo(x.id, "sm"), teamA(x.id, x.name)])])].concat(cells)
        .concat(tails.map(function (t) { return el("td", { "class": t[2] ? "tot" : "", text: t[1][i] == null ? "" : String(t[1][i]) }); })));
    }
    return el("div", { "class": "tablewrap" }, [el("table", { "class": "ptable stable" }, [el("thead", {}, [head]), el("tbody", {}, [line(a, g.away, 0), line(h, g.home, 1)])])]);
  }
  // what follows the periods in a game's line score: heading, [away, home], whether it is the total
  function lineTails(g, s) { return [["T", [s.as == null ? 0 : s.as, s.hs == null ? 0 : s.hs], 1]]; }
  function oddsLine(g) {
    if (LINES) return g.line && g.line[0] && g.state !== "final" ? lineCard(g) : null;
    var p = g.p != null ? g.p : g.p0;
    if (p == null) return null;
    var two = pct(p);
    var out = el("div", { "class": "gc-odds" }, [
      el("span", { "class": "gc-lab", text: g.p != null ? "Chance of winning" : "Chance of winning before the game" }),
      el("div", { "class": "gc-bar" }, [el("span", { "class": "a", style: "width:" + two[0], text: g.away.name + " " + two[0] }),
        el("span", { "class": "h", style: "width:" + two[1], text: two[1] + " " + g.home.name })]), keyline(g)]);
    if (g.line && g.line[0]) out.appendChild(el("p", { "class": "gc-line" }, ["Betting line: ", el("b", { text: g.line[0] }), g.line[1] ? ", over/under " + g.line[1] : "", ". The percentages above are this site's own, not the bookmakers'."]));
    return out;
  }
  function fillCard(cmp, g, d) {
    cmp.innerHTML = "";
    if (!d.team || !d.team.away || !d.team.home) return;
    var rows = compareRows(teamTotals(d.team.away), teamTotals(d.team.home));
    cmp.appendChild(el("h3", { "class": "gc-h", text: "Team comparison" }));
    rows.forEach(function (c) {
      var a = c[1], h = c[2];
      if (a == null || h == null) return;
      var lo = Math.min(a, h, 0), sum = (a - lo) + (h - lo), aw = sum ? 100 * (a - lo) / sum : 50;
      var aBetter = c[4] ? a > h : a < h, hBetter = c[4] ? h > a : h < a;
      cmp.appendChild(el("div", { "class": "gc-row" }, [
        el("span", { "class": "v" + (aBetter ? " best" : ""), text: c[5] || c[3](a) }),
        el("div", { "class": "gc-track", "aria-hidden": "true" }, [el("span", { "class": "a" + (aBetter ? " best" : ""), style: "width:" + aw + "%" }), el("span", { "class": "h" + (hBetter ? " best" : ""), style: "width:" + (100 - aw) + "%" })]),
        el("span", { "class": "v h" + (hBetter ? " best" : ""), text: c[6] || c[3](h) }),
        el("span", { "class": "l", text: c[0] })]));
    });
  }

  function drawGame(id) {
    stopGame();
    var box = $("game"), g = data.games.filter(function (x) { return String(x.id) === String(id); })[0];
    box.innerHTML = "";
    if (!g) { box.appendChild(el("p", { "class": "empty", text: "This game is not on this season's schedule." })); return; }
    var t = g.start ? new Date(g.start * 1000) : null;
    function side(x) { return el("span", { "class": "mside" }, [rankTag(x.rank, x.id), logo(x.id), teamA(x.id, x.name)]); }
    var title = el("h1", { "class": "mtitle sr" }, [side(g.away), el("span", { "class": "mv", text: g.neutral ? " vs " : " at " }), side(g.home)]);
    var status = el("p", { "class": "mstatus" }), top = el("div", {}), periods = el("div", { "class": "msets" });
    var cmp = el("div", { "class": "gc-cmp" }), extra = el("div", {}), boxes = el("div", { "class": "mboxes" });
    function head() {      // the parts that change with the score
      var s = gameState(g);
      status.innerHTML = "";
      // the round, the day, the time and the channel, on the first line of the card (the teams and the score are right under it)
      status.appendChild(el("span", { text: ([g.round, g.series].filter(Boolean).join(": ") ? [g.round, g.series].filter(Boolean).join(": ") + " · " : "") + long(g.date) + (t && !isNaN(t) ? ", " + t.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "") +
        (g.tv && g.tv.length ? " · " + g.tv.join(", ") : "") + (g.state === "other" && !g.live ? " · " + (g.note || "not played") : "") }));
      top.innerHTML = ""; top.appendChild(scoreLine(g));
      periods.innerHTML = "";
      var q = periodTable(g);
      if (q) periods.appendChild(q);
    }
    head();
    liveHooks.push(function (x) { if (x === g) head(); });
    var card = el("section", { "class": "gcard", "aria-label": "Game summary" }, [status, top, periods, oddsLine(g), cmp]);
    box.appendChild(title); box.appendChild(card); box.appendChild(extra); box.appendChild(boxes);
    if (data.game_page) box.appendChild(el("p", { "class": "note keep" }, [el("a", { href: data.game_page + g.id, rel: "noopener", text: W("game.espn_link") })]));

    function readBox() {
      var s = gameState(g);
      return fetch("game/" + g.id + ".json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
        fillCard(cmp, g, d);
        gameExtra(extra, g, d);
        boxes.innerHTML = "";
        [["away", g.away], ["home", g.home]].forEach(function (p) {
          boxes.appendChild(el("div", {}, [el("h2", { "class": "mteam" }, [rankTag(p[1].rank, p[1].id), logo(p[1].id), teamA(p[1].id, p[1].name)]), boxTables((d.players || {})[p[0]], p[1].name, d)]));
        });
        if (d.status !== "F" && (s.live || !s.fin)) gameTimers.push(setTimeout(readBox, 60 * 1000));
      }).catch(function () {
        boxes.innerHTML = "";
        boxes.appendChild(el("p", { "class": "empty", text: s.live ? "Team and player stats appear here within about 10 minutes of the start." :
          s.fin ? "The box score has not come in yet. It usually arrives within a few minutes of the end." : "Team and player stats appear here once the game starts." }));
        if (s.live || s.fin) gameTimers.push(setTimeout(readBox, 60 * 1000));
      });
    }
    readBox();
  }
  // anything a sport adds between a game's card and its box scores
  function gameExtra(holder, g, d) { holder.innerHTML = ""; }

  // ---- a team's page: its games, its stats and its players ----
  function drawTeam(id) {
    var box = $("team");
    box.innerHTML = "";
    var t = rankOf(id), info = fbs[id];
    var mine = data.games.filter(function (g) { return g.away.id === id || g.home.id === id; });
    var which = t ? scope : "fbs";            // an unranked team is measured against the whole division
    var name = t ? t.name : info ? info[1] : (mine.length ? (mine[0].away.id === id ? mine[0].away.name : mine[0].home.name) : id);
    var st = (data.standings || []).filter(function (x) { return x.id === id; })[0];
    var full = st && st.place ? st.place + " " + name : name;          // "Boston Celtics"
    var goat = ((data.goat || {}).top || []).filter(function (x) { return x.id === id; })[0];
    var rec = (info && info[3]) || {}, bits = [];
    if (rec.all || (t && t.record)) bits.push(rec.all || t.record);
    if (info && info[2]) bits.push(info[2] + (PRO() ? (rec.div ? " (" + rec.div + " in the division)" : "") : rec.conf ? " (" + rec.conf + " in conference)" : ""));
    if (data.numbered) bits.push(PRO() ? ordinal(t.rank) + " in " + ALL() : t ? "No. " + t.rank + " in the " + data.poll.name : "Not ranked in the " + data.poll.name);
    if (goat) bits.push("No. " + goat.rank + " in the GOAT ranking");
    box.appendChild(el("div", { "class": "thead" }, [logo(id, "big"), el("div", {}, [el("h1", { text: full }), el("p", { "class": "tsub", text: bits.join(" · ") }),
      rec.home || rec.away ? el("p", { "class": "tsub", text: ["Home " + (rec.home || "0-0"), "Away " + (rec.away || "0-0"), PRO() && rec.conf ? "In the conference " + rec.conf : "", rec.ranked ? "Against the AP top 25 " + rec.ranked : "", rec.last10 ? "Last ten " + rec.last10 : "", rec.streak ? "Streak " + rec.streak : ""].filter(Boolean).join(" · ") }) : null])]));
    if (!info && !t) { box.appendChild(el("p", { "class": "note", text: name + " is not in " + ALL() + ", so this site lists only its games against teams that are." })); }
    box.appendChild(el("div", { "class": "nav filters" }, [scopeSwitch(function () { drawTeam(id); }, !t)]));
    if (t && !PRO()) box.appendChild(el("div", { "class": "tvs" }, [versus(t)]));

    // games: the latest results and what is next
    var next = mine.filter(function (g) { return g.state !== "final" && g.date >= today; }).slice(0, 5);
    var done = mine.filter(function (g) { return g.state === "final"; }).slice(-5);
    var m = el("section", { "class": "tsec" }, [el("h2", { text: W("team.games") })]);
    if (next.length) { m.appendChild(el("h3", { "class": "day", text: W("team.coming_up") })); m.appendChild(el("ol", { "class": "games" }, next.map(function (g) { return row(g, true); }))); }
    if (done.length) { m.appendChild(el("h3", { "class": "day", text: W("team.latest_results") })); m.appendChild(el("ol", { "class": "games" }, done.slice().reverse().map(function (g) { return row(g, true); }))); }
    if (!mine.length) m.appendChild(el("p", { "class": "empty", text: "No games are listed for " + name + "." }));
    if (mine.length && info) m.appendChild(el("p", { "class": "note keep" }, [el("a", { href: "#/", onclick: function () { if (!t) setScope("fbs"); state.team = id; }, text: PRO() ? "All " + name + " games this season" : "All of " + name + "'s games this season" })]));
    box.appendChild(m);
    if (!info && !t) return;

    var stats = el("section", { "class": "tsec" }, [el("h2", { text: W("team.stats") }), el("p", { "class": "empty", text: "Loading…" })]);
    var people = el("section", { "class": "tsec" }, [el("h2", { text: W("team.players") }), el("p", { "class": "empty", text: "Loading…" })]);
    box.appendChild(stats); box.appendChild(people);
    loadTeams(which).then(function (d) {
      var row1 = d.teams.filter(function (x) { return x.id === id; })[0];
      stats.removeChild(stats.lastChild);
      if (!row1 || !row1.games) { stats.appendChild(el("p", { "class": "empty", text: "No box scores yet this season." })); return; }
      var tiles = TSTATS.map(function (c) {
        var v = row1[c[0]];
        var vals = d.teams.map(function (x) { return x[c[0]]; }).filter(function (x) { return x != null; });
        var place = v == null ? null : 1 + vals.filter(function (x) { return c[3] ? x > v : x < v; }).length;
        return el("div", { "class": "tile" + (place && place <= 5 ? " top" : "") }, [el("span", { "class": "lab", text: c[1] }),
          el("b", { text: v == null ? "–" : c[2](v) }), el("span", { "class": "plc", text: place ? ordinal(place) + " of " + vals.length : "" })]);
      });
      tiles.push(el("div", { "class": "tile" }, [el("span", { "class": "lab", text: "Rating" }), el("b", { text: row1.power ? ordinal(row1.power) : "–" }), el("span", { "class": "plc", text: "in " + ALL() + ", by this site's rating" })]));
      tiles.push(el("div", { "class": "tile" }, [el("span", { "class": "lab", text: "Schedule strength" }), el("b", { text: row1.sos_rank ? ordinal(row1.sos_rank) : "–" }), el("span", { "class": "plc", text: "hardest of " + d.teams.length })]));
      stats.appendChild(el("div", { "class": "tiles" }, tiles));
      stats.appendChild(el("p", { "class": "note keep", text: row1.w + "-" + row1.l + (row1.t ? "-" + row1.t : "") + ". Stats from " + row1.games + (row1.games === 1 ? " box score" : " box scores") + "; places are among " + (PRO() ? "the " + d.teams.length + " " + data.league_name + " teams" : which === "fbs" || NOPOLL() ? "all " + d.teams.length + " " + ALL() + " teams" : "the 25 ranked teams") + ". " }));
      stats.lastChild.appendChild(el("a", { href: "#/teams", text: "All team stats" }));
    }).catch(function () {});
    loadRoster(which).then(function () {
      var list = roster.players.filter(function (p) { return p.team_id === id; }).sort(function (a, b) {
        return (b.regular - a.regular) || POS_ORDER.indexOf(a.group || a.pos) - POS_ORDER.indexOf(b.group || b.pos) || (val(b, "impact_g") || 0) - (val(a, "impact_g") || 0);
      });
      people.removeChild(people.lastChild);
      if (!list.length) { people.appendChild(el("p", { "class": "empty", text: "No box scores yet this season." })); return; }
      var heads = [["#", "Rank by Impact among regulars", ""], ["Player", "", "l"], ["Pos", "", ""], ["GP", "Games played", ""], ["Impact", "Impact per " + IMPACT_UNIT + ": what he adds over an average regular at his position", ""], ["This season", "", "l"]];
      var head = el("tr", {}, heads.map(function (c) { return el("th", { scope: "col", "class": c[2], title: c[1] || null }, [el("span", { "class": "th", text: c[0] })]); }));
      var showAll = false;
      function fill() {
        while (people.childNodes.length > 1) people.removeChild(people.lastChild);
        var rows = showAll ? list : list.filter(function (p) { return p.regular; });
        if (!rows.length) rows = list;
        var body = el("tbody", {}, rows.map(function (p) {
          return el("tr", { "class": p.regular ? "" : "part" }, [el("td", { text: p.rank ? String(p.rank) : "–" }),
            el("td", { "class": "l nm" }, [el("a", { href: "#/player/" + encodeURIComponent(p.id) }, [face(p), el("span", { text: p.name })])]),
            el("td", { text: p.pos }), el("td", { text: String(p.gp) }), el("td", { "class": "strong", text: fmt.s2(val(p, "impact_g")) }),
            el("td", { "class": "l statline", text: statLine(p) })]);
        }));
        people.appendChild(el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": name + " players, scrolls sideways" }, [
          el("table", { "class": "ptable tptable" }, [el("thead", {}, [head]), body])]));
        if (rows.length < list.length || showAll) people.appendChild(el("p", { "class": "more" }, [el("button", { type: "button", "class": "morebtn",
          text: showAll ? "Show the regulars only" : "Show all " + list.length + " players", onclick: function () { showAll = !showAll; fill(); } })]));
        people.appendChild(el("p", { "class": "note", text: W("team.players_note" + (!PRO() && (which === "fbs" || NOPOLL()) ? "_fbs" : "")) }));
      }
      fill();
    }).catch(function () {});
  }

  function route() {
    var h = location.hash, card = /^#\/?player\/(.+)$/.exec(h), game = /^#\/?game\/(\d+)/.exec(h), tm = /^#\/?team\/(.+)$/.exec(h);
    stopGame();
    var page = tm ? "team" : game ? "game" : card ? "card" : /^#\/?players/.test(h) ? "players" : /^#\/?rankings/.test(h) ? "rankings" : /^#\/?teams/.test(h) ? "teams" : "games";
    ["games", "rankings", "teams", "players", "card", "game", "team"].forEach(function (p) { $("page-" + p).hidden = p !== page; });
    Array.prototype.forEach.call(document.querySelectorAll(".pages a"), function (a) {
      if (a.dataset.page === (page === "card" ? "players" : page === "game" ? "games" : page === "team" ? "teams" : page)) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    document.title = ({ rankings: W("rankings.title"), teams: W("teams.title" + FBS()), players: W("players.title" + FBS()), game: W("games.box_score"), team: "Team", card: "Player card" }[page] || W("games.title" + FBS())) + " | " + data.site;
    if (page === "team") drawTeam(decodeURIComponent(tm[1])); else if (page === "game") drawGame(game[1]); else if (page === "rankings") drawRanks(); else if (page === "teams") drawTeams(); else if (page === "players") drawPlayers(); else if (page === "card") drawCard(decodeURIComponent(card[1])); else draw();
    window.scrollTo(0, 0);
  }

  // ---- a page left open, or come back to later, does not go stale ----
  // Live scores keep themselves current (above). Everything else, the standings, the rankings and
  // the schedule, comes with the page: when a newer copy has been published the page is loaded
  // again, on coming back to it after ten minutes away or, while it sits at its top, every fifteen.
  var loadedAt = Date.now();
  function reloadIfNewer() {
    fetch("data.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (d && data && d.updated && d.updated !== data.updated) location.reload();
    }).catch(function () {});
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden && Date.now() - loadedAt > 10 * 60 * 1000) reloadIfNewer(); });
  setInterval(function () { if (!document.hidden && (window.pageYOffset || 0) < 60) reloadIfNewer(); }, 15 * 60 * 1000);

  fetch("data.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
    data = d;
    if (LINES) d.games.forEach(function (g) { delete g.p; delete g.p0; });
    (d.fbs || []).forEach(function (x) { fbs[x[0]] = x; });
    if (d.last_season) {      // the new season has not begun: say that these are last season's numbers
      var starts = d.last_season.starts ? day(d.last_season.starts).toLocaleDateString(undefined, { month: "long", day: "numeric" }) : "";
      var main = document.querySelector("main");
      main.insertBefore(el("p", { "class": "seasonnote", text: W(starts ? "season.last" : "season.last_undated", { season: d.season_label, next: d.last_season.next, date: starts }) }), main.firstChild);
    }
    $("brand").textContent = d.site;
    var lg = $("leagues"), base = d.league ? "../" : "";
    if (lg && (d.leagues || []).length > 1) d.leagues.forEach(function (o) {
      lg.appendChild(el("a", { href: base + (o[0] ? o[0] + "/" : ""), "aria-current": (d.league || "") === o[0] ? "page" : null, text: o[1] }));
    });
    document.body.classList.add("lg-" + (d.league || "main"));
    if (d.pro) document.body.classList.add("pro");
    Array.prototype.forEach.call(document.querySelectorAll("[data-w]"), function (n) { var s = W(n.getAttribute("data-w")); if (s) n.textContent = s; });
    $("lede").textContent = W("games.lede" + FBS(), { poll: d.poll.name });
    var u = new Date(d.updated);
    $("foot-updated").textContent = "Scores and schedule updated " + (isNaN(u) ? d.updated : u.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })) +
      (d.poll.date ? ". Rankings: " + d.poll.name + " of " + day(d.poll.date).toLocaleDateString(undefined, { dateStyle: "long" }) : "") + ".";
    window.addEventListener("hashchange", route);
    route();
    pollLive();
  }).catch(function (e) {
    if (window.console) console.error(e);
    $("h-list").textContent = "The games could not be loaded";
    $("list").appendChild(el("p", { "class": "empty", text: "Reload the page to try again. If this keeps happening, the first update may not have run yet." }));
  });
})();
