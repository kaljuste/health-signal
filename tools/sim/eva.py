"""Mars walks second by second: four complete EVAs for the arm unit, from suit seal to helmet off.

Every scenario starts as a normal walk. The body follows a small physiological model driven by the work rate;
the rules of the arm unit run every second and the simulated astronaut obeys them (rest when told, return when told).
Shapes learned from real data: heart rate against oxygen uptake, lactate against relative heart rate (learn.py);
the storm replays Curiosity's dose-rate record of 10-13 September 2017 in real time."""
import math
import numpy as np
from . import base

RESERVE_MIN = 30.0
INGRESS_MIN = 9.0            # hatch and airlock filling
WALK_SPEED = 0.74            # m/s in the suit (620 m in 14 min)
START_LOCAL_H = 10.0
COOL_W = [0, 120, 200, 290, 380, 470]
COOL_USE = [0, 0.55, 0.78, 1.0, 1.25, 1.5]
SITE_A, SITE_B = (470.0, 266.0), (682.0, 388.0)        # metres from the airlock; route lengths about 620 m and 900 m
ROUTE = 1.148                                           # the route is about 15 % longer than the straight line

# (phase, task, seconds, work rate W, target point or None)
def script(drill_w, sample_w=280):
    return [
        ("airlock", "Suit sealed, leak check", 300, 130, None),
        ("prebreathe", "Pre-breathe on oxygen", 1200, 118, None),
        ("depress", "Airlock emptying", 480, 130, None),
        ("egress", "Hatch open, egress", 180, 250, None),
        ("traverse", "Walk to site A", None, 310, SITE_A),
        ("work", "Sampling at site A", 2700, sample_w, None),
        ("rest", "Rest and drink", 300, 140, None),
        ("work", "Drilling a core at site A", 1800, drill_w, None),
        ("traverse", "Walk to site B", None, 310, SITE_B),
        ("work", "Setting up instruments at site B", 2400, 300, None),
        ("rest", "Rest and drink", 300, 140, None),
        ("traverse", "Walk back to the airlock", None, 300, (0.0, 0.0)),
    ]

TAIL = [("ingress", "Ingress, hatch closed", 180, 220, None), ("repress", "Airlock filling", 360, 125, None), ("post", "Helmet off, body check", 300, 110, None)]

TEXT = {
    1: "Leak check. Stand still.", 2: "Pre-breathe: 20 min on oxygen. Rest.", 3: "Airlock emptying. Check gloves and visor.", 4: "Hatch open. Go.",
    5: "All margins hold. Drink at the next stop.", 6: "Rest stop. Drink 200 mL.",
    7: "Stop and rest 5 min. Cooling to max. Drink.", 8: "Second heat cue. End the task and walk back at an easy pace.",
    9: "CO2 is climbing without effort. Stop work and watch it.", 10: "Walk back now at an easy pace. Scrubber fault suspected.",
    11: "Storm warning. Walk back to the airlock now.", 12: "Walk back now. Stamina is the limit.",
    13: "Ingress. Close the hatch.", 14: "Airlock filling. Helmet stays on until 56 kPa.", 15: "Helmet off. Post-EVA body check, then drink 500 mL.",
    16: "Ease the pace. One heat cue is active.", 17: "Walk back now. The shortest resource is the limit.",
    18: "Dose rate is climbing. Stay on the route home.", 19: "Margin is getting short. Plan the walk back.",
}


