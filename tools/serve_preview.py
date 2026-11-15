#!/usr/bin/env python3
"""Preview server for the site in mocks/, the simulated mission and the live audience view.

    python3 -I tools/serve_preview.py                      local preview: http://127.0.0.1:8037/
    python3 -I tools/serve_preview.py --public-url https://xyz.ngrok.app      behind a tunnel (ngrok http 8037)
    python3 -I tools/serve_preview.py --host 0.0.0.0 --port 8037 --public-url https://demo.example.org   on a server

Serves only: the files in mocks/, the design module design/ (as /design/: style guide and templates), the submission
drafts in deliverables/ (as /deliverables/), the launcher (/launch/), the three data dashboards (/dash/…) and the
docs (/docs/…) — those four to this machine and the owner's Tailscale devices only — the database
data/sim/mission_sim.sqlite (as /db/mission_sim.sqlite), and:
    GET  /api/health            is an AI model connected? is the voice connected? is the pitch film there (mocks/media/pitch.mp4)?
    POST /api/assistant         {question, context, app, mode, history} -> {answer, model}; with stream: true the answer as plain text, piece by piece
    POST /api/tts               {text} -> audio/mpeg, the assistant's voice (ElevenLabs)
    POST /api/stt               a short recording (audio/webm or audio/mp4) -> {text} (ElevenLabs Scribe)
    GET  /live                  the audience view of the arm unit (phones; follows the presenter, no controls)
    POST /api/live/publish      the presenter's state (needs the presenter key)
    GET  /api/live/events       server-sent events: every state change, for the audience
    GET  /api/live/state|time|info|pack?scenario=...

Keys. The OpenRouter key and the ElevenLabs key (.env) stay on this machine: never sent to a browser, never printed. Publishing a
stream needs the presenter key: LIVE_PRESENTER_KEY in .env, or a random one made at start and shown once in
the presenter link below. As soon as the server is reachable from outside (--public-url or --host), the
assistant and the voice need the presenter key too, so visitors cannot spend AI credits; they get the rule-built
briefing as text on screen, unless they bring their own keys: headers X-OpenRouter-Key and
X-ElevenLabs-Key, used for that one request only, never stored or logged (docs/07 §4.7; the public site deploy/site).
Tailscale: `tailscale serve --bg --https=8037 http://127.0.0.1:8037` publishes this server to the tailnet only (HTTPS, so the
iPad's microphone and clipboard work). Requests that arrive that way count as trusted, like a browser on this machine; a
Funnel (public) request never does. Pass --tailnet-url https://<machine>.<tailnet>.ts.net:8037 so the launcher shows those links.
Nothing outside mocks/, design/, deliverables/, launcher/, the three dashboard files, docs/*.md and the one database file
can be read through this server (.env in particular)."""
import argparse, gzip, hashlib, hmac, ipaddress, json, mimetypes, os, queue, secrets, sqlite3, ssl, sys, threading, time, urllib.error, urllib.parse, urllib.request
import io, itertools
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:  # python.org builds on macOS ship without a CA bundle: use certifi's, else the system file
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if os.path.exists("/etc/ssl/cert.pem") else ssl.create_default_context()

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "mocks"
DB = ROOT / "data/sim/mission_sim.sqlite"
ALLOWED_EXT = {".html", ".css", ".js", ".json", ".png", ".svg", ".wasm", ".ico", ".txt", ".woff2", ".jpg", ".webp", ".pptx", ".pdf", ".mp4", ".webm", ".vtt"}
DESIGN = ROOT / "design"
DELIVERABLES = ROOT / "deliverables"
LAUNCHER = ROOT / "launcher"
DOCS = ROOT / "docs"
DASHBOARDS = {"explorer": ROOT / "data/explorer/dashboard.html", "reference": ROOT / "data/reference/reference.html",
              "mission": ROOT / "data/mission/mission_plan.html"}    # private planning dashboards: trusted viewers only
