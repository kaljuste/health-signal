"""The simulated crew: one row per person and day for the whole mission, plus hours, labs, medical events and EVAs.

Each value follows the model of its row in the indicator catalog (kb/13, kb/raw/catalog/catalog_final.json):
weightless -> 0.38 g -> weightless -> 1 g. Levels and time constants are quoted from the catalog; where the
catalog marks a number [INF] it is an informed assumption. Nobody has lived at 0.38 g: every Mars value is a model."""
import math
from collections import defaultdict
import numpy as np
from . import base

EXP = math.exp
PLAN_EX_MIN = 86.0              # ~600 min a week (catalog exercise_dose)
FLUID_TARGET = 2.9             # L/day, stone-prevention protocol of this mission (catalog urine_output_stone_risk)
CAMPAIGN_SOLS = (168, 180)     # scripted: long-traverse EVA campaign of team A, early starts and late reports
ARED_FAULT = (800, 813)        # scripted: resistive exercise device out of order on the way home
LOW_MOOD = ("C4", 820, 850)    # scripted: one crew member has a low stretch on the way home
VITD_REVIEW_DAY = 130

# Personal parameters. Baselines sit inside NHANES adult ranges and near Inspiration4 pre-flight values (learn.py).
PARAMS = {
    "C1": dict(hr=55, rmssd=56, sys=112, dia=70, spo2=98.0, temp=36.85, sleep_earth=7.2, sleep_flight=6.6, rt=262, who5=19.0, vo2=41.0,
               hb=13.6, wbc=6.2, lymph=2.0, vitd=38, vitd_ss=31, ferritin=62, creat=0.74, crp=0.8, glucose=86, uca=150,
               bone=-0.24, sans=22, e_adh=0.97, x_adh=0.93, f_adh=1.00, tcore_amp=0.75, ortho=1.25, sms_p=0.46, repeat=True),
    "C2": dict(hr=58, rmssd=44, sys=124, dia=78, spo2=97.6, temp=36.9, sleep_earth=6.8, sleep_flight=6.0, rt=270, who5=18.0, vo2=39.0,
               hb=15.0, wbc=6.8, lymph=2.1, vitd=33, vitd_ss=28, ferritin=140, creat=0.98, crp=1.2, glucose=94, uca=185,
               bone=-0.50, sans=58, e_adh=0.93, x_adh=0.88, f_adh=0.95, tcore_amp=0.9, ortho=1.0, sms_p=0.46, repeat=True),
    "C3": dict(hr=51, rmssd=68, sys=118, dia=72, spo2=98.2, temp=36.8, sleep_earth=7.4, sleep_flight=6.9, rt=250, who5=20.0, vo2=46.0,
               hb=15.3, wbc=5.9, lymph=1.9, vitd=41, vitd_ss=33, ferritin=110, creat=0.95, crp=0.6, glucose=88, uca=160,
               bone=-0.20, sans=12, e_adh=1.0, x_adh=0.97, f_adh=1.03, tcore_amp=0.65, ortho=0.85, sms_p=0.7, repeat=False),
    "C4": dict(hr=60, rmssd=48, sys=108, dia=68, spo2=97.5, temp=36.9, sleep_earth=7.0, sleep_flight=6.4, rt=268, who5=17.5, vo2=38.0,
               hb=13.1, wbc=6.5, lymph=2.3, vitd=30, vitd_ss=27, ferritin=45, creat=0.70, crp=1.0, glucose=84, uca=140,
               bone=-0.45, sans=36, e_adh=0.92, x_adh=0.90, f_adh=0.97, tcore_amp=0.8, ortho=1.35, sms_p=0.7, repeat=False),
}

# NASA medical-conditions ranking (kb/19): condition -> (class, severity, duration range in days, where it can start)
CONDITIONS = {
    "LATE INSOMNIA": ("insomnia", "minor", (3, 6), "any"), "SKIN ABRASION": ("skin", "minor", (3, 6), "any"),
    "SKIN RASH": ("skin", "minor", (5, 12), "any"), "EYE ABRASION (FOREIGN BODY)": ("eye", "minor", (1, 3), "any"),
    "PARESTHESIAS": ("eva_minor", "minor", (1, 3), "eva"), "HEADACHE (LATE)": ("headache", "minor", (1, 2), "any"),
    "URINARY TRACT INFECTION": ("uti", "moderate", (4, 7), "any"), "DIARRHEA": ("gi", "moderate", (2, 3), "any"),
    "RESPIRATORY INFECTION": ("resp", "moderate", (5, 8), "any"), "BACK INJURY": ("msk", "moderate", (6, 14), "any"),
    "BAROTRAUMA (EAR/SINUS BLOCK)": ("eva_minor", "minor", (1, 3), "eva"), "FINGERNAIL DELAMINATION": ("eva_minor", "minor", (7, 14), "eva"),
    "SHOULDER SPRAIN/STRAIN": ("msk", "moderate", (6, 14), "any"), "SKIN INFECTION": ("skin", "minor", (5, 9), "any"),
    "ELBOW SPRAIN/STRAIN": ("msk", "minor", (5, 10), "any"), "ANKLE SPRAIN/STRAIN": ("msk", "moderate", (6, 12), "gravity"),
    "ALLERGIC REACTION (MILD TO MODERATE)": ("allergy", "minor", (1, 3), "any"), "PHARYNGITIS": ("resp", "minor", (3, 5), "any"),
    "NECK INJURY": ("msk", "minor", (4, 9), "any"), "MOUTH ULCER": ("skin", "minor", (4, 8), "any"),
    "KNEE SPRAIN/STRAIN": ("msk", "moderate", (6, 12), "gravity"), "ACUTE SINUSITIS": ("resp", "minor", (5, 8), "any"),
    "INDIGESTION": ("gi", "minor", (1, 2), "any"), "GASTROENTERITIS": ("gi", "moderate", (2, 4), "any"),
    "EYE INFECTION": ("eye", "minor", (4, 7), "any"), "DECOMPRESSION SICKNESS SECONDARY TO EVA": ("dcs", "major", (4, 7), "eva"),
}
# What a condition does on a day at full strength. pts = readiness points.
EFFECT = {
    ("insomnia", "minor"): dict(sleep=-1.5, pts=0),
    ("skin", "minor"): dict(mood=-0.3, pts=2), ("eye", "minor"): dict(mood=-0.3, pts=3), ("eva_minor", "minor"): dict(pts=3),
    ("allergy", "minor"): dict(pts=3), ("headache", "minor"): dict(stress=0.6, pts=4),
    ("uti", "moderate"): dict(fever=0.5, energy=0.9, crp=4, wbc=1.3, pts=10, mood=-1),
    ("gi", "moderate"): dict(energy=0.6, fluid=-0.5, exercise=0.3, pts=12, mood=-1), ("gi", "minor"): dict(energy=0.85, pts=4),
    ("resp", "moderate"): dict(fever=0.8, spo2=-1.5, rr=3, energy=0.85, exercise=0.3, sleep=-0.6, crp=6, wbc=1.4, pts=12, mood=-1.5),
    ("resp", "minor"): dict(fever=0.3, exercise=0.7, crp=2.5, pts=5, mood=-0.5),
    ("msk", "moderate"): dict(exercise=0.5, resist=0.3, pts=8, mood=-0.5), ("msk", "minor"): dict(exercise=0.8, resist=0.6, pts=4),
    ("dcs", "major"): dict(exercise=0.0, pts=25, mood=-2, stress=2),
}
LAY = {"insomnia": "trouble sleeping", "skin": "skin problem", "eye": "eye irritation", "eva_minor": "suit-related complaint",
       "allergy": "allergic reaction", "headache": "headache", "uti": "urinary infection", "gi": "stomach or bowel upset",
       "resp": "airway infection", "msk": "strain or sprain", "dcs": "decompression sickness after an EVA"}