def simulate(sid, ctx, learned, storm_profile, rng):
    """Run one EVA. ctx: values of that day (resting heart rate, readiness, fitness, balance, dose rate, sunset...)."""
    lac = learned["lactate_curve"]; hv = learned["hr_vo2"]
    mass = ctx["mass"]; hrmax = 208 - 0.7 * ctx["age"]
    vo2max = ctx["vo2_ml_kg"] * mass / 1000 * ctx["vo2max_pct"] / 100          # L/min
    hr0 = ctx["hr_rest"] + 14                                                    # upright, suited, alert (assumed)
    tired = sid == "fatigue"                                                     # scripted: end of a two-week campaign with short nights
    p_sus = (0.38 if tired else 0.45) * vo2max * 348                             # sustainable work rate, W (assumed 45 % of maximum; 38 % when worn out)
    k_heat = 0.0028 if tired else 0.0022                                         # core rise per watt of work (assumed; worse after sleep loss)
    form = 1 + 0.012 * max(0, 85 - ctx["readiness"]) + 0.01 * max(0, 100 - ctx["vo2max_pct"]) + 0.25 * math.exp(-ctx["days_on_mars"] / 20.0)
    lac_shift = 0.05 + 0.002 * max(0, 85 - ctx["readiness"]) + 0.004 * max(0.0, ctx["sleep_debt"] - 5)   # unfit day: curve shifts left (assumed)
    tc0 = ctx["temp"] + 0.25                                                     # late-morning value
    rate0 = ctx["dose_rate"]
    segs = script(450, 300) if tired else script(340)
    fault_t = 1980 + 180 + 838 + 1500 if sid == "co2" else None                  # mid-way through sampling
    onset_t = 2640 if sid == "storm" else None                                  # the dose rate starts to creep 44 min after suit seal
    alert_t = None                                                              # set when the habitat confirms the storm

    rows, events = [], []
    ev = lambda t, kind, sev, var, text: events.append(dict(scenario_id=sid, t_s=int(t), kind=kind, severity=sev, var_id=var, text=text))
    # state
    t = 0; x = y = 0.0; path = [(0.0, 0.0)]
    M = 130.0; hr = hr0 - 6; tc = tc0; lactate = 1.0
    stamina = float(np.clip(100.0 - 3.0 * max(0.0, ctx['sleep_debt'] - 5) - 0.8 * max(0.0, 85 - ctx['readiness']), 50, 100))   # a worn-out day starts lower (assumed)
    plan_rate = 0.30 * form * (300 / 290.0) + 0.021 * max(0.0, 300 - p_sus)     # % per minute at a steady working pace
    _unused = 0; co2 = 1.7; suit_t = 20.5
    o2 = 100.0; batt = 100.0; water = 100.0; scrub = 100.0; dose = 0.0; drink = 0.0; fault_add = 0.0
    level = 2; noise = 0.0; bal_n = 0.0
    hr_hi = 0; co2_rise = 0; caution_ep = 0; in_caution = False; returning = None; rest_left = 0; slow = 1.0; eased = None; dose_hi = 0
    hist_co2, hist_stam = [], []
    seg_i = 0; seg_t = 0; outside = False; done = False
    queue = list(segs)
    cur = queue.pop(0)
    ev(0, "phase", "info", None, cur[1])
    last_state = "go"; last_next = 0
    stam_rate = 0.3

    def dist_back():
        return math.hypot(x, y) * 1.0 if returning or cur[0] != "traverse" else math.hypot(x, y)

    def route_len():                                    # walk back along the legs already walked
        pts = path + [(x, y)]
        return sum(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]) for k in range(len(pts) - 1))

    while not done and t < 6 * 3600:
        phase, task, dur, m_target, target = cur
        outside = phase in ("egress", "traverse", "work", "rest") or (phase == "ingress" and seg_t < 60)
        suited_loop = phase not in ("post",)
        # ---- work rate
        m_goal = m_target * (slow if phase == "work" else 1.0)
        if rest_left > 0:
            m_goal = 140.0
        noise = 0.97 * noise + rng.normal(0, 4.0)
        M += (m_goal + noise - M) * 0.05
        vo2 = M / 348.0
        # ---- heart rate: slope learned from cycle tests; heat and day-form add drift
        hr_ss = hr0 + hv["bpm_per_l_min"] * vo2 + 8.0 * max(0.0, tc - tc0) + 0.12 * (100 - ctx["readiness"]) + 0.10 * (100 - stamina)   # heat and fatigue drift (assumed)
        hr_ss = min(hr_ss, hrmax - 2)
        hr += (hr_ss - hr) / (35.0 if hr_ss > hr else 75.0)
        # ---- cooling and core temperature
        want = int(np.clip(1 + round((M - 150) / 110.0), 1, 5))
        if in_caution or rest_left > 0: want = 5
        if t % 30 == 0: level += (want > level) - (want < level)
        tc_ss = tc0 + k_heat * (M - 150) - 0.08 * (level - 3) + 0.004 * max(0, ctx["sleep_debt"] - 5)
        tc += (tc_ss - tc) / 720.0
        heat = 3.47 * (tc - tc0)
        # ---- lactate: learned curve against relative heart rate (without the heat drift)
        xrel = hr / hrmax + lac_shift
        l_ss = lac["a"] + lac["b"] * math.exp(lac["c"] * (xrel - 0.6))
        l_ss = min(l_ss, 12.0)
        lactate += (l_ss - lactate) / (150.0 if l_ss > lactate else 900.0)
        # ---- stamina
        if outside or phase in ("ingress",):
            rate = 0.30 * form * (M / 290.0) + 0.021 * max(0.0, M - p_sus) - (0.25 if M < 200 else 0.0)
            stamina = float(np.clip(stamina - rate / 60.0, 0, 100))
            stam_rate += (max(rate, 0.05) - stam_rate) / 600.0
        # ---- suit
        if phase in ("airlock", "prebreathe"): suit_p = 58.0
        elif phase == "depress": suit_p = 58.0 - (58.0 - base.SUIT_KPA) * min(1.0, seg_t / 420.0)
        elif phase == "repress": suit_p = base.SUIT_KPA + (base.CABIN_KPA - base.SUIT_KPA) * min(1.0, seg_t / 330.0)
        elif phase == "post": suit_p = base.CABIN_KPA
        else: suit_p = base.SUIT_KPA
        on_tank = phase not in ("airlock", "prebreathe", "post")
        if on_tank:
            o2 -= 100 * (vo2 + 0.05) / (8.0 * 60 * 0.85) / 60.0
            scrub -= 100 * vo2 / (8.5 * 60 * 0.80) / 60.0
            water -= 100 * COOL_USE[level] / (7.5 * 3600.0)
        batt -= 100 * (1 + 0.05 * (level - 3)) / (8.5 * 3600.0)
        if fault_t is not None and t >= fault_t and phase != "post":
            fault_add += 0.30 * (M / 300.0) / 60.0
        co2_ss = (1.2 + 0.0040 * M + fault_add) if phase != "post" else 2.0
        co2 += (co2_ss - co2) / 45.0
        suit_t += ((19.5 + 0.006 * M - 0.5 * (level - 3)) - suit_t) / 240.0
        # ---- radiation: real surface rate; the storm replays Curiosity's hourly record in real time
        mult = 1.0
        if onset_t is not None and t >= onset_t:
            prof = [1.0] + list(storm_profile)                    # hourly means, taken at the middle of each hour
            k = (t - onset_t) / 3600.0 + 0.5
            i0 = min(int(k), len(prof) - 2)
            mult = prof[i0] + (prof[i0 + 1] - prof[i0]) * (k - i0)
        rate_now = rate0 * mult * (1 + rng.normal(0, 0.04))
        if outside: dose += rate0 * mult / 3600.0
        # ---- movement
        if phase == "traverse":
            sp = WALK_SPEED / ROUTE * (0.84 if stamina < 35 else 1.0)
            dx, dy = target[0] - x, target[1] - y
            dd = math.hypot(dx, dy)
            if dd <= sp:
                x, y = target; path.append((x, y)); seg_t = 10 ** 9      # arrived
            else:
                x += dx / dd * sp; y += dy / dd * sp
        d_back = math.hypot(x, y) * ROUTE
        walk_min = d_back / (WALK_SPEED * (0.84 if stamina < 35 else 1.0)) / 60.0
        # ---- model estimates
        bal_n = 0.98 * bal_n + rng.normal(0, 0.25)
        balance = float(np.clip(ctx["balance"] - 0.35 * (100 - stamina) - 6.0 * max(0.0, lactate - 2.0) + bal_n, 0, 100))
        zf = -5.0 + 1.2 * max(0.0, tc - tc0) / 0.6 + 2.5 * max(0.0, hr / hrmax - 0.75) + 0.015 * (100 - stamina) + 1.0 * math.exp(-ctx["days_on_mars"] / 10.0)
        faint = 100.0 / (1 + math.exp(-zf))
        # ---- time left per resource (minutes)
        hist_co2.append(co2)
        slope_co2 = (co2 - hist_co2[-181]) / 3.0 if len(hist_co2) > 181 else 0.0       # mmHg per minute over the last 3 min
        local_h = START_LOCAL_H + t / 3600.0
        left = {
            "Oxygen": o2 / (100 * (max(vo2, 0.7) + 0.05) / (8.0 * 60 * 0.85)),
            "Battery": batt / (100 / (8.5 * 60.0)),
            "Cooling water": water / (100 * COOL_USE[max(level, 3)] / (7.5 * 60.0)),
            "CO₂ scrubber": scrub / (100 * max(vo2, 0.7) / (8.5 * 60 * 0.80)),
            "Daylight": (ctx["sunset_h"] - local_h) * 60.0,
            "Stamina": max(0.0, (stamina - 15.0) / plan_rate),
        }
        left_event = None
        if alert_t is not None:
            left_event = max(0.0, 30.0 - (t - alert_t) / 60.0); left["Storm rule"] = left_event      # our rule: indoors within 30 min of the warning
        if fault_t is not None and slope_co2 > 0.12 and co2 > 3.2:
            left_event = max(0.0, (20.0 - co2) / max(slope_co2, 0.05)); left["CO₂ limit"] = left_event
        # consumables keep a 30-minute reserve; event limits (storm rule, CO2 limit) only need the walk and the airlock (9 min)
        margin = {k: v - walk_min - (INGRESS_MIN if k in ("Storm rule", "CO₂ limit") else RESERVE_MIN) for k, v in left.items()}
        limiter = min(margin, key=margin.get)
        stay = margin[limiter]
        # ---- rules (every second)
        hr_hi = hr_hi + 1 if hr > 140 else 0
        co2_rise = co2_rise + 1 if (slope_co2 > 0.15 and M < 330) else 0
        cues = []
        if outside:
            if hr_hi >= 120: cues.append(("eva.hr_bpm", "Heart rate above 140 bpm for 2 min"))
            if tc - tc0 >= 0.6: cues.append(("eva.core_c", f"Core {tc - tc0:.1f} °C over the pre-EVA value"))
            if lactate >= 4: cues.append(("eva.lactate_mmol", "Lactate high"))
            if stamina < 35: cues.append(("eva.stamina_pct", "Stamina low"))
            if balance < 65: cues.append(("eva.balance_score", "Balance low"))
            if faint >= 10: cues.append(("eva.faint_risk_pct", f"Chance to faint raised: about {faint:.0f} %"))
            if co2_rise >= 180: cues.append(("eva.suit_co2_mmhg", f"CO2 rising {slope_co2:.1f} mmHg per minute"))
            if mult >= 1.2: cues.append(("eva.dose_rate_usv_h", f"Dose rate {mult:.2f} times the usual surface rate"))
        dose_hi = dose_hi + 1 if mult >= 1.2 else 0
        if dose_hi == 1 and outside: ev(t, "caution", "caution", "eva.dose_rate_usv_h", "Dose rate 1.2 times the usual surface rate and climbing.")
        emergency = outside and (tc >= 39.5 or heat >= 3.0 or co2 >= 20)
        if outside and returning is None:
            if dose_hi >= 600:
                returning = "storm"; alert_t = t
                ev(t, "alarm", "return", "eva.dose_rate_usv_h", f"Storm warning from the habitat: solar particle event confirmed, rate {mult:.2f} times the usual for 10 min. EVA ends; indoors within 30 min.")
            elif co2_rise >= 360:
                returning = "co2"; ev(t, "alarm", "return", "eva.suit_co2_mmhg", f"CO2 scrubber fault suspected: {co2:.1f} mmHg and rising {slope_co2:.1f} a minute. Return called.")
            elif stay <= 0 or stamina < 20 or faint >= 20 or tc >= 39.0:
                returning = "stamina" if limiter == "Stamina" or stamina < 20 else "margin"
                ev(t, "alarm", "return", "eva.stay_min", f"Return called: {limiter.lower()} is the limit.")
            elif caution_ep >= 1 and not in_caution and rest_left == 0 and len([c for c in cues if c[0] in ("eva.hr_bpm", "eva.core_c", "eva.lactate_mmol")]) >= 2:
                returning = "heat"; ev(t, "alarm", "return", "eva.core_c", "Heat cues are back after the rest. Task ended, return called.")
            if returning:
                queue = [("traverse", "Walk back to the airlock", None, 250 if returning in ("co2", "heat", "stamina") else 300, (0.0, 0.0))]
                cur = queue.pop(0); seg_t = 0; rest_left = 0
                ev(t, "phase", "info", None, cur[1])
        phys = [c for c in cues if c[0] not in ("eva.suit_co2_mmhg", "eva.dose_rate_usv_h")]
        if outside and returning is None and not in_caution and rest_left == 0 and cur[0] == "work":
            if len(phys) >= 2 or heat >= 2.4:                              # two cues together: stop, rest, cool (NASA V2 11011 cues)
                in_caution = True; caution_ep += 1; rest_left = 300; drink += 200
                ev(t, "caution", "caution", phys[0][0], "; ".join(c[1] for c in phys) + ". Stop and rest 5 min, cooling to max.")
            elif len(phys) == 1 and eased != cur[1]:                       # one cue: slow down
                eased = cur[1]; slow *= 0.92
                ev(t, "caution", "caution", phys[0][0], phys[0][1] + ". Ease the pace.")
        if rest_left > 0:
            rest_left -= 1
            if rest_left == 0:
                in_caution = False; slow = 0.78
                ev(t, "action", "info", None, "Rested 5 min. Work resumes at a lower pace.")
        if outside and returning is None and not in_caution and co2_rise == 180:
            ev(t, "caution", "caution", "eva.suit_co2_mmhg", f"CO2 rising {slope_co2:.1f} mmHg per minute without effort. Stop work and watch.")
        state = "emergency" if emergency else "return" if (returning and outside) else "caution" if (outside and (in_caution or cues or stay < 20)) else "go"
        if phase == "airlock": nid = 1
        elif phase == "prebreathe": nid = 2
        elif phase == "depress": nid = 3
        elif phase == "egress": nid = 4
        elif phase == "ingress": nid = 13
        elif phase == "repress": nid = 14
        elif phase == "post": nid = 15
        elif returning: nid = {"storm": 11, "co2": 10, "heat": 8, "stamina": 12, "margin": 17, "plan": 12}[returning]
        elif in_caution or rest_left > 0: nid = 7
        elif co2_rise >= 180: nid = 9
        elif dose_hi > 0 and not phys: nid = 18
        elif phys: nid = 16
        elif state == "caution": nid = 19
        elif phase == "rest": nid = 6
        else: nid = 5
        if phase == "rest" and seg_t == 60: drink += 200
        seg_left = None if dur is None else max(0, dur - seg_t)
        if rest_left > 0: seg_left = rest_left
        rows.append(dict(scenario_id=sid, t_s=t, phase=phase, task=task if rest_left == 0 else "Rest ordered by the unit", seg_left_s=seg_left, state=state,
                         limiter=limiter if outside else None, stay_min=round(stay, 1) if outside else None, walk_back_min=round(walk_min, 1),
                         dist_m=round(d_back), x_m=round(x, 1), y_m=round(y, 1), met_w=round(M), hr_bpm=round(hr + rng.normal(0, 0.8)), core_c=round(tc, 2),
                         lactate_mmol=round(lactate, 2), stamina_pct=round(stamina, 1), balance_score=round(balance), faint_risk_pct=round(faint, 1),
                         heat_kj_kg=round(heat, 2), suit_p_kpa=round(suit_p + rng.normal(0, 0.02), 2), suit_o2_pct=round(o2, 1),
                         suit_co2_mmhg=round(co2 + rng.normal(0, 0.05), 2), suit_temp_c=round(suit_t + rng.normal(0, 0.05), 1), battery_pct=round(batt, 1),
                         water_pct=round(water, 1), scrubber_pct=round(scrub, 1), cooling_level=level, dose_rate_usv_h=round(rate_now, 1), eva_dose_usv=round(dose, 1),
                         drink_ml=round(drink), left_o2_min=round(left["Oxygen"]), left_battery_min=round(left["Battery"]), left_water_min=round(left["Cooling water"]),
                         left_scrubber_min=round(left["CO₂ scrubber"]), left_daylight_min=round(left["Daylight"]), left_stamina_min=round(left["Stamina"]),
                         left_event_min=None if left_event is None else round(left_event, 1), next_id=nid))
        if state != last_state:
            if state == "go" and last_state in ("caution",): ev(t, "info", "info", None, "Back to Go.")
            last_state = state
        # ---- next second, next segment
        t += 1; seg_t += 1
        if (dur is not None and seg_t >= dur) or seg_t >= 10 ** 9:
            # before walking farther out: does the next task still fit the stay time?
            if queue and queue[0][1] == "Walk to site B" and returning is None and (stay < 2400 / 60 + 2 * 6.3 + 5 or caution_ep >= 1):
                returning = "plan"
                ev(t, "alarm", "return", "eva.stay_min", f"Site B does not fit: {max(stay, 0):.0f} min to stay, the task needs 58. {limiter} is the limit. Walk back.")
                queue = [("traverse", "Walk back to the airlock", None, 280, (0.0, 0.0))]
            if not queue:
                if cur[0] == "traverse" and math.hypot(x, y) < 1.0 and cur[1].startswith("Walk back"):
                    queue = list(TAIL)
                else:
                    done = True
            if queue:
                cur = queue.pop(0); seg_t = 0
                ev(t, "phase", "info", None, cur[1])
    peak_hr = max(r["hr_bpm"] for r in rows)
    out_rows = [r for r in rows if r["phase"] in ("egress", "traverse", "work", "rest", "ingress")]
    summary = dict(duration_s=len(rows), outside_min=round(len(out_rows) / 60), peak_hr=peak_hr, peak_core=max(r["core_c"] for r in rows),
                   peak_lactate=max(r["lactate_mmol"] for r in rows), min_stamina=min(r["stamina_pct"] for r in rows), peak_co2=max(r["suit_co2_mmhg"] for r in rows),
                   dose_usv=rows[-1]["eva_dose_usv"], max_dist_m=max(r["dist_m"] for r in rows), drink_ml=rows[-1]["drink_ml"],
                   cautions=sum(1 for e in events if e["kind"] == "caution"), returned=returning)
    return rows, events, summary