TAILNET_NETS = [ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48")]
MAX_CONTEXT, MAX_QUESTION, MAX_TOKENS = 30000, 600, 600
RATE = {"window": 60.0, "max": 20, "hits": []}

SYSTEM = """You are the on-board health assistant of a crewed Mars mission. You talk with one crew member.

What you are given: the crew member's measured and estimated values for this exact moment, the results of the on-board rules, the instruction the flight surgeon team on Earth sent for today (or the standing orders if the link is down), tomorrow's plan, and knowledge-base notes for whatever is flagged. Everything is simulated mission data.

How to answer:
- Use only what is in the context. Never invent a value, a limit or an instruction. If the context does not hold the answer, say so in one sentence.
- The on-board rules and Earth's instruction decide. You explain them and help the crew member act on them; you do not overrule them and you do not clear a warning.
- Start with the answer. Then the one or two numbers that support it. Then what to do next. Plain words, no jargon, no lists unless asked.
- Say where an instruction comes from: "the rule on board says" or "Earth's instruction this morning says". If the last instruction from Earth is days old, say how old.
- Values marked MODEL are estimates, not measurements: say "estimated".
- For anything that needs a medical decision, point to the crew medical officer. You are not a doctor and this is not a medical device.
- Be calm and brief. The crew member is busy and does not want to read analytics."""
VOICE = "\nThis is a spoken conversation: answer in two to four short sentences, no symbols or abbreviations that are hard to say aloud. Make the first sentence very short (under ten words) and let it give the answer: it is spoken while you write the rest."
CHAT = "\nThis is a text chat: answer in at most six sentences."
ARM = "\nThe crew member is outside in a spacesuit and reads or hears you on the arm unit: at most two short sentences, the action first. Keep the first sentence under ten words: it is spoken while you write the second."


def load_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    return env


ap = argparse.ArgumentParser(description="Preview server with the live audience view")
ap.add_argument("port_pos", nargs="?", type=int, help=argparse.SUPPRESS)
ap.add_argument("--port", type=int, default=8037)
ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to accept connections from other machines")
ap.add_argument("--public-url", default="", help="address the audience uses, e.g. the tunnel URL; shown in the QR code")
ap.add_argument("--tailnet-url", default=os.environ.get("TAILNET_URL", ""), help="this server through `tailscale serve`, e.g. https://<machine>.<tailnet>.ts.net:8037")
ARGS = ap.parse_args()
PORT = ARGS.port_pos or ARGS.port
PUBLIC_URL = ARGS.public_url.rstrip("/")
TAILNET_URL = ARGS.tailnet_url.rstrip("/")
EXPOSED = bool(PUBLIC_URL) or ARGS.host not in ("127.0.0.1", "localhost", "::1")

ENV = load_env()
KEY = ENV.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
# Default: a small, fast, current model. A spoken answer must come back in a second or two (tested 2026-11-14: 1.6 s; Sonnet 5.5 took 3.6 s).
MODEL = ENV.get("OPENROUTER_MODEL") or os.environ.get("OPENROUTER_MODEL") or "anthropic/claude-haiku-5.5"
STARTED = time.strftime("%Y-%m-%d %H:%M")
PRESENTER_KEY = ENV.get("LIVE_PRESENTER_KEY") or os.environ.get("LIVE_PRESENTER_KEY") or secrets.token_urlsafe(16)

# ---- voice: ElevenLabs, server-side only. One deep male voice for both apps, only for spoken answers (no other voice, D-31).
def cfg(name, default=""):
    return ENV.get(name) or os.environ.get(name) or default

EL_KEY = cfg("ELEVENLABS_API_KEY")
EL_API = cfg("ELEVENLABS_API_BASE", "https://api.elevenlabs.io").rstrip("/")     # a regional host (api.us.elevenlabs.io), or a test double
EL_VOICE_ID = cfg("ELEVENLABS_VOICE_ID")                     # set it to pin a voice; else a deep male voice of the account is picked
EL_VOICE_FALLBACK = "nPczCjzI2devNBz1zQrb"                   # "Brian", a deep male default voice; used only if the voice list cannot be read
EL_TTS_MODELS = list(dict.fromkeys(m for m in (cfg("ELEVENLABS_MODEL"), "eleven_v4", "eleven_v3", "eleven_multilingual_v2") if m))
EL_STT_MODELS = list(dict.fromkeys(m for m in (cfg("ELEVENLABS_STT_MODEL"), "scribe_v3", "scribe_v2") if m))
EL = {"voice": None, "voice_name": "", "tts": None, "stt": None, "cache": {}, "lock": threading.Lock(), "hits": []}
MAX_SPEECH_CHARS, MAX_AUDIO_BYTES, VOICE_RATE = 1500, 8_000_000, 40      # per request, per recording, calls a minute
OR_API = cfg("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")   # OpenRouter, or a test double

# ---- visitor keys ("bring your own", docs/07 §4.7). A caller that is neither trusted nor holds the presenter key may send
# its own keys (X-OpenRouter-Key, X-ElevenLabs-Key). Such a key is used for that one request only: it is never stored,
# logged, echoed, or put into a module global. In memory there is only a salted hash (rate limits, "this key worked").
BYO_SALT = secrets.token_bytes(16)                           # per process: the hashes mean nothing outside it
BYO_RATE = {"assistant": (20, 60, 120), "voice": (40, 120, 240)}    # calls a minute: per key, per address, all visitors
BYO = {"lock": threading.Lock(), "hits": {}, "el_ok": {}, "cache": {}, "tts_hint": None}
BYO_MSG = {
    ("assistant", "no_key"): "Add your OpenRouter key to talk to the AI assistant here; until then the rule-built briefing answers.",
    ("assistant", "key_invalid"): "OpenRouter did not accept this key. Check it, or ask for a new test key.",
    ("assistant", "key_used_up"): "This OpenRouter key has used up its credit. Ask for a new test key.",
    ("assistant", "rate"): "Too many questions in a minute. Wait a moment and ask again.",
    ("voice", "no_key"): "Add your ElevenLabs key to hear the assistant's voice; until then the answers are shown on screen.",
    ("voice", "key_invalid"): "ElevenLabs did not accept this key. It may be wrong, or lack Text to Speech and Speech to Text access.",
    ("voice", "key_used_up"): "This ElevenLabs key has used up its characters or credits. Ask for a new test key.",
    ("voice", "rate"): "Too many voice requests in a minute. Wait a moment and try again.",
}
BYO_STATUS = {"no_key": 403, "key_invalid": 401, "key_used_up": 402, "rate": 429}


def key_shape_ok(k):
    """A plausible API key: printable ASCII, no spaces, sensible length. Anything else is refused without a provider call."""
    return 8 <= len(k) <= 256 and all(33 <= ord(c) < 127 for c in k)


def key_tag(k):
    return hmac.new(BYO_SALT, k.encode(), hashlib.sha256).hexdigest()[:24]


def byo_rate(kind, tag, addr):
    """Per visitor key, per address and for all visitors together; True if this call may go ahead."""
    per_key, per_addr, total = BYO_RATE[kind]
    now = time.time()
    with BYO["lock"]:
        hits = BYO["hits"]
        if len(hits) > 4000:                                 # forget callers that have been quiet for a minute
            for b in [b for b, ts in hits.items() if not ts or now - ts[-1] >= 60]:
                del hits[b]
        buckets = ((kind + ":k:" + tag, per_key), (kind + ":a:" + addr, per_addr), (kind + ":all", total))
        for b, cap in buckets:
            hits[b] = [t for t in hits.get(b, []) if now - t < 60]
            if len(hits[b]) >= cap:
                return False
        for b, _ in buckets:
            hits[b].append(now)
        return True


def provider_error(e):
    """The JSON body of a provider's HTTP error (read once, at most 8 KB, kept on the error); {} if there is none. Never logged."""
    if not hasattr(e, "hs_body"):
        try:
            j = json.loads(e.read(8192).decode("utf-8", "replace"))
            e.hs_body = j if isinstance(j, dict) else {}
        except Exception:
            e.hs_body = {}
    return e.hs_body


def or_refusal(e):
    """An OpenRouter error for a visitor key -> "key_invalid", "key_used_up", or None (another failure: 502)."""
    err = provider_error(e).get("error")
    err = err if isinstance(err, dict) else {}
    meta = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
    src, msg = str(meta.get("limit_source") or "").lower(), str(err.get("message") or "").lower()
    if src == "openrouter_in_flight_budget":                 # many calls at once on one key: a pause helps, nothing is used up
        return None
    if src or e.code == 402:                                 # openrouter_key_limit, openrouter_credits, ...: the money is gone
        return "key_used_up"
    if e.code == 403 and any(w in msg for w in ("limit", "budget", "credit", "insufficient")):
        return "key_used_up"
    if e.code == 403 and any(w in msg for w in ("moderation", "flagged", "guardrail")):
        return None                                          # the text was refused, not the key
    if e.code in (401, 403):
        return "key_invalid"
    return None


def el_refusal(e):
    """An ElevenLabs error for a visitor key -> "key_invalid", "key_used_up", or None (another failure: 502)."""
    d = provider_error(e).get("detail")
    if isinstance(d, dict):
        code, msg = " ".join(str(d.get(k) or "") for k in ("code", "status", "type")).lower(), str(d.get("message") or "").lower()
    else:
        code, msg = "", str(d or "").lower()
    if e.code == 402 or any(w in code for w in ("quota", "credit", "payment")) or (e.code in (401, 403) and any(w in msg for w in ("quota", "credit", "limit"))):
        return "key_used_up"                                 # quota_exceeded (401), insufficient_credits (402), a key's own limit
    if e.code in (401, 403) or any(w in code for w in ("invalid_api_key", "missing_api_key", "authentication_error", "authorization_error", "permission", "unusual_activity")):
        return "key_invalid"                                 # also 400 invalid_api_key_length (seen 2026-11-14 for a malformed key)
    return None                                              # 400 max_character_limit_exceeded (text too long), 404, 429, 5xx

# ---- public relay for the audience (deploy/monitordemo): when this machine holds LIVE_RELAY_KEY, tools/live_bridge.py sends the
# live state there. The QR code then shows the relay's address and the number of phones comes from the relay.
RELAY_URL = (cfg("LIVE_RELAY_URL") or "https://monitordemo.healthsignal.space").rstrip("/") if cfg("LIVE_RELAY_KEY") else ""
RELAY = {"n": None, "at": 0.0, "busy": False}
MEDIA_CACHE = "no-cache"      # cache header for video files; the public site sets a day (deploy/site/site.py), so Cloudflare serves the film


def relay_viewers():
    """Phones on the public relay; None when there is no relay or it does not answer. Never blocks: refreshed in the background."""
    if not RELAY_URL:
        return None
    if time.time() - RELAY["at"] > 2 and not RELAY["busy"]:
        RELAY["busy"] = True

        def go():
            try:
                req = urllib.request.Request(RELAY_URL + "/api/live/info", headers={"User-Agent": "healthsignal-preview"})
                with urllib.request.urlopen(req, timeout=4, context=SSL_CTX) as r:
                    RELAY["n"] = int(json.loads(r.read().decode()).get("viewers", 0))
            except Exception:
                RELAY["n"] = None
            finally:
                RELAY["at"], RELAY["busy"] = time.time(), False
        threading.Thread(target=go, daemon=True).start()
    return RELAY["n"]


# ---- live relay: one stream, the latest state, and the phones that follow it
LIVE = {"state": None, "seq": 0, "subs": set(), "lock": threading.Lock(), "pub": []}
MAX_SUBS, MAX_STATE = 600, 6000
PACK_NUM = ["seg_left_s", "stay_min", "walk_back_min", "dist_m", "x_m", "y_m", "met_w", "hr_bpm", "core_c", "lactate_mmol", "stamina_pct", "balance_score",
            "faint_risk_pct", "heat_kj_kg", "suit_p_kpa", "suit_o2_pct", "suit_co2_mmhg", "suit_temp_c", "battery_pct", "water_pct", "scrubber_pct", "cooling_level",
            "dose_rate_usv_h", "eva_dose_usv", "drink_ml", "left_o2_min", "left_battery_min", "left_water_min", "left_scrubber_min", "left_daylight_min",
            "left_stamina_min", "left_event_min", "next_id"]
PACK_STR = ["phase", "task", "state", "limiter"]
CACHE = {}


def now_ms():
    return int(time.time() * 1000)


def gz_cached(key, mtime, make):
    """Compress once per file version; phones on mobile data should not pull megabytes of plain text."""
    hit = CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    data = gzip.compress(make(), 6)
    CACHE[key] = (mtime, data)
    return data


def eva_pack(sid):
    """Everything the audience view needs for one walk, without the 20 MB database: columns as arrays."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        sc = con.execute("select * from eva_scenario where scenario_id=?", (sid,)).fetchone()
        if not sc:
            return None
        rows = con.execute(f"select {','.join(PACK_NUM + PACK_STR)} from eva_sample where scenario_id=? order by t_s", (sid,)).fetchall()
        pack = {"sid": sid, "sc": dict(sc), "n": len(rows),
                "num": {k: [r[k] for r in rows] for k in PACK_NUM},
                "text": {str(r[0]): r[1] for r in con.execute("select next_id, text from eva_text where scenario_id=?", (sid,))},
                "events": [dict(r) for r in con.execute("select t_s, kind, severity, var_id, text from eva_event where scenario_id=? order by t_s, rowid", (sid,))],
                "vars": {r["var_id"]: dict(r) for r in con.execute("select var_id, label, unit, decimals, kind, rule_text from variable where scope='eva'")},
                "meta": {r[0]: r[1] for r in con.execute("select key, value from meta where key in ('landing_site','name')")}}
        for k in PACK_STR:                                   # text columns as runs: [value, count, value, count, ...]
            runs, last = [], object()
            for r in rows:
                if r[k] == last: runs[-1] += 1
                else: runs += [r[k], 1]; last = r[k]
            pack.setdefault("str", {})[k] = runs
        return json.dumps(pack, separators=(",", ":")).encode()
    finally:
        con.close()


def model_request(question, context, app, mode, history, stream=False, key=None):
    system = SYSTEM + (ARM if app == "arm" else VOICE if mode == "voice" else CHAT)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "CONTEXT FOR THIS MOMENT (the crew member does not see this text):\n" + context}]
    messages.append({"role": "assistant", "content": "Understood. I will answer from this context only."})
    for h in history[-6:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            messages.append({"role": h["role"], "content": h["content"][:1500]})
    messages.append({"role": "user", "content": question})
    # No hidden reasoning: left on, the model used up to all 600 tokens thinking before the first word (slow, and now and
    # then an empty answer; measured 2026-11-14: 3.4 s and empty with it, 1.2 to 1.9 s and a full answer without).
    body = {"model": MODEL, "messages": messages, "max_tokens": MAX_TOKENS, "temperature": 0.3, "reasoning": {"enabled": False}}
    if stream:
        body["stream"] = True
    return urllib.request.Request(OR_API + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                  headers={"Authorization": "Bearer " + (key or KEY), "Content-Type": "application/json", "X-Title": "Mars crew health preview"})


def ask_model_stream(question, context, app, mode, history, key=None):
    """The answer piece by piece, as the model writes it, so the voice can start with the first sentence.
    An error of the AI service is raised on the first piece, before anything was sent to the browser.
    key: a visitor's OpenRouter key for this one call; None = ours from .env."""
    with urllib.request.urlopen(model_request(question, context, app, mode, history, stream=True, key=key), timeout=60, context=SSL_CTX) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                piece = ((json.loads(data).get("choices") or [{}])[0].get("delta") or {}).get("content")
            except ValueError:
                continue
            if piece:
                yield piece


def ask_model(question, context, app, mode, history, key=None):
    req = model_request(question, context, app, mode, history, key=key)
    with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
        j = json.loads(r.read().decode())
    if key and "choices" not in j and isinstance(j.get("error"), dict):     # an error inside a 200 reply: judge it like an HTTP error
        code = j["error"].get("code")
        raise urllib.error.HTTPError(req.full_url, code if isinstance(code, int) else 502, "provider error", None, io.BytesIO(json.dumps(j).encode()))
    choice = j["choices"][0]
    answer = (choice["message"].get("content") or "").strip()
    if choice.get("finish_reason") == "length":              # cut off by the token limit: end on the last whole sentence, never mid-word
        cut = max(answer.rfind(". "), answer.rfind(".\n"), answer.rfind("? "), answer.rfind("! "))
        if cut > 40:
            answer = answer[:cut + 1]
    return answer, j.get("model", MODEL)


def el_call(method, path, body=None, headers=None, timeout=45, key=None):
    """One call to ElevenLabs. The key is added here and nowhere else (key: a visitor's key for this call; None = ours)."""
    req = urllib.request.Request(EL_API + path, data=body, method=method, headers=dict({"xi-api-key": key or EL_KEY}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        return r.read()


def el_voice():
    """The voice id: ELEVENLABS_VOICE_ID if set, else the deepest-sounding male English voice the account offers."""
    if EL["voice"]:
        return EL["voice"]
    if EL_VOICE_ID:
        EL["voice"], EL["voice_name"] = EL_VOICE_ID, "set in .env"
        return EL["voice"]
    best, score = None, -1
    try:
        voices = json.loads(el_call("GET", "/v2/voices?page_size=100", timeout=20)).get("voices", [])
        prefer = ["brian", "bill", "adam", "george", "daniel", "callum"]
        for v in voices:
            lab = {str(k).lower(): str(x).lower() for k, x in (v.get("labels") or {}).items()}
            text = " ".join([str(v.get("description") or "").lower()] + list(lab.values()))
            if lab.get("gender", "male") != "male" or "female" in text:
                continue
            name = str(v.get("name") or "").lower().split(" ")[0]
            sc = (4 if "deep" in text else 0) + (2 if any(w in text for w in ("resonant", "baritone", "bass", "low")) else 0) \
                + (1 if lab.get("age") in ("middle_aged", "middle aged", "old") else 0) + (1 if lab.get("language", "en") == "en" else 0) \
                + (len(prefer) - prefer.index(name) if name in prefer else 0) * 0.5
            if sc > score:
                best, score = v, sc
    except Exception:
        best = None
    EL["voice"], EL["voice_name"] = (best["voice_id"], str(best.get("name") or "")) if best else (EL_VOICE_FALLBACK, "Brian (fallback)")
    return EL["voice"]


def tts_chain():
    return [(m, kind) for m in EL_TTS_MODELS for kind in (("tts", "dialogue") if m.startswith("eleven_v4") else ("tts",))]


def tts_once(text, voice, model, kind, key=None):
    """One text-to-speech call -> MP3 bytes. Only stability and similarity are sent: v4 takes no other voice settings."""
    settings = {"stability": 0.5, "similarity_boost": 0.8}
    if kind == "tts":
        body = {"text": text, "model_id": model, "voice_settings": settings}
        audio = el_call("POST", f"/v1/text-to-speech/{urllib.parse.quote(voice)}?output_format=mp3_44100_128", json.dumps(body).encode(), {"Content-Type": "application/json", "Accept": "audio/mpeg"}, key=key)
    else:                                                    # the docs name the Text to Dialogue API for v4: one speaker, one line
        body = {"inputs": [{"text": text, "voice_id": voice}], "model_id": model}
        audio = el_call("POST", "/v1/text-to-dialogue?output_format=mp3_44100_128", json.dumps(body).encode(), {"Content-Type": "application/json", "Accept": "audio/mpeg"}, key=key)
    if len(audio) < 200:
        raise ValueError("empty audio")
    return audio


def speak(text):
    """Text -> MP3 bytes. Tries the newest model first (Eleven v4), then v3, then Multilingual v2; remembers what worked.
    v4 takes stability and similarity only (no style, no speed), so those two are all we send."""
    key = hashlib.sha256(text.encode()).hexdigest()
    with EL["lock"]:
        if key in EL["cache"]:
            return EL["cache"][key]
    voice, last = el_voice(), None
    tries = [EL["tts"]] if EL["tts"] else tts_chain()
    for model, kind in tries:
        try:
            audio = tts_once(text, voice, model, kind)
            with EL["lock"]:
                EL["tts"] = (model, kind)
                if len(EL["cache"]) >= 80:
                    EL["cache"].pop(next(iter(EL["cache"])))
                EL["cache"][key] = (audio, (model, kind))
            return audio, (model, kind)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 403, 429):                    # wrong key, no access, or out of quota: another model will not help
                break
        except Exception as e:
            last = e
    EL["tts"] = None
    raise last or RuntimeError("no voice model answered")


def speak_byo(text, key, tag):
    """Text -> MP3 bytes with a visitor's key. Nothing global is chosen from it: the voice is ELEVENLABS_VOICE_ID, else the
    voice our own key picked, else the fallback (no voice listing: a visitor key may lack "Voices read"); the model chain is
    tried per call, starting with the model that worked last for a visitor (only an order hint, never a skip).
    Cache: visitors share one cache of their own (voice + text), and a clip comes from it only for a key that ElevenLabs
    accepted in the last 10 minutes, so a made-up key never gets audio."""
    voice = EL_VOICE_ID or EL["voice"] or EL_VOICE_FALLBACK
    ck = hashlib.sha256((voice + "\n" + text).encode()).hexdigest()
    with BYO["lock"]:
        if time.time() - BYO["el_ok"].get(tag, 0) < 600 and ck in BYO["cache"]:
            return BYO["cache"][ck]
        hint = BYO["tts_hint"] or EL["tts"]
    chain = tts_chain()
    if hint in chain:
        chain.remove(hint); chain.insert(0, hint)
    last = None
    for model, kind in chain:
        try:
            try:
                audio = tts_once(text, voice, model, kind, key=key)
            except urllib.error.HTTPError as e:
                if e.code != 404 or voice == EL_VOICE_FALLBACK:
                    raise
                voice = EL_VOICE_FALLBACK                    # our voice is not in this visitor's account: the default voice
                audio = tts_once(text, voice, model, kind, key=key)
            with BYO["lock"]:
                now = time.time()
                if len(BYO["el_ok"]) > 2000:
                    BYO["el_ok"] = {t: at for t, at in BYO["el_ok"].items() if now - at < 600}
                BYO["el_ok"][tag], BYO["tts_hint"] = now, (model, kind)
                if len(BYO["cache"]) >= 80:
                    BYO["cache"].pop(next(iter(BYO["cache"])))
                BYO["cache"][ck] = (audio, (model, kind))
            return audio, (model, kind)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 402, 403, 429) or el_refusal(e):      # key refused, used up or busy: another model will not help
                break
        except Exception as e:
            last = e
    raise last or RuntimeError("no voice model answered")


def transcribe(audio, ctype, key=None):
    """A short recording -> text (ElevenLabs Scribe). The multipart body is built by hand: no extra library."""
    ext = "mp4" if "mp4" in ctype or "m4a" in ctype or "aac" in ctype else "ogg" if "ogg" in ctype else "wav" if "wav" in ctype else "webm"
    last, own = None, not key                                # key: a visitor's key; their call never sets our choice
    models = ([EL["stt"]] if EL["stt"] else EL_STT_MODELS) if own else list(dict.fromkeys(([EL["stt"]] if EL["stt"] else []) + EL_STT_MODELS))
    for model in models:
        bnd = "----hs" + secrets.token_hex(12)
        parts = b""
        for k, v in (("model_id", model), ("language_code", "en"), ("tag_audio_events", "false")):
            parts += f'--{bnd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        parts += f'--{bnd}\r\nContent-Disposition: form-data; name="file"; filename="speech.{ext}"\r\nContent-Type: {ctype.split(";")[0] or "audio/webm"}\r\n\r\n'.encode() + audio + f"\r\n--{bnd}--\r\n".encode()
        try:
            j = json.loads(el_call("POST", "/v1/speech-to-text", parts, {"Content-Type": "multipart/form-data; boundary=" + bnd}, key=key))
            if own:
                EL["stt"] = model
            return str(j.get("text") or "").strip()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 403, 429) if own else (e.code in (401, 402, 403, 429) or el_refusal(e)):
                break
        except Exception as e:
            last = e
    if own:
        EL["stt"] = None
    raise last or RuntimeError("no speech-to-text model answered")


