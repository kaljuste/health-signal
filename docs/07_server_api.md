---
id: server-api
title: Preview server and API
status: draft
updated: 2026-11-14
owner: parent
made_with: Claude Code (Claude Opus 5.5, Claude Fable 5.2)
public: true
sources: [tools/serve_preview.py, deploy/site/site.py, deploy/deploy.sh, deploy/privacy_gate.py, .env.example, mocks/assets/simdb.js, mocks/assets/assistant.js, mocks/assets/present.js, launcher/index.html, mocks/arm_unit.html, kb/24_two_app_concept_and_mocks.md, kb/25_simulation_dataset.md]
depends_on: [arch]
---

# Preview server and API

> One small Python program serves the site, the apps and the database, passes questions to the AI model and text to the voice service without exposing a key, and relays the presenter's arm unit to the audience's phones.

## 1. Purpose

`tools/serve_preview.py` is the only server of the project. It exists so that the browser can read the simulated mission (browsers will not load a database from `file://`), so that the OpenRouter key and the ElevenLabs key never reach a browser, and so that phones can follow the presenter's arm unit in step. It uses the Python standard library only.

## 2. Scope

- **In:** every route with method, parameters, reply, access rule and limits; command-line flags; environment variables; what files are served; the live-view relay; behaviour when something fails.
- **Out:** the prompts and the context text ([`09_assistant.md`](09_assistant.md)), what the pages do with the replies ([`08_apps.md`](08_apps.md)), the tables inside the database ([`06_database_schema.md`](06_database_schema.md)), hosting and the overall security model ([`01_architecture.md`](01_architecture.md)).

## 3. How it works

1. At start the server parses the flags, reads `.env` from the project root, and decides whether it is **exposed** (`--public-url` given, or `--host` not `127.0.0.1`, `localhost` or `::1`).
2. It prints three lines: the local preview address, the **presenter link** (with the presenter key after `#key=`), and the audience address. If the database is missing it says how to make it.
3. It serves requests with `ThreadingHTTPServer` (one thread per connection, daemon threads, listen queue 128).
4. A `GET` is matched in this order: API routes, the database, the `/design` and `/deliverables` redirects, the `/live/` redirect, then static files.
5. A `POST` is first checked for same origin, then routed to `/api/live/publish`, `/api/tts`, `/api/stt` or `/api/assistant`.
6. Each request is logged to stderr as `HH:MM:SS "request line" status`, except the frequent `/api/live/publish`, `/api/live/time` and `/api/live/state`. Request bodies are never logged.

## 4. Interfaces

### 4.1 Routes

| Method | Path | Parameters | Reply | Access | Limits |
|---|---|---|---|---|---|
| GET | `/api/health` | Optional headers `X-Presenter-Key`, `X-OpenRouter-Key`, `X-ElevenLabs-Key` | `{"ai": bool, "model": str or null, "db": bool, "voice": bool, "voice_label": str or null, "presenter": bool, "byo": bool, "film": bool}`. `presenter` is true if the caller is trusted (this machine or the tailnet) or holds the presenter key; then `ai` and `voice` are true if our matching key is configured. `byo` is `not presenter`: the caller must bring its own keys (§4.7); then `ai` = an `X-OpenRouter-Key` header is present and `voice` = an `X-ElevenLabs-Key` header is present (not checked with the provider). `voice_label` is a name for the screen, such as "ElevenLabs v4" | Anyone | none |
| POST | `/api/assistant` | JSON `{question, context, app, mode, history}`; header `X-Presenter-Key` or `X-OpenRouter-Key` when not trusted | 200 `{"answer": str, "model": str}` | Same origin; trusted or presenter (our key), else the visitor's key (§4.7) | Trusted/presenter: 20 calls per 60 s for all of them together. Visitors: §4.7. Body at most 42,000 bytes |
| POST | `/api/tts` | JSON `{text}`; header `X-Presenter-Key` or `X-ElevenLabs-Key` when not trusted | 200 `audio/mpeg` (MP3, 44.1 kHz, 128 kbit/s), header `X-Voice-Model` with the model that spoke | Same origin; trusted or presenter (our key), else the visitor's key (§4.7) | Trusted/presenter: 40 voice calls per 60 s together (shared with `/api/stt`). Visitors: §4.7. Body at most 20,000 bytes; text cut to 1,500 characters |
| POST | `/api/stt` | The recording as the raw request body; `Content-Type` such as `audio/webm;codecs=opus` or `audio/mp4`; header `X-Presenter-Key` or `X-ElevenLabs-Key` when not trusted | 200 `{"text": str}` | As `/api/tts` | Shared voice limit; body from 500 bytes to 8,000,000 bytes |
| GET | `/live` | Read by the page: `start=1`, `poll=1` | `mocks/arm_unit.html`, which switches to audience mode on this path | Anyone | none |
| GET | `/live/` (any trailing slashes) | none | 302 to `/live` | Anyone | none |
| POST | `/api/live/publish` | JSON state (§4.5); header `X-Presenter-Key` | `{"ok": true, "viewers": int, "now": ms}` | Same origin and presenter key, also on the local machine | 30 per second; body at most 6,000 bytes |
| GET | `/api/live/events` | none | `text/event-stream`: first `retry: 2000`, then `data: {state}` per change, `: keep-alive` after 12 s without one | Anyone | 600 open streams in total |
| GET | `/api/live/state` | none | The latest state, or `{"on": false, "seq": 0, "ts": ms}` | Anyone | none |
| GET | `/api/live/time` | none | `{"now": ms}`, the server clock | Anyone | none |
| GET | `/api/live/info` | none | `{"viewers": int, "on": bool, "public_url": str, "exposed": bool}` | Anyone | none |
| GET | `/api/live/key` | none | `{"key": presenter key}` | Trusted local only; 403 otherwise | none |
| GET | `/api/live/pack` | `scenario=<id>`, letters and digits only | The walk pack (§4.6), gzip if accepted, `Cache-Control: public, max-age=300` | Anyone | none |
| GET | `/db/mission_sim.sqlite` | none | `data/sim/mission_sim.sqlite` as `application/octet-stream`, gzip if accepted | Anyone | none |
| GET | `/design` | none | 301 to `/design/` | Anyone | none |
| GET | `/design/<file>` | none | File from `design/`; `/design/` gives `styleguide.html` | Anyone | Allowed extensions only |
| GET | `/deliverables` | none | 301 to `/deliverables/` | Anyone (the redirect is not checked) | none |
| GET | `/deliverables/<file>` | none | File from `deliverables/`; `/deliverables/` gives `board.html`; a `.md` file is sent as plain text | Trusted (this machine or the tailnet); 404 otherwise | Allowed extensions, plus `.md` as text |
| GET | any other path | none | File from `mocks/`; `/` gives `index.html`, `dir/` gives `dir/index.html` | Anyone | Allowed extensions only |
| HEAD, PUT, DELETE, OPTIONS | any | none | 501 (HTML page from `http.server`) | n/a | n/a |

