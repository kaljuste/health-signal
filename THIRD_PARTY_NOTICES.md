# Third-party materials and their licences

Health Signal's own work (code, website, apps, documentation, manuals, the simulated mission database) is licensed under the **Apache License 2.0** (see `LICENSE`). This file names every material in the project that is not ours, with its licence, as the NASA Space Apps Challenge Participant Terms require ("Any licenses applicable to your Solution Materials must be identified in the documentation"). Every source is also cited on the project page and on the website (Data tab: `mocks/sources.html`; limits and their sources: Measures tab).

## Code shipped with the website

| Material | Where | Licence |
|---|---|---|
| sql.js (SQLite compiled to WebAssembly) | `mocks/vendor/sqljs/` | MIT (`mocks/vendor/sqljs/LICENSE`) |
| qrcode-generator 1.4.4 by Kazuhiko Arase | `mocks/vendor/qrcode/` | MIT (`mocks/vendor/qrcode/README.txt`) |

## Fonts shipped with the website

| Font | Where | Licence |
|---|---|---|
| Manrope | `mocks/assets/hs/fonts/` | SIL Open Font License 1.1 (`OFL-manrope.txt`) |
| Chakra Petch | `mocks/assets/hs/fonts/` | SIL Open Font License 1.1 (`OFL-chakra-petch.txt`) |
| Azeret Mono | `mocks/assets/hs/fonts/` | SIL Open Font License 1.1 (`OFL-azeret-mono.txt`) |

## Data behind the simulated mission

The database `data/sim/mission_sim.sqlite` contains no record copied from any of these sources. Real measurements of NASA and partner missions are replayed onto the simulated mission dates ("replay"); the other sources only shape the simulation through aggregates, baselines, limits and probabilities. The raw data itself is not part of this repository. The table `source_use` inside the database lists every source and how it was used.

| Source | Use | Licence | Link |
|---|---|---|---|
| Curiosity RAD radiation dose, cruise and Mars surface (NASA PDS) | replay | NASA, public domain | https://pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/ |
| LRO CRaTER radiation dose, deep space (NASA PDS) | replay | NASA, public domain | https://pds-ppi.igpp.ucla.edu/data/lro-crater/data-der-hk/ |
| Curiosity REMS weather at Gale crater | replay | NASA/JPL, public domain | https://mars.nasa.gov/rss/api/?feed=weather&category=msl&feedtype=json |
| ISS cabin temperature, humidity, CO₂ and dose (NASA OSDR Environmental Data App) | replay | NASA, public domain | https://visualization.osdr.nasa.gov/eda/ |
| NASA DONKI solar particle events (CCMC) | replay | NASA, public domain | https://ccmc.gsfc.nasa.gov/tools/DONKI/ |
| OMNI2 hourly proton flux (NASA SPDF, OMNIWeb) | replay | NASA, public domain; acknowledge OMNIWeb | https://omniweb.gsfc.nasa.gov/ |
| NOAA list of solar proton events | replay | US Government work, public domain | https://umbra.nascom.nasa.gov/SEP/ |
| JPL Horizons positions of Earth and Mars | computed mission plan | NASA/JPL, public domain | https://ssd.jpl.nasa.gov/horizons/ |
| Inspiration4 complete blood count (NASA OSDR, OSD-569) | baseline | NASA open data, public domain; cite the study | https://osdr.nasa.gov/bio/repo/data/studies/OSD-569 |
| Inspiration4 comprehensive metabolic panel (NASA OSDR, OSD-575) | baseline | NASA open data, public domain; cite the study | https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 |
| NASA-STD-3001 and NASA OCHMO technical briefs | limits and rules | NASA, public | https://www.nasa.gov/directorates/esdmd/hhp/human-spaceflight-and-aviation-standards/ |
| NASA ranking of medical conditions by probability (Integrated Medical Model) | probability of medical events | NASA, public | https://www.nasa.gov/wp-content/uploads/2026/08/ranking-of-medical-conditions-by-probability.pdf |
| NASA Human Research Roadmap, the human health risks | Risks tab | NASA, public | https://humanresearchroadmap.nasa.gov/Risks/ |
| CDC NHANES 2013–2014 | healthy adult baselines | US Government work, public domain; NCHS data-use terms (statistical use only, no re-identification) | https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?BeginYear=2013 |
| ACTES graded cycle-ergometer tests (PhysioNet) | shape of exercise heart rate | Open Data Commons Attribution License v1.0 | https://physionet.org/content/actes-cycloergometer-exercise/1.0.0/ |
| MMASH 24-hour heart, sleep and stress data (PhysioNet) | shape of heart rate over the day | Open Data Commons Open Database License v1.0 | https://physionet.org/content/mmash/1.0.0/ |
| Graded exercise tests with blood lactate (Zenodo) | shape of lactate | CC BY 4.0 | https://zenodo.org/records/10841412 |
| Graded head-down tilt, heart rate variability (Zenodo) | check of direction | CC BY 4.0 | https://zenodo.org/records/22116030 |
| Sleep deprivation, vigilance and mood (OpenNeuro ds004902) | shape of reaction time and mood | CC0 | https://openneuro.org/datasets/ds004902 |
| SILSO sunspot number (Royal Observatory of Belgium) and NOAA SWPC solar cycle prediction | choice of the replay window only; no value copied | SILSO: CC BY-NC 4.0; NOAA SWPC: public domain | https://www.sidc.be/SILSO/ · https://www.swpc.noaa.gov/products/solar-cycle-progression |

Three further PhysioNet datasets that may not be redistributed (PhysioNet Contributor Review Health Data License 1.5.0) were examined but are **not used** in the simulation and are not part of this repository.

## Facts quoted on the website

Three figures in "From Mars to Earth" on the Overview are from the World Health Organization and are linked there: https://www.who.int/news-room/fact-sheets/detail/universal-health-coverage-(uhc) · https://www.who.int/health-topics/health-workforce · https://www.who.int/news/item/30-06-2025-social-connection-linked-to-improved-heath-and-reduced-risk-of-early-death

## Services used at run time and in production (not shipped)

| Service | Use | Terms |
|---|---|---|
| OpenRouter, with the model Anthropic Claude Haiku 5.5 | the assistant's answers | OpenRouter's and the model provider's terms of service |
| ElevenLabs | the assistant's synthetic voice and speech to text | ElevenLabs' terms of service |
| Google Veo; ElevenLabs | the 30-second film, AI-generated (marked in the film) | the services' terms |
| Claude Code by Anthropic | AI agents that wrote code and drafted texts under our direction (see README, Use of AI) | Anthropic's terms of service |
| Cloudflare Tunnel | hosting of the public website | Cloudflare's terms of service |

The assistant's answers and voice are made at run time through our server; none of them is stored in this repository.