SCEN = {
    "nominal": dict(sort=1, title="Normal walk", outcome="nominal",
                    text="Nine sols after landing. The walk runs to plan: sampling, a drilled core, instruments at the second site, back before the reserve is touched. Stamina is the shortest resource all the way: the body runs out before the suit."),
    "fatigue": dict(sort=2, title="Fatigue rising", outcome="shortened: fatigue",
                    text="The last day of a two-week EVA campaign with short nights; readiness is 'ready with limits'. The first 100 minutes look normal. Drilling in hard rock pushes the work rate past what the body can hold: first one heat cue (ease the pace), then two cues together (stop, rest five minutes, cooling to max). The cues come back, stamina no longer covers the walk home plus the reserve, and the unit calls the return. The second site is dropped."),
    "co2": dict(sort=3, title="Suit CO₂ high", outcome="terminated: CO2 scrubber fault",
                text="A normal walk until the CO2 scrubber starts to fail during sampling. Helmet CO2 climbs steadily although the work is light: a scrubber pattern, not effort. The unit warns after three minutes and calls the return after six, long before the 20 mmHg limit."),
    "storm": dict(sort=4, title="Radiation storm warning", outcome="terminated: solar storm warning",
                  text="A normal walk while, unseen, a solar storm begins. The dose rate outside creeps up from 44 minutes into the walk; the unit cautions at 1.2 times the usual rate, and when the habitat confirms a particle event the rule ends the EVA. The curve is what Curiosity measured on Mars on 10 September 2017, replayed in real time: the rate doubles within five hours, when the crew is already indoors."),
}


