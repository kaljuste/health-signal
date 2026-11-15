---
id: design
title: Design system
status: draft
updated: 2026-11-14
owner: parent
made_with: Claude Code (Claude Opus 5.5, Claude Fable 5.2)
public: true
sources: [design/README.md, design/tokens.json, design/build.py]
depends_on: [overview]
---

# Design system

> One look for the site, both apps, the slides, the video and every document. The full guide is `design/README.md`; the visual guide is `/design/` on the preview server.

## 1. Purpose
Everything the team shows reads the same tokens, so a change in one place reaches every screen, slide and frame.

## 2. Scope
- In: colours, type, spacing, components, icons, working mark, slide deck build, video frames, document and link-card templates, asset register.
- Out: content (lives in `deliverables/`), app logic (`08_apps.md`).

## 3. How it works
1. `design/tokens.json` holds every value.
2. `python3 -I design/build.py` writes `design/tokens.css`, the icon sprite, both slide decks (template and the pitch deck in `deliverables/pitch_deck/`) as HTML and PowerPoint, and copies tokens, components, fonts and brand files to `mocks/assets/hs/`.
3. Pages link `tokens.css` and `components.css` and use only `var(--…)` values and `hs-` classes.

## 4. Interfaces
| Kind | Name | Description |
|---|---|---|
| Source | `design/tokens.json` | Dark and light values, type, spacing, slide and video geometry |
| Source | `deliverables/pitch_deck/deck.json` | Text of the pitch deck |
| Output | `mocks/assets/hs/` | What the site and apps load |
| Output | `deliverables/pitch_deck/slides.html`, `slides.pptx` | The pitch deck (7 slides) |
| Not built from tokens | `mocks/assets/slides.js`, `mocks/assets/present.js`, `mocks/assets/bodyfig.js` | The slides of presentation mode (one to three per tab, `08_apps.md` §4.5). Same colours and fonts as the tokens, but written as fixed values in the script, so they also work on the two apps that carry their own token copy |
| Register | `design/ASSETS.md` | Every picture, font and icon with source, licence, label |

## 5. Run it
```sh
python3 -I design/build.py
python3 -I tools/serve_preview.py     # then open http://127.0.0.1:8037/design/
```

## 6. Data and provenance
Fonts are SIL OFL; icons and the mark are our own SVG; screenshots are of our own apps (simulated data). AI-made pictures carry the **AI-generated** mark and a row in `design/ASSETS.md`.

## 7. Decisions and assumptions
A dark theme of our own, with the deviations listed in `13_decisions.md` (D-12).

## 8. Open questions
- The co-designer's name and logo choice.
- Moving the apps' page-local CSS onto the shared `hs-` classes.
- The presentation-mode slides (`mocks/assets/present.js`) and the new pages' charts hold colour values of their own. A change to `design/tokens.json` does not reach them.
- The team link list (`launcher/index.html`) is plain on purpose and uses no tokens (D-20).

## 9. Change log
| Date | Change |
|---|---|
| 2026-11-13 | Created |
| 2026-11-14 | Presentation-mode slides and the plain link list noted as outside the token build |
| 2026-11-14 | The body figure (`mocks/assets/bodyfig.js`, our own drawing) is shared by the habitat app and two slides |
