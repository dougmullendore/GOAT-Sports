---
name: GOAT Sports
description: The day of sport as one black-and-white data field, every league read off the same lattice in one monospace face.
colors:
  void: "#000000"
  lumin: "#ffffff"
typography:
  display:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, monospace"
    fontSize: "clamp(2.5rem, 6.2vw, 5.25rem)"
    fontWeight: 300
    lineHeight: 0.92
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 75"
  headline:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, monospace"
    fontSize: "1.375rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "0.04em"
  title:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, monospace"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "0.08em"
  numeral:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, monospace"
    fontSize: "1.375rem"
    fontWeight: 300
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "'tnum' 1"
  body:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
    fontFeature: "'tnum' 1"
    fontVariation: "'wdth' 87.5"
  label:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, monospace"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "0.1em"
rounded:
  none: "0"
spacing:
  rule: "1px"
  row-y: "11px"
  row-x: "10px"
  gutter-phone: "16px"
  gutter: "24px"
  league: "48px"
  section: "64px"
components:
  button-outline:
    backgroundColor: "{colors.void}"
    textColor: "{colors.lumin}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "40px"
  button-outline-hover:
    backgroundColor: "{colors.lumin}"
    textColor: "{colors.void}"
  button-outline-pressed:
    backgroundColor: "{colors.lumin}"
    textColor: "{colors.void}"
  calendar-day:
    backgroundColor: "{colors.void}"
    textColor: "{colors.lumin}"
    rounded: "{rounded.none}"
    padding: "8px 12px"
    height: "72px"
  calendar-day-selected:
    backgroundColor: "{colors.lumin}"
    textColor: "{colors.void}"
  game-row:
    backgroundColor: "{colors.void}"
    textColor: "{colors.lumin}"
    typography: "{typography.body}"
    padding: "11px 10px"
    height: "52px"
  game-row-live:
    backgroundColor: "{colors.lumin}"
    textColor: "{colors.void}"
  rank-standing:
    backgroundColor: "{colors.lumin}"
    textColor: "{colors.void}"
    rounded: "{rounded.none}"
    padding: "0 .3em"
  rank-goat:
    backgroundColor: "transparent"
    textColor: "{colors.lumin}"
    rounded: "{rounded.none}"
    padding: "0 .3em"
  logo-tile:
    backgroundColor: "{colors.lumin}"
    rounded: "{rounded.none}"
    padding: "3px"
    size: "30px"
---

# Design System: GOAT Sports

## Overview

**Creative North Star: "The Two-Ink Data Field"**

Every league's day is read off one black-and-white lattice. The page is a field of pure black (#000) crossed by 1px white rules, set in a single monospace face at data density: uppercase labels, tabular figures, numbers that line up down the column. There is no grey, no colour, no gradient tone, no radius and no shadow. Nothing floats; everything sits on the grid and is told apart by position, weight, size and case.

Emphasis has exactly one form: inversion. A white block with black type means live, pressed, selected, hovered, the chosen day, the current page, the winner, a place in the poll. Because it is the only signal, it is never spent on decoration. The light theme is not a second palette; it is the same page with the two inks swapped, chosen by the Invert button or by the device's light setting.

Sports are told apart by rhythm, not hue. Each sport owns a fixed barcode pattern of bar widths and gaps, drawn as its mark beside its name and in the front page's list of sports. The system rejects the dark dashboard of rounded cards, one accent colour per section and same-weight grey blocks.