def build(con, cal, H, envd, learned, storm_profile, forced, evas, rng_of):
    idx = {r["day"]: i for i, r in enumerate(cal)}
    crew = next(c for c in base.CREW if c[0] == base.FOCUS)
    from .body import PARAMS
    land = next(r["day"] for r in cal if r["phase"] == "surface")
    for sid, day in forced.items():
        i, h, e = idx[day], H[base.FOCUS], envd[day]
        bal = next((h["balance_pct"][k] for k in range(i, i - 10, -1) if h["balance_pct"][k] is not None), 100.0)
        ctx = dict(age=crew[4], mass=h["body_mass_kg"][i], vo2_ml_kg=PARAMS[base.FOCUS]["vo2"], vo2max_pct=h["vo2max_pct"][i], hr_rest=h["hr_rest_bpm"][i],
                   readiness=h["readiness"][i], readiness_band=h["readiness_band"][i], sleep_h=h["sleep_h"][i], sleep_debt=h["sleep_debt_h"][i],
                   temp=h["temp_core_c"][i], balance=bal, days_on_mars=day - land, dose_rate=base.DOSE_SURFACE * 1000 / 24 * (e["dose_day_msv"] / base.DOSE_SURFACE if sid != "storm" else 1.0),
                   sunset_h=e["sunset_h"], sunrise_h=e["sunrise_h"], out_temp_max_c=e["out_temp_max_c"], out_temp_min_c=e["out_temp_min_c"])
        rows, events, s = simulate(sid, ctx, learned, storm_profile, rng_of(f"eva1hz:{sid}"))
        base.put(con, "eva_sample", rows)
        base.put(con, "eva_event", events)
        base.put(con, "eva_text", [dict(scenario_id=sid, next_id=k, text=v) for k, v in TEXT.items()])
        first = lambda kinds: next((x["t_s"] for x in events if x["kind"] in kinds), None)
        snap = {"nominal": 6138, "fatigue": next((x["t_s"] for x in events if "Stop and rest" in x["text"]), 6500) + 75, "co2": (first(("alarm",)) or 6000) + 240, "storm": (first(("alarm",)) or 6000) + 240}[sid]
        log = next(x for x in evas if x["day"] == day and x["team"] == "A")
        log.update(actual_min=round(s["duration_s"] / 60), planned_min=216, distance_m=round(2 * s["max_dist_m"], -1), peak_hr=s["peak_hr"], dose_usv=round(s["dose_usv"]),
                   summary=SCEN[sid]["text"], outcome=SCEN[sid]["outcome"])
        ctx_out = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in ctx.items()}
        ctx_out.update(summary=s, eva_number=log["number"], call_sign=crew[1], start_local="10:00", reserve_min=RESERVE_MIN, walk_speed_m_s=WALK_SPEED,
                       site_a=SITE_A, site_b=SITE_B)
        base.put(con, "eva_scenario", [dict(scenario_id=sid, eva_id=None, sort=SCEN[sid]["sort"], title=SCEN[sid]["title"], day=day, sol=cal[i]["sol"],
                                            date_utc=cal[i]["date"].isoformat(), crew_id=base.FOCUS, start_local_h=START_LOCAL_H, duration_s=s["duration_s"],
                                            snapshot_t_s=snap, outcome=SCEN[sid]["outcome"], summary=SCEN[sid]["text"], context_json=base.jdump(ctx_out))])
    return None
