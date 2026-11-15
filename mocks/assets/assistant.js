/* The on-board health assistant: what it knows at a point in time, a spoken briefing without AI, and the AI call.

   It gets three things, nothing else:
     1. the values and rule results of the moment (from the simulated mission, SQLite)
     2. the exact instruction from Earth for that day (or the standing orders during the blackout)
     3. knowledge-base entries for whatever is flagged (why it matters, what to do, where the limit comes from)
   Rules decide; the assistant explains. The AI call goes through the local server (/api/assistant); the key never
   reaches the browser. Without the server the briefing still works: it is built by rules, not by AI.

   Needs assets/simdb.js. API:
     Assistant.contextForDay(day, crewId)  -> { text, data }
     Assistant.contextForEva(scenarioId, tSeconds) -> { text, data }
     Assistant.briefing(ctx)               -> short text, no AI
     Assistant.ask(question, ctx, history, mode, { onText, signal }) -> Promise<{ answer, model, offline }>
     Assistant.askAloud(question, ctx, history, mode, { speak, onText, onSpoken }) -> the same, spoken sentence by sentence
     Assistant.speakStream(onEnd) -> { feed(textSoFar, final) }, Assistant.stopSpeaking(),
     Assistant.listen({ onText, onEnd, onError }) -> stop()
     Assistant.voiceLabel() -> "ElevenLabs v4", or "" before the voice has answered
   Public site only (health says byo:true; visitors bring their own keys, see "Visitor keys" below):
     Assistant.onStatus(fn, statusEl) -> fn(health) now and after every key change; a "Keys" button next to statusEl
     Assistant.aiStatus(health, long) -> label for a byo visitor or null; Assistant.noteEl(answer) -> the key note or null
     Assistant.openKeys() -> the key dialog; Assistant.toast(text, withKeysButton) */
