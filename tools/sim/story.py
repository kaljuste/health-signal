"""Snapshot days of the focus astronaut: the days with a written analysis and a full letter from Earth.

Every sentence is built from the simulated values of that day, so text and data cannot disagree.
On all other days the app still has the rule results, tomorrow's plan and Earth's short instruction."""
from . import base
from .rules import LABEL, _m, idx_day, ORDER


def snapshot_days(cal, H, envd, forced):
    h = H[base.FOCUS]
    idx = {r["day"]: i for i, r in enumerate(cal)}
    land, dep, home = idx_day(cal, "surface"), idx_day(cal, "return"), idx_day(cal, "recovery")
    black = [r["day"] for r in cal if r["comm"] == "blackout"]
    d600 = next(r["day"] for r in cal if h["dose_cum_msv"][idx[r["day"]]] >= 600)
    return [
        (0, "launch", "Launch day"), (2, "fd2", "Third day in weightlessness"), (30, "month1", "One month out"),
        (85, "minor_storm", "A minor solar storm"), (97, "co2", "Bad air: CO2 removal fault"),
        (land - 1, "pre_mars", "Day before Mars landing"), (land, "mars_landing", "Mars landing"), (land + 3, "sol3", "Third sol: learning to stand again"),
        (forced["nominal"], "eva_nominal", "First long walk (arm unit: normal walk)"),
        (forced["fatigue"], "eva_fatigue", "End of the EVA campaign (arm unit: fatigue rising)"),
        (forced["fatigue"] + 2, "stand_down", "Sol 180: stand-down after short nights"),
        (black[0] - 1, "pre_blackout", "Last link before the Sun cuts it"), (black[len(black) // 2], "blackout", "Day 7 without Earth"),
        (black[-1] + 1, "link_back", "The link is back"),
        (forced["co2"], "eva_co2", "Suit CO2 scrubber fault (arm unit: suit CO2 high)"),
        (forced["storm"], "eva_storm", "Solar storm on Mars (arm unit: storm warning)"),
        (dep - 1, "pre_departure", "Day before leaving Mars"),
        (768, "deep_storm", "Solar storm in deep space: in the shelter"), (d600, "dose_600", "The career dose limit is passed"),
        (806, "device_fault", "Exercise device out of order"),
        (home - 1, "pre_earth", "Day before Earth landing"), (home, "earth_landing", "Home: Earth landing"), (home + 7, "r7", "One week back"),
        (cal[-1]["day"], "r45", "Six weeks back: what stays"),
    ]


WHY = {
    "launch": "Baselines end here. From today every value is read against the person's own pre-flight level.",
    "fd2": "The body is settling into weightlessness: fluid moves to the head, the stomach protests, the back hurts. All expected, all followed.",
    "month1": "The fast changes are over. What moves from now on is slow: bone, muscle, eyes, dose.",
    "minor_storm": "Not every storm needs the shelter. The rule looks at the measured rate, not at the headline.",
    "co2": "A device fault the crew can feel: headache, slower thinking, poor sleep. The limit is 3 mmHg for one hour.",
    "pre_mars": "After 172 days without gravity the crew must land, stand and work. This is the readiness check that cannot be repeated.",
    "mars_landing": "Gravity is back at 38 %. Balance and blood pressure are at their worst for one to three days.",
    "sol3": "Recovery is fast in the first sols. The rules decide when walking alone, ladders and EVAs are allowed again.",
    "eva_nominal": "The first long walk. On sol 9 the body, not the suit, limits the stay.",
    "eva_fatigue": "Two weeks of early starts and late reports. The walk goes ahead with limits and shows why the limits exist.",
    "stand_down": "Sleep debt has built up over a fortnight. Reaction speed shows it; Earth orders a stand-down.",
    "pre_blackout": "From tomorrow no message passes for 12 days. Today's instruction has to stand on its own.",
    "blackout": "No uplink for a week. The on-board rules and the standing orders carry the crew.",
    "link_back": "Earth catches up on 12 days of data in one review.",
    "eva_co2": "A suit fault that looks harmless for minutes. The trend rule calls the return long before the limit.",
    "eva_storm": "A storm warning during an EVA. On Mars the air blunts the storm, the rule still says: inside.",
    "pre_departure": "After 18 months at 0.38 g the body goes back to weightlessness. Half the crew will be motion sick again.",
    "deep_storm": "The largest storm of the mission, in deep space. The shelter is the only protection.",
    "dose_600": "NASA's career limit of 600 mSv is passed, as known before launch. Nothing can be felt.",
    "device_fault": "The resistive exercise device fails for 14 days. Strength falls within days; bone follows.",
    "pre_earth": "Landing at full gravity after 190 days of weightlessness: the hardest hour for heart and balance.",
    "earth_landing": "Home. The first day is the weakest of the whole mission.",
    "r7": "Most functions are back within a week. Bone is not.",
    "r45": "What six weeks at home repaired, and what the mission keeps.",
}

ASK = {
    "launch": ["What will my body do in the first days?", "Which of my values should I watch this week?"],
    "fd2": ["Is my back pain normal?", "Why did I lose two kilos already?", "Can I exercise today?"],
    "month1": ["What changed in my first month?", "How are my bones doing?", "What did Earth say about my blood panel?"],
    "minor_storm": ["Do we need the shelter?", "How much dose did the storm add?"],
    "co2": ["Why do I have a headache?", "How bad is the air right now?", "What should I do tonight?"],
    "pre_mars": ["Am I fit to land tomorrow?", "What do I do right after touchdown?", "How likely am I to faint?"],
    "mars_landing": ["Can I walk on my own?", "When can I go outside?", "Why is my heart rate so high?"],
    "sol3": ["Am I cleared for the ladder?", "How is my balance compared with yesterday?"],
    "eva_nominal": ["Am I fit for today's EVA?", "What limits my time outside?"],
    "eva_fatigue": ["Should I go out today?", "What are my limits on this EVA?", "Why is my readiness down?"],
    "stand_down": ["Why is my readiness down?", "What did Earth change in my plan?", "When can I do an EVA again?"],
    "pre_blackout": ["What are my standing orders?", "What happens if something goes wrong during the blackout?"],
    "blackout": ["How old is my last instruction from Earth?", "Is anything drifting that Earth should see?"],
    "link_back": ["What did Earth say about the last 12 days?", "Did I miss anything?"],
    "eva_co2": ["What happened on today's EVA?", "Was I in danger?"],
    "eva_storm": ["How much dose did I get today?", "When can we go outside again?"],
    "pre_departure": ["Am I fit for the launch tomorrow?", "What did 18 months on Mars do to my bones?"],
    "deep_storm": ["How long do we stay in the shelter?", "What did the shelter save me?"],
    "dose_600": ["What does passing 600 mSv mean for me?", "Can I still lower my dose?"],
    "device_fault": ["What do I do without the resistive device?", "How fast will I lose strength?"],
    "pre_earth": ["Am I fit to land tomorrow?", "What will the first hour on Earth be like?"],
    "earth_landing": ["Why can I not stand?", "How long until I walk normally?"],
    "r7": ["What is back to normal?", "What is not?"],
    "r45": ["What did the mission cost my body?", "Will my bones recover?"],
}


def letter(key, d, cal, h, i, envd, A):
    """Earth's letter, written from the data of the day before (i-1)."""
    j = max(i - 1, 0)
    g = lambda k, n=j: h[k][n]
    s7 = _m(h["sleep_h"], j, 7); e7 = _m(h["energy_pct"], j, 7); x7 = _m(h["exercise_pct"], j, 7)
    a = A[(cal[j]["day"], base.FOCUS)]
    T = {
        "launch": lambda: f"Good morning, KESTREL. Your baselines are complete: resting heart rate {_m(h['hr_rest_bpm'], j, 14):.0f} bpm, sleep {_m(h['sleep_h'], j, 14):.1f} h, reaction time {_m(h['pvt_rt_ms'], j, 14):.0f} ms, body mass {g('body_mass_kg'):.1f} kg. Everything we tell you from now on compares you with these numbers, not with other people. Expect a poor night, a stuffy head and less appetite in the first three days. Drink on schedule even when you are not thirsty. We are with you, a few light-seconds behind.",
        "fd2": lambda: f"Day three. You have lost {h['body_mass_kg'][i - 3] - g('body_mass_kg'):.1f} kg since launch: that is fluid, not tissue, and it is expected. " + (f"Your back pain ({g('back_pain_0_10'):.0f} of 10) comes from the spine lengthening; it fades within about 12 days. Knees-to-chest stretches help. " if g('back_pain_0_10') >= 1 else "No back pain so far, which is the exception. ") + f"You ate {g('energy_pct'):.0f} % of your need yesterday. Appetite returns this week; please log every meal so we can see it. Exercise starts in full today.",
        "month1": lambda: f"One month. The fast changes are done: heart rate {g('hr_rest_bpm'):.0f} bpm at rest, blood pressure about 10 mmHg under your Earth value, aerobic fitness at {g('vo2max_pct'):.0f} % after the early dip and now climbing with training. Leg strength is {g('leg_strength_pct'):.0f} %. Your hip bone estimate stands at {g('bmd_hip_pct'):.1f} %. From here the slow items matter: bone, eyes, dose ({g('dose_cum_msv'):.0f} mSv so far). Sleep averaged {s7:.1f} h this week. We will look at each of these with you once a month; the daily notes stay short.",
        "minor_storm": lambda: f"A minor solar particle event reached us yesterday, level S1. Your cabin dose rate stayed under twice the usual level, so the shelter rule did not trigger and we agree with that. Dose yesterday: {envd[cal[j]['day']]['dose_day_msv']:.2f} mSv against a usual 1.4. Keep to the normal plan. If the rate passes 200 µSv per hour the unit will tell you before we can.",
        "co2": lambda: f"Cabin CO2 reached {envd[cal[j]['day']]['cabin_co2_max1h']:.1f} mmHg yesterday, over the 3.0 limit, because removal bed A is degraded. This explains the headache and the slower reaction test ({-g('pvt_z'):.1f} SD under your usual). The repair plan is in the maintenance uplink: swap to bed B today. Until then sleep in the forward module where airflow is best, keep exercise easy, drink, and take the painkiller your crew doctor suggests. Values should be back under 2.5 mmHg within a day of the swap.",
        "pre_mars": lambda: f"Landing tomorrow. After {d} days in weightlessness our estimate is that you would fail a stand test at Earth gravity with {g('ortho_risk_pct'):.0f} % probability; Mars gravity is kinder, but nobody has measured by how much. So: salt tablets and one litre of fluid two hours before entry, compression garment on, anti-nausea medication within reach. After touchdown stay seated, stand up only with HERON beside you, and do the stand test before you walk. Your fitness is good: aerobic {g('vo2max_pct'):.0f} %, legs {g('leg_strength_pct'):.0f} %, hip bone {g('bmd_hip_pct'):.1f} %. Sleep was {g('sleep_h'):.1f} h last night; go to bed early. You are ready.",
        "mars_landing": lambda: "You are on Mars. This message was written before your landing data reached us: you will have your first values before we do. The rules on board decide today. Expect dizziness on standing, clumsy walking and perhaps nausea; all three fade within days. Do the stand test and the balance walk with a crewmate at your side, drink, eat what you can, sleep. Nothing else is asked of you today.",
        "sol3": lambda: f"Your recovery is on the fast track. Balance went from {h['balance_pct'][i - 3]:.0f} % on landing day to {g('balance_pct'):.0f} % yesterday; the stand test from {h['stand_dhr_bpm'][i - 3]:.0f} to {g('stand_dhr_bpm'):.0f} bpm. Rule for the next sols: ladder and airlock work once balance is above 80 % on two tests in a row; no jumps and no maximal lifts in the first week. Resistive training restarts today at 60 % of your last flight loads.",
        "eva_nominal": lambda: f"EVA 02 today. Readiness {g('readiness'):.0f}: go. Nine sols after landing your stamina will set the limit, not the suit. Drink 500 mL before you seal the suit and at each rest stop. The arm unit converts everything to time you can stay; trust it over how you feel. Your balance is {next((x for x in reversed(h['balance_pct'][:i]) if x is not None), 100):.0f} % of pre-flight: take slopes slowly.",
        "eva_fatigue": lambda: f"Last walk of the campaign. Your sleep this week averaged {s7:.1f} h and your reaction test is {-g('pvt_z'):.1f} SD under your usual. Readiness {g('readiness'):.0f} means go with limits: body check every 20 minutes, ease off at the first heat cue, stop and rest when two come together. Drilling in hard rock is where crews overrun their pace. OSPREY leads; you support. After today you stand down for three sols.",
        "stand_down": lambda: f"We looked at your last two weeks as a whole. Sleep fell from about {_m(h['sleep_h'], j - 14, 14):.1f} h to {s7:.1f} h a night during the campaign, your reaction test is {-g('pvt_z'):.1f} SD slower, you did {x7:.0f} % of your exercise and ate {e7:.0f} % of your need. Each alone is small; together they explain yesterday's readiness of {g('readiness'):.0f} and the heat cues on your last EVA. Our instruction: three sols without EVA, evening reports cancelled, first task at 09:00, 8.5 hours in bed, one extra meal pouch a day. Your rover drive moves to 10:30. Nothing is wrong with you that sleep will not repair.",
        "pre_blackout": lambda: f"This is the last full message before the Sun stands between us for 12 days. Your standing orders: keep the routine exactly; the on-board rules decide; EVAs pause until the link is back; log symptoms daily. Your values going in are good: readiness {g('readiness'):.0f}, sleep {s7:.1f} h, hip bone {g('bmd_hip_pct'):.1f} %, dose {g('dose_cum_msv'):.0f} mSv. If a rule calls a warning, follow its action list and the crew doctor; do not wait for us. We will read every day of it when the link returns.",
        "link_back": lambda: f"We are back and have read all 12 days. Sleep averaged {_m(h['sleep_h'], j, 12):.1f} h, exercise {_m(h['exercise_pct'], j, 12):.0f} % of plan, energy {_m(h['energy_pct'], j, 12):.0f} % of need; wellbeing dipped to {min(h['mood_who5'][j - 11: j + 1]):.0f} of 25 at its lowest and is recovering. The on-board rules raised {sum(1 for k in range(j - 11, j + 1) if any(v[0] in ('warning', 'critical') for v in A[(cal[k]['day'], base.FOCUS)].values()))} warning days; we agree with how each was handled. EVAs resume from tomorrow. Well done for holding the routine alone.",
        "eva_co2": lambda: f"EVA today, readiness {g('readiness'):.0f}: go. Routine sampling walk. A reminder that applies to every walk: if any suit value drifts steadily for minutes without a reason you can name, stop and let the unit decide. A drift is a fault until proven otherwise.",
        "eva_storm": lambda: f"EVA today, readiness {g('readiness'):.0f}: go. Space weather is quiet as far as we can see from here, but we see the Sun's far side poorly and our warning reaches you {cal[i]['light_min']:.0f} minutes late. The habitat monitor and the orbiter relay are your first warning, not us. If a flare alert comes, the walk ends: no discussion.",
        "pre_departure": lambda: f"Ascent tomorrow. Eighteen months at Mars gravity have treated you well: aerobic fitness {g('vo2max_pct'):.0f} %, legs {g('leg_strength_pct'):.0f} %, balance normal. Your hip bone estimate is {g('bmd_hip_pct'):.1f} % and will fall faster again in weightlessness; the resistive plan for the trip home is in your schedule from day two. Dose so far {g('dose_cum_msv'):.0f} mSv. Expect motion sickness and back pain in the first week, as on the way out: the first-days kit is packed for it. Light breakfast, medication ready.",
        "deep_storm": lambda: f"The storm that began yesterday is the largest of your mission. Yesterday you received {envd[cal[j]['day']]['dose_day_msv']:.1f} mSv in the shelter; in the open cabin it would have been {envd[cal[j]['day']]['dose_unsheltered_msv']:.1f} mSv. Stay in the shelter except for short, planned trips until the rate is under twice the usual level, probably in two days. Sleep will be poor and exercise is cancelled; both are made up next week. This is the real storm of 10 September 2017 replayed: a much larger one is possible, and the same rule covers it.",
        "dose_600": lambda: f"Your mission dose passed 600 mSv yesterday: {g('dose_cum_msv'):.0f} mSv. This is NASA's career limit, and we knew before launch that this mission would cross it on the way home; you accepted that risk with us. Nothing in your body changes today and nothing in your plan. What still counts: shelter discipline in any storm, and sleeping in the best shielded place. You will end near {g('dose_cum_msv') + 1.4 * (idx_day(cal, 'recovery') - d):.0f} mSv. We will go through what that means for your health checks after landing in the next private talk.",
        "device_fault": lambda: f"The resistive device has been out for {d - 800} days and the repair needs about a week more. Without loading your leg strength is falling: {g('leg_strength_pct'):.0f} % of pre-flight, {h['leg_strength_pct'][j - 6] - g('leg_strength_pct'):.0f} points lost in a week. Follow the fall-back programme six days a week: elastic bands, body-weight squats, cycle intervals. It will not hold bone as the device does, so we have also set fluids at 3.2 L and asked for a urine calcium check at the next panel. When the device is back, loads restart at 70 % and rise weekly.",
        "pre_earth": lambda: f"Home tomorrow. After {d - idx_day(cal, 'return')} days of weightlessness we estimate a {g('ortho_risk_pct'):.0f} % chance that you could not complete a stand test on landing day: plan on not standing alone. Protocol: salt tablets and one litre of fluid two hours before entry, compression garment, anti-nausea medication, reclined seat. The recovery team lifts you out. Your numbers: aerobic fitness {g('vo2max_pct'):.0f} %, legs {g('leg_strength_pct'):.0f} %, hip bone {g('bmd_hip_pct'):.1f} %, optic disc +{g('sans_trt_um'):.0f} µm, dose {g('dose_cum_msv'):.0f} mSv. Rehabilitation starts the day after tomorrow and is planned for 45 days.",
    }
    return T[key]() if key in T else None


def analysis(key, d, cal, h, i, envd, A, costs):
    g = lambda k: h[k][i]
    a = A[(d, base.FOCUS)]; ea = A[(d, "ENV")]
    flags = sorted(a.items(), key=lambda kv: -ORDER[kv[1][0]])
    parts = [f"Readiness {g('readiness'):.0f} of 100: {g('readiness_band').lower()}."]
    cs = [c for c in sorted(costs.get((d, base.FOCUS), []), key=lambda x: -x[1]) if c[1] >= 0.95][:4]
    if cs:
        parts.append("What costs points: " + ", ".join(f"{n.lower()} ({p:.0f})" for n, p in cs) + ".")
    body = [f"{LABEL[k].lower()}: {v[2]} [{v[0]}]" for k, v in flags if k != "readiness"][:6]
    if body:
        parts.append("Flagged: " + "; ".join(body) + ".")
    else:
        parts.append("No body value is flagged.")
    env = [f"{LABEL[k].lower()}: {v[2]} [{v[0]}]" for k, v in ea.items()]
    if env:
        parts.append("Environment: " + "; ".join(env) + ".")
    if g("symptoms"):
        parts.append(f"Symptoms logged: {g('symptoms')}.")
    return " ".join(parts)


def build(cal, H, envd, A, cost_rows, forced, ups):
    h = H[base.FOCUS]
    idx = {r["day"]: i for i, r in enumerate(cal)}
    costs = {}
    for c in cost_rows:
        costs.setdefault((c["day"], c["crew_id"]), []).append((c["item"], c["points"]))
    rows, labels = [], {}
    for d, key, title in snapshot_days(cal, H, envd, forced):
        i = idx[d]
        rows.append(dict(day=d, crew_id=base.FOCUS, title=title, why=WHY[key], analysis=analysis(key, d, cal, h, i, envd, A, costs),
                         questions_json=base.jdump(ASK[key])))
        labels[d] = title
        txt = letter(key, d, cal, h, i, envd, A)
        u = ups[(d, base.FOCUS)]
        if txt and u["status"] in ("received", "short", "in_person"):
            u["narrative"] = txt
        if key == "pre_blackout" and txt:                  # the last letter stays valid through the blackout
            for r in cal:
                if r["comm"] == "blackout":
                    ups[(r["day"], base.FOCUS)]["narrative"] = f"Written before the blackout, on mission day {d}: " + txt
    return rows, labels