Visitor-key errors of `/api/assistant`, `/api/tts` and `/api/stt` are JSON `{"error": "<one plain sentence>", "code": "<code>"}`: `no_key` 403, `key_invalid` 401, `key_used_up` 402, `rate` 429 (§4.7). All other errors stay as below, without `code`.

**`POST /api/assistant` in detail.**

| Field | Type | Server handling |
|---|---|---|
| `question` | string | Trimmed, cut to 600 characters. Required |
| `context` | string | Cut to 30,000 characters. Required |
| `app` | `"habitat"` or `"arm"` | `"arm"` selects the arm-unit reply rule |
| `mode` | `"chat"` or `"voice"` | Selects the chat or voice reply rule when `app` is not `"arm"` |
| `history` | list of `{role, content}` | Last 6 items kept; only roles `user` and `assistant` with string content, each cut to 1,500 characters |

The server builds the message list (system prompt, context, a fixed acknowledgement, history, question) and calls OpenRouter once (`max_tokens` 600, `temperature` 0.3). If the reply was cut by the token limit (`finish_reason` is `length`), the answer is shortened to its last whole sentence. Prompt text: [`09_assistant.md`](09_assistant.md).

**`POST /api/tts` and `POST /api/stt` in detail.** Both call ElevenLabs with the key in the `xi-api-key` header; the browser never sees it.

| Step | What the server does |
|---|---|
| Voice | `ELEVENLABS_VOICE_ID` if set. Else, once per server start, `GET /v2/voices?page_size=100` and a score per male voice: "deep" in its description or labels counts most, then "resonant", "baritone", "bass" or "low", a middle-aged or old voice, English, and a short list of preferred names. If the list cannot be read, a fixed fallback voice id is used |
| Text to speech | The text is flattened to one line and cut to 1,500 characters. Tries in order: `ELEVENLABS_MODEL` if set, `eleven_v4` on `/v1/text-to-speech/{voice_id}`, `eleven_v4` on `/v1/text-to-dialogue` (one speaker, one line), `eleven_v3`, `eleven_multilingual_v2`. The first that returns audio is remembered for the next calls. Only `stability` 0.5 and `similarity_boost` 0.8 are sent, because v4 takes no other voice settings. Output format `mp3_44100_128` |
| Cache | The audio is kept in memory under a hash of the text, 80 clips at most. The same sentence read again is served from memory |
| Speech to text | The body is wrapped by hand into a multipart form (`model_id`, `language_code` `en`, `tag_audio_events` `false`, `file`) and sent to `/v1/speech-to-text`. Tries `ELEVENLABS_STT_MODEL` if set, then `scribe_v3`, then `scribe_v2`. The reply's `text` is returned, trimmed |
| Give up early | On 401, 403 or 429 from ElevenLabs no other model is tried: the key is wrong, has no access, or the quota is used up |

### 4.2 Static files

