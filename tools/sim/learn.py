"""Learn shapes and baselines from the real datasets in the reference database.

Every parameter is written to the table learned_param with its dataset, sample size and method,
so the site can show what was learned from what. Only aggregates leave the reference database:
no individual record is copied (three body datasets may not be redistributed)."""
import math
from collections import defaultdict
import numpy as np
from . import base


def _pairs(con, dataset, variables):
    """{subject: {t_label or t_rel_seconds: {variable: value}}}"""
    out = defaultdict(lambda: defaultdict(dict))
    q = f"select subject_id, t_label, t_rel_seconds, variable, value from subject_obs where dataset_id=? and variable in ({','.join('?' * len(variables))})"
    for s, tl, ts, v, val in con.execute(q, [dataset, *variables]):
        if val is None:
            continue
        out[s][tl if ts is None else ts][v] = val
    return out


def hr_day_shape(con):
    """24-hour heart-rate shape: hourly median, as a ratio to the person's lowest 3-hour mean."""
    by = defaultdict(lambda: defaultdict(list))
    for s, ts, v in con.execute("select subject_id, t_rel_seconds, value from subject_obs where dataset_id='mmash_24h' and variable='heart_rate'"):
        if v and 30 < v < 220:
            by[s][int((ts % 86400) // 3600)].append(v)
    shapes = []
    for s, hrs in by.items():
        if len(hrs) < 22:
            continue
        m = [float(np.mean(hrs[h])) if hrs.get(h) else np.nan for h in range(24)]
        m = np.array(m); ok = ~np.isnan(m)
        m[~ok] = np.interp(np.flatnonzero(~ok), np.flatnonzero(ok), m[ok])
        ext = np.concatenate([m, m[:2]])
        low = min(ext[i:i + 3].mean() for i in range(24))
        shapes.append(m / low)
    sh = np.median(np.array(shapes), axis=0)
    return dict(value=[round(float(x), 3) for x in sh], dataset="mmash_24h", n=len(shapes),
                method="hourly mean heart rate per person, divided by that person's lowest 3-hour mean; median over people",
                used_for="hr_bpm (hourly, habitat app)")


def lactate_curve(con):
    """Blood lactate against relative heart rate in graded exercise tests: L = a + b*exp(c*(x-0.6))."""
    data = _pairs(con, "graded_tests_lactate_tcd", ["blood_lactate", "heart_rate", "summary_hrmax"])
    xs, ys, n = [], [], 0
    for s, stages in data.items():
        hrmax = stages.get("summary", {}).get("summary_hrmax")
        if not hrmax or hrmax < 140:
            continue
        n += 1
        for k, d in stages.items():
            if k != "summary" and "blood_lactate" in d and "heart_rate" in d and 0.45 < d["heart_rate"] / hrmax <= 1.02:
                xs.append(d["heart_rate"] / hrmax); ys.append(d["blood_lactate"])
    xs, ys = np.array(xs), np.array(ys)
    edges = np.arange(0.5, 1.025, 0.05)
    bx, by = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (xs >= lo) & (xs < hi)
        if m.sum() >= 20:
            bx.append((lo + hi) / 2); by.append(float(np.median(ys[m])))
    bx, by = np.array(bx), np.array(by)
    best = None
    for c in np.arange(4, 40.01, 0.5):
        A = np.vstack([np.ones_like(bx), np.exp(c * (bx - 0.6))]).T
        coef, *_ = np.linalg.lstsq(A, by, rcond=None)
        sse = float(((A @ coef - by) ** 2).sum())
        if best is None or sse < best[0]:
            best = (sse, float(coef[0]), float(coef[1]), float(c))
    _, a, b, c = best
    return dict(value=dict(a=round(a, 3), b=round(b, 4), c=round(c, 2), bins=[[round(float(x), 3), round(y, 2)] for x, y in zip(bx, by)]),
                dataset="graded_tests_lactate_tcd", n=n,
                method="median lactate in 5-point bins of heart rate / maximal heart rate, then least-squares fit of a + b*exp(c*(x-0.6))",
                used_for="lactate_mmol (arm unit)")


def hr_vo2(con):
    """Heart rate against oxygen uptake on a cycle: slope and resting intercept per person."""
    data = _pairs(con, "cycle_graded_actes", ["heart_rate", "vo2_l_min", "power"])
    slopes, inter, eff = [], [], []
    for s, ts in data.items():
        pts = [(d["vo2_l_min"], d["heart_rate"], d.get("power", 0)) for d in ts.values() if "vo2_l_min" in d and "heart_rate" in d]
        pts = [p for p in pts if p[0] > 0.2 and 40 < p[1] < 210]
        if len(pts) < 30:
            continue
        v, h, p = map(np.array, zip(*pts))
        k, i = np.polyfit(v, h, 1); slopes.append(k); inter.append(i)
        m = p > 20
        if m.sum() > 20:
            eff.append(np.polyfit(p[m], v[m], 1)[0])
    return dict(value=dict(bpm_per_l_min=round(float(np.median(slopes)), 1), intercept_bpm=round(float(np.median(inter)), 1),
                           l_min_per_watt=round(float(np.median(eff)), 4)),
                dataset="cycle_graded_actes", n=len(slopes),
                method="straight-line fit of heart rate on oxygen uptake per person; median over people",
                used_for="hr_bpm during Mars walks (arm unit)")


def pvt_sleep_loss(con):
    r = {t: (n, m, sd) for t, n, m, sd in con.execute(
        "select t_label, count(*), avg(value), avg(value*value) from subject_obs where dataset_id='sleepdep_eeg_behaviour' and variable='pvt_median_rt' group by 1")}
    n0, m0, q0 = r["normal_sleep"]; n1, m1, _ = r["sleep_deprived"]
    sd0 = math.sqrt(max(q0 - m0 * m0, 0))
    ratio = m1 / m0
    # One night without sleep is about 24 - 15.84 = 8.16 h of wakefulness beyond the sustainable day (Van Dongen 2003, kb/13).
    return dict(value=dict(rested_ms=round(m0, 1), deprived_ms=round(m1, 1), ratio=round(ratio, 3),
                           slowing_per_debt_hour=round((ratio - 1) / 8.16, 4), between_person_sd_ms=round(sd0, 1)),
                dataset="sleepdep_eeg_behaviour", n=n0 + n1,
                method="mean of median reaction time, rested against one night without sleep",
                used_for="pvt_rt_ms, pvt_z")


def tilt_response(con):
    data = _pairs(con, "hdt_graded_hrv", ["heart_rate", "hrv_rmssd", "tilt_angle"])
    by = defaultdict(lambda: [[], []])
    for s, ts in data.items():
        for d in ts.values():
            if "tilt_angle" in d and "heart_rate" in d:
                by[round(d["tilt_angle"])][0].append(d["heart_rate"]); by[round(d["tilt_angle"])][1].append(d.get("hrv_rmssd", np.nan))
    tab = {a: (float(np.mean(h)), float(np.nanmean(r)), len(h)) for a, (h, r) in sorted(by.items())}
    return dict(value={str(a): dict(hr=round(h, 1), rmssd=round(r, 1), n=n) for a, (h, r, n) in tab.items()},
                dataset="hdt_graded_hrv", n=len(data), method="mean heart rate and RMSSD at each tilt angle",
                used_for="hrv_rmssd_ms and hr_rest_bpm response to head-ward fluid shift (sanity check)")


def baselines(con):
    """Healthy adult baselines: NHANES 2013-14 adults aged 30-55 (median, IQR) and Inspiration4 pre-flight means."""
    out = {}
    ages = {s: v for s, v in con.execute("select subject_id, value from subject_obs where dataset_id='nhanes_2013_2014_baseline' and variable='age'")}
    sexes = {s: v for s, v in con.execute("select subject_id, value from subject_obs where dataset_id='nhanes_2013_2014_baseline' and variable='sex_code'")}
    keep = {s for s, a in ages.items() if 30 <= a <= 55}
    codes = sorted(set(sexes.values()))
    for var in ["hemoglobin", "white_blood_cell_count", "absolute_lymphocytes", "creatinine", "glucose", "resting_pulse",
                "systolic_bp", "diastolic_bp", "sleep_hours_weeknight", "iron"]:
        rows = [(s, v) for s, v in con.execute("select subject_id, value from subject_obs where dataset_id='nhanes_2013_2014_baseline' and variable=?", [var]) if s in keep and v is not None]
        d = {}
        for code in codes:
            vals = np.array([v for s, v in rows if sexes.get(s) == code])
            if len(vals) > 30:
                d[f"sex_code_{code:g}"] = dict(p25=round(float(np.percentile(vals, 25)), 2), median=round(float(np.median(vals)), 2),
                                               p75=round(float(np.percentile(vals, 75)), 2), n=int(len(vals)))
        out[var] = d
    i4 = {}
    for ds in ("i4_cbc", "i4_cmp"):
        for var, m, n in con.execute(
                "select variable, avg(value), count(*) from subject_obs where dataset_id=? and t_rel_days<0 group by 1", [ds]):
            i4[var] = dict(preflight_mean=round(m, 2), n=n)
    return (dict(value=out, dataset="nhanes_2013_2014_baseline", n=len(keep),
                 method="median and quartiles, adults aged 30 to 55, by sex code as given in the file",
                 used_for="crew baselines: hemoglobin_g_dl, wbc_k_ul, lymph_k_ul, creatinine_mg_dl, glucose_mg_dl, hr_rest_bpm, bp_sys_mmhg, sleep_h"),
            dict(value=i4, dataset="i4_cbc, i4_cmp", n=4,
                 method="mean of all pre-flight draws of the four Inspiration4 crew",
                 used_for="check that crew baselines sit where real astronauts' pre-flight values sit"))


def learn_all(con_out):
    con = base.ref()
    nh, i4 = baselines(con)
    params = {"hr_day_shape": hr_day_shape(con), "lactate_curve": lactate_curve(con), "hr_vo2": hr_vo2(con),
              "pvt_sleep_loss": pvt_sleep_loss(con), "tilt_response": tilt_response(con), "baseline_nhanes": nh, "baseline_i4": i4}
    con.close()
    base.put(con_out, "learned_param", [dict(param_id=k, value_json=base.jdump(v["value"]), dataset_id=v["dataset"], n=v["n"],
                                             method=v["method"], used_for=v["used_for"]) for k, v in params.items()])
    return {k: v["value"] for k, v in params.items()}