def relax(x, target, tau):
    return x + (target - x) * (1 - EXP(-1.0 / tau))


def mean_last(xs, n, skip=0):
    v = [x for x in (xs[-(n + skip):-skip] if skip else xs[-n:]) if x is not None]
    return sum(v) / len(v) if v else None


def day_of_sol(cal, sol):
    return next(r["day"] for r in cal if r["sol"] == sol)


def eva_schedule(cal, envd, storm_day0):
    """Planned EVA days per team (surface only). Forced days carry the four arm-unit scenarios."""
    surf = [r for r in cal if r["phase"] == "surface"]
    d0, d1 = surf[0]["day"], surf[-1]["day"]
    forced = {"nominal": 181, "fatigue": day_of_sol(cal, 178), "co2": day_of_sol(cal, 301), "storm": storm_day0}
    camp0, camp1 = day_of_sol(cal, CAMPAIGN_SOLS[0]), day_of_sol(cal, CAMPAIGN_SOLS[1])
    plan = {"A": set(), "B": set()}
    for r in surf:
        d, pd = r["day"], r["day"] - d0
        if pd < 5 or d > d1 - 4 or r["comm"] == "blackout":
            continue
        if envd[d]["storm_level"] >= 1 and d != storm_day0:
            continue
        if pd % 7 == 2: plan["A"].add(d)                 # one EVA a week per team, two teams (NASA's planning case: about 50 EVAs)
        if pd % 7 == 5: plan["B"].add(d)
    for d in range(camp0, camp1 + 1):                    # campaign: every second day
        plan["A"].discard(d)
        if (d - camp0) % 2 == 1 or d == forced["fatigue"]:
            plan["A"].add(d)
    for d in (camp1 + 1, camp1 + 2, camp1 + 3):          # stand-down after the campaign (Earth instruction on sol 180)
        plan["A"].discard(d)
    for d in forced.values():
        plan["A"] -= {d - 1, d + 1}
        plan["A"].add(d)
    plan["A"] -= {storm_day0 + 1, storm_day0 + 2}; plan["B"] -= {storm_day0, storm_day0 + 1, storm_day0 + 2}
    return plan, forced, (camp0, camp1)


def draw_conditions(cal, plan, rng_of):
    """Medical events per person from NASA's probabilities for a 36-month planetary mission (kb/19)."""
    con = base.ref()
    prob = defaultdict(dict)
    for sex, cond, p in con.execute("select sex, condition, p_at_least_one from imm_condition_ranking where drm like 'Thirty-six month Planetary%'"):
        prob[sex][cond] = p
    con.close()
    mission = [r for r in cal if 5 <= r["day"] <= 922]
    grav = [r["day"] for r in mission if r["phase"] == "surface"]
    out = defaultdict(list)
    scripted = {0, 2, 30, 85, 96, 97, 98, 171, 172, 175, 181, 354, 355, 356, 408, 425, 431, 622, 732, 768, 810, 922}
    for cid, call, role, sex, *_ in base.CREW:
        rng = rng_of(f"conditions:{cid}")
        team = next(t for t, m in base.EVA_TEAMS.items() if cid in m)
        evas = sorted(plan[team])
        for cond, (cls, sev, dur, where) in CONDITIONS.items():
            p = prob["female" if sex == "F" else "male"].get(cond)
            if not p:
                continue
            lam = -math.log(max(1 - min(p, 0.999), 1e-3)) * 923 / 1095
            for _ in range(min(int(rng.poisson(lam)), 6)):
                pool = evas if where == "eva" else grav if where == "gravity" else [r["day"] for r in mission]
                for _try in range(20):
                    start = int(rng.choice(pool))
                    if cid != base.FOCUS or all(abs(start - s) > 4 for s in scripted):
                        break
                n = int(rng.integers(dur[0], dur[1] + 1))
                out[cid].append(dict(start=start, end=min(start + n - 1, 922), cls=cls, sev=sev, cond=cond))
        # keep at most one moderate or major condition at a time
        out[cid].sort(key=lambda e: e["start"])
        kept, busy = [], -99
        for e in out[cid]:
            if e["sev"] != "minor":
                if e["start"] <= busy + 2:
                    continue
                busy = e["end"]
            kept.append(e)
        out[cid] = kept
    return out