| Rule | Detail |
|---|---|
| Base folders | `mocks/` (default), `design/` under `/design/`, `deliverables/` under `/deliverables/` (local only), plus the one database file |
| Allowed extensions | `.html .css .js .json .png .svg .wasm .ico .txt .woff2 .jpg .webp .pptx .pdf` |
| Refused | Any path part starting with a dot; any path that resolves outside its base folder (symlinks are resolved first); folders; other extensions. Reply 404 `{"error": "not found"}` |
| Content types | `.wasm` as `application/wasm`, `.sqlite` as `application/octet-stream`, others by `mimetypes`; text types get `; charset=utf-8` |
| Compression | Text files, `.wasm` and `.sqlite` are gzip-compressed (level 6) when the browser accepts it. Each result is cached in memory per file and modification time |
| Cache headers | Files `no-cache`; JSON replies `no-store`; packs `public, max-age=300` |
| Other headers | `X-Content-Type-Options: nosniff`, `Vary: Accept-Encoding` on files |

Sizes measured on 2026-11-13: the database is 19,841,024 bytes, 3,042,925 gzip-compressed; the pack of the normal walk is 2,185,714 bytes, 120,605 gzip-compressed.

### 4.3 Command-line flags

| Flag | Default | Meaning |
|---|---|---|
| `--port` | `8037` | Port to listen on. A bare number as first argument works too (`serve_preview.py 8040`) |
| `--host` | `127.0.0.1` | Address to listen on. `0.0.0.0` accepts other machines and makes the server exposed |
| `--public-url` | empty | The address the audience uses (tunnel or domain). Shown in the presenter link, the QR code and `/api/live/info`. Makes the server exposed |
| `--tailnet-url` | the environment variable `TAILNET_URL`, else empty | This server's address through Tailscale Serve. Shown on the team link list and in the start messages (§4.5b) |

### 4.4 Environment variables

Read from `.env` in the project root first, then from the process environment. `.env` lines are `KEY=value`; `#` comments, a leading `export ` and surrounding quotes are allowed.

| Variable | If missing | Used for |
|---|---|---|
| `OPENROUTER_API_KEY` | AI is off: `/api/assistant` replies 503 and the pages use the rule-built briefing | `Authorization: Bearer` header to OpenRouter |
| `OPENROUTER_MODEL` | `anthropic/claude-haiku-5.5` | Model name sent to OpenRouter |
| `ELEVENLABS_API_KEY` | The voice is off: `/api/tts` and `/api/stt` reply 503; nothing is spoken and the answers stay on screen | `xi-api-key` header to ElevenLabs |
| `ELEVENLABS_VOICE_ID` | A deep male English voice of the account is picked (see above) | Pins the voice |
| `ELEVENLABS_MODEL` | `eleven_v4`, then `eleven_v3`, then `eleven_multilingual_v2` | Pins the speech model (the others stay as fallbacks) |
| `ELEVENLABS_STT_MODEL` | `scribe_v3`, then `scribe_v2` | Pins the recognition model. Not listed in `.env.example` |
| `ELEVENLABS_API_BASE` | `https://api.elevenlabs.io` | A regional host, or a stand-in for tests. Not listed in `.env.example` |
| `OPENROUTER_API_BASE` | `https://openrouter.ai/api/v1` | A stand-in for tests (`/chat/completions` is added). Not listed in `.env.example` |
| `LIVE_PRESENTER_KEY` | A random `secrets.token_urlsafe(16)` at each start | Presenter key for publishing and, when exposed, for AI answers. Set it on a hosted server so the presenter link survives a restart. Not listed in `.env.example` |

The other keys in `.env.example` (`NASA_API_KEY`, `EARTHDATA_*`, `FIRMS_MAP_KEY`, `NCBI_*`, `ANTHROPIC_API_KEY`) are not read by the server. On 2026-11-14 `.env` holds the three `ELEVENLABS_` names with empty values: the key still has to be pasted in.

### 4.5 Live-view relay

**Shape.** One stream, one latest state, held in memory (`LIVE` in the code). No database, no file.

**Publish.** The presenter's page sends its state. The server keeps only these fields, with types forced and lengths cut:

| Field | Kept as |
|---|---|
| `on` | bool |
| `sid` | walk id, string, at most 20 characters |
| `t` | float, second of the walk |
| `playing` | bool |
| `speed` | float |
| `view` | `"route"` or `"read"` |
| `trace` | string, at most 30 characters |
| `acked` | number or null |
| `at` | float, the presenter's time on the shared clock (ms) |
| `ans` | optional `{q, a, n}`: question (400), answer (1,600), note (300 characters) |

The server adds `seq` (counter) and `ts` (server time), stores the result as the latest state, and puts it into the queue of every phone.

**Follow.** Each phone opens `/api/live/events`. It first gets the latest state (or `{"on": false, ...}`), then every new one. A phone that falls 50 messages behind has its queue emptied and gets only the newest state. The stream sends a keep-alive comment after 12 s of silence and tells the browser to reconnect after 2 s (`retry: 2000`).

**Clock.** Phones and presenter align with `/api/live/time` (fastest of three round trips). A phone computes the presenter's current second itself: `t + speed × (now − at)` while playing. So the state needs to be sent only on change, plus a heartbeat (the page sends one every 1 s while playing, every 3 s while paused, and checks for changes every 100 ms).

**Pack.** `/api/live/pack?scenario=<id>` gives one walk without the database, as JSON:

