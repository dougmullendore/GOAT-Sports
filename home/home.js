/* GOAT Sports, the front page: each league's games on one day, and a door to each sport. No libraries. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var data = null, shown = null;

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
    football: '<path d="M3.6 20.4c-1.2-5.600 1.100-11.600 6.200-14.700 3.100-1.900 7.100-2.500 10.600-2.100.400 3.500-.200 7.500-2.100 10.600-3.100 5.100-9.100 7.400-14.700 6.200z"/><path d="M9.200 14.800l5.600-5.600"/><path d="M10.300 11.300l2.400 2.400"/><path d="M12.300 9.300l2.400 2.400"/>'
  };
  // what each sport's door says, and the pages behind it
  var DOORS = {
    hockey: ["NHL", "Every game with each team's chance of winning, standings, expected goals, line combinations and playoff odds.",
      [["Games", "#/"], ["Standings", "#/standings"], ["Teams", "#/teams"], ["Players", "#/players"], ["Lines", "#/lines"], ["Odds", "#/odds"]]],
    volleyball: ["Women's college, LOVB and MLV", "The top 25's matches day by day, the AVCA poll and the GOAT ranking, and a card for every Division I player.",
      [["Matches", "#/"], ["Rankings", "#/rankings"], ["Teams", "#/teams"], ["Players", "#/players"], ["LOVB", "lovb/"], ["MLV", "mlv/"]]],
    football: ["College, FBS", "The top 25's games week by week, the AP poll and the GOAT ranking, team stats and a card for every player.",
      [["Games", "#/"], ["Rankings", "#/rankings"], ["Teams", "#/teams"], ["Players", "#/players"]]]
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

  function row(lg, g) {
    var fin = g.state === "final", live = g.state === "live";
    var as = g.away[3], hs = g.home[3], scored = (fin || live) && as != null && hs != null;
    var awayWon = fin && scored && as > hs, homeWon = fin && scored && hs > as;
    var t = g.start ? new Date(g.start * 1000) : null;
    var note = g.state === "other" ? (g.note ? g.note.charAt(0).toUpperCase() + g.note.slice(1) : "Not played") : "";
    var when = fin ? "Final" : live ? "" : note ? note : t && !isNaN(t) ? t.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "Time not set";
    function team(side, s, lost) {
      var kids = [logo(lg, s[0], s[1]), el("span", { "class": "name", text: s[1] }), s[2] ? el("span", { "class": "rk", text: String(s[2]) }) : null];
      if (side === "home") kids.reverse();
      return el("span", { "class": "team " + side + (lost ? " lost" : "") }, kids);
    }
    var mid = scored
      ? el("span", { "class": "mid" }, [el("span", { "class": homeWon ? "l" : "", text: String(as) }), el("span", { "class": "dash", text: "–" }), el("span", { "class": awayWon ? "l" : "", text: String(hs) })])
      : g.p != null && !fin
        ? el("span", { "class": "mid odds", title: "Each team's chance of winning" }, [el("span", { "class": g.p > 0.5 ? "l" : "", text: pct(g.p)[0] }), el("span", { "class": "dash", text: "at" }), el("span", { "class": g.p < 0.5 ? "l" : "", text: pct(g.p)[1] })])
        : el("span", { "class": "mid at", text: "at" });
    var label = g.away[1] + " at " + g.home[1] + (scored ? ", " + as + " to " + hs + (fin ? ", final" : ", in progress") : "");
    return el("li", { "class": "game" + (live ? " on" : "") }, [el("a", { "class": "row", href: lg.game + g.id, "aria-label": label }, [
      el("span", { "class": "when" }, live ? [el("span", { "class": "livetag" }, [el("span", { "class": "dot", "aria-hidden": "true" }), "Live"])] : [when]),
      team("away", g.away, homeWon), mid, team("home", g.home, awayWon),
      el("span", { "class": "more", text: fin ? "Box score" : live ? "Live score" : (g.tv || []).join(", ") })])]);
  }

  function draw() {
    var holder = $("today"), nav = $("nav");
    holder.innerHTML = ""; nav.innerHTML = "";
    var days = {};
    data.leagues.forEach(function (lg) { lg.games.forEach(function (g) { days[dayOf(g)] = 1; }); });
    var all = Object.keys(days).sort();
    if (!shown) shown = today;
    var label = shown === today ? "Today's games" : shown === addDays(today, 1) ? "Tomorrow's games" : shown === addDays(today, -1) ? "Yesterday's games" : "Games on " + long(shown);
    $("h-day").textContent = label;
    document.title = label + " | GOAT Sports";
    var before = all.filter(function (d) { return d < shown; }).pop(), after = all.filter(function (d) { return d > shown; })[0];
    nav.appendChild(el("button", { type: "button", text: "Earlier day", disabled: !before, onclick: function () { shown = before; draw(); } }));
    nav.appendChild(el("button", { type: "button", text: "Today", "aria-pressed": String(shown === today), onclick: function () { shown = today; draw(); } }));
    nav.appendChild(el("button", { type: "button", text: "Later day", disabled: !after, onclick: function () { shown = after; draw(); } }));

    var total = 0, quiet = [];
    data.leagues.forEach(function (lg) {
      var games = lg.games.filter(function (g) { return dayOf(g) === shown; });
      if (!games.length) { quiet.push(lg); return; }
      total += games.length;
      // a game under way first, then by start time
      games.sort(function (a, b) { return (b.state === "live") - (a.state === "live") || (a.start || 0) - (b.start || 0); });
      var sec = el("section", { "class": "lg s-" + lg.sport }, [
        el("div", { "class": "lg-head" }, [
          el("h2", {}, [el("a", { href: lg.href, text: lg.name }), el("span", { "class": "kind", text: lg.label })]),
          el("a", { "class": "all", href: lg.href, text: "All " + lg.name + " " + lg.unit + " →" })]),
        el("ol", { "class": "games" }, games.map(function (g) { return row(lg, g); }))]);
      if (lg.ranked_only) sec.appendChild(el("p", { "class": "note", text: games.length + " " + (games.length === 1 ? ONE[lg.unit] : lg.unit) + " with a team in the " + (lg.poll || "top 25") + ". Numbers are this week's rankings." }));
      holder.appendChild(sec);
    });
    $("lede").textContent = total ? long(shown) + ". The visiting team is on the left; percentages are each team's chance of winning. Choose a game for its own page." : long(shown) + ".";
    if (!total) holder.appendChild(el("p", { "class": "empty", text: "No games are listed for this day. Try an earlier or later day." }));
    quiet.forEach(function (lg) {
      if (!lg.ready) return;
      var coming = lg.games.map(dayOf).filter(function (d) { return d > shown; }).sort()[0] || lg.next;
      var what = (lg.ranked_only ? "No ranked " + lg.name.toLowerCase() + " " : "No " + lg.name + " ") + lg.unit;
      holder.appendChild(el("p", { "class": "quiet s-" + lg.sport }, [what + " on this day" + (coming ? "; the next are on " + long(coming) + ". " : ". "),
        el("a", { href: lg.href, text: lg.name })]));
    });
  }

  function cards() {
    var holder = $("cards");
    holder.innerHTML = "";
    data.sports.forEach(function (s) {
      var d = DOORS[s.key];
      if (!d) return;
      var h = el("h3", {}, [el("a", { href: s.href })]);
      h.firstChild.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + ICON[s.key] + "</svg>";
      h.firstChild.appendChild(el("span", { text: s.name }));
      holder.appendChild(el("article", { "class": "card s-" + s.key + (s.ready ? "" : " soon") }, [h,
        el("p", { text: d[0] + ". " + d[1] + (s.ready ? "" : " Being set up: its first update has not run yet.") }),
        el("ul", {}, d[2].map(function (p) { return el("li", {}, [el("a", { href: s.href + p[1], text: p[0] })]); }))]));
    });
  }

  fetch("home.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
    data = d;
    var u = new Date(d.updated);
    $("foot-updated").textContent = "Updated " + (isNaN(u) ? d.updated : u.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })) + ".";
    draw(); cards();
  }).catch(function () {
    $("lede").textContent = "The games could not be loaded. Reload the page to try again.";
  });
})();