def voice_label():
    m = EL["tts"][0] if EL["tts"] else EL_TTS_MODELS[0]
    return {"eleven_v4": "ElevenLabs v4", "eleven_v4_turbo": "ElevenLabs v4 Turbo", "eleven_v3": "ElevenLabs v3", "eleven_multilingual_v2": "ElevenLabs Multilingual v2"}.get(m, "ElevenLabs " + m)


class Handler(BaseHTTPRequestHandler):
    server_version = "preview/3"

    def log_message(self, fmt, *args):
        line = fmt % args
        if "/api/live/publish" in line or "/api/live/time" in line or "/api/live/state" in line or "/api/live/info" in line:
            return                                           # several a second during a demo: keep the log readable
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), line))

    # ---- who is asking
    def has_key(self):
        k = self.headers.get("X-Presenter-Key") or ""
        return bool(k) and hmac.compare_digest(k.encode(), PRESENTER_KEY.encode())

    def via_tailnet(self):
        """A device on the owner's tailnet, reaching this server through `tailscale serve` (which connects from 127.0.0.1).
        Trusted only when the Host is a *.ts.net name, the original client is a Tailscale address, and the request is not
        a public Funnel request or anything forwarded by Cloudflare or ngrok. Nothing is trusted once the server is exposed."""
        if EXPOSED or self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        if self.headers.get("Tailscale-Funnel-Request") or any(self.headers.get(h) for h in ("Cf-Ray", "Cf-Connecting-Ip", "Ngrok-Trace-Id", "Forwarded")):
            return False
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").split(":")[0].lower()
        if not host.endswith(".ts.net"):
            return False
        try:
            ip = ipaddress.ip_address((self.headers.get("X-Forwarded-For") or "").split(",")[0].strip())
        except ValueError:
            return False
        return any(ip in n for n in TAILNET_NETS)

    def trusted(self):
        """This machine or the owner's tailnet."""
        return self.trusted_local() or self.via_tailnet()

    def trusted_local(self):
        """A browser on this machine talking to this server directly. A tunnel also connects from 127.0.0.1, so the
        forwarding headers and the Host name are checked too, and nothing is trusted once the server is exposed."""
        if EXPOSED or self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        if any(self.headers.get(h) for h in ("X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto", "Forwarded", "X-Real-Ip", "Cf-Connecting-Ip", "Cf-Ray", "True-Client-Ip", "Via", "Ngrok-Trace-Id")):
            return False
        return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

    def visitor(self):
        """None for a trusted or presenter caller (our keys from .env, as before). Otherwise the visitor's own keys from the
        headers, for this request only: {"or": OpenRouter key or None, "el": ElevenLabs key or None}."""
        if self.trusted() or self.has_key():
            return None
        return {"or": (self.headers.get("X-OpenRouter-Key") or "").strip() or None,
                "el": (self.headers.get("X-ElevenLabs-Key") or "").strip() or None}

    def caller_addr(self):
        return (self.headers.get("Cf-Connecting-Ip") or "").strip()[:64] or self.client_address[0]

    def refuse(self, kind, code):
        """A visitor-key refusal: {"error": one plain sentence, "code": code}. Never contains key material."""
        self.send_json(BYO_STATUS[code], {"error": BYO_MSG[(kind, code)], "code": code})

    def byo_gate(self, kind, key):
        """For a visitor: their key, its tag, or None after a refusal was sent (no key, odd key, too many calls)."""
        if not key:
            return self.refuse(kind, "no_key")
        if not key_shape_ok(key):
            return self.refuse(kind, "key_invalid")
        tag = key_tag(key)
        if not byo_rate(kind, tag, self.caller_addr()):
            return self.refuse(kind, "rate")
        return tag

    def same_origin(self):
        o = self.headers.get("Origin")
        if not o:
            return True
        o = o.split("://", 1)[-1]
        return o == (self.headers.get("Host") or "") or (self.via_tailnet() and o == (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""))

    # ---- replies
    def send_json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, data, ctype, gz=None, cache="no-cache"):
        if gz is not None and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            data, enc = gz, "gzip"
        else:
            enc = None
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if enc:
            self.send_header("Content-Encoding", enc)
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_media(self, path, ctype):
        """A video file, whole or in the byte range the player asks for (Safari plays nothing without ranges)."""
        size, start, end, code = path.stat().st_size, 0, None, 200
        rng = (self.headers.get("Range") or "").strip()
        if rng.startswith("bytes=") and "," not in rng:
            a, _, b = rng[6:].partition("-")
            try:
                if a:
                    start, end = int(a), (int(b) if b else size - 1)
                elif b:
                    start, end = max(0, size - int(b)), size - 1
                code = 206
            except ValueError:
                start, end, code = 0, None, 200
        end = size - 1 if end is None else min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416); self.send_header("Content-Range", "bytes */%d" % size); self.send_header("Content-Length", "0"); self.end_headers()
            return
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", MEDIA_CACHE)
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start); left = end - start + 1
                while left > 0:
                    chunk = f.read(min(262144, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk); left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass                                             # the player jumped or the page closed

    def send_file(self, path):
        if path.suffix in (".mp4", ".webm"):
            return self.send_media(path, "video/mp4" if path.suffix == ".mp4" else "video/webm")
        ctype = "application/wasm" if path.suffix == ".wasm" else "application/octet-stream" if path.suffix == ".sqlite" else (mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        text = ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml")
        if text:
            ctype += "; charset=utf-8"
        if (text or path.suffix in (".sqlite", ".wasm")) and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            return self.send_bytes(b"", ctype, gz=gz_cached(str(path), path.stat().st_mtime, path.read_bytes))
        self.send_bytes(path.read_bytes(), ctype)

    # ---- live stream
    def live_events(self):
        with LIVE["lock"]:
            if len(LIVE["subs"]) >= MAX_SUBS:
                return self.send_json(503, {"error": "The live view is full."})
            q = queue.Queue(maxsize=50)
            LIVE["subs"].add(q)
            first = LIVE["state"]
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"retry: 2000\n\n")
            msg = first or {"on": False, "seq": 0, "ts": now_ms()}
            while True:
                if msg is None:
                    self.wfile.write(b": keep-alive\n\n")
                else:
                    self.wfile.write(b"data: " + json.dumps(msg, separators=(",", ":")).encode() + b"\n\n")
                self.wfile.flush()
                try:
                    msg = q.get(timeout=12)
                except queue.Empty:
                    msg = None
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with LIVE["lock"]:
                LIVE["subs"].discard(q)

    def live_publish(self):
        if not self.has_key():
            return self.send_json(403, {"error": "presenter key missing or wrong"})
        now = time.time()
        LIVE["pub"] = [t for t in LIVE["pub"] if now - t < 1.0]
        if len(LIVE["pub"]) >= 30:
            return self.send_json(429, {"error": "too many updates"})
        LIVE["pub"].append(now)
        n = int(self.headers.get("Content-Length", "0"))
        if n > MAX_STATE:
            return self.send_json(413, {"error": "state too large"})
        try:
            st = json.loads(self.rfile.read(n).decode())
            assert isinstance(st, dict)
        except Exception:
            return self.send_json(400, {"error": "bad state"})
        clean = {"on": bool(st.get("on")), "sid": str(st.get("sid", ""))[:20], "t": float(st.get("t", 0)), "playing": bool(st.get("playing")),
                 "speed": float(st.get("speed", 1)), "view": "route" if st.get("view") == "route" else "read", "trace": str(st.get("trace", ""))[:30],
                 "acked": st.get("acked") if isinstance(st.get("acked"), (int, float)) else None, "at": float(st.get("at", now_ms()))}
        a = st.get("ans")
        if isinstance(a, dict):
            clean["ans"] = {"q": str(a.get("q", ""))[:400], "a": str(a.get("a", ""))[:1600], "n": str(a.get("n", ""))[:300]}
        with LIVE["lock"]:
            LIVE["seq"] += 1
            clean.update(seq=LIVE["seq"], ts=now_ms())
            LIVE["state"] = clean
            subs = list(LIVE["subs"])
        for q in subs:
            try:
                q.put_nowait(clean)
            except queue.Full:                               # a phone that cannot keep up gets the newest state only
                try:
                    while True: q.get_nowait()
                except queue.Empty:
                    pass
                try: q.put_nowait(clean)
                except queue.Full: pass
        rv = relay_viewers()
        self.send_json(200, {"ok": True, "viewers": len(subs) if rv is None else rv, "now": now_ms()})

    # ---- voice: text to speech and speech to text, both through ElevenLabs with the key kept here
    def voice(self, path):
        v = self.visitor()
        if v is not None:                                    # a visitor: their own ElevenLabs key, or nothing
            tag = self.byo_gate("voice", v["el"])
            return self.voice_run(path, v["el"], tag) if tag else None
        if not EL_KEY:
            return self.send_json(503, {"error": "No voice connected (ELEVENLABS_API_KEY missing in .env). Answers are shown on screen only."})
        now = time.time()
        EL["hits"] = [t for t in EL["hits"] if now - t < 60]
        if len(EL["hits"]) >= VOICE_RATE:
            return self.send_json(429, {"error": "Too many voice requests in a minute."})
        EL["hits"].append(now)
        return self.voice_run(path)

    def voice_run(self, path, key=None, tag=None):
        """key: a visitor's ElevenLabs key for this request (None = ours)."""
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if path == "/api/tts":
                if n > 20000:
                    return self.send_json(413, {"error": "text too long"})
                text = " ".join(str(json.loads(self.rfile.read(n).decode()).get("text", "")).split())[:MAX_SPEECH_CHARS]
                if not text:
                    return self.send_json(400, {"error": "text is required"})
                audio, used = speak_byo(text, key, tag) if key else speak(text)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Voice-Model", used[0])
                self.end_headers()
                return self.wfile.write(audio)
            if n < 500 or n > MAX_AUDIO_BYTES:
                return self.send_json(413 if n else 400, {"error": "the recording is empty or too long"})
            text = transcribe(self.rfile.read(n), (self.headers.get("Content-Type") or "audio/webm").lower(), key=key)
            if key:
                with BYO["lock"]:
                    BYO["el_ok"][tag] = time.time()
            return self.send_json(200, {"text": text})
        except urllib.error.HTTPError as e:
            if key:
                code = el_refusal(e)
                if code:
                    return self.refuse("voice", code)
                if e.code == 429:
                    return self.send_json(502, {"error": "The voice service is busy right now. This answer is shown on screen only."})
            why = {401: "the ElevenLabs key was refused", 403: "the ElevenLabs key has no access to this voice or model", 429: "the ElevenLabs quota is used up"}.get(e.code, "error %s" % e.code)
            self.send_json(502, {"error": "The voice service answered: %s." % why})
        except Exception as e:                                   # never echo request or key material
            self.send_json(500, {"error": "Voice call failed: %s" % type(e).__name__})

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        query = dict(p.split("=", 1) for p in self.path.split("?", 1)[1].split("&") if "=" in p) if "?" in self.path else {}
        if path == "/api/health":
            v = self.visitor()                               # a visitor: ai/voice = the key header is there (not checked with the provider)
            ok = v is None
            ai, voice = (bool(KEY) and ok, bool(EL_KEY) and ok) if ok else (bool(v["or"]), bool(v["el"]))
            return self.send_json(200, {"ai": ai, "model": MODEL if ai else None, "db": DB.exists(),
                                        "voice": voice, "voice_label": voice_label() if voice else None, "presenter": ok and (SITE / "assets" / "present.js").is_file(), "byo": not ok,
                                        "film": (SITE / "media" / "pitch.mp4").is_file()})      # the 30-second pitch film on the overview
        if path == "/api/live/time":
            return self.send_json(200, {"now": now_ms()})
        if path == "/api/live/info":
            with LIVE["lock"]:
                st = LIVE["state"]
                rv = relay_viewers()                          # with a public relay: its phones and its address (the QR code)
                return self.send_json(200, {"viewers": len(LIVE["subs"]) if rv is None else rv, "on": bool(st and st.get("on")), "public_url": PUBLIC_URL or RELAY_URL,
                                            "exposed": EXPOSED, "relay": bool(RELAY_URL), "local_viewers": len(LIVE["subs"])})
        if path == "/api/live/state":
            return self.send_json(200, LIVE["state"] or {"on": False, "seq": 0, "ts": now_ms()})
        if path == "/api/live/key":                          # only for a browser on this machine, never through a tunnel
            return self.send_json(200, {"key": PRESENTER_KEY}) if self.trusted() else self.send_json(403, {"error": "open the presenter link with its key"})
        if path == "/api/live/events":
            return self.live_events()
        if path == "/api/live/pack":
            sid = query.get("scenario", "")
            if not sid.isalnum() or not DB.exists():
                return self.send_json(404, {"error": "not found"})
            raw = eva_pack(sid)
            if raw is None:
                return self.send_json(404, {"error": "no such walk"})
            return self.send_bytes(raw, "application/json; charset=utf-8", gz=gz_cached("pack:" + sid, DB.stat().st_mtime, lambda: raw), cache="public, max-age=300")
        if path == "/db/mission_sim.sqlite":
            return self.send_file(DB) if DB.exists() else self.send_json(404, {"error": "run python3 -I tools/generate_mission_sim.py first"})
        if path == "/api/launch/info":                              # the launcher's addresses and status (trusted viewers only)
            if not self.trusted():
                return self.send_json(404, {"error": "not found"})
            return self.send_json(200, {"tailnet_url": TAILNET_URL, "local_url": f"http://127.0.0.1:{PORT}", "via": "tailnet" if self.via_tailnet() else "local",
                                        "model": MODEL if KEY else "", "voice": voice_label() if EL_KEY else "", "started": STARTED, "dashboards": {k: v.exists() for k, v in DASHBOARDS.items()}})
        if path in ("/launch", "/launch/"):
            if path == "/launch":
                self.send_response(301); self.send_header("Location", "/launch/"); self.send_header("Content-Length", "0"); self.end_headers()
                return
            return self.send_file(LAUNCHER / "index.html") if self.trusted() else self.send_json(404, {"error": "not found"})
        if path.startswith("/dash/"):                               # private planning dashboards: trusted viewers only
            f = DASHBOARDS.get(path[len("/dash/"):].strip("/"))
            if not f or not f.exists() or not self.trusted():
                return self.send_json(404, {"error": "not found"})
            return self.send_file(f)
        if path == "/docs" or path.startswith("/docs/"):            # the specs as plain text: trusted viewers only
            name = path[len("/docs/"):] or "README.md"
            f = (DOCS / name).resolve()
            if not self.trusted() or DOCS.resolve() not in f.parents or f.suffix != ".md" or not f.is_file() or "/" in name:
                return self.send_json(404, {"error": "not found"})
            return self.send_bytes(f.read_bytes(), "text/plain; charset=utf-8")
        if path in ("/design", "/deliverables"):                    # relative links: always serve these under a trailing slash
            self.send_response(301); self.send_header("Location", path + "/"); self.send_header("Content-Length", "0"); self.end_headers()
            return
        if path.rstrip("/") == "/live" and path != "/live":       # one address only, so the page's relative links resolve
            self.send_response(302); self.send_header("Location", "/live"); self.send_header("Content-Length", "0"); self.end_headers()
            return
        rel = path.lstrip("/") or "index.html"
        if rel == "live":
            rel = "arm_unit.html"
        if rel.endswith("/"):
            rel += "index.html"
        base = SITE
        if rel.split("/")[0] == "design":                    # the design module: style guide, templates, tokens
            base, rel = DESIGN, rel[len("design/"):] or "styleguide.html"
            if rel.endswith("index.html"):
                rel = rel[:-len("index.html")] + "styleguide.html"
        elif rel.split("/")[0] == "deliverables":            # drafts of the submission: this machine and the tailnet, never a tunnel
            if not self.trusted():
                return self.send_json(404, {"error": "not found"})
            base, rel = DELIVERABLES, rel[len("deliverables/"):] or "board.html"
            if rel.endswith("index.html"):
                rel = rel[:-len("index.html")] + "board.html"
            if rel.endswith(".md"):                          # run sheet, strategy, checklist: plain text for the team (linked from /launch/)
                f = (DELIVERABLES / rel).resolve()
                if DELIVERABLES.resolve() not in f.parents or not f.is_file() or any(p.startswith(".") for p in Path(rel).parts):
                    return self.send_json(404, {"error": "not found"})
                return self.send_bytes(f.read_bytes(), "text/plain; charset=utf-8")
        target = (base / rel).resolve()
        if base.resolve() not in target.parents or target.suffix.lower() not in ALLOWED_EXT or not target.is_file() or any(p.startswith(".") for p in Path(rel).parts):
            return self.send_json(404, {"error": "not found"})
        self.send_file(target)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not self.same_origin():
            return self.send_json(403, {"error": "cross-site request refused"})
        if path == "/api/live/publish":
            return self.live_publish()
        if path in ("/api/tts", "/api/stt"):
            return self.voice(path)
        if path != "/api/assistant":
            return self.send_json(404, {"error": "not found"})
        v = self.visitor()
        key = None                                           # None = our key from .env; else the visitor's, for this request only
        if v is not None:
            if not self.byo_gate("assistant", v["or"]):
                return
            key = v["or"]
        else:
            if not KEY:
                return self.send_json(503, {"error": "No AI model connected (OPENROUTER_API_KEY missing in .env). The rule-built briefing is used instead."})
            now = time.time()
            RATE["hits"] = [t for t in RATE["hits"] if now - t < RATE["window"]]
            if len(RATE["hits"]) >= RATE["max"]:
                return self.send_json(429, {"error": "Too many questions in a minute."})
            RATE["hits"].append(now)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n > MAX_CONTEXT + 12000:
                return self.send_json(413, {"error": "request too large"})
            req = json.loads(self.rfile.read(n).decode())
            question = str(req.get("question", "")).strip()[:MAX_QUESTION]
            context = str(req.get("context", ""))[:MAX_CONTEXT]
            if not question or not context:
                return self.send_json(400, {"error": "question and context are required"})
            if req.get("stream"):                            # plain text, sent while the model writes (a spoken answer starts sooner)
                pieces = ask_model_stream(question, context, req.get("app"), req.get("mode"), req.get("history") or [], key=key)
                first = next(pieces, "")
                if not first:
                    raise RuntimeError("empty answer")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store, no-transform")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("X-Model", MODEL)
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                try:
                    for piece in itertools.chain([first], pieces):
                        self.wfile.write(piece.encode()); self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass                                     # the browser stopped listening (Stop pressed, page closed)
                except Exception:
                    pass                                     # the stream broke: the browser keeps the whole sentences it has
                return
            answer, model = ask_model(question, context, req.get("app"), req.get("mode"), req.get("history") or [], key=key)
            if not answer:
                raise RuntimeError("empty answer")           # the browser then shows the rule-built briefing, never an empty bubble
            self.send_json(200, {"answer": answer, "model": model})
        except urllib.error.HTTPError as e:
            if key:
                code = or_refusal(e)
                if code:
                    return self.refuse("assistant", code)
            self.send_json(502, {"error": "The AI service answered with an error (%s)." % e.code})
        except Exception as e:                                   # never echo request or key material
            self.send_json(500, {"error": "Assistant call failed: %s" % type(e).__name__})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


if __name__ == "__main__":
    if not DB.exists():
        print("No database yet. Run: python3 -I tools/generate_mission_sim.py")
    srv = Server((ARGS.host, PORT), Handler)
    local = f"http://127.0.0.1:{PORT}"
    print(f"Launcher:   {local}/launch/" + (f"   ·   tailnet: {TAILNET_URL}/launch/" if TAILNET_URL else ""))
    print(f"Preview:    {local}/   (AI model {'connected' if KEY else 'not connected'}; voice {'ElevenLabs connected' if EL_KEY else 'not connected: answers on screen only'}; Ctrl+C to stop)")
    print(f"Presenter:  {PUBLIC_URL or local}/arm_unit.html?presenter=1#key={PRESENTER_KEY}")
    print(f"Audience:   {PUBLIC_URL or local}/live" + ("" if EXPOSED else (f"   ·   tailnet: {TAILNET_URL}/live" if TAILNET_URL else "   (this machine only; for phones start a tunnel and pass --public-url)")))
    sys.stdout.flush()
    try:
        if EL_KEY:                                               # look the voice up now, so the first spoken answer does not wait for it (costs no characters)
            threading.Thread(target=el_voice, daemon=True).start()
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