| Key | Content |
|---|---|
| `sid`, `n` | Walk id, number of seconds |
| `sc` | The row of `eva_scenario` |
| `num` | 33 numeric columns of `eva_sample` as arrays, one value per second |
| `str` | `phase`, `task`, `state`, `limiter` as runs: `[value, count, value, count, ...]` |
| `text` | `eva_text`: next-action text by `next_id` |
| `events` | `eva_event` rows: `t_s`, `kind`, `severity`, `var_id`, `text` |
| `vars` | `variable` rows with `scope = 'eva'`: label, unit, decimals, kind, rule text |
| `meta` | `landing_site`, `name` |

Walk ids today: `nominal`, `fatigue`, `co2`, `storm`.

### 4.5b Tailnet mode, launcher and always-on service (added 2026-11-14)

The server runs all the time as the macOS LaunchAgent `space.healthsignal.preview` (`~/Library/LaunchAgents/space.healthsignal.preview.plist`: `python3 -I tools/serve_preview.py --port 8037 --tailnet-url https://<machine>.<tailnet>.ts.net:8037`, `RunAtLoad`, `KeepAlive`, log `~/Library/Logs/healthsignal-preview.log`). It still listens on `127.0.0.1:8037` only. `tailscale serve --bg --https=8037 http://127.0.0.1:8037` publishes it to the owner's tailnet over HTTPS (tailnet only, no Funnel), so the iPad's microphone and clipboard work.

**Trust.** `trusted()` = `trusted_local()` (a browser on this machine) or `via_tailnet()`: the request comes from `127.0.0.1` through Tailscale Serve, the Host (or `X-Forwarded-Host`) ends in `.ts.net`, the first `X-Forwarded-For` address is in `100.64.0.0/10` or `fd7a:115c:a1e0::/48`, and there is no `Tailscale-Funnel-Request`, `Cf-Ray`, `Cf-Connecting-Ip`, `Ngrok-Trace-Id` or `Forwarded` header. Nothing is trusted when the server is exposed (`--public-url` or `--host`). Trusted viewers get the AI assistant and the voice without a key, the presenter key (`/api/live/key`), the Present switch, `/deliverables/`, the team link list, the dashboards and the docs. `same_origin()` also accepts the tailnet Origin.

| Route | Who | Returns |
|---|---|---|
| `GET /launch/` (`/launch` redirects) | trusted | `launcher/index.html`: the team's one list of links, in the order to go through them (1 the site in story order, 2 presentation, 3 what we hand in, 4 research, 5 docs), each with its full address and one line on what it is. Every address uses the Tailscale name (`--tailnet-url`), so the same list works on every team device; on this Mac it falls back to `127.0.0.1` when Tailscale does not answer, and `/launch/?local=1` forces the local addresses. One status line (server, AI model, voice, live stream); every minute the page asks the server for each link and marks any that does not answer |
| `GET /deliverables/<path>.md` | trusted | a deliverable (run sheet, strategy, checklist) as `text/plain`, so the list can link to it; other viewers get 404 |
| `GET /api/launch/info` | trusted | `{tailnet_url, local_url, via, model, voice, started, dashboards}` |
| `GET /dash/explorer`, `/dash/reference`, `/dash/mission` | trusted | the three planning dashboards from `data/` (only these three files) |
| `GET /docs/<file>.md` (`/docs/` = README) | trusted | a spec as `text/plain` (no subfolders) |

Commands: restart `launchctl kickstart -k gui/$(id -u)/space.healthsignal.preview`; stop `launchctl bootout gui/$(id -u)/space.healthsignal.preview`; unpublish `tailscale serve --https=8037 off`. The Mac must be awake for the iPad to reach it. The raw Tailscale address (`100.x.y.z`) does not work and is not used: the server listens on `127.0.0.1` only, the HTTPS certificate is for the `.ts.net` name, and the trust rule asks for that name. If `launchctl print gui/$(id -u)/space.healthsignal.preview` shows `spawn scheduled` while the site answers, a copy started by hand holds the port and the restart command has no effect: `lsof -ti tcp:8037 | xargs kill`, and the service takes over (seen on 2026-11-14).

**Keeping the list complete.** A new page, route or file the team opens gets a line in `LINKS` in `launcher/index.html` in the same change. `tools/check_docs.py` reports an error when a page in `mocks/` has no line or a line points to no file.

### 4.5c Public relay for the audience (monitordemo)

For the event the phones do not need ngrok or `--public-url`: a relay on the team's server replaces them (decision D-25). The local server is unchanged.

- **Chain:** presenter's arm unit, local server `127.0.0.1:8037`, `tools/live_bridge.py` (LaunchAgent `space.healthsignal.livebridge`), relay container, phones at `https://monitordemo.healthsignal.space/live`.
- **Paths let through** (`deploy/monitordemo/relay.py`): GET `/live`, `/api/health`, `/api/live/time`, `/api/live/info`, `/api/live/state`, `/api/live/events`, `/api/live/pack` and anything under `/assets/` or `/vendor/`; POST only `/api/live/publish`. Everything else answers 404.
- **Key:** `LIVE_RELAY_KEY` in `.env` is the same value as `LIVE_PRESENTER_KEY` in the container; it is never printed.
- **Clock:** the bridge measures the relay's clock minus the laptop's and corrects the `at` of every state, so phones sync to the relay's clock.
- **Redeploy rule:** after any change to the arm unit, its scripts or the simulated-mission database, run `bash deploy/deploy.sh monitordemo`, or the phones show an older version.
- **Known limit:** the presenter's "phones following" number counts the local server's viewers, not the relay's. The real number: `python3 -I tools/live_bridge.py --check`.
- Details, stop and start commands: `deploy/README.md`.

