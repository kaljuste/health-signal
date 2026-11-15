---
id: publishing
title: Publishing: repository, site and licences
status: draft
updated: 2026-11-15
owner: parent
made_with: Claude Code (Claude Opus 5.5, Claude Fable 5.2)
public: true
sources: [.gitignore, kb/03_judging_awards_and_winners.md, kb/10_open_questions_and_nov13_checklist.md, CLAUDE.md]
depends_on: [arch]
---

# Publishing: repository, site and licences

> What the public sees (site, deck, video, project page, optional GitHub repository), what never leaves the parent's machine, and under which licences.

## 1. Purpose
Show a strong, clean package without the drafts and research notes behind it, and without anything that may not be shared.

## 2. What goes where

Agreed with the parent on 2026-11-15 (D-34).

| Folder or file | Public repo | Public site | Why |
|---|---|---|---|
| `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md` | yes | – | Front page, our licence (Apache-2.0), every third-party licence |
| `mocks/` without the presentation layer | yes | yes | The product: website, both apps, manuals (PDF), the film. Includes the site's own copies of styles, fonts (with their OFL licence files), our logo and icons, which the site needs to render |
| `mocks/assets/present.js`, `slides.js`, `sr1.js` | no | no | The presentation layer (stage use only) |
| `data/sim/mission_sim.sqlite` | yes | yes | The simulated mission; no raw data in it |
| `tools/serve_preview.py` | yes | yes (inside the container) | The server: site, assistant, voice; no keys |
| `tools/sim/`, `tools/generate_mission_sim.py`, `tools/mission_planner.py` | yes | – | How the simulation is made (needs the source data to run) |
| `docs/` (files with `public: true`) | yes | – | The documentation. Not `12_ai_usage_log.md` and `13_decisions.md` (internal records) |
| `design/` (design module, templates, style guide, brand sources, build script) | no | no | Development tool; the site carries its own generated copy |
| `manuals/` (sources of the manuals) | no | – | Development files; the PDFs are in `mocks/manuals/` |
| `deliverables/` | no | no | Working texts of the submission; the final texts are on the NASA project page |
| `launcher/`, `deploy/` | no | no | The team's link list; hosting files that name our server |
| `kb/` | no | – | Research notes and captures |
| `data/anchors/`, `data/reference/`, `data/explorer/`, `data/nasa_docs/`, `data/mission/`, `config/` | **no** | **no** | Source data and its databases; three datasets may not be redistributed |
| Other scripts in `tools/` (fetching, explorer, reference database, checks, manuals build) | no | – | Development tools around the source data |
| `CLAUDE.md`, `.claude/`, `.private/`, `.env`, the co-designer's tutor folder, `.playwright-mcp/` | **never** | **never** | Internal instructions, private notes, keys, private learning material, tool cache |

## 3. Licences

The Space Apps Participant Terms (version of 7 August 2026, section "Intellectual property rights in solutions") require that original content is freely available or licensed as open source as defined by the Open Source Initiative; if no licence is named, NASA distributes it under Apache 2.0. Third-party material must be freely available or OSI-licensed, and "any licenses applicable to your Solution Materials must be identified in the documentation". Every source must be cited.

| Material | Licence | Where it is stated |
|---|---|---|
| Our code, website, apps, documentation, manuals, simulated database | **Apache-2.0** (D-34) | `LICENSE`, README |
| sql.js, qrcode-generator | MIT | `THIRD_PARTY_NOTICES.md`; licence files in `mocks/vendor/` |
| Fonts Manrope, Chakra Petch, Azeret Mono | SIL OFL 1.1 | `THIRD_PARTY_NOTICES.md`; OFL files next to the fonts in `mocks/assets/hs/fonts/` (copied by `design/build.py`) |
| Data behind the simulation (20 sources) | Per source: NASA and NOAA public domain, CC0, CC BY 4.0, ODC-By 1.0, ODbL 1.0, NHANES terms, SILSO CC BY-NC 4.0 | `THIRD_PARTY_NOTICES.md`; table `source_use` in the database; Data tab |
| AI services and hosting (OpenRouter, ElevenLabs, Google Veo, Claude Code, Cloudflare) | Their terms of service | `THIRD_PARTY_NOTICES.md` |

## 3b. The public repository

**https://github.com/kaljuste/health-signal** (public, created 2026-11-15). It is not this working folder: `python3 -I tools/export_repo.py` builds a clean copy in `~/Development/Zed/health-signal` from the list in §2 (the presentation layer, the design module, working texts, the knowledge base and all source data stay out), turns links to unpublished files into plain text, writes a short `.env.example` and `.gitignore`, and checks the copy for key-like strings, the private names list and private hostnames. To publish a change: run the script, look at `git status` and `git diff` in that folder, commit there and push. The README's illustrations are the slides of presentation mode (`docs/images/`).

## 4. Before every public commit
1. `python3 -I tools/check_docs.py` passes (no forbidden terms, front matter valid).
2. `git status` shows none of the "never" paths; `.gitignore` covers them.
3. No key in any file: search for `sk-`, `OPENROUTER`, `ELEVENLABS`, `TOKEN=` values.
4. Every picture is in `design/ASSETS.md`; AI pictures carry the mark.
5. Nothing in the project page, the README, the public docs, the manuals or the product says what was built when, before or during the event (D-32); nothing untrue about timing either.
6. `LICENSE` and `THIRD_PARTY_NOTICES.md` are present, and every new third-party file, font, library or dataset has a line in `THIRD_PARTY_NOTICES.md`.

## 5. Open questions
- Answered 2026-11-15: `mission_sim.sqlite` may be public. It holds no record copied from any source; the three PhysioNet datasets that may not be redistributed are not used at all (`05_simulation.md`, `02_data_sources.md`).
- Repository linked from the project page or not (not required, not judged; `kb/10`).

## 6. Change log
| Date | Change |
|---|---|
| 2026-11-13 | Created |
| 2026-11-14 | Launcher, dashboards and docs: this machine and the tailnet only |
| 2026-11-14 | `launcher/`, the remote script, the voice and model services; the database download on the Database tab |
| 2026-11-15 | Internal AI usage and cost report in `.private/ai_usage/` (not public) |
| 2026-11-15 | Licence decided: Apache-2.0 (D-34); `LICENSE` and `THIRD_PARTY_NOTICES.md`; what goes into the repository agreed with the parent; the open question about the simulated database answered |
| 2026-11-15 | Public repository created from the export script (§3b) |