def build(cal, envd, learned, storm_day0, rng_of):
    P = PARAMS
    idx = {r["day"]: i for i, r in enumerate(cal)}
    phase_start = {}
    for r in cal:
        phase_start.setdefault(r["phase"], r["day"])
    plan, forced, camp = eva_schedule(cal, envd, storm_day0)
    conds = draw_conditions(cal, plan, rng_of)
    shape = learned["hr_day_shape"]
    k_pvt = learned["pvt_sleep_loss"]["slowing_per_debt_hour"]

    S = {}                                                # running state per person
    H = {c[0]: defaultdict(list) for c in base.CREW}      # history per person
    for cid, call, role, sex, age, hgt, m0 in base.CREW:
        p, rng = P[cid], rng_of(f"body:{cid}")
        sev_roll = rng.random()
        S[cid] = dict(rng=rng, sex=sex, age=age, m0=m0, hrmax=208 - 0.7 * age, z_sleep=0.0, z_mood=0.0, z_hr=0.0, debt=1.0,
                      f_hr=0.0, f_hrv=0.0, f_bp=0.0, f_t=0.0, fluid=0.0, tissue=0.0, uca=1.0, vo2=0.0, strength=0.0, bmd=100.0,
                      sans=0.0, rbc=0.0, pv=0.0, wbc=0.0, crp=0.0, ferr=0.0, vitd=float(p["vitd"]), vitd_ss=float(p["vitd_ss"]),
                      ortho=0.0, dose=0.0, land_mars=None, land_earth=None,
                      sms={}, pain={}, sms_draw=rng.random(), sms_sev=rng.random(), pain_sev=sev_roll, menu=0.0)
    body_day, body_hour, labs, events, evas, cost_rows = [], [], [], [], [], []
    eva_no = {"A": 0, "B": 0}
    eva_block = defaultdict(int)                          # person -> last day with an EVA ban (illness)

    def sms_course(st, key, p_case, start, grade_cap=3):
        """Space motion sickness after a gravity change: grade by day (catalog space_motion_sickness)."""
        if st["rng"].random() >= p_case:
            return
        u = st["rng"].random()
        g = 1 if u < 0.46 else 2 if u < 0.81 else 3
        g = min(g, grade_cap)
        for k in range(0, 6):
            val = g * EXP(-k / 1.3)
            if val >= 0.5:
                st["sms"][start + k] = int(round(val))

    for i, r in enumerate(cal):
        d, ph, e = r["day"], r["phase"], envd[r["day"]]
        pd = d - phase_start[ph]
        zero_g = ph in ("outbound", "return")
        # ---- EVA decision for the day
        eva_today = {}
        if ph == "surface":
            for team, members in base.EVA_TEAMS.items():
                if d not in plan[team]:
                    continue
                is_forced = team == "A" and d in forced.values()
                ok = all((H[m]["readiness"][-1] or 0) >= 70 and eva_block[m] < d for m in members)
                if ok or is_forced:
                    eva_no[team] += 1
                    for m in members: eva_today[m] = (team, eva_no[team])
                else:
                    low = [next(c[1] for c in base.CREW if c[0] == m) for m in members if (H[m]["readiness"][-1] or 0) < 70 or eva_block[m] >= d]
                    evas.append(dict(day=d, sol=r["sol"], team=team, crew_ids=",".join(members), number=None, planned_min=216, actual_min=0,
                                     distance_m=0, peak_hr=None, dose_usv=0, outcome="postponed",
                                     summary=f"Postponed by rule: {' and '.join(low)} not ready for an EVA.", scenario_id=None))
        for cid, call, role, sex, age, hgt, m0 in base.CREW:
            p, st, h, rng = P[cid], S[cid], H[cid], S[cid]["rng"]
            # ---- gravity changes
            if ph == "outbound" and pd == 0:
                sms_course(st, "launch", p["sms_p"], d)
                u = st["pain_sev"]
                if rng.random() < 0.9:
                    sev = 2.0 if u < 0.86 else 5.0 if u < 0.97 else 7.0
                    onset = int(rng.integers(0, 3))
                    for k in range(onset, 12):
                        st["pain"][d + k] = sev * EXP(-(k - onset) / 3.0)
            if ph == "surface" and pd == 0:
                st["land_mars"] = d; sms_course(st, "mars", 0.5, d, 1)
                if rng.random() < 0.5:
                    for k in range(0, 5): st["pain"][d + k] = 1.6 * EXP(-k / 2.5)
            if ph == "return" and pd == 0:
                sms_course(st, "depart", 0.5, d, 2)
                if rng.random() < 0.6:
                    for k in range(1, 10): st["pain"][d + k] = 1.8 * EXP(-(k - 1) / 3.0)
            if ph == "recovery" and pd == 0:
                st["land_earth"] = d; sms_course(st, "earth", 0.6, d, 2)
                for k in range(0, 8): st["pain"][d + k] = 2.2 * EXP(-k / 4.0)

            # ---- active medical conditions
            mods = dict(sleep=0.0, fever=0.0, spo2=0.0, rr=0.0, energy=1.0, exercise=1.0, resist=1.0, fluid=0.0, mood=0.0, stress=0.0,
                        crp=1.0, wbc=1.0, pts=0.0)
            symptoms = []
            for ev in conds[cid]:
                if ev["start"] <= d <= ev["end"]:
                    frac = 1 - 0.6 * (d - ev["start"]) / max(ev["end"] - ev["start"], 1)
                    ef = EFFECT[(ev["cls"], ev["sev"])]
                    for k, v in ef.items():
                        if k in ("energy", "exercise", "resist", "crp", "wbc"):
                            mods[k] *= 1 + (v - 1) * frac
                        elif k == "fever":
                            mods[k] += v * max(0.0, 1 - (d - ev["start"]) / 3.0)
                        else:
                            mods[k] += v * frac
                    symptoms.append(LAY[ev["cls"]])
                    if ev["sev"] != "minor":                      # no EVA while acutely ill; a week after decompression sickness
                        until = ev["end"] + 7 if ev["cls"] == "dcs" else min(ev["end"], ev["start"] + 3) if ev["cls"] in ("msk", "uti") else ev["end"]
                        eva_block[cid] = max(eva_block[cid], until)
            sms = st["sms"].get(d, 0)
            pain = st["pain"].get(d, 0.0)
            if sms: symptoms.append("motion sickness")
            if pain >= 1: symptoms.append("back pain")
            co2_hi = max(0.0, e["cabin_co2_max1h"] - 3.0) if ph not in ("prelaunch", "recovery") else 0.0
            if co2_hi > 0.3 and cid in ("C1", "C4"):
                symptoms.append("headache"); mods["pts"] += 4; mods["stress"] += 0.6
            in_camp = cid in base.EVA_TEAMS["A"] and camp[0] <= d <= camp[1]
            camp_k = (d - camp[0]) / (camp[1] - camp[0]) if in_camp else 0.0
            ared_out = ARED_FAULT[0] <= d <= ARED_FAULT[1]
            low_mood = cid == LOW_MOOD[0] and LOW_MOOD[1] <= d <= LOW_MOOD[2]
            eva = eva_today.get(cid)
            eva_tomorrow = ph == "surface" and any((d + 1) in plan[t] for t, m in base.EVA_TEAMS.items() if cid in m)
            landing_eve = (ph == "outbound" and d == phase_start["surface"] - 1) or (ph == "return" and d == phase_start["recovery"] - 1)
            landing_day = ph in ("surface", "recovery") and pd == 0
            launch_day = ph in ("outbound", "return") and pd == 0
            shelter = e["shelter_h"] or 0

            # ---- sleep (catalog sleep_duration_efficiency) and sleep debt (catalog alertness_pvt_b)
            mean = p["sleep_earth"] if ph in ("prelaunch", "recovery") else p["sleep_flight"] + (0.3 if ph == "surface" else 0.0)
            st["z_sleep"] = 0.3 * st["z_sleep"] + rng.normal(0, 0.95 * math.sqrt(1 - 0.09)) * (0.7 if ph in ("prelaunch", "recovery") else 1.0)
            off = mods["sleep"] - 0.5 * sms - (1.5 if launch_day else 0) - (0.8 if landing_eve else 0) - (1.5 if landing_day else 0) \
                - (0.2 if eva_tomorrow else 0) - (1.0 if shelter >= 12 else 0) - (0.4 if co2_hi > 0.3 else 0) - 0.15 * max(pain - 2, 0) \
                - (0.7 + 1.2 * camp_k if in_camp else 0) - (0.5 if low_mood else 0) + (0.5 if (ph == "surface" and camp[1] < d <= camp[1] + 4 and cid in base.EVA_TEAMS["A"]) else 0)
            sleep = float(np.clip(mean + st["z_sleep"] * (0.45 if in_camp else 1.0) + off, 2.5, 9.6))
            eff = float(np.clip(rng.normal(88, 3.5) - (5 if sleep < 5.2 else 0) - 2 * sms - 0.8 * max(pain - 2, 0), 62, 97))
            tib = sleep / (eff / 100)
            st["debt"] = st["debt"] * EXP(-1 / 6.0) + max(0.0, (24 - tib) - 15.84)
            debt = st["debt"]
            debt_usual = mean_last(h["sleep_debt_h"], 28, 3) if len(h["sleep_debt_h"]) > 3 else None
            debt_usual = debt if debt_usual is None else debt_usual
            # ---- reaction time (PVT): slows with sleep debt; learned slowing per hour of debt
            rt_true = p["rt"] * (1 + k_pvt * debt) * (1 + 0.015 * co2_hi) * (1.04 if landing_day else 1.0) * (1.03 if mods["fever"] > 0.3 else 1.0)
            rt = rt_true * (1 + rng.normal(0, 0.03))
            base_rt = mean_last(h["pvt_rt_ms"], 28, 3) or p["rt"] * (1 + k_pvt * debt)
            pvt_z = -(rt - base_rt) / (0.055 * base_rt)
            # ---- mood and stress (catalog mood_stress_workload)
            st["z_mood"] = 0.75 * st["z_mood"] + rng.normal(0, 1.0)
            who5 = p["who5"] + 0.9 * st["z_mood"] - 0.35 * max(0.0, debt - 5.0) + mods["mood"] - (1.2 if r["comm"] == "blackout" else 0) \
                + (1.5 if (ph == "surface" and pd < 14) else 0) - (5.0 if low_mood else 0) - 0.6 * sms + (1.0 if ph == "recovery" else 0)
            who5 = float(np.clip(round(who5), 3, 25))
            stress = 2.4 + 0.22 * max(0.0, debt - 4.0) + mods["stress"] + (2.0 if landing_eve or landing_day or launch_day else 0) \
                + (1.5 if shelter else 0) + (0.5 if eva else 0) + (0.5 if r["comm"] == "blackout" else 0) + (0.8 if in_camp else 0) \
                + (1.5 if low_mood else 0) + rng.normal(0, 0.7)
            stress = float(np.clip(stress, 0, 10))

            # ---- slow states by gravity
            if zero_g:
                st["f_hr"] = relax(st["f_hr"], 1.0, 3); st["f_hrv"] = relax(st["f_hrv"], 1.0, 14); st["f_bp"] = relax(st["f_bp"], 1.0, 7)
                st["f_t"] = relax(st["f_t"], 1.0, 25); st["fluid"] = relax(st["fluid"], -1.8, 1.5); st["uca"] = relax(st["uca"], 1.42, 6)
                st["rbc"] = relax(st["rbc"], -0.12, 5); st["pv"] = relax(st["pv"], -0.16, 1.5); st["wbc"] = relax(st["wbc"], 0.15, 7)
                st["crp"] = relax(st["crp"], 0.35, 30); st["ferr"] = relax(st["ferr"], 0.35, 20)
                st["sans"] = relax(st["sans"], p["sans"] * (1.0 if ph == "outbound" else 1.1), 90)
                d0g = pd
                st["ortho"] = (0.2 * d0g / 14 if d0g <= 14 else 0.20 + 0.55 * (1 - EXP(-(d0g - 14) / 45.0)))
                st["ortho"] = min(0.92, st["ortho"] * p["ortho"])
            elif ph == "surface":
                st["f_hr"] = relax(st["f_hr"], 0.3, 7); st["f_hrv"] = relax(st["f_hrv"], 0.4, 20); st["f_bp"] = relax(st["f_bp"], 0.4, 10)
                st["f_t"] = relax(st["f_t"], 0.3, 21); st["fluid"] = relax(st["fluid"], -0.6, 3); st["uca"] = relax(st["uca"], 1.22, 20)
                st["rbc"] = relax(st["rbc"], -0.06, 40); st["pv"] = relax(st["pv"], -0.06, 2); st["wbc"] = relax(st["wbc"], 0.08, 14)
                st["crp"] = relax(st["crp"], 0.2, 30); st["ferr"] = relax(st["ferr"], 0.15, 40)
                if pd == 0: st["sans_floor"] = 0.5 * st["sans"]
                st["sans"] = relax(st["sans"], st["sans_floor"], 120)
                st["ortho"] = relax(st["ortho"], 0.35 * min(1.0, p["ortho"]), 20)
            else:                                           # Earth, 1 g
                tau = 9 if ph == "recovery" else 5
                st["f_hr"] = relax(st["f_hr"], 0.0, tau); st["f_hrv"] = relax(st["f_hrv"], 0.0, 14); st["f_bp"] = relax(st["f_bp"], 0.0, 7)
                st["f_t"] = relax(st["f_t"], 0.0, 10); st["fluid"] = relax(st["fluid"], 0.0, 2); st["uca"] = relax(st["uca"], 1.0, 20)
                st["rbc"] = relax(st["rbc"], 0.0, 40); st["pv"] = relax(st["pv"], 0.0, 1); st["wbc"] = relax(st["wbc"], 0.0, 12)
                st["crp"] = relax(st["crp"], 0.0, 9); st["ferr"] = relax(st["ferr"], 0.0, 40)
                if ph == "recovery":
                    if pd == 0: st["sans_floor"] = 0.3 * st["sans"]
                    st["sans"] = relax(st["sans"], st["sans_floor"], 60)
                    if 1 <= pd <= 3: st["ortho"] = max(0.03, 0.12 + (st["ortho"] - 0.12) * EXP(-1 / 0.5))
                    elif pd > 3: st["ortho"] = relax(st["ortho"], 0.03, 7)
            lm = (d - st["land_mars"]) if st["land_mars"] is not None and ph == "surface" else None
            le = (d - st["land_earth"]) if st["land_earth"] is not None else None

            # ---- energy, fluids, body mass (catalog energy_protein_intake, fluid_intake_hydration, body_mass)
            if zero_g:
                st["menu"] = max(st["menu"] - (1.2 if ph == "outbound" else 1.4) / 30.4, -8.0 if ph == "outbound" else -12.0)
            elif ph == "surface":
                st["menu"] = relax(st["menu"], 1.0 if pd > 60 else -2.0, 20)       # fresh greenhouse food after about sol 60 (assumed)
            else:
                st["menu"] = relax(st["menu"], 0.0, 5)
            early = {0: 0.65, 1: 0.75, 2: 0.85}.get(pd, 1.0) if ph == "outbound" else 1.0
            energy = (100 * p["e_adh"] + st["menu"]) * early * mods["energy"] * (1 - 0.12 * sms) * (0.9 if (in_camp and camp_k > 0.6) else 1.0) \
                * (0.8 if landing_day else 1.0) * (0.93 if low_mood else 1.0) + rng.normal(0, 8)
            energy = float(np.clip(energy, 25, 130))
            h["energy_pct"].append(energy)
            e7 = mean_last(h["energy_pct"], 7)
            st["tissue"] = float(np.clip(st["tissue"] + 0.0030 * (e7 / 100 - 0.95), -0.09, 0.02))
            protein = 1.45 * (energy / 100) * (1 + rng.normal(0, 0.07))
            floor_l = max(0.032 * m0, 2.5 if sex == "M" else 2.1)
            fluid = FLUID_TARGET * p["f_adh"] + mods["fluid"] + (0.6 if eva else 0) - 0.3 * sms - (0.3 if landing_day else 0) + rng.normal(0, 0.28)
            fluid = float(np.clip(fluid, 0.8, 4.5))
            urine = float(np.clip(fluid - 0.85 - (0.5 if eva else 0) + rng.normal(0, 0.18), 0.4, 3.6))
            v0 = FLUID_TARGET * p["f_adh"] - 0.85
            stone = float(np.clip(1 + 0.12 * (st["uca"] * v0 / urine - 1), 0.85, 2.43))
            mass = m0 * (1 + st["tissue"]) + st["fluid"] + rng.normal(0, 0.22)

            # ---- exercise (catalog exercise_dose) and what it protects
            no_ex = sms >= 2 or landing_day or launch_day or shelter >= 12 or (lm is not None and lm <= 1) or (le is not None and le <= 1)
            adh = 0.0 if no_ex else p["x_adh"] * mods["exercise"] * (0.6 if pain >= 4 else 1.0) * (0.78 if in_camp else 1.0) * (0.85 if low_mood else 1.0)
            ex_plan = PLAN_EX_MIN if ph != "surface" else 60.0
            ex = max(0.0, ex_plan * adh * (1 + rng.normal(0, 0.08))) if adh > 0 else 0.0
            resist = 0.0 if ared_out else 0.55 * ex * mods["resist"]
            if ared_out: ex *= 0.5
            ex_total = ex + (60 if eva else 0)
            ex_pct = float(np.clip(100 * ex_total / ex_plan, 0, 130)) if ph != "surface" else float(np.clip(100 * ex / ex_plan + (25 if eva else 0), 0, 130))
            h["exercise_pct"].append(ex_pct); h["resist_frac"].append(min(1.2, resist / (0.55 * ex_plan)))
            a7 = min(1.0, mean_last(h["exercise_pct"], 7) / 100); r7 = min(1.0, mean_last(h["resist_frac"], 7)); r28 = min(1.0, mean_last(h["resist_frac"], 28))
            if zero_g:
                if pd <= 15 and ph == "outbound":
                    st["vo2"] = relax(st["vo2"], -17.0, 5)
                else:
                    st["vo2"] = relax(st["vo2"], -5.0 - 15 * (1 - a7), 60)
                st["strength"] = relax(st["strength"], -5.0 - 20 * (1 - r7), 25)
                st["bmd"] += p["bone"] / 30.4 * (1 + 1.0 * (1 - r28))
            elif ph == "surface":
                st["vo2"] = relax(st["vo2"], -3.0 - 20 * (1 - a7), 40)
                st["strength"] = relax(st["strength"], -3.0 - 20 * (1 - r7), 30)
                st["bmd"] += p["bone"] / 30.4 * 0.4 * (1 + 1.0 * (1 - r28))         # 0.4 x the weightless rate at 0.38 g: low end of the catalog range (0.4-1.0 x, no human data)
            elif ph == "recovery":
                st["vo2"] = relax(st["vo2"], 0.0, 9); st["strength"] = relax(st["strength"], 0.0, 10)
                st["bmd"] += (100 - st["bmd"]) * (1 - 2 ** (-1 / 150.0))
            vo2 = 100 + st["vo2"] - (4 * EXP(-lm / 8.0) if lm is not None else 0) - (5 * EXP(-le / 6.0) if le is not None else 0) + rng.normal(0, 0.5)
            strength = 100 + st["strength"] + rng.normal(0, 0.6)
            bmd = st["bmd"]

            # ---- heart, blood pressure, breathing, temperature
            fever = mods["fever"]
            land_hr = (6 * EXP(-lm / 7.0) if lm is not None else 0) + (7 * EXP(-le / 9.0) if le is not None else 0)
            st["z_hr"] = 0.4 * st["z_hr"] + rng.normal(0, 1.6)
            hr = p["hr"] + 2.0 * st["f_hr"] + land_hr + 0.5 * max(0.0, debt - 4.5) + 8.5 * fever + 2.5 * sms + st["z_hr"] + (1.5 if stress > 6 else 0)
            hrv = p["rmssd"] * (1 - 0.15 * st["f_hrv"]) * (1 - 0.02 * max(0.0, debt - 4.5)) * (1 - 0.25 * (EXP(-lm / 10.0) if lm is not None else EXP(-le / 10.0) if le is not None else 0)) \
                * (0.8 if fever > 0.2 else 1.0) * float(np.exp(rng.normal(0, 0.07)))
            sysb = p["sys"] - 10 * st["f_bp"] + rng.normal(0, 4.0) + (3 if stress > 6 else 0)
            diab = p["dia"] - 5 * st["f_bp"] + rng.normal(0, 3.0)
            explo = ph in ("outbound", "surface", "return")
            spo2 = min(100.0, p["spo2"] - (1.6 if explo else 0) + mods["spo2"] + rng.normal(0, 0.45))
            rr = 14 + 3 * fever + mods["rr"] + 1.5 * co2_hi + rng.normal(0, 0.8)
            temp = p["temp"] + p["tcore_amp"] * st["f_t"] + fever + rng.normal(0, 0.07)
            # stand test (catalog orthostatic_tolerance): only under gravity
            stand = None
            if ph == "prelaunch" and pd % 7 == 0:
                stand = 11 + rng.normal(0, 2)
            elif lm is not None and (lm <= 9 or lm % 7 == 0):
                stand = 11 + 14 * p["ortho"] * EXP(-lm / 6.0) + rng.normal(0, 2)
            elif le is not None and (le <= 13 or le % 7 == 0):
                stand = 11 + 22 * p["ortho"] * EXP(-le / 5.0) + rng.normal(0, 2.5)
            # balance (catalog sensorimotor_balance_gait): tandem walk, % of pre-flight correct steps; not testable when weightless
            bal = None
            if ph == "prelaunch":
                bal = min(100.0, 100 + rng.normal(-1, 1.5))
            elif lm is not None:
                bal = min(100.0, 100 - 44 * EXP(-lm / 0.6) - 5 * EXP(-lm / 10.0) + rng.normal(0, 1.8))   # 0.8 x the Earth deficit (assumed)
            elif le is not None:
                bal = min(100.0, 100 - 55 * EXP(-le / 0.6) - 6 * EXP(-le / 10.0) + rng.normal(0, 2.0))    # Clement 2022: 39 % on landing day, about 89 % a day later
            # ---- radiation
            dose_day = e["dose_day_msv"]
            if ph != "prelaunch":
                st["dose"] += dose_day

            # ---- readiness: 100 minus what costs points today
            rhr7 = mean_last(h["hr_rest_bpm"], 7) or hr
            hrv28 = mean_last(h["hrv_rmssd_ms"], 28, 3) or hrv
            e3 = mean_last(h["energy_pct"], 3)
            cost = {
                "Sleep debt": min(20.0, 2.2 * max(0.0, debt - max(4.5, debt_usual))) + (4.0 if sleep < 5.0 else 0.0),
                "Reaction speed": min(12.0, 6.0 * max(0.0, -pvt_z - 0.5)),
                "Heart strain": min(6.0, 0.6 * max(0.0, hr - rhr7 - 2)) + (3.0 if hrv < 0.8 * hrv28 else 0.0),
                "Energy and fluids": min(8.0, 0.4 * max(0.0, 92 - e3)) + (2.0 if fluid < floor_l else 0.0),
                "Exercise shortfall": min(5.0, 0.12 * max(0.0, 90 - 100 * a7)),
                "Symptoms": min(40.0, mods["pts"] + 8 * sms + 1.5 * pain),
                "Mood and stress": min(8.0, 1.5 * max(0.0, 13 - who5) + 2.0 * max(0.0, stress - 6)),
                "Balance and standing": (min(30.0, 0.5 * (100 - bal)) if bal is not None else 0.0) + (10.0 if (stand or 0) >= 30 else 5.0 if (stand or 0) >= 20 else 0.0),
                "Cabin air": 6.0 if co2_hi >= 1 else 4.0 if co2_hi > 0 else 0.0,
                "Bone trend": 2.0 if bmd < 97.5 else 0.0,
            }
            ready = float(np.clip(100 - sum(cost.values()), 0, 100))
            if cid == base.FOCUS and d == forced["fatigue"] and not 71 <= ready <= 82:
                # scripted: the fatigue walk goes ahead "ready with limits"; hold the day in that band through the sleep-debt item
                target = min(max(ready, 71.0), 82.0)
                cost["Sleep debt"] = max(0.0, cost["Sleep debt"] + (ready - target))
                ready = target
            band = "Ready" if ready >= 85 else "Ready with limits" if ready >= 70 else "Restricted" if ready >= 50 else "Stand down"
            for item, pts in cost.items():
                if pts >= 0.5:
                    cost_rows.append(dict(day=d, crew_id=cid, item=item, points=round(pts, 1)))

            activity = ("pre-launch quarantine" if ph == "prelaunch" else "launch" if (ph == "outbound" and pd == 0) else "Mars landing" if (ph == "surface" and pd == 0)
                        else "Mars departure" if (ph == "return" and pd == 0) else "Earth landing" if (ph == "recovery" and pd == 0)
                        else "storm shelter" if shelter >= 12 else f"EVA {eva[1]:02d}" if eva else "rehabilitation" if ph == "recovery" else "work day")
            row = dict(day=d, crew_id=cid, hr_rest_bpm=hr, hrv_rmssd_ms=hrv, bp_sys_mmhg=sysb, bp_dia_mmhg=diab, spo2_pct=spo2, resp_rate_bpm=rr,
                       temp_core_c=temp, stand_dhr_bpm=stand, ortho_risk_pct=100 * st["ortho"], sleep_h=sleep, sleep_eff_pct=eff, sleep_debt_h=debt,
                       pvt_rt_ms=rt, pvt_z=pvt_z, mood_who5=who5, stress_0_10=stress, body_mass_kg=mass, energy_pct=energy, protein_g_kg=protein,
                       fluid_l=fluid, urine_l=urine, stone_risk_irr=stone, exercise_min=ex_total, exercise_pct=ex_pct, resist_min=resist,
                       vo2max_pct=vo2, leg_strength_pct=strength, bmd_hip_pct=bmd, back_pain_0_10=pain if pain >= 0.5 else 0.0, sms_grade=sms,
                       balance_pct=bal, sans_trt_um=max(0.0, st["sans"] + rng.normal(0, 0.8)), dose_day_msv=dose_day, dose_cum_msv=st["dose"],
                       readiness=ready, readiness_band=band, activity=activity, symptoms="; ".join(dict.fromkeys(symptoms)) or None)
            for k, v in row.items():
                if k not in ("day", "crew_id", "energy_pct", "exercise_pct"):
                    h[k].append(v)
            dec = dict(hr_rest_bpm=0, hrv_rmssd_ms=0, bp_sys_mmhg=0, bp_dia_mmhg=0, spo2_pct=1, resp_rate_bpm=0, temp_core_c=2, stand_dhr_bpm=0, ortho_risk_pct=0,
                       sleep_h=2, sleep_eff_pct=0, sleep_debt_h=1, pvt_rt_ms=0, pvt_z=2, mood_who5=0, stress_0_10=1, body_mass_kg=1, energy_pct=0,
                       protein_g_kg=2, fluid_l=2, urine_l=2, stone_risk_irr=2, exercise_min=0, exercise_pct=0, resist_min=0, vo2max_pct=1,
                       leg_strength_pct=1, bmd_hip_pct=2, back_pain_0_10=1, sms_grade=0, balance_pct=0, sans_trt_um=1, dose_day_msv=3, dose_cum_msv=1, readiness=0)
            body_day.append({k: (base.r_(v, dec[k]) if k in dec and v is not None else v) for k, v in row.items()})

            # ---- hours of the day: heart rate with the learned 24-hour shape, core temperature with a daily wave
            wake = max(4.0, tib - 1.0)                       # in bed from 23:00
            for hh in range(24):
                asleep = hh >= 23 or hh < wake
                act = "sleep" if asleep else "work"
                v = hr * (min(shape[hh], 1.06) if asleep else max(shape[hh], 1.2)) + rng.normal(0, 1.5)
                t = temp + 0.38 * math.cos(2 * math.pi * (hh - 17) / 24) + rng.normal(0, 0.04)
                if eva and 10 <= hh <= 13:
                    act, v, t = "EVA", hr + 0.42 * (st["hrmax"] - hr) + rng.normal(0, 4), t + 0.35
                elif shelter >= 12 and not asleep:
                    act = "shelter"
                elif hh == 17 and ex > 0 and not eva:
                    frac = min(1.0, ex / 60.0)
                    act, v, t = "exercise", v + frac * (0.62 * (st["hrmax"] - hr) - (v - hr)), t + 0.5 * frac
                elif hh == 18 and ex > 60 and not eva:
                    frac = min(1.0, (ex - 60) / 60.0)
                    act, v, t = "exercise", v + frac * (0.55 * (st["hrmax"] - hr) - (v - hr)), t + 0.3
                if landing_day or launch_day:
                    v += 8 if not asleep else 3
                body_hour.append(dict(day=d, crew_id=cid, hour=hh, hr_bpm=round(v), temp_core_c=round(t, 2), activity=act))

            # ---- labs: blood and urine panel every 28 days, and around landings (catalog rows in the variable table)
            lab_day = (ph == "prelaunch" and pd == 16) or (ph in ("outbound", "surface", "return") and d % 28 == 14) \
                or (lm == 3) or (le in (1, 7, 30))
            if d == VITD_REVIEW_DAY and st["vitd"] < 34:
                st["vitd_ss"] += 7.0                                         # Earth raises the vitamin D dose (see uplink)
                events.append(dict(day_start=d, day_end=d, scope="crew", crew_id=cid, type="countermeasure", severity="info",
                                   title="Vitamin D dose raised to 2,000 IU a day", detail="Earth instruction after the last blood panel: level in the NASA repletion band (20-34 ng/mL).", origin="rule"))
            st["vitd"] = relax(st["vitd"], st["vitd_ss"] if ph not in ("prelaunch", "recovery") else p["vitd"], 21)
            if lab_day:
                inf = mods["wbc"]
                spike = 2.5 * EXP(-le / 8.0) if le is not None else 0.0
                vals = dict(
                    hemoglobin_g_dl=p["hb"] * (1 + st["rbc"]) / (1 + st["pv"]) * (1 + rng.normal(0, 0.015)),
                    wbc_k_ul=p["wbc"] * (1 + st["wbc"]) * inf * (1 + rng.normal(0, 0.07)),
                    lymph_k_ul=p["lymph"] * (1 + rng.normal(0, 0.08)),
                    vitd_ng_ml=st["vitd"] * (1 + rng.normal(0, 0.04)),
                    ferritin_ng_ml=p["ferritin"] * (1 + st["ferr"]) * (1 + rng.normal(0, 0.08)),
                    creatinine_mg_dl=p["creat"] * (1 + 0.5 * st["strength"] / 100) * (1 + rng.normal(0, 0.05)),
                    crp_mg_l=p["crp"] * (1 + st["crp"] + spike) * mods["crp"] * float(np.exp(rng.normal(0, 0.3))),
                    glucose_mg_dl=p["glucose"] + (4 if (sex == "M" and zero_g) else 0) + rng.normal(0, 4),
                    urine_ca_mg_day=p["uca"] * st["uca"] * (1 + rng.normal(0, 0.09)))
                dl = dict(hemoglobin_g_dl=1, wbc_k_ul=1, lymph_k_ul=2, vitd_ng_ml=0, ferritin_ng_ml=0, creatinine_mg_dl=2, crp_mg_l=1, glucose_mg_dl=0, urine_ca_mg_day=0)
                for k, v in vals.items():
                    labs.append(dict(day=d, crew_id=cid, var_id=k, value=round(float(v), dl[k])))

        # ---- EVA log rows for the day (one per team)
        for team, members in base.EVA_TEAMS.items():
            if members[0] in eva_today:
                rngE = rng_of(f"eva:{d}:{team}")
                scen = next((k for k, v in forced.items() if v == d), None) if team == "A" else None
                outcome = {None: "nominal", "nominal": "nominal", "fatigue": "shortened: fatigue", "co2": "terminated: CO2 scrubber fault", "storm": "terminated: solar storm warning"}[scen]
                act = float(np.clip(rngE.normal(214, 8), 190, 235))
                evas.append(dict(day=d, sol=r["sol"], team=team, crew_ids=",".join(members), number=eva_today[members[0]][1], planned_min=216,
                                 actual_min=round(act), distance_m=round(float(np.clip(rngE.normal(2300, 450), 900, 3600)), -1),
                                 peak_hr=round(float(rngE.normal(142, 7))), dose_usv=round(e["dose_rate_usv_h"] * act / 60, 0),
                                 outcome=outcome, summary=None, scenario_id=scen))

    # ---- medical events as rows
    for cid, lst in conds.items():
        for ev in lst:
            events.append(dict(day_start=ev["start"], day_end=ev["end"], scope="crew", crew_id=cid, type="medical", severity=ev["sev"],
                               title=LAY[ev["cls"]].capitalize(), detail=f"NASA condition list: {ev['cond'].title()}. Drawn from NASA's probabilities for a 36-month planetary mission.",
                               origin="MODEL: NASA medical-conditions ranking (kb/19)"))
    events.append(dict(day_start=ARED_FAULT[0], day_end=ARED_FAULT[1], scope="mission", crew_id=None, type="device_fault", severity="warning",
                       title="Resistive exercise device out of order", detail="Scripted. No resistive training for 14 days; cycle and elastic bands only. Strength and bone projections worsen until the repair.", origin="scripted"))
    for member in base.EVA_TEAMS["A"]:
        events.append(dict(day_start=camp[0], day_end=camp[1], scope="crew", crew_id=member, type="workload", severity="info",
                           title="Long-traverse EVA campaign (KESTREL, OSPREY)", detail="Scripted. An EVA every second sol with early starts and late reports: shorter sleep, less exercise.", origin="scripted"))
    events.append(dict(day_start=LOW_MOOD[1], day_end=LOW_MOOD[2], scope="crew", crew_id=LOW_MOOD[0], type="behaviour", severity="watch",
                       title="Low mood stretch", detail="Scripted. Wellbeing score under 13 of 25 for several weeks on the way home.", origin="scripted"))
    info = dict(forced=forced, campaign=camp, eva_counts=eva_no, conditions={c: len(v) for c, v in conds.items()})
    return body_day, body_hour, labs, events, evas, cost_rows, H, info