### 4.5d The public website (healthsignal.space)

The final public site runs in the container `healthsignal-site` (decision of 2026-11-14: online without the presentation mode and without any AI or voice key of ours on the server; visitors bring their own keys, §4.7). The local version is unchanged.

- **Wrapper:** `deploy/site/site.py` runs `tools/serve_preview.py` in hosted mode (`--host 0.0.0.0 --port 8080 --public-url https://healthsignal.space`; `APP_DIR`, `PORT`, `PUBLIC_URL` override them for a local test). It removes `OPENROUTER_API_KEY`, `ELEVENLABS_API_KEY`, `LIVE_PRESENTER_KEY` and `LIVE_RELAY_KEY` from its environment, sets our keys to none, refuses to start if an `.env` is in the image, and trusts nobody: `trusted()` and `has_key()` are always false, so every caller is a visitor and `/api/health` says `presenter: false` for everyone.
- **Let through:** GET `/`, the eleven pages (`index`, `system`, `mission`, `risks`, `measures`, `sources`, `simulation`, `database`, `habitat`, `arm_unit`, `context` `.html`), anything under `/assets/`, `/vendor/`, `/content/`, `/screens/`, `/media/`, `/manuals/` (the two user manuals as PDF), `/db/mission_sim.sqlite`, `/api/health`, `/api/live/time`; POST `/api/assistant`, `/api/tts`, `/api/stt` (same origin: the Host, the public address or `www.healthsignal.space`). `/live` and `/live/…` answer 302 to `https://monitordemo.healthsignal.space/live`. Everything else answers 404, among them `/api/live/publish`, `/api/live/key`, `/api/live/events`, `/api/live/info`, `/api/live/state`, `/api/live/pack`, `/design/`, `/launch/`, `/deliverables/`, `/docs`, `/dash/`.
- **No presentation layer:** `present.js`, `slides.js` and `sr1.js` are not in the image and answer 404. `nav.js` loads them only when `/api/health` says `presenter: true` (never here) or the visitor opened a page with `?present=1`; in that one case the browser logs three 404s and nothing appears. The Present switch can never show.
- **Staging** (`bash deploy/deploy.sh site`): `mocks/` without dot files, Python files, the three presentation files and the screenshots no page shows; `tools/serve_preview.py`; a `VACUUM INTO` copy of the database; the wrapper, `Dockerfile` and `docker-compose.yml` (read-only, non-root, no ports, network `appnet`, 384 MB, 1 CPU, no `env_file`). Then the **privacy gate** `deploy/privacy_gate.py` runs over the staged folder before anything is uploaded: it fails if the folder holds `.env*`, `.private`, `deliverables`, `launcher`, `docs` or `kb`, or if any term of `.private/forbidden_terms.txt` (case-insensitive, not inside a longer word) occurs in a text file or the database; it prints only file names. On a failure nothing is uploaded. `bash deploy/deploy.sh site --stage-only <dir>` or `DRY_RUN=1 bash deploy/deploy.sh site` stage and check without uploading.
- **Placeholder:** `deploy/site/public/index.html` stays in the repository but is no longer used: the new deploy does not upload it and removes the old copy on the server. To go back to the placeholder, deploy an older `deploy/site/` from git.

### 4.6 Failure behaviour

| Situation | What happens |
|---|---|
| Database missing | Start message says how to make it. `/db/mission_sim.sqlite` replies 404 with the command; `/api/health` shows `"db": false`; packs reply 404; pages show a banner from `simdb.js` |
| No `OPENROUTER_API_KEY` | `/api/assistant` 503 with a plain message; the page answers with the rule-built briefing |
| Not trusted, no presenter key, no visitor key | `/api/assistant` 403 `no_key`; page uses the briefing |
| Visitor key refused or used up | 401 `key_invalid` or 402 `key_used_up` (§4.7); page uses the briefing or shows the answer without voice, and says why |
| More than 20 questions in 60 s | 429; page uses the briefing |
| Body too large | 413 |
| `question` or `context` empty | 400 |
| OpenRouter replies with an HTTP error | 502 "The AI service answered with an error (code)." |
| Voice: no `ELEVENLABS_API_KEY` | `/api/tts` and `/api/stt` 503; nothing is spoken, the answer stays on screen, and the page asks the server again after 20 s |
| Voice: not trusted, no presenter key, no visitor key | 403 `no_key`; same fallback |
| Voice: more than 40 calls in 60 s | 429; that one answer is shown without voice |
| Voice: text over 20,000 bytes, or empty | 413, 400 |
| Voice: recording under 500 bytes or over 8 MB | 413 (400 if the body is empty); the page asks to type the question |
| ElevenLabs replies with an HTTP error on every model tried | 502 "The voice service answered: ..." with the reason for 401 (key refused), 403 (no access to this voice or model) and 429 (quota used up) |
| Voice: timeout (45 s), network error, bad reply | 500 "Voice call failed: `<exception name>`". Never the request or the key |
| Timeout (60 s), network error, bad reply | 500 "Assistant call failed: `<exception name>`". Never the request or the key |
| POST from another origin | 403 "cross-site request refused" |
| Publish: wrong or missing key | 403; the presenter page switches its live mode off |
| Publish: more than 30 per second, over 6,000 bytes, not a JSON object | 429, 413, 400 |
| Live view full (600 streams) | `/api/live/events` replies 503 "The live view is full." |
| Phone loses the stream | Browser reconnects after 2 s; the page also polls `/api/live/state` every 3 s if nothing arrived for 6 s. With `?poll=1` it polls every 0.8 s instead of streaming |
| Server restart | Live state is lost. Without a fixed `LIVE_PRESENTER_KEY` the key changes and the presenter must open the new link |
| Unknown path or refused file | 404 `{"error": "not found"}` |
| `HEAD` or other methods | 501 |

