---
version: 1
slug: "goat-sports-home-index-html"
primary_target: "GOAT-Sports/home/index.html"
related_targets: ["GOAT-Sports/hockey/site/index.html"]
---

# Surface: GOAT Sports front page (today's games), then every sport site

Mode: Operate. A fan checks what is on today across every league, who is winning, where to watch, and opens a game. Frequent, short visits, often on a phone. Must not get busy like ESPN, must not get slower to scan on a phone, must not read as a template reskin. Nothing visual is fixed; product truth, data, features and accessibility work are.

Chosen direction: Datamatics, adopted by the user on the decision page over the assigned Big Board.

## Direction contract

THESIS: The day of sport as one data field: every league's games read off a black-and-white lattice in one monospace face. It refuses the dark dashboard of rounded cards, one accent colour per section and same-weight grey blocks.

OWN-WORLD: Pure black void (#000) and pure white (#fff) only: no grey, no colour, no gradient, no radius, no shadow. One monospace face (Martian Mono) at data density, uppercase labels, tabular figures. 1px white rules; barcode bar fields; sine curves; inversion (white block, black ink) is the only emphasis, used for live, pressed, selected and the winner. Each sport is told apart by its own bar rhythm, never a colour. The light theme is the same page inverted.

STORY: The fan lands on today's field, sees at once which leagues are on and which games are live, scans a league's rows (time, teams, numbers, our chance, channel), reads that the chances are ours and not betting lines, and opens a game.

FIRST VIEWPORT: Top bar: bar mark and GOAT SPORTS, the five sports, then readouts (games today, live now, updated). Under it, full width, the Day Field: a canvas band about 200px tall, one bar cluster per game in start-time order grouped by league, bar density set by each game's chance of winning, a sine line through the favourites' chances, live clusters flickering, league names under their groups; tapping a group jumps to that league. Then the date at display size with the day controls and Choose leagues on its left, and the live module (inverted, white) on its right. League tables below.

FORM: catalog world ikeda-datamatics, a dealt challenger the user adopted (my grounded list had it unranked; the roll assigned candidate 4). Seed key b65967eb. Signature move: the Day Field band and inversion-on-change.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Changes the user made after the build (2026-10-13; these outrank the contract above)

- The Day Field band (bars and sine line) is removed. A row of league links with game counts sits under the masthead instead.
- A calendar strip (days; weeks for football and pro volleyball) replaces Earlier / Today / Later, on the front page and every sport's games page.
- Betting lines (sportsbook line and over/under, from ESPN, DraftKings today) replace the site's own chances of winning on football, basketball, baseball and hockey. Volleyball keeps the site's own chance, labelled as such. Pages with lines carry the 1-800-GAMBLER helpline.
- Team logos show as themselves in greyscale on a small white tile (the two-ink threshold made many unreadable). Grey appears only inside logos and player photos, which are content.