**Key Characteristics:**
- Two inks only: void (#000) and lumin (#fff), swapped wholesale for the light theme.
- One face, Martian Mono, varied by width (75 to 112.5) and weight (200 to 700); tabular figures everywhere.
- 1px rules carry all structure; no fills, no cards, no radius, no shadow.
- Inversion is the only emphasis.
- Each sport is identified by its own bar rhythm, never a colour.
- Team logos and player photos appear in greyscale: the only grey on the page, and it is content.

## Colors

A strict two-ink system: one ground, one ink, and the ability to swap them.

### Primary
- **Lumin** (white in the dark theme, black in the light): every glyph, every rule, every outline, and the fill of every inverted block (live rows, pressed buttons, the selected calendar day, the current tab, filled rank boxes, the W box, the live module).

### Neutral
- **Void** (black in the dark theme, white in the light): the ground of the page, and the ink inside any inverted block.

### Named Rules
**The Two Inks Rule.** Only void and lumin are ever set as colour. There is no third value, no tint, no opacity step. A shape is either ground or ink.

**The Pure Inversion Rule.** The light theme is the dark theme with void and lumin swapped (via `data-theme="light"` or `prefers-color-scheme: light`), nothing else. Inside an inverted row the two inks swap again locally, so numbers, W/L boxes and rank boxes invert with the row.

**The Content Grey Exception.** Team logos are shown as themselves in greyscale (`grayscale(1) contrast(1.1)`) on a small fixed-white tile, and player photos in greyscale inside a 1px ruled square. Grey exists only inside these images, because they are content; it never appears in type, rules or fills.

**The Rhythm Not Colour Rule.** A sport is identified by its bar rhythm, as [bar width, gap] steps repeated: football heavy-light-light (4,1 / 1,1 / 1,3), basketball even (1,1), baseball in threes (1,1 / 1,1 / 1,4), hockey wide and narrow (4,2 / 1,2), volleyball a burst then a rest (2,1 / 1,1 / 1,1 / 1,1 / 4,3). Never give a sport a colour.

## Typography

**Display Font:** Martian Mono (with ui-monospace, Cascadia Mono, Menlo, monospace)
**Body Font:** Martian Mono
**Label/Mono Font:** Martian Mono

**Character:** One variable monospace does every job. Hierarchy comes from width (condensed 75% for display, 87.5% for running text on the front page), weight (200 for a losing score, 300 for display, 500 for names and headings, 600 for live tags and lines) and case.

### Hierarchy
- **Display** (300, clamp(2.5rem, 6.2vw, 5.25rem), 0.92, width 75%, uppercase): the date on the front page and a page's title on the sport sites (there clamp(2.25rem, 5.6vw, 4.25rem)). One per page.
- **Headline** (500, 1.375rem, 1.2, 0.04em, uppercase): a league's name over its games, beside its bar mark.
- **Title** (500, 1rem, 1.2, 0.06-0.08em, uppercase): section heads, set on a 1px rule.
- **Numeral** (300, 1.375rem, 1, -0.02em): the date in a calendar cell, scores, readouts; scores in the live module run to 1.75rem.
- **Body** (400, 0.875rem, 1.5, tabular figures): team names (500, uppercase, 0.03em), rows and prose. Notes cap at 80-90ch and drop to 0.75rem.
- **Label** (400, 0.6875rem, 0.1em, uppercase): column heads, readout labels, buttons, tabs, channels, weekday and month in the calendar, "How to read this".

### Named Rules
**The One Face Rule.** Martian Mono is the only family on every page. Contrast comes from width, weight, size and case, never a second face.

**The Weight Means Result Rule.** The losing side of a final and the dimmed part of a score drop to weight 200; the line and live tags rise to 600. Weight, not tone, separates won from lost.

## Layout

A single centred column, max 1240px, with a 24px gutter (16px on phones). Structure is ruled, not boxed: every league is a heading on a 1px rule followed by a ruled list; every game is one row on a fixed column grid (time 6.5rem, away team, middle 8rem, home team, channels 11rem) named once by a column-head row. Sections sit 64px apart, leagues 48px (28px on phones).

The top of every page is the sports strip (the current sport inverted), then a masthead with the bar mark, readouts separated by vertical rules, and the Invert button. On the front page a ruled row of league links with game counts follows, then the date at display size beside the inverted live module, then the calendar strip with the leagues picker at its end.

On phones (760px front page, 640px sport sites, 480px for the strip) a game row folds to two lines: away and home stacked on the left, the score or line on the right, time and channels below. The calendar scrolls sideways a whole cell at a time (scroll-snap) instead of wrapping. Touch targets keep a 44px minimum.

## Elevation & Depth

None. The system is completely flat: no shadows, no layering, no blur, no tonal surfaces. Depth is replaced by inversion: what matters is not raised, it is turned to the other ink. The only `box-shadow` in use is an inset 1px line drawn as an outline (open boxes, logo tiles in the light theme) and an inset 4px bar marking today in the calendar; both are rules, not elevation.

### Named Rules
**The Flat Field Rule.** Nothing casts a shadow or sits above anything else. If a thing needs to stand out, invert it.

## Shapes

Square everything: radius 0, enforced on the sport sites with `border-radius: 0 !important`. Borders are always 1px solid lumin; a dashed 1px border means unavailable or empty (a disabled day button, a sport not yet open, an empty state). Adjacent outlined controls share edges by overlapping 1px, so a group of buttons or calendar cells reads as one ruled strip. The recurring silhouette is the bar: the sport marks, the half-filled square in the Invert button, the blinking live square. Gradients appear only with hard stops to draw a bar or stripe pattern, never as tone.

## Components

### Buttons
Outlined, square, uppercase; pressing inverts them.
- **Shape:** square (0), 1px lumin border.
- **Default:** void ground, lumin label (0.6875rem, 0.1em, uppercase), 0 16px padding, 40px tall (44px on phones).
- **Hover / Pressed:** fully inverted (lumin ground, void label). `aria-pressed="true"` holds the inverted state.
- **Disabled:** dashed border and struck-through label.
- **Invert button:** the theme switch; an outlined button led by a drawn half-filled square, pressed when the light theme is on.

### Calendar
A strip of days (weeks for football and pro volleyball), each cell outlined and sharing edges with its neighbours.
- **Cell:** weekday over month in label type, the date as a numeral, the game count under it; about 92-96px wide, 72px tall (60px on phones).
- **Selected:** inverted. **Today:** an inset 4px bar along the bottom edge, which swaps ink when today is also selected. **Hover:** inverted.
- **Behaviour:** scrolls sideways with snap; never wraps.

### Game Rows
The core of the system: one game per ruled row, laid over by a single link to the game's page.
- **Default:** void ground, a 1px rule beneath, 11px 10px padding, 52px minimum height.
- **Hover / Focus:** inverted; focus uses the inversion instead of an outline.
- **Live:** inverted at rest, with an uppercase live tag whose small square blinks (1s, stepped); a score that changes flips the row back to void for a beat. Both stop under reduced motion.
- **Middle cell:** a score (loser at weight 200), a betting line (the line at 600 over the over/under in label size), or, on volleyball only, the site's own chance of winning.
- **W / L:** a filled lumin square with W for the winner, an outlined square with L for the loser, beside the team name.

### Rank Boxes
- **Filled:** lumin box, void numeral (0.75rem, 500): a place in the poll or the standings.
- **Outlined:** a 1px inset outline, lumin numeral: a GOAT number (and "not ranked").
- Inside an inverted row, both swap ink with the row.

### Logo Tiles
Team logos as themselves, in greyscale, on a 30px fixed-white tile with 3px padding, so every mark keeps its shape in either theme. In the light theme and on inverted rows the tile carries a 1px inset edge. Text badges (no logo) are outlined and transparent.

### Navigation
- **Sports strip:** label type, the site's name in 600; the current sport inverted; hover inverted. On narrow phones the name shortens to "GOAT".
- **Page tabs (sport sites) and league links (front page):** label type; current page inverted; league links are separated by vertical 1px rules and carry their game count.

### Explanations and the Key Line
- **How to read this:** notes under lists and tables fold into a disclosure whose summary is a label-type line; opening it reveals the plain-English note.
- **Key line:** the always-visible line under games: on pages with betting lines it names the sportsbook, says lines move and gives 1-800-GAMBLER; on the front page it sits as its own ruled row. On volleyball it states the chances are the site's own, not betting lines.

### Live Module
The front page's "live now" (or "next up") block: the one fully inverted panel on the page, a ruled list of games with scores at 1.75rem.

## Do's and Don'ts

### Do:
- **Do** use only void and lumin, and build the light theme by swapping them, never by adding values.
- **Do** mark live, pressed, selected, hovered, current and winning by inversion, and only by inversion.
- **Do** draw a new sport's identity as a bar rhythm of [width, gap] steps beside its name.
- **Do** set everything in Martian Mono with tabular figures; labels at 0.6875rem, 0.1em, uppercase.
- **Do** carry structure on 1px rules and overlap neighbouring outlines by 1px so groups read as one strip.
- **Do** show logos and player photos in greyscale, logos on a white tile, so they stay legible in both themes.
- **Do** stop the live blink and the score flip when reduced motion is set.

### Don't:
- **Don't** give a sport, league or state a colour; there is no accent.
- **Don't** introduce grey in type, rules or fills; grey lives only inside logos and photos.
- **Don't** round a corner, cast a shadow, or use a gradient as tone.
- **Don't** wrap content in filled cards; rule it.
- **Don't** add a second typeface.
- **Don't** show the site's own chance of winning where a sportsbook line exists, or show a line without naming the sportsbook and the 1-800-GAMBLER helpline.