### 4.7 Visitor keys ("bring your own key")

**Contract** (shared with the browser side, `mocks/assets/assistant.js`, [`09_assistant.md`](09_assistant.md)): the browser may send `X-OpenRouter-Key` and/or `X-ElevenLabs-Key` on `/api/health`, `/api/assistant`, `/api/tts` and `/api/stt`, next to the optional `X-Presenter-Key`.

**Key choice, per request** (`Handler.visitor()`):

| Caller | Key used | Visitor headers |
|---|---|---|
| Trusted (this machine, the tailnet) or holding the presenter key | ours from `.env`, exactly as before (limits, messages, the shared voice and model choice) | ignored |
| Anyone else, with a key header | the visitor's key, for this one request | used |
| Anyone else, without | none: 403 `no_key` | n/a |

A header that is not a plausible key (8 to 256 printable ASCII characters, no spaces) is refused as `key_invalid` without a provider call.

**Error mapping.** The provider's error body is read (at most 8 KB, never logged or passed on); the status alone never decides.

| Provider answer | Our reply |
|---|---|
| OpenRouter `error.metadata.limit_source` set (`openrouter_key_limit`, `openrouter_credits`, …), any status | 402 `key_used_up` |
| OpenRouter 402 (insufficient credits on the account or the key) | 402 `key_used_up` |
| OpenRouter 403 whose message names a limit, budget or credit ("Budget limit exceeded. $1 of $1 used") | 402 `key_used_up` |
| OpenRouter 402 with `limit_source` `openrouter_in_flight_budget` (too many calls at once) | 502, no code |
| OpenRouter 403 for moderation or a guardrail ("flagged") | 502, no code |
| OpenRouter 401 ("Invalid credentials", "User not found."), any other 403 | 401 `key_invalid` |
| OpenRouter 200 with an `error` object instead of `choices` | judged like an HTTP error with `error.code` |
| ElevenLabs 402, or `detail.code`/`detail.status`/`detail.type` containing quota, credit or payment (`quota_exceeded` under 401, `insufficient_credits` / `payment_required` under 402) | 402 `key_used_up` |
| ElevenLabs 401 or 403 whose message names quota, credit or limit (a key's own character limit; undocumented) | 402 `key_used_up` |
| ElevenLabs any other 401 or 403 (`invalid_api_key`, `missing_api_key`, `insufficient_permissions`), or a 400 with `authentication_error` / `invalid_api_key` (a malformed key: `invalid_api_key_length`, seen 2026-11-14) | 401 `key_invalid` ("wrong, or lacks Text to Speech and Speech to Text access") |
| ElevenLabs 429 (`system_busy`, `rate_limit_exceeded`, `concurrent_limit_exceeded`) | 502 "The voice service is busy right now." |
| ElevenLabs 400 `max_character_limit_exceeded`, 404, 5xx | 502 as before |
| Our own per-visitor limit (below) | 429 `rate` |

Sources (read 2026-11-14): OpenRouter "Errors" API reference (401 invalid credentials, 402 insufficient credits, 403 budget limit with `metadata.limit_source`); ElevenLabs "Errors" developer reference (body `detail.{type, code, message, status}`, `status` is legacy) and help-center note on `invalid_api_key` / `quota_exceeded`; the `invalid_api_key_length` 400 was observed live with a made-up key.

**Voice with a visitor key** (`speak_byo`, `transcribe(key=…)`): no voice listing (a visitor key may lack "Voices read"). The voice is `ELEVENLABS_VOICE_ID` if set, else the voice our own key picked if known, else the fallback "Brian"; if ElevenLabs answers 404 for that voice, the fallback is used. The model chain (`eleven_v4` standard and dialogue route, `eleven_v3`, `eleven_multilingual_v2`; Scribe v3, v2) is tried per request; the model that last worked for any visitor is tried first (an order hint only). Nothing a visitor call does changes our own remembered voice, model or cache.

**Audio cache for visitors:** one cache of its own (80 clips, key = voice + text), separate from ours. A clip is served from it only to a key that ElevenLabs accepted in the last 10 minutes (a salted hash of the key is remembered for that); a made-up key always goes to ElevenLabs and gets its refusal.

**Rate limits for visitors** (per minute, checked in this order, all must pass): assistant 20 per key, 60 per address, 120 for all visitors together; voice (TTS and STT together) 40 per key, 120 per address, 240 together. The key is identified by a salted hash (salt made at start, never stored); the address is `Cf-Connecting-Ip`, else the socket address. The per-address limit is generous because a whole event room may share one address. Trusted and presenter callers keep the old limits (20 and 40 a minute together).

**Never stored:** a visitor key goes into no module global, file, log line, error message or reply. The access log has only the request line and status (no headers). In memory, for at most 10 minutes per key, there is a salted hash: for the rate limits and "this key worked". The system prompt is always ours and the request size limits stay, so the endpoint cannot be used as a general model proxy.

## 5. Run it

```sh
python3 -I tools/serve_preview.py                                  # local: http://127.0.0.1:8037/
python3 -I tools/serve_preview.py --port 8040                      # another port
ngrok http 8037                                                    # laptop fallback for phones, then:
python3 -I tools/serve_preview.py --public-url https://<tunnel address>
python3 -I tools/serve_preview.py --host 0.0.0.0 --public-url https://live.healthsignal.space   # planned stream container
```

For the event the relay in §4.5c replaces the ngrok fallback for phones.

Quick checks (no key is printed):

```sh
curl -s http://127.0.0.1:8037/api/health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8037/.env          # expect 404
curl -s -o /dev/null -w '%{http_code}\n' -H 'Cf-Ray: x' http://127.0.0.1:8037/api/live/key   # expect 403
curl -s -o /tmp/voice.mp3 -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{"text":"Readiness 77."}' http://127.0.0.1:8037/api/tts   # 200 with a key, 503 without
```

Checked on 2026-11-13 with a local instance on a spare port: `/.env`, `/../.env`, `/%2e%2e/.env`, `/tools/serve_preview.py`, `/design/build.py` gave 404; `/api/live/key` gave 200 locally and 403 with a `Cf-Ray` header or a foreign `Host`; a cross-origin POST gave 403; publishing without a key gave 403; on an exposed instance `/api/live/key` gave 403, `/api/health` gave `"ai": false` and `/api/assistant` gave 403.

Checked on 2026-11-14 (visitor keys) with the staged site wrapper on spare ports: all eleven pages, assets and the database 200; the blocked paths 404, `/live` 302 to monitordemo; `/api/health` without keys `byo: true, ai: false, voice: false, presenter: false`, with `X-OpenRouter-Key` `ai: true`; `/api/assistant` without key 403 `no_key`, with a made-up key 401 `key_invalid` (real OpenRouter); `/api/tts` and `/api/stt` with a made-up key 401 `key_invalid` (real ElevenLabs answers 400 `invalid_api_key_length`); against a local stand-in for both providers every row of the mapping table in §4.7, the per-key limit (429 after 20) and the cache rule. Real calls with the project's keys sent as visitor headers: two answers (plain and streamed) and 57 KB of `eleven_v4` audio. On the project's own server file, trusted callers ignored the visitor headers and kept the old replies. A POST to `https://monitordemo.healthsignal.space` with its own `Origin` passed the same-origin check (Cloudflare keeps the Host).

Checked on 2026-11-14 with a second instance on a spare port and a local stand-in for the ElevenLabs API: `/api/tts` returned audio with `X-Voice-Model: eleven_v4`; when the stand-in refused v4 on the standard route, the server used the dialogue route, and when it refused that too, `eleven_v3`, and kept the working choice; the deep male voice was picked from the voice list; `/api/stt` returned the text; both apps played the audio and stopped it on request. Without a key the always-on server gave 503 on `/api/tts`. **The real ElevenLabs service has not been called yet.** Test questions through OpenRouter the same night: `anthropic/claude-haiku-5.5` answered in 1.6 s, `anthropic/claude-sonnet-5.5` in 3.6 s.

## 6. Data and provenance

| What the server sends | Label | Source |
|---|---|---|
| Database, packs | SIM (with per-value labels inside) | `tools/generate_mission_sim.py` |
| Assistant answers | AI | OpenRouter model, from the context the browser sent |
| Spoken answers | AI (synthetic voice) | ElevenLabs, from the answer text |
| Recognised questions | AI (speech to text) | ElevenLabs, from the recording the browser sent |
| Live state | Presenter's actions | The presenter's arm unit |
| Server time | Real clock | The server |

The server adds no data of its own and stores nothing on disk. Spoken clips are cached in memory only; recordings are passed on and not kept.

## 7. Decisions and assumptions

- Runtime AI only through this server; keys never in the browser (`13_decisions.md`, D-01).
- Hosting behind Cloudflare tunnels on the parent's VPS (D-07).
- Live audience view (D-08).
- One ElevenLabs voice for both apps, reached only through this server (D-19).
- Assumption: one presenter at a time, one process per address; the relay is not built to scale beyond one process.

## 8. Open questions

1. **`HEAD` gives 501.** Uptime checks and some proxies use `HEAD`; the tunnel's health checks may report the server as down.
2. **AI rate limit is global for trusted and presenter callers.** 20 questions per minute shared, the hit list changed without a lock. Fine for one presenter. Visitors have their own per-key limits since 2026-11-14 (§4.7).
3. **Live events are open to anyone.** There is no per-address limit, so one script can take all 600 streams (one thread each) and lock real phones out.
4. **The presenter key ends up in logs.** It is printed to stdout at start. In a container, that goes to the container log, and with a fixed `LIVE_PRESENTER_KEY` it stays valid. Consider printing it only to a terminal, or masking it.
5. **Bad numbers in a publish drop the connection.** A non-numeric `t`, `speed` or `at`, or a broken `Content-Length`, raises outside the error handler; the connection closes without a reply. Only key holders can reach it.
6. **Same-origin check versus the tunnel. Closed 2026-11-14:** a POST through the real tunnel to monitordemo with its own `Origin` passed; Cloudflare keeps the `Host`. The site wrapper also accepts its public address and `www.healthsignal.space` as origins.
7. **Event streams through Cloudflare are untested** (`kb/24` §3b). `X-Accel-Buffering: no` only helps nginx.
8. **Pack size.** `kb/24` and `kb/25` say "90 KB"; the normal walk measured 121 KB compressed (2.2 MB raw) on 2026-11-13. Update the notes or shrink the pack.
9. **`/design/` is public, `/deliverables/` is not.** On an exposed server `/design/templates/deck.json`, `slides.html` and `slides.pptx` (the draft deck text) are readable by anyone. Decide whether that is intended.
10. **`/deliverables/` redirect. Partly closed:** the folder exists since 2026-11-13 and the route works for trusted viewers. Still open: the 301 from `/deliverables` is sent before the trust check, so a remote visitor learns the route exists.
11. **Dead fallback in `simdb.js`.** It also tries `../data/sim/mission_sim.sqlite`, which works only if the project root is served by a plain static server. `CLAUDE.md` forbids that because it exposes `.env`. Remove the fallback.
12. **No Content Security Policy** or other hardening headers; Cloudflare could add them.
13. **Licence files not served.** `mocks/vendor/sqljs/LICENSE` and `SHA256SUMS` have no allowed extension; only the `README.txt` notes are reachable.

14. **Voice untested against the real service.** No ElevenLabs key is in `.env` (2026-11-14). Unknown until tested: whether `eleven_v4` answers on `/v1/text-to-speech` for our account (the ElevenLabs model page, read 2026-11-14, names the Text to Dialogue API for v4), whether the dialogue route accepts our one-line request, and how long a spoken answer takes. The fallbacks are in place.
15. **ElevenLabs default voices.** The ElevenLabs voices page (read 2026-11-14) says its default voices expire on 2026-12-31. A voice picked from the account's list may stop working after that date; pin a lasting voice with `ELEVENLABS_VOICE_ID` if the site stays online for judging.
16. **Voice limit is global and unlocked for trusted and presenter callers,** like the AI limit (item 2). Visitors: §4.7.
17. **Visitor voice.** On the site container there is no own key, so visitors hear the fallback voice "Brian" unless `ELEVENLABS_VOICE_ID` is set in its compose file. ElevenLabs default voices expire on 2026-12-31 (item 15).
18. **`?presenter=1` on the public site** opens the arm unit's presenter controls; publishing and the key route answer 404 there, so the page only shows that the server refused. Harmless, but visible to anyone who tries the parameter.

## 9. Change log

| Date | Change |
|---|---|
| 2026-11-13 | Created. Covers the `/deliverables/` route, the `/design` and `/deliverables` redirects and the `.pptx` and `.pdf` extensions added to the server on 2026-11-13 |
| 2026-11-14 | Tailnet mode (`--tailnet-url`, `via_tailnet()`, `trusted()`), launcher, `/dash/*`, `/docs/*`, always-on LaunchAgent, Tailscale Serve on 8037 |
| 2026-11-14 | Voice routes `/api/tts` and `/api/stt` (ElevenLabs), new fields in `/api/health`, default model `anthropic/claude-haiku-5.5`, `max_tokens` 600 with sentence-safe cut, the launcher as a plain link list |
| 2026-11-14 | Link list: Tailscale addresses on every link, order to go through, per-link check every minute, `?local=1`; `/deliverables/*.md` as plain text for trusted viewers; note on a stray server copy; `check_docs.py` checks the list |
| 2026-11-14 | Visitor keys (§4.7): `X-OpenRouter-Key`, `X-ElevenLabs-Key`, `byo` in `/api/health`, error codes `no_key` / `key_invalid` / `key_used_up` / `rate`, per-visitor limits, `OPENROUTER_API_BASE`. The public site container (§4.5d) with `deploy/site/site.py` and the privacy gate |
| 2026-11-14 | `/api/assistant`: `stream: true` gives the answer as plain text while it is written; hidden reasoning off; an empty answer is an error. The voice is looked up at start. Video files (`.mp4`, `.webm`) are served with byte ranges; `/api/health` has `film` (is `mocks/media/pitch.mp4` there) |
| 2026-11-14 | Public site: `/manuals/` let through (the two user manuals as PDF) |
