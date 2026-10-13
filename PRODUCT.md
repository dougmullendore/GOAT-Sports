# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

A mobile app is planned. Whether it will be the website installed or wrapped as an app, or separate native iOS and Android apps, is **undecided**. Until that is settled, design for the web, and treat phones (including the site saved to a home screen) as a first-class screen.

## Users

The general public: sports fans who follow more than one league and want one place to check them. They come to see what's on today and where to watch it, follow scores as games happen, look up standings and stats, and size up a matchup before it starts. They use the site on phones and computers, often in short visits during the day or while a game is on.

## Product Purpose

GOAT Sports is meant to become the all-in-one sports site, bringing together scores, stats, betting information and a social hub. Today it is five sports sites under one front page:

- football (NFL and college)
- basketball (NBA and men's college)
- MLB baseball
- NHL hockey
- women's volleyball (college D1, LOVB and MLV)

Each has games with win chances and where to watch, live scores, standings and rankings, team stats, and a page for every team, game and player.

Success means fans make it the one site they open for every sport they follow, instead of moving between a league app, a TV guide, a stats site and a betting app.

## Positioning

- **One site, every league:** nine leagues side by side, women's volleyball given the same depth as the NFL, and one front page listing every league's games for the day.
- **Its own numbers:** GOAT rankings, playoff odds, player Impact and percentiles, and (for hockey) line combinations and expected goals. All are worked out by the site from results and box scores, not copied from someone else.
- **The betting line beside every game:** the sportsbook's line (from ESPN's feed, DraftKings today) for football, basketball, baseball and hockey. Decided by the owner on 2026-10-13: lines replace the site's own chances of winning in the game lists and on game pages. Volleyball has no sportsbook lines, so it keeps the site's own chance, labelled as such.
- **The practical answer first:** each game shows when it starts in the reader's own time zone, where to watch it and the score as it happens.
- **Plain and calm:** no ads, no accounts, no clutter, and everything in everyday words.

## Operating Context

- Data is pulled automatically on a schedule by a Python pipeline in each sport's `pipeline/` folder. Sources include ESPN, the NHL's feeds, ncaa.com and the AP and AVCA polls. During game hours, live scores refresh about every 5 minutes. The schedule is in `.github/workflows/update.yml`.
- The site is published as static pages on GitHub Pages: `dougmullendore.github.io/GOAT-Sports/`. Each sport lives under its own path.
- The site's wording can be edited without code in each sport's `site/words.txt`.
- Polls (AP top 25, AVCA) drive what college games the front page lists, and set the rank tags.

## Capabilities and Constraints

**Today:** games by day (a calendar of days, or weeks for football and pro volleyball), live scores and box scores, betting lines (volleyball: the site's own win chances), standings and polls, GOAT rankings, team stats, player lists ranked by Impact, player cards with percentiles, team pages, hockey lines and playoff odds, and light and dark themes.

**Planned:**
- **More betting information:** picks, more markets, line movement. Lines already show; every page that shows them names the sportsbook, says lines move, and carries the 1-800-GAMBLER helpline. The site's own chances of winning are still worked out by the pipelines but are no longer shown outside volleyball.
- **A sportsbook, later:** wagering is a future step. Before any wagering or sportsbook links ship, age limits, location rules and responsible-gambling messaging have to be worked out. **Not yet decided:** how wagering works, and with which partner.
- **A social hub:** what it includes (accounts, comments, follows, sharing) is **undecided**. It will need features the static site does not have today, such as accounts and a server.

**Ground rules (your decision, delegated: these are my recommendations):**
- **Firm:**
  - Plain-English wording, with no jargon and no small print.
  - Light and dark themes on every page.
  - Accessible, keyboard-usable pages.
  - Fast pages that work well on phones.
- **Firm for now:** each sport stays self-contained, so a change to one cannot break another. Shared pieces (the sports strip, the front page) live in `home/` and `tools/`.
- **Current, not permanent:**
  - Plain HTML, CSS and JavaScript on static GitHub Pages, with no framework or build step.
  - The social hub and the sportsbook will likely need a server. Revisit the stack when they start.

**Terminology in use:**
- **GOAT ranking:** the site's own team ranking.
- **Impact:** a player's points added over an average regular at the same position.
- **Chance of winning:** the site's own win probability (shown for volleyball only).
- **Betting line:** the sportsbook's line and over/under, read from ESPN.
- **Beat / Lost to:** a team's results against the top 25.
- **Lines (hockey page):** hockey line combinations, not betting lines.

## Brand Commitments

- **Name:** GOAT Sports. Each sport keeps the pattern GOAT Football, GOAT Basketball, GOAT Baseball, GOAT Hockey and GOAT Volleyball.
- **Voice:** plain, friendly and exact. Short everyday words, full sentences, no hype and no jargon. Numbers are explained in a sentence, not a footnote.
- **Independence disclaimer:** the site is not affiliated with or endorsed by the NCAA, the AVCA, LOVB, MLV, the NHL, the NFL, ESPN, the Associated Press or any team or school. This must stay, and will need to grow as leagues and betting partners are added.

## Evidence on Hand

- Live data for every league, refreshed by the pipeline. The state is stored on the `state` branch and the published pages on `gh-pages`.
- Team logos (from league and ncaa.com sources), player photos (from league sources and saved roster pages for volleyball), and the site's own icons in each `site/` folder.
- Each sport's README explains how its ratings and numbers work.
- **None of the following exists, and none should be made up:** user counts, testimonials, press, partnerships, sportsbook relationships or a record of prediction accuracy.

## Product Principles

1. **Every sport is first-class.** A smaller league gets the same depth and care as the biggest one.
2. **Answer the fan's question first:** what's on, where to watch, who's winning, how good they are. Depth comes one tap later.
3. **Every number says whose it is.** A sportsbook's line is named as the sportsbook's; the site's own ratings are explained in plain words; neither is presented as a sure thing.
4. **Plain words, no clutter.** If something needs small print to make sense, change it until it doesn't.
5. **Grow without breaking.** New sports, social features and betting are added without making the core scores and stats slower or harder to read.

## Accessibility & Inclusion

The target is WCAG 2.1 AA (my recommendation, delegated). The current site already has a skip link, visible focus outlines, light and dark themes, and turns off the live-dot animation when reduced motion is set.

Responsible gambling is a product requirement once betting information grows into wagering: age gating, location limits and help resources.