(function () {
  const A = {};
  const q = (s, p) => SimDB.q(s, p), one = (s, p) => SimDB.one(s, p);
  const f = (v, d) => (v === null || v === undefined) ? "n/a" : Number(v).toFixed(d === undefined ? 1 : d);
  const WORD = { ok: "ok", watch: "watch", warning: "warning", critical: "critical" };

  A.contextForDay = function (day, crewId) {
    crewId = crewId || SimDB.meta.focus_crew;
    const d = one("select * from day where day=?", [day]), b = one("select * from body_day where day=? and crew_id=?", [day, crewId]);
    const e = one("select * from env_day where day=?", [day]), crew = SimDB.crew[crewId];
    const flags = q("select a.var_id, a.status, a.value, a.reason, v.label, v.unit, v.why, v.action, v.rule_text, v.rule_tag, v.kind from assessment a join variable v on v.var_id=a.var_id where a.day=? and a.crew_id in (?, 'ENV') order by case a.status when 'critical' then 0 when 'warning' then 1 else 2 end, v.sort", [day, crewId]);
    const costs = q("select item, points from readiness_cost where day=? and crew_id=? order by points desc", [day, crewId]);
    const up = one("select * from uplink where day=? and crew_id=?", [day, crewId]);
    const items = up ? JSON.parse(up.items_json || "[]") : [];
    const plan = q("select topic, text, why from plan where day=? and crew_id=? order by seq", [day, crewId]);
    const events = q("select scope, crew_id, type, severity, title, detail, day_start, day_end from event where day_start<=? and day_end>=? and (crew_id is null or crew_id=?)", [day, day, crewId]);
    const snap = one("select * from snapshot where day=? and crew_id=?", [day, crewId]);
    const labs = q("select l.var_id, l.value, l.day, v.label, v.unit from lab l join variable v on v.var_id=l.var_id where l.crew_id=? and l.day=(select max(day) from lab where crew_id=? and day<=?)", [crewId, crewId, day]);
    const eva = one("select * from eva where day=? and crew_ids like ?", [day, "%" + crewId + "%"]);
    const next = q("select day, key_label from day where day>? and key_label is not null order by day limit 3", [day]);
    const avg = (col, n) => { const r = one(`select avg(${col}) m from body_day where crew_id=? and day between ? and ?`, [crewId, day - n + 1, day]); return r ? r.m : null; };
    const KEYS = [["sleep_h", 1], ["sleep_debt_h", 1], ["pvt_z", 1], ["mood_who5", 0], ["stress_0_10", 1], ["hr_rest_bpm", 0], ["hrv_rmssd_ms", 0], ["bp_sys_mmhg", 0], ["spo2_pct", 1],
      ["temp_core_c", 1], ["body_mass_kg", 1], ["energy_pct", 0], ["fluid_l", 1], ["urine_l", 1], ["stone_risk_irr", 2], ["exercise_pct", 0], ["vo2max_pct", 0], ["leg_strength_pct", 0],
      ["bmd_hip_pct", 1], ["sans_trt_um", 0], ["balance_pct", 0], ["stand_dhr_bpm", 0], ["ortho_risk_pct", 0], ["back_pain_0_10", 0], ["sms_grade", 0], ["dose_cum_msv", 0]];
    const L = SimDB.dayLabel(day);
    const where = d.phase === "surface" ? `on Mars at ${SimDB.meta.landing_site}, sol ${d.sol}, gravity 0.38 g` : d.phase === "outbound" ? `in deep space on the way to Mars, day ${d.phase_day} of 172, weightless`
      : d.phase === "return" ? `in deep space on the way home, day ${d.phase_day} of 189, weightless` : d.phase === "prelaunch" ? "on Earth before launch" : `back on Earth, day ${d.phase_day} after landing`;
    const T = [];
    T.push(`MISSION: ${SimDB.meta.name}. Simulated data. Today is mission day ${day} (${d.date_utc}); the crew is ${where}.`);
    T.push(`LINK TO EARTH: signal takes ${f(d.light_time_min, 1)} min one way (${f(d.round_trip_min, 0)} min for a question and its answer). Link state: ${d.comm}.`);
    T.push(`CREW MEMBER: call sign ${crew.call_sign}, ${crew.role}, ${crew.sex === "F" ? "female" : "male"}, ${crew.age} years. Activity today: ${b.activity}.` + (b.symptoms ? ` Symptoms logged: ${b.symptoms}.` : ""));
    T.push(`READINESS: ${f(b.readiness, 0)} of 100 (${b.readiness_band}).` + (costs.length ? " Costs points: " + costs.map(c => `${c.item} ${f(c.points, 0)}`).join(", ") + "." : " Nothing costs points.") + " Rule: " + SimDB.vars.readiness.rule_text + " An EVA is allowed from readiness 70; between 70 and 84 with limits.");
    T.push("VALUES (today | 7-day mean | 30-day mean):");
    KEYS.forEach(([k, dec]) => { const v = SimDB.vars[k]; if (b[k] === null || b[k] === undefined) return; T.push(`- ${v.label} [${v.kind}]: ${f(b[k], dec)} ${v.unit} | ${f(avg(k, 7), dec)} | ${f(avg(k, 30), dec)}`); });
    if (labs.length) T.push(`LAST BLOOD AND URINE PANEL (day ${labs[0].day}): ` + labs.map(l => `${l.label} ${l.value} ${l.unit}`).join("; ") + ".");
    T.push(`ENVIRONMENT: cabin CO2 ${f(e.cabin_co2_mmhg, 1)} mmHg (24-h mean), 1-h peak ${f(e.cabin_co2_max1h, 1)}; inspired oxygen ${f(e.cabin_pio2_mmhg, 0)} mmHg; ${f(e.cabin_temp_c, 1)} °C, ${f(e.cabin_rh_pct, 0)} % humidity; dose today ${f(e.dose_day_msv, 2)} mSv; storm level S${e.storm_level}` + (e.shelter_h ? `; ${e.shelter_h} h in the storm shelter (without it the dose would have been ${f(e.dose_unsheltered_msv, 1)} mSv)` : "") + (e.out_temp_max_c !== null ? `; outside ${f(e.out_temp_max_c, 0)} °C by day, ${f(e.out_temp_min_c, 0)} °C at night, sunset ${Math.floor(e.sunset_h)}:${String(Math.round(e.sunset_h % 1 * 60)).padStart(2, "0")}` : "") + ".");
    if (flags.length) { T.push("RULE RESULTS (on-board rules, these are decisions):"); flags.forEach(x => T.push(`- ${x.label}: ${WORD[x.status].toUpperCase()}. ${x.reason}.`)); } else T.push("RULE RESULTS: every value is inside its limits.");
    if (events.length) { T.push("EVENTS TODAY:"); events.forEach(x => T.push(`- ${x.title} (${x.severity}; day ${x.day_start}${x.day_end !== x.day_start ? " to " + x.day_end : ""}). ${x.detail}`)); }
    if (eva) T.push(`EVA TODAY: ${eva.outcome === "postponed" ? "postponed. " + eva.summary : `EVA ${eva.number}, ${eva.actual_min} min, outcome: ${eva.outcome}.` + (eva.summary ? " " + eva.summary : "")}`);
    if (up) {
      if (up.status === "none") T.push(`INSTRUCTION FROM EARTH: none today. The Sun blocks the link. The last instruction is ${up.age_days} day(s) old (written from data up to day ${up.based_on_day}). Standing orders:`);
      else if (up.status === "in_person") T.push("INSTRUCTION FROM EARTH: the flight surgeon is on site (on Earth).");
      else T.push(`INSTRUCTION FROM EARTH (received this morning, written by the flight surgeon team from data up to day ${up.based_on_day}; it travelled ${f(up.delay_min, 0)} min${up.status === "short" ? "; weak link, short text only" : ""}): ${up.headline}`);
      items.forEach(it => T.push(`- [${it.topic}] ${it.text} Reason: ${it.why}`));
      if (up.narrative) T.push("LETTER FROM THE FLIGHT SURGEON: " + up.narrative);
    }
    if (plan.length) { T.push("PLAN FOR TOMORROW (on-board rules):"); plan.forEach(p => T.push(`- [${p.topic}] ${p.text} Reason: ${p.why}`)); }
    if (snap) T.push(`WHY THIS DAY MATTERS: ${snap.why}`);
    if (next.length) T.push("COMING UP: " + next.map(n => `day ${n.day}: ${n.key_label}`).join("; ") + ".");
    if (flags.length) { T.push("KNOWLEDGE BASE (for the flagged values):"); const seen = {}; flags.forEach(x => { if (seen[x.var_id]) return; seen[x.var_id] = 1; T.push(`- ${x.label}. Why it matters: ${x.why} What to do: ${x.action || "see plan"} Rule: ${x.rule_text} Source: ${x.rule_tag}.`); }); }
    return { app: "habitat", day, crewId, text: T.join("\n"), data: { d, b, e, flags, costs, up, items, plan, events, snap, labs, eva, label: L } };
  };

  A.contextForEva = function (sid, t) {
    const sc = one("select * from eva_scenario where scenario_id=?", [sid]);
    t = Math.max(0, Math.min(sc.duration_s - 1, Math.round(t)));
    const s = one("select * from eva_sample where scenario_id=? and t_s=?", [sid, t]);
    const c = JSON.parse(sc.context_json);
    const log = q("select t_s, kind, severity, text from eva_event where scenario_id=? and t_s<=? and kind!='phase' order by t_s", [sid, t]);
    const next = one("select text from eva_text where scenario_id=? and next_id=?", [sid, s.next_id]);
    const hm = m => { m = Math.max(0, Math.round(m)); return Math.floor(m / 60) + ":" + String(m % 60).padStart(2, "0"); };
    const clock = x => `${Math.floor(x / 3600)}:${String(Math.floor(x % 3600 / 60)).padStart(2, "0")}:${String(x % 60).padStart(2, "0")}`;
    const T = [];
    T.push(`SITUATION: Mars walk (EVA ${c.eva_number}) at ${SimDB.meta.landing_site}, sol ${sc.sol}, mission day ${sc.day}. Simulated data. Crew member ${c.call_sign}. Suit sealed ${clock(t)} ago; local time ${Math.floor(10 + t / 3600)}:${String(Math.floor(t % 3600 / 60)).padStart(2, "0")}.`);
    T.push(`MORNING STATE: readiness ${f(c.readiness, 0)} (${c.readiness_band}), sleep last night ${f(c.sleep_h, 1)} h, sleep debt ${f(c.sleep_debt, 0)} h.`);
    T.push(`NOW: ${s.task} (phase ${s.phase}). Unit state: ${s.state.toUpperCase()}.` + (s.stay_min !== null ? ` Time to stay: ${hm(s.stay_min)} h:min, limited by ${s.limiter}. Walk back: ${f(s.dist_m, 0)} m, ${f(s.walk_back_min, 0)} min.` : ""));
    T.push(`UNIT SAYS: ${next ? next.text : ""}`);
    T.push(`BODY: heart rate ${s.hr_bpm} bpm; core ${f(s.core_c, 1)} °C; stored heat ${f(s.heat_kj_kg, 1)} kJ/kg (limit 3.0); work rate ${s.met_w} W; lactate ${f(s.lactate_mmol, 1)} mmol/L [MODEL]; stamina ${f(s.stamina_pct, 0)} % [MODEL]; balance ${s.balance_score} of 100 [MODEL]; chance to faint ${f(s.faint_risk_pct, 0)} % [MODEL]; drunk ${s.drink_ml} mL.`);
    T.push(`SUIT: pressure ${f(s.suit_p_kpa, 1)} kPa; oxygen tank ${f(s.suit_o2_pct, 0)} %; helmet CO2 ${f(s.suit_co2_mmhg, 1)} mmHg (limit 20 for 1 h); battery ${f(s.battery_pct, 0)} %; cooling water ${f(s.water_pct, 0)} %, cooling level ${s.cooling_level} of 5; scrubber ${f(s.scrubber_pct, 0)} %.`);
    T.push(`TIME LEFT (min): oxygen ${s.left_o2_min}, battery ${s.left_battery_min}, cooling water ${s.left_water_min}, scrubber ${s.left_scrubber_min}, daylight ${s.left_daylight_min}, stamina ${s.left_stamina_min}` + (s.left_event_min !== null ? `, event limit ${f(s.left_event_min, 0)}` : "") + ". Reserve kept: 30 min.");
    T.push(`RADIATION: dose rate ${f(s.dose_rate_usv_h, 0)} µSv/h (usual on Mars about 21); dose this EVA ${f(s.eva_dose_usv, 0)} µSv.`);
    if (log.length) { T.push("LOG SO FAR:"); log.forEach(x => T.push(`- ${clock(x.t_s)} ${x.severity}: ${x.text}`)); } else T.push("LOG SO FAR: no caution or alarm.");
    T.push(`SCENARIO NOTE: ${sc.summary}`);
    T.push("RULES OF THE UNIT: caution on one heat cue (heart rate above 140 bpm for 2 min, core 0.6 °C over the pre-EVA value); two cues together mean stop, rest 5 min, cooling to max [NASA V2 11011]. Return when the stay time reaches zero, on a confirmed CO2 climb, or on a storm warning. Helmet CO2 limit 20 mmHg for at most 1 hour [NASA V2 11040].");
    return { app: "arm", scenario: sid, t, text: T.join("\n"), data: { sc, s, c, log, next } };
  };

  /* A short spoken briefing built by rules alone: works without any AI. */
  A.briefing = function (ctx) {
    if (ctx.app === "arm") {
      const { s, next } = ctx.data;
      const hm = m => { m = Math.max(0, Math.round(m)); return (Math.floor(m / 60) ? Math.floor(m / 60) + " hours " : "") + (m % 60) + " minutes"; };
      const a = [];
      if (s.stay_min === null) a.push(`${s.task}.`);
      else a.push(`State ${s.state}. ` + (s.state === "return" ? `Margin after the walk back: ${hm(s.stay_min)}.` : `You can stay ${hm(s.stay_min)}, limited by ${String(s.limiter).toLowerCase()}.`));
      if (next) a.push(next.text);
      a.push(`Heart rate ${s.hr_bpm}, core ${Number(s.core_c).toFixed(1)}, helmet C O 2 ${Number(s.suit_co2_mmhg).toFixed(1)}.`);
      return a.join(" ");
    }
    const { b, flags, up, items, d } = ctx.data;
    const a = [`Readiness ${Math.round(b.readiness)}, ${String(b.readiness_band).toLowerCase()}.`];
    const hard = flags.filter(x => x.status !== "watch").slice(0, 3);
    if (hard.length) a.push("Flagged: " + hard.map(x => `${x.label.toLowerCase()}, ${x.reason}`).join("; ") + ".");
    else if (flags.length) a.push(`${flags.length} value${flags.length > 1 ? "s" : ""} to watch, nothing urgent.`);
    else a.push("Every value is inside its limits.");
    if (up && up.status === "none") a.push(`No link to Earth. The last instruction is ${up.age_days} days old; standing orders apply.`);
    else if (up && items.length) a.push(`From Earth: ${items[0].text}`);
    return a.join(" ");
  };

  /* Ask the AI through the server. Falls back to the rule-built briefing when no AI is connected.
     On a server that is reachable from outside, only the presenter (who holds the presenter key) gets AI answers. */
  /* ---------- Visitor keys (the public site only: the server says byo:true) ----------
     The public site holds no AI or voice key of ours. A visitor brings their own (or a capped test key from us): kept in
     localStorage["hs.keys"] = {"or": "...", "el": "..."}, sent as X-OpenRouter-Key / X-ElevenLabs-Key headers with each
     request, never in a URL, a log, an error text or the page. A key the provider refused (used up, not accepted) is not
     sent again until the visitor replaces or removes it: localStorage["hs.keys.state"] = {"or": "key_used_up", ...}.
     Pass link: any page opened with #or=<key>&el=<key> stores them and removes the fragment at once. On the laptop, the
     tailnet and for the presenter (byo:false) none of this shows. Docs: docs/09_assistant.md, "Visitor keys". */
  const AUD = () => window.ARM_MODE === "audience";
  const K = { byo: null, said: {} };
  const lsGet = (n, d) => { try { const o = JSON.parse(localStorage.getItem(n) || "null"); return o && typeof o === "object" ? o : d; } catch (e) { return d; } };
  const lsSet = (n, o) => { try { Object.keys(o).length ? localStorage.setItem(n, JSON.stringify(o)) : localStorage.removeItem(n); } catch (e) {} };
  const keys = () => { const o = lsGet("hs.keys", {}), r = {}; ["or", "el"].forEach(k => { if (typeof o[k] === "string" && o[k].trim()) r[k] = o[k].trim(); }); return r; };
  const keyState = () => lsGet("hs.keys.state", {});
  const usable = k => !!keys()[k] && !keyState()[k];
  function setKeys(nw, removeAll) {                // nw: {or?, el?}; a replaced key starts with a clean state
    const k = removeAll ? {} : keys(), st = removeAll ? {} : keyState();
    Object.keys(nw).forEach(n => { if (nw[n]) { k[n] = nw[n]; delete st[n]; } });
    lsSet("hs.keys", k); lsSet("hs.keys.state", st); K.said = {};
    document.dispatchEvent(new CustomEvent("assistant-keys"));
  }
  function markKey(k, code) { const st = keyState(); st[k] = code; lsSet("hs.keys.state", st); document.dispatchEvent(new CustomEvent("assistant-keys")); }
  const keyHeader = () => {
    const h = {}; let p = null; try { p = sessionStorage.getItem("presenterKey"); } catch (e) {}
    if (p) h["X-Presenter-Key"] = p;
    if (K.byo !== false) { const k = keys(), st = keyState(); if (k.or && !st.or) h["X-OpenRouter-Key"] = k.or; if (k.el && !st.el) h["X-ElevenLabs-Key"] = k.el; }
    return h;
  };
  const KEY_CODES = { no_key: 1, key_invalid: 1, key_used_up: 1, rate: 1 };
  const MSG = {
    or: { no_key: ["The AI assistant needs a key.", "Add a test key or your own."], key_used_up: ["This key is used up. The AI assistant was available for a short test.", "Add your own key to continue."],
          key_invalid: ["This key was not accepted.", "Check it in the key dialog."], rate: ["Too many requests at once. Try again in a moment.", ""] },
    el: { no_key: ["Voice input needs a key.", "Add a test key or your own."], key_used_up: ["Voice was available for a short test time.", "Add your own key to continue."],
          key_invalid: ["This voice key was not accepted.", "Check it in the key dialog."], rate: ["Too many requests at once. Try again in a moment.", ""] }
  };
  const msgText = (k, code) => MSG[k][code].filter(Boolean).join(" ");

  A.health = async function () {
    let h;
    try { const r = await fetch("api/health", { cache: "no-store", headers: keyHeader() }); if (!r.ok) throw 0; h = await r.json(); } catch (e) { return { ai: false, reason: "no server" }; }
    K.byo = h.byo === true;
    if (K.byo) { const k = keys(), st = keyState(); h.keys = { ai: st.or || (k.or ? "yours" : "none"), voice: st.el || (k.el ? "yours" : "none") }; }
    return h;
  };
  /* Status for the apps: fn(health) now, and again whenever the visitor's keys change. With anchor (the element that
     shows the assistant/voice status) a small "Keys" button next to it opens the key dialog, on the public site only. */
  A.onStatus = function (fn, anchor) {
    const run = () => A.health().then(h => { if (anchor) keysEntry(anchor, h); fn(h); });
    document.addEventListener("assistant-keys", run); run();
  };
  /* The AI part of a status label for a byo visitor; null otherwise (the app keeps its own label). */
  A.aiStatus = function (h, long) {
    if (!h || !h.byo || !h.keys) return null;
    const tail = long ? "the rule-built briefing answers" : "rules";
    return { yours: h.ai ? (long ? "AI connected with your key: " + String(h.model).split("/").pop() : "AI model · your key") : (long ? "Your key is set; no AI model answered" : "AI key set · no model"),
      none: "No AI key: " + tail, key_used_up: "AI key used up: " + tail, key_invalid: "AI key not accepted: " + tail }[h.keys.ai] || null;
  };
  /* The line under an answer that came from the rules because of a key: text plus a link to the dialog; null otherwise. */
  A.noteEl = function (r) {
    if (!r || !r.keyCode || !MSG.or[r.keyCode]) return null;
    const m = MSG.or[r.keyCode], s = document.createElement("span"); s.className = "hs-keys-note"; s.textContent = m[0] + (m[1] ? " " : "");
    if (m[1]) s.append(keysLink(m[1]));
    return s;
  };
  function keysLink(text) { const a = document.createElement("a"); a.href = "#"; a.className = "hs-keys-link"; a.textContent = text; a.addEventListener("click", e => { e.preventDefault(); A.openKeys(); }); return a; }

  const ICON_KEY = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/></svg>';
  function keysStyle() {
    if (document.getElementById("hsKeysCss")) return;
    const st = document.createElement("style"); st.id = "hsKeysCss";
    st.textContent = [
      ".hs-keys-entry{display:inline-flex;align-items:center;gap:5px;flex:none;height:24px;padding:0 9px;border:1px solid var(--color-border-strong,#706e68);border-radius:var(--radius-pill,999px);background:var(--color-surface-input,#1f1f1f);color:var(--color-text-accent-soft,#ffb39e);font:var(--type-label,600 13px/1.2 'Chakra Petch',sans-serif);font-size:11px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;white-space:nowrap;vertical-align:middle}",
      ".hs-keys-entry:hover{background:var(--color-surface-input-hover,#2b2b2b)}",
      ".hs-keys-entry.need{border-color:var(--color-border-accent,#e5522c)}",
      ".hs-keys-entry.icon{width:26px;height:26px;padding:0;justify-content:center;font-size:0;letter-spacing:0}.hs-keys-entry.icon svg{width:15px;height:15px}",
      "p.hs-keys-row{margin:6px 0 0}",
      ".ah:has(> .hs-keys-entry) > b{white-space:nowrap}",
      ".hs-keys-link{color:var(--color-text-accent-soft,#ffb39e);text-decoration:underline;text-underline-offset:2px;cursor:pointer}",
      ".hs-keys-link:hover{color:var(--color-text-default,#e8e4d8)}",
      "dialog.hs-keys{width:min(460px,calc(100vw - 24px));max-height:calc(100dvh - 24px);overflow:auto;padding:0;border:1px solid var(--color-border-default,#2b2b2b);border-top:3px solid var(--color-border-accent,#e5522c);border-radius:var(--radius-lg,20px);background:var(--color-surface-raised,#171717);color:var(--color-text-default,#e8e4d8);font:var(--type-body-default,400 16px/1.5 'Manrope',sans-serif);box-shadow:0 18px 60px rgba(0,0,0,.6)}",
      "dialog.hs-keys::backdrop{background:var(--color-overlay-scrim,rgba(5,5,5,.72))}",
      ".hs-keys form{margin:0;padding:20px 22px 22px;display:grid;gap:14px}",
      ".hs-keys .top{display:flex;align-items:center;justify-content:space-between;gap:12px}",
      ".hs-keys h2{margin:0;font:var(--type-label,600 13px/1.2 'Chakra Petch',sans-serif);font-size:15px;letter-spacing:1.4px;text-transform:uppercase;color:var(--color-text-display,#ddd6c5);display:flex;align-items:center;gap:8px}",
      ".hs-keys h2 svg{color:var(--color-text-accent,#e5522c);width:18px;height:18px}",
      ".hs-keys .x{width:32px;height:32px;border-radius:50%;border:1px solid var(--color-border-strong,#706e68);background:transparent;color:var(--color-text-muted,#9a968c);font:400 18px/1 'Manrope',sans-serif;cursor:pointer}",
      ".hs-keys .x:hover{color:var(--color-text-default,#e8e4d8)}",
      ".hs-keys p{margin:0;font:var(--type-body-small,400 13px/1.4 'Manrope',sans-serif);color:var(--color-text-muted,#9a968c);max-width:none}",
      ".hs-keys label{display:grid;gap:6px}",
      ".hs-keys .lab{display:flex;align-items:center;justify-content:space-between;gap:8px;font:var(--type-label,600 13px/1.2 'Chakra Petch',sans-serif);letter-spacing:1px;text-transform:uppercase;color:var(--color-text-display,#ddd6c5)}",
      ".hs-keys .chip{font:var(--type-body-small,400 13px/1.4 'Manrope',sans-serif);font-size:12px;letter-spacing:0;text-transform:none;padding:1px 8px;border-radius:var(--radius-pill,999px);background:var(--color-surface-input,#1f1f1f);color:var(--color-text-muted,#9a968c)}",
      ".hs-keys .chip.ok{background:var(--color-surface-status-success,rgba(111,191,115,.15));color:var(--color-text-status-success,#6fbf73)}",
      ".hs-keys .chip.bad{background:var(--color-surface-status-danger,rgba(229,82,44,.15));color:var(--color-text-status-danger,#ff7a59)}",
      ".hs-keys input{width:100%;box-sizing:border-box;font:var(--type-mono-default,500 13px/1.4 'Azeret Mono',monospace);color:var(--color-text-default,#e8e4d8);background:var(--color-surface-input,#1f1f1f);border:1px solid var(--color-border-strong,#706e68);border-radius:var(--radius-md,12px);padding:11px 12px}",
      ".hs-keys input::placeholder{color:var(--color-text-muted,#9a968c);font-family:'Manrope',sans-serif}",
      ".hs-keys input:focus-visible{outline:2px solid var(--color-border-focus,#f2c14e);outline-offset:1px}",
      ".hs-keys .hint{font-size:12px}",
      ".hs-keys .hint a{color:var(--color-text-accent-soft,#ffb39e)}",
      ".hs-keys .why{padding:10px 12px;border-radius:var(--radius-md,12px);background:var(--color-surface-default,#0e0e0e);border:1px solid var(--color-border-default,#2b2b2b);color:var(--color-text-default,#e8e4d8)}",
      ".hs-keys .btns{display:flex;flex-wrap:wrap;gap:10px;justify-content:flex-end;margin-top:2px}",
      ".hs-keys .btns button{font:var(--type-button,600 13px/1.2 'Chakra Petch',sans-serif);letter-spacing:1.04px;text-transform:uppercase;padding:11px 18px;border-radius:var(--radius-md,12px);border:1px solid transparent;cursor:pointer}",
      ".hs-keys .btns .pri{background:var(--color-action-primary,#e5522c);color:var(--color-action-on-primary,#0e0e0e)}",
      ".hs-keys .btns .pri:hover{background:var(--color-action-primary-hover,#ff7a59)}",
      ".hs-keys .btns .sec{background:var(--color-surface-input,#1f1f1f);color:var(--color-text-accent-soft,#ffb39e);border-color:var(--color-border-strong,#706e68)}",
      ".hs-keys .btns .sec:hover{background:var(--color-surface-input-hover,#2b2b2b)}",
      ".hs-keys .btns .sec[disabled]{opacity:.45;cursor:default}",
      ".hs-keys .msg{color:var(--color-text-status-success,#6fbf73)}.hs-keys .msg:empty{display:none}",
      "#hsKeysToast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:80;width:max-content;max-width:calc(100vw - 24px);box-sizing:border-box;display:flex;align-items:center;gap:12px;padding:12px 14px 12px 16px;border-radius:var(--radius-md,12px);background:var(--color-surface-raised,#171717);border:1px solid var(--color-border-strong,#706e68);border-left:3px solid var(--color-border-accent,#e5522c);color:var(--color-text-default,#e8e4d8);font:var(--type-body-small,400 13px/1.4 'Manrope',sans-serif);box-shadow:0 8px 30px rgba(0,0,0,.55)}",
      "#hsKeysToast[hidden]{display:none}",
      "#hsKeysToast button{flex:none;font:var(--type-button,600 13px/1.2 'Chakra Petch',sans-serif);font-size:11px;letter-spacing:1px;text-transform:uppercase;padding:7px 10px;border-radius:var(--radius-sm,6px);border:1px solid var(--color-border-strong,#706e68);background:var(--color-surface-input,#1f1f1f);color:var(--color-text-accent-soft,#ffb39e);cursor:pointer}",
      "#hsKeysToast .tx{flex:1 1 auto;min-width:0}"
    ].join("\n");
    document.head.append(st);
  }
  /* A short message at the bottom of the screen; withKeys adds a button that opens the dialog. Never in the audience view. */
  A.toast = function (text, withKeys) {
    if (AUD()) return;
    const go = () => {
      keysStyle();
      let t = document.getElementById("hsKeysToast");
      if (!t) {
        t = document.createElement("div"); t.id = "hsKeysToast"; t.setAttribute("role", "status"); t.hidden = true;
        const tx = document.createElement("span"); tx.className = "tx"; const kb = document.createElement("button"); kb.type = "button"; kb.className = "k"; kb.textContent = "Keys";
        kb.addEventListener("click", () => { t.hidden = true; A.openKeys(); });
        const x = document.createElement("button"); x.type = "button"; x.textContent = "×"; x.setAttribute("aria-label", "Close"); x.addEventListener("click", () => { t.hidden = true; });
        t.append(tx, kb, x); document.body.append(t);
      }
      t.querySelector(".tx").textContent = text; t.querySelector(".k").hidden = !withKeys; t.hidden = false;
      clearTimeout(K.toastT); K.toastT = setTimeout(() => { t.hidden = true; }, 9000);
    };
    if (document.body) go(); else addEventListener("DOMContentLoaded", go);
  };
  const tellOnce = (k, code) => { const id = k + code; if (K.said[id] && code !== "rate") return; if (code === "rate" && Date.now() - (K.said[id] || 0) < 10000) return; K.said[id] = Date.now(); A.toast(msgText(k, code), code !== "rate"); };

  function keysEntry(anchor, h) {
    const id = anchor.id + "Keys"; let b = document.getElementById(id);
    if (!h.byo || AUD()) { if (b) b.remove(); return; }
    keysStyle();
    if (!b) {
      b = document.createElement("button"); b.type = "button"; b.id = id; b.className = "hs-keys-entry";   // outside an app screen the German layer may translate it
      b.innerHTML = ICON_KEY; b.append("Keys"); b.title = "AI and voice keys"; b.setAttribute("aria-label", "AI and voice keys");
      b.addEventListener("click", () => A.openKeys());
      if (anchor.tagName === "P") { const p = document.createElement("p"); p.className = "hs-keys-row"; p.id = id + "Row"; p.append(b); anchor.after(p); }
      else { b.classList.add("icon"); anchor.after(b); }                // in a tight header row: the key icon alone
    }
    b.classList.toggle("need", !(h.keys && h.keys.ai === "yours"));
  }

  /* The key dialog: two password fields, Save, Remove keys. Stored keys are never put back into the page: an empty field
     keeps the stored key, a filled one replaces it. */
  A.openKeys = function () {
    if (AUD()) return;
    keysStyle();
    let d = document.getElementById("hsKeys");
    if (!d) {
      d = document.createElement("dialog"); d.id = "hsKeys"; d.className = "hs-keys"; d.setAttribute("aria-labelledby", "hsKeysT");
      d.innerHTML = '<form method="dialog" autocomplete="off">'
        + '<div class="top"><h2 id="hsKeysT">' + ICON_KEY + 'AI and voice keys</h2><button class="x" type="button" data-close aria-label="Close">×</button></div>'
        + '<label><span class="lab">OpenRouter key <span class="chip" data-chip="or"></span></span><input type="password" name="or" spellcheck="false" autocapitalize="off" autocomplete="off" placeholder="sk-or-…"><span class="hint">For the AI assistant. Get one at <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">openrouter.ai/keys</a>.</span></label>'
        + '<label><span class="lab">ElevenLabs key <span class="chip" data-chip="el"></span></span><input type="password" name="el" spellcheck="false" autocapitalize="off" autocomplete="off" placeholder="sk_…"><span class="hint">For the voice. At <a href="https://elevenlabs.io/app/settings/api-keys" target="_blank" rel="noopener noreferrer">elevenlabs.io</a> → API keys; it needs Text to Speech and Speech to Text access.</span></label>'
        + '<p class="why">Kept only in this browser. Sent with each question to this site\'s server, which passes it on to OpenRouter or ElevenLabs and does not store it.</p>'
        + '<p class="msg" role="status"></p>'
        + '<div class="btns"><button class="sec" type="button" data-remove>Remove keys</button><button class="pri" type="submit">Save</button></div></form>';
      document.body.append(d);
      const f = d.querySelector("form"), msg = d.querySelector(".msg");
      d.querySelector("[data-close]").addEventListener("click", () => d.close());
      d.addEventListener("click", e => { if (e.target === d) d.close(); });            // a tap on the backdrop closes it
      d.addEventListener("close", () => { f.reset(); });
      f.addEventListener("submit", e => {
        e.preventDefault();
        const nw = { or: f.or.value.trim(), el: f.el.value.trim() };
        if (!nw.or && !nw.el) { msg.textContent = "Paste a key into one of the fields first."; return; }
        setKeys(nw); f.reset(); fill(); msg.textContent = "Saved in this browser.";
        setTimeout(() => { if (d.open) d.close(); }, 900);
      });
      d.querySelector("[data-remove]").addEventListener("click", () => { setKeys({}, true); f.reset(); fill(); msg.textContent = "Keys removed from this browser."; });
    }
    function fill() {
      const k = keys(), st = keyState();
      ["or", "el"].forEach(n => {
        const c = d.querySelector('[data-chip="' + n + '"]'), s = st[n];
        c.textContent = !k[n] ? "not set" : s === "key_used_up" ? "used up" : s === "key_invalid" ? "not accepted" : "stored";
        c.className = "chip" + (!k[n] ? "" : s ? " bad" : " ok");
        d.querySelector('input[name="' + n + '"]').placeholder = k[n] ? "Stored. Paste a new key to replace it." : (n === "or" ? "sk-or-…" : "sk_…");
      });
      d.querySelector("[data-remove]").disabled = !(k.or || k.el);
    }
    fill(); d.querySelector(".msg").textContent = "";
    if (!d.open) { if (d.showModal) d.showModal(); else d.setAttribute("open", ""); }
  };

  /* Pass link: #or=<key>&el=<key> (either or both, URL-encoded). The fragment never reaches a server; it is removed at once. */
  (function importPass() {
    if (AUD() || !/(?:^#|&)(?:or|el)=/.test(location.hash)) return;
    const p = new URLSearchParams(location.hash.slice(1)), nw = {};
    ["or", "el"].forEach(n => { const v = (p.get(n) || "").trim(); if (v) nw[n] = v; p.delete(n); });
    const rest = p.toString();
    try { history.replaceState(history.state, "", location.pathname + location.search + (rest ? "#" + rest : "")); } catch (e) {}
    if (!nw.or && !nw.el) return;
    setKeys(nw);
    A.toast("Test keys added. The AI assistant and the voice are switched on in this browser.", false);
  })();
  /* opt.onText(textSoFar, final): the answer arrives piece by piece while the model writes it (so a voice can start with
     the first sentence). opt.signal: an AbortSignal to cancel. A server that does not stream answers in one piece: same result. */
  A.ask = async function (question, ctx, history, mode, opt) {
    opt = opt || {};
    const body = { question, context: ctx.text, app: ctx.app, mode: mode || "chat", history: (history || []).slice(-6) };
    if (opt.onText) body.stream = true;
    let got = "";
    if (K.byo && !usable("or")) {                                     // public site, no usable key: the rules answer, no request
      const answer = A.briefing(ctx); if (opt.onText) opt.onText(answer, true);
      return { answer, model: null, offline: true, keyCode: "no_key", error: msgText("or", "no_key") };
    }
    try {
      const r = await fetch("api/assistant", { method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, keyHeader()), body: JSON.stringify(body), signal: opt.signal });
      if (r.ok && r.body && /text\/plain/.test(r.headers.get("Content-Type") || "")) {
        const rd = r.body.getReader(), dec = new TextDecoder();
        for (;;) { const x = await rd.read(); if (x.done) break; got += dec.decode(x.value, { stream: true }); opt.onText(got, false); }
        got = got.trim(); if (!got) throw new Error("empty answer");
        opt.onText(got, true);
        return { answer: got, model: r.headers.get("X-Model"), offline: false };
      }
      const j = await r.json();
      if (!r.ok) { const er = new Error(j.error || ("HTTP " + r.status)); if (KEY_CODES[j.code]) er.code = j.code; throw er; }
      if (opt.onText) opt.onText(j.answer, true);
      return { answer: j.answer, model: j.model, offline: false };
    } catch (e) {
      if (e && e.name === "AbortError") return { answer: "", aborted: true };
      if (e && e.code) {                                              // a key problem: the rules answer, the note says why
        if (e.code === "key_used_up" || e.code === "key_invalid") markKey("or", e.code);
        const answer = A.briefing(ctx); if (opt.onText) opt.onText(answer, true);
        return { answer, model: null, offline: true, keyCode: e.code, error: msgText("or", e.code) };
      }
      const whole = got.match(/^[\s\S]*[.!?]/);                       // the stream broke: keep what was said in whole sentences
      if (whole && whole[0].length > 40) { if (opt.onText) opt.onText(whole[0], true); return { answer: whole[0], model: null, offline: false }; }
      const answer = A.briefing(ctx); if (opt.onText) opt.onText(answer, true);
      return { answer, model: null, offline: true, error: String(e && e.message || e) };
    }
  };

  /* ---------- Voice ----------
     Out: one voice for both apps, only as the answer to a question (voice to voice). The server turns the text into
          speech with ElevenLabs (/api/tts; the key never reaches the browser), sentence by sentence, so the voice starts
          after the first sentence instead of after the whole answer. There is no other voice: when ElevenLabs does not
          answer, nothing is spoken and the answer stays on screen (the browser's own voice is never used, D-31).
     In:  the browser's speech recognition where it exists (the words appear while you speak); otherwise a short
          recording goes to the server (/api/stt, ElevenLabs Scribe) and comes back as text.
     Press once to talk, press again (or stop talking) to send: nothing listens unless it was switched on. */
  const V = { el: null, token: 0, offUntil: 0, label: "", speaking: false, ctrl: null, cur: null };
  const SAY = [[/CO₂|CO2/g, "C O 2"], [/µSv\/h/g, "microsievert per hour"], [/µSv/g, "microsievert"], [/mSv/g, "millisievert"], [/mmHg/g, "millimetres of mercury"],
    [/mmol\/L/g, "millimole per litre"], [/kJ\/kg/g, "kilojoule per kilogram"], [/kPa/g, "kilopascal"], [/\bbpm\b/g, "beats per minute"], [/°C/g, " degrees Celsius"],
    [/\bEVA\b/g, "E V A"], [/\bSpO2\b/gi, "blood oxygen"], [/\bHRV\b/g, "heart rate variability"], [/\s+/g, " "]];
  const sayable = t => SAY.reduce((s, [a, b]) => s.replace(a, b), String(t || "")).trim();
  const audioEl = () => { if (!V.el) { V.el = new Audio(); V.el.preload = "auto"; } return V.el; };
  /* Browsers only let a page play sound after a tap or a key press: wake the audio element on the first one. */
  const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
  const unlock = () => { const a = audioEl(); if (a.dataset.ok) return; a.src = SILENCE; const p = a.play(); if (p && p.then) p.then(() => { a.dataset.ok = "1"; }).catch(() => {}); };
  ["pointerdown", "keydown"].forEach(ev => addEventListener(ev, unlock, { capture: true, passive: true }));

  function pill(on, text) {                      // a small sign while the assistant speaks or listens, with a stop button
    let p = document.getElementById("voicePill");
    if (!p) {
      p = document.createElement("div"); p.id = "voicePill"; p.setAttribute("role", "status");
      p.style.cssText = "position:fixed;left:50%;top:52px;transform:translateX(-50%);z-index:70;display:none;align-items:center;gap:10px;padding:9px 9px 9px 18px;border-radius:999px;background:#171717;border:1px solid #706e68;color:#e8e4d8;font:600 15px/1 'Chakra Petch',sans-serif;letter-spacing:1.4px;text-transform:uppercase;box-shadow:0 6px 24px rgba(0,0,0,.5)";
      const dot = document.createElement("i"); dot.style.cssText = "width:12px;height:12px;border-radius:50%;background:#e5522c;animation:vpulse 1s ease-in-out infinite alternate";
      const t = document.createElement("span"); t.id = "voicePillT";
      const b = document.createElement("button"); b.type = "button"; b.textContent = "Stop"; b.style.cssText = "font:inherit;letter-spacing:inherit;text-transform:inherit;color:#0e0e0e;background:#e8e4d8;border:0;border-radius:999px;padding:6px 12px;cursor:pointer";
      b.addEventListener("click", () => { A.stopSpeaking(); if (V.stopListen) V.stopListen(); });
      const st = document.createElement("style"); st.textContent = "@keyframes vpulse{from{opacity:.35;transform:scale(.8)}to{opacity:1;transform:scale(1.15)}}";
      p.append(st, dot, t, b); document.body.append(p);
    }
    p.style.display = on ? "inline-flex" : "none";
    if (text) document.getElementById("voicePillT").textContent = text;
  }
  function setSpeaking(on, engine) {
    V.speaking = on; pill(on, on ? "Speaking · " + engine : "");
    document.dispatchEvent(new CustomEvent("assistant-speaking", { detail: { on, engine } }));
  }
  document.addEventListener("assistant-keys", () => { V.offUntil = 0; });      // a new or removed visitor key: ask for the voice again at once
  A.isSpeaking = () => V.speaking;
  A.voiceLabel = () => V.label || "";
  function noVoice() {                           // ElevenLabs gave nothing for this answer: say so briefly, the text is on screen
    pill(true, "No voice · answer on screen");
    clearTimeout(V.noVoiceT); V.noVoiceT = setTimeout(() => { if (!V.speaking && !V.askCtrl) pill(false); }, 3500);
  }
  /* Text -> an audio address from the server's voice. Throws when there is none. A missing voice is asked for again after
     20 s, never switched off for good: a page that was open before the key was added finds the voice by itself. */
  const VOICE_NAMES = { eleven_v4: "ElevenLabs v4", eleven_v4_turbo: "ElevenLabs v4 Turbo", eleven_v3: "ElevenLabs v3" };
  async function tts(text, signal) {
    if (Date.now() < V.offUntil) throw new Error("no voice");
    if (K.byo && !usable("el")) throw new Error("no voice key");     // public site without a usable key: no voice, text only
    const r = await fetch("api/tts", { method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, keyHeader()), body: JSON.stringify({ text }), signal });
    if (r.ok && /audio/.test(r.headers.get("Content-Type") || "")) {
      V.label = VOICE_NAMES[r.headers.get("X-Voice-Model")] || (/^ElevenLabs/.test(V.label) ? V.label : "ElevenLabs");
      return URL.createObjectURL(await r.blob());
    }
    let code = null; try { code = (await r.json()).code; } catch (e) {}
    if (KEY_CODES[code] && code !== "no_key") {
      if (code !== "rate") { markKey("el", code); V.label = ""; }
      tellOnce("el", code);
      throw new Error("voice " + code);
    }
    if (r.status === 503 || r.status === 403) { V.offUntil = Date.now() + 20000; V.label = ""; }
    throw new Error("voice " + r.status);
  }
  /* Whole sentences from the start of a text. Short ones are joined, so a piece is worth a request. */
  function pieces(text, final) {
    const out = []; let cur = 0, m;
    const re = final ? /[.!?]+["”')\]]*(?=\s|$)/g : /[.!?]+["”')\]]*(?=\s)/g;      // "5.3" is not an end; while writing, neither is the last character
    while ((m = re.exec(text))) {
      const end = re.lastIndex, part = text.slice(cur, end).trim();
      if (part.length >= 24) { out.push(part); cur = end; }
    }
    let done = cur;
    if (final && text.slice(cur).trim()) { out.push(text.slice(cur).trim()); done = text.length; }
    return { out, done };
  }
  /* One utterance that can be fed while its text is still being written: feed(textSoFar, final). The first sentence is
     turned into speech at once; the next pieces are fetched while it plays and follow without a gap. */
  A.speakStream = function (onEnd) {
    A.stopSpeaking();
    const my = ++V.token, ctrl = new AbortController(), q = [];
    let fed = 0, total = 0, closed = false, fetching = false, playing = false, over = false, dead = false, missed = false, spoke = false;
    V.ctrl = ctrl;
    const alive = () => my === V.token;
    const finish = () => { if (!alive() || over) return; over = true; setSpeaking(false); if ((dead || missed) && !spoke) noVoice(); if (onEnd) onEnd(); };
    const play = it => {                         // only the ElevenLabs voice; a piece without audio is skipped, never read by the browser
      playing = true;
      const next = () => { playing = false; if (it.url) URL.revokeObjectURL(it.url); pump(); };
      if (!it.url) { next(); return; }
      const a = audioEl(); a.onended = a.onerror = () => { a.onended = a.onerror = null; next(); };
      a.src = it.url; setSpeaking(true, V.label || "ElevenLabs");
      const pr = a.play();
      if (!pr || !pr.then) { spoke = true; return; }
      pr.then(() => { spoke = true; }, () => { a.onended = a.onerror = null; if (!alive()) return; dead = true; q.length = 0; next(); });
    };
    function pump() {
      if (!alive() || over) return;
      const want = q.find(it => !it.asked);
      if (want && !fetching && !dead) {
        want.asked = true; fetching = true;
        tts(want.text, ctrl.signal).then(url => { want.url = url; }, e => { want.fail = true; if (e && e.name === "AbortError") return; missed = true; }).then(() => { fetching = false; pump(); });
      }
      if (dead) q.forEach(it => { if (!it.asked) { it.asked = true; it.fail = true; } });       // the browser blocked the sound: the rest stays text
      if (!playing && q.length && (q[0].url || q[0].fail)) play(q.shift());
      else if (!playing && !q.length && closed && !fetching) finish();
    }
    return {
      feed(text, final) {
        if (!alive() || closed) return;
        const t = sayable(text), r = pieces(t.slice(fed), !!final);
        r.out.forEach(x => { if (total < 1500) { total += x.length; q.push({ text: x }); } });      // the same upper limit as one request had
        fed += r.done; if (final) closed = true;
        pump();
      },
      stop() { if (alive()) A.stopSpeaking(); }
    };
  };
  A.stopSpeaking = function () {
    V.token++;
    if (V.ctrl) { try { V.ctrl.abort(); } catch (e) {} V.ctrl = null; }
    if (V.askCtrl) { try { V.askCtrl.abort(); } catch (e) {} V.askCtrl = null; pill(false); }
    if (V.el && !V.el.paused) { V.el.pause(); }
    if (V.speaking) setSpeaking(false);
  };
  /* One turn of the conversation, the same in both apps: ask, show the words while they are written, and (unless
     h.speak is false) say them in the assistant's voice, starting with the first sentence.
     h.onText(textSoFar, final), h.onSpoken(). Stop (the pill, or A.stopSpeaking) cancels the turn: { aborted: true }. */
  A.askAloud = async function (question, ctx, history, mode, h) {
    h = h || {};
    const sp = h.speak === false ? null : A.speakStream(h.onSpoken);
    if (!sp) A.stopSpeaking();
    const ac = new AbortController(); V.askCtrl = ac;
    if (sp) pill(true, "Thinking");
    const r = await A.ask(question, ctx, history, mode, { signal: ac.signal, onText: (t, fin) => { if (h.onText) h.onText(t, fin); if (sp && fin) { if (V.askCtrl === ac) V.askCtrl = null; } if (sp) sp.feed(t, fin); } });
    if (V.askCtrl === ac) V.askCtrl = null;
    if (r.aborted) return r;
    if (sp && !V.speaking) pill(true, "Thinking");                 // the words are there, the voice is a moment behind
    if (!sp) pill(false);
    return r;
  };

  const SR = () => window.SpeechRecognition || window.webkitSpeechRecognition;
  const canRecord = () => !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  A.canListen = () => !!(SR() || canRecord());
  function recordListen(h) {                     // no speech recognition in this browser: record, let the server transcribe
    if (K.byo && !usable("el")) {                // public site: recording goes to the server's speech-to-text, which needs a key
      const st = keyState().el, code = st || "no_key";
      setTimeout(() => { if (h.onError) h.onError(msgText("el", code) + " You can type the question."); A.openKeys(); if (h.onEnd) h.onEnd(""); }, 0);
      return () => {};
    }
    let rec = null, ctx = null, raf = 0, stopped = false, spoke = false, quiet = 0; const t0 = performance.now(), chunks = [];
    const stop = () => { if (stopped) return; stopped = true; cancelAnimationFrame(raf); try { if (rec && rec.state !== "inactive") rec.stop(); } catch (e) {} };
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }).then(stream => {
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(m => MediaRecorder.isTypeSupported(m)) || "";
      rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop()); if (ctx) ctx.close().catch(() => {});
        if (!spoke) { if (h.onEnd) h.onEnd(""); return; }
        try {
          const blob = new Blob(chunks, { type: rec.mimeType || mime || "audio/webm" });
          const r = await fetch("api/stt", { method: "POST", headers: Object.assign({ "Content-Type": blob.type }, keyHeader()), body: blob });
          const j = await r.json();
          if (!r.ok && KEY_CODES[j.code]) {                         // a key problem: say it in one line, offer the dialog
            if (j.code === "key_used_up" || j.code === "key_invalid") markKey("el", j.code);
            if (h.onError) h.onError(msgText("el", j.code) + " You can type the question."); if (j.code !== "rate") A.openKeys(); if (h.onEnd) h.onEnd(""); return;
          }
          if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
          if (h.onText) h.onText(j.text, true); if (h.onEnd) h.onEnd(j.text);
        } catch (e) { if (h.onError) h.onError("Speech to text is not available here. Type the question instead. (" + (e && e.message || e) + ")"); if (h.onEnd) h.onEnd(""); }
      };
      rec.start();
      /* End of the turn: 1.4 s of quiet after something was said; nothing said for 7 s; or 25 s at most. */
      ctx = new (window.AudioContext || window.webkitAudioContext)(); const an = ctx.createAnalyser(); an.fftSize = 1024; ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.fftSize);
      const tick = () => {
        if (stopped) return;
        an.getByteTimeDomainData(buf); let sum = 0; for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
        const now = performance.now();
        if (Math.sqrt(sum / buf.length) > 0.035) { spoke = true; quiet = 0; } else if (!quiet) quiet = now;
        if ((spoke && quiet && now - quiet > 1400) || (!spoke && now - t0 > 7000) || now - t0 > 25000) { stop(); return; }
        raf = requestAnimationFrame(tick);
      };
      tick();
    }).catch(e => { if (h.onError) h.onError(e && e.name === "NotAllowedError" ? "Microphone access was refused." : "No microphone found."); if (h.onEnd) h.onEnd(""); });
    return stop;
  }
  A.listen = function (h) {
    A.stopSpeaking();
    const wrap = Object.assign({}, h, { onEnd: t => { V.stopListen = null; pill(false); if (h.onEnd) h.onEnd(t); } });
    pill(true, "Listening");
    const R = SR();
    if (!R) {
      if (!canRecord()) { pill(false); if (h.onError) h.onError("This browser has no speech recognition. Type the question instead."); return () => {}; }
      return (V.stopListen = recordListen(wrap));
    }
    const rec = new R(); rec.lang = "en-GB"; rec.interimResults = true; rec.maxAlternatives = 1;
    let finalText = "", heard = "", failed = false, stopRec = null;
    rec.onresult = ev => { let t = ""; for (const r of ev.results) { t += r[0].transcript; if (r.isFinal) finalText = t; } heard = t; if (h.onText) h.onText(t, false); };
    rec.onerror = ev => {
      if ((ev.error === "network" || ev.error === "service-not-allowed" || ev.error === "language-not-supported") && canRecord()) {   // the browser's service is not reachable: use ours
        failed = true; stopRec = recordListen(wrap); return;
      }
      if (ev.error === "no-speech" || ev.error === "aborted") return;
      failed = true; if (h.onError) h.onError(ev.error === "not-allowed" ? "Microphone access was refused." : "Speech recognition: " + ev.error);
    };
    rec.onend = () => { if (stopRec) return; wrap.onEnd(finalText || (failed ? "" : heard)); };
    try { rec.start(); } catch (e) { pill(false); if (h.onError) h.onError("Speech recognition could not start."); return () => {}; }
    return (V.stopListen = () => { if (stopRec) stopRec(); else { try { rec.stop(); } catch (e) {} } });
  };
  /* What the server offers: an AI model, and the ElevenLabs voice. Asked once per page. */
  A.health().then(h => { if (h && h.voice) { V.label = h.voice_label || "ElevenLabs"; } else if (h && h.voice === false) V.offUntil = Date.now() + 20000; document.dispatchEvent(new CustomEvent("assistant-voice", { detail: { label: A.voiceLabel(), server: !!(h && h.voice) } })); });
  window.Assistant = A;
})();
