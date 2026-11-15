#!/usr/bin/env python3
"""Generate the full simulated Mars mission for the two apps.

    python3 -I tools/generate_mission_sim.py

Reads   data/reference/mission_reference.sqlite (real datasets), data/mission/ (the planned 2037 mission),
        kb/raw/catalog/catalog_final.json (models and thresholds).
Writes  data/sim/mission_sim.sqlite  (everything the apps and the assistant read)
        data/sim/SUMMARY.json        (counts and checks)

Same seed, same data: the run is reproducible. Design and limits: kb/25_simulation_dataset.md."""
import json, sys, time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim import base, learn, env, body, rules, story, eva   # noqa: E402

USED = {  # reference dataset -> (how it is used, what it feeds, note)
    "crater": ("replay", "dose_rate_usv_h, dose_day_msv, storm days in deep space", "Day-to-day change and storm days on the way out and back. Level comes from NASA's effective-dose rate. Our series is derived from housekeeping counters: used for variation, not for absolute dose."),
    "msl_rad": ("replay", "dose_rate_usv_h, dose_day_msv on Mars; arm unit dose rate; the storm scenario", "Curiosity's surface dose on the matching day; its hourly record of 10-13 Sep 2017 is the storm curve."),
    "omni": ("replay", "storm_level", "Proton flux at Earth on the matching day sets the storm level in deep space."),
    "noaa_sep_events": ("replay", "storm events", "Names and dates of the replayed storms."),
    "donki_sep_events": ("replay", "storm events", "Far-side event of 18 Apr 2017 behind the scripted Mars storm."),
    "iss_env": ("replay", "cabin_co2_mmhg, cabin_temp_c, cabin_rh_pct", "Hour-by-hour cabin pattern, rescaled to today's CO2 limit."),
    "mars_weather": ("replay", "out_temp_max_c, out_temp_min_c, out_pressure_pa, out_uv_index, sunrise, sunset", "Curiosity REMS, Mars year 33, matched by season."),
    "sunspots": ("level", "choice of the replay window", "Solar-cycle phase of the mission: the replay window is the same phase of the last cycle. Not copied into the simulation."),
    "mmash_24h": ("shape", "hr_bpm by hour (habitat app)", "24-hour heart-rate shape."),
    "graded_tests_lactate_tcd": ("shape", "eva.lactate_mmol", "Lactate against relative heart rate, 833 graded tests."),
    "cycle_graded_actes": ("shape", "eva.hr_bpm", "Heart rate against oxygen uptake."),
    "sleepdep_eeg_behaviour": ("shape", "pvt_rt_ms, pvt_z", "How much one night without sleep slows reactions."),
    "hdt_graded_hrv": ("check", "hrv_rmssd_ms, hr_rest_bpm", "Direction of the response to head-ward fluid shift (sanity check only)."),
    "nhanes_2013_2014_baseline": ("baseline", "crew baselines for blood pressure, heart rate, blood values, sleep", "Healthy adult ranges, ages 30 to 55."),
    "i4_cbc": ("baseline", "hemoglobin_g_dl, wbc_k_ul, lymph_k_ul", "Real astronauts' pre-flight values: check on the crew baselines."),
    "i4_cmp": ("baseline", "creatinine_mg_dl, glucose_mg_dl", "Real astronauts' pre-flight values: check on the crew baselines."),
}
EXTRA = [  # sources that are not tables in the reference database
    ("jpl_horizons", "JPL Horizons positions of Earth, Mars and the ship", "computed", "REAL astronomy", "NASA/JPL, public domain", "https://ssd.jpl.nasa.gov/horizons/", "computed",
     "day table: dates, sol, light time, link state, season", "The mission calendar: every date, sol and signal delay."),
    ("nasa_imm_ranking", "NASA ranking of medical conditions by probability (36-month planetary mission)", "table", "NASA model output", "NASA, public", "https://www.nasa.gov/ochmo/", "probability",
     "medical events (event table)", "Which illness or injury happens to whom, and how often."),
    ("indicator_catalog", "Our indicator catalog: 72 indicators with models and thresholds from NASA standards and papers", "document", "compiled, fact-checked", "our compilation of public sources", "", "model",
     "every body value: size and speed of change per mission phase; every threshold", "The model behind each simulated body value."),
    ("nasa_std_3001", "NASA-STD-3001 and OCHMO technical briefs", "document", "NASA standard", "NASA, public", "https://www.nasa.gov/ochmo/", "rule",
     "limits for cabin air, radiation, bone, fitness, suit CO2 and heat", "Where the hard limits come from."),
]


FEEDS = {  # variable ids each source feeds (for the links on the site)
    "crater": "dose_rate_usv_h,dose_day_msv,dose_cum_msv,storm_level", "msl_rad": "dose_rate_usv_h,dose_day_msv,dose_cum_msv,eva.dose_rate_usv_h,eva.eva_dose_usv",
    "omni": "storm_level", "noaa_sep_events": "storm_level", "donki_sep_events": "storm_level", "iss_env": "cabin_co2_mmhg,cabin_temp_c,cabin_rh_pct",
    "mars_weather": "out_temp_max_c,out_temp_min_c,out_pressure_pa,out_uv_index", "mmash_24h": "hr_rest_bpm", "graded_tests_lactate_tcd": "eva.lactate_mmol",
    "cycle_graded_actes": "eva.hr_bpm", "sleepdep_eeg_behaviour": "pvt_rt_ms,pvt_z", "hdt_graded_hrv": "hrv_rmssd_ms",
    "nhanes_2013_2014_baseline": "hr_rest_bpm,bp_sys_mmhg,bp_dia_mmhg,sleep_h,hemoglobin_g_dl,wbc_k_ul,lymph_k_ul,creatinine_mg_dl,glucose_mg_dl",
    "i4_cbc": "hemoglobin_g_dl,wbc_k_ul,lymph_k_ul", "i4_cmp": "creatinine_mg_dl,glucose_mg_dl", "jpl_horizons": "light_time_min,comm_state,gravity_g",
    "nasa_std_3001": "cabin_co2_mmhg,cabin_pio2_mmhg,dose_cum_msv,bmd_hip_pct,vo2max_pct,leg_strength_pct,sans_trt_um,vitd_ng_ml,eva.suit_co2_mmhg,eva.heat_kj_kg",
}


def main():
    t0 = time.time()
    con = base.new_db()
    cal = base.load_calendar()
    learned = learn.learn_all(con)
    env_day, env_hour, env_events, envd, einfo = env.build(cal, base.rng_for("env"))
    bday, bhour, labs, crew_events, evas, cost_rows, H, binfo = body.build(cal, envd, learned, einfo["storm_day0"], base.rng_for)

    # airlock cycles on EVA days pull the oxygen level down for about an hour each
    eh = {(r["day"], r["hour"]): r for r in env_hour}
    for e in evas:
        if e["outcome"] == "postponed":
            continue
        for hour, dip in ((9, 1.9), (13, 1.7)):
            eh[(e["day"], hour)]["cabin_pio2_mmhg"] = round(eh[(e["day"], hour)]["cabin_pio2_mmhg"] - dip / 2, 1)   # two teams can share a day
    for r in env_day:
        vals = [eh[(r["day"], h)]["cabin_pio2_mmhg"] for h in range(24)]
        r["cabin_pio2_mmhg"], r["cabin_pio2_min"] = round(sum(vals) / 24, 2), min(vals)
        envd[r["day"]]["cabin_pio2_mmhg"], envd[r["day"]]["cabin_pio2_min"] = r["cabin_pio2_mmhg"], r["cabin_pio2_min"]

    A = rules.assess(cal, envd, H, labs)
    ups = rules.write_all(con, cal, envd, H, A, labs, evas, binfo["forced"])
    snaps, labels = story.build(cal, H, envd, A, cost_rows, binfo["forced"], ups)
    eva.build(con, cal, H, envd, learned, einfo["storm_profile"] and env.storm_profile(base.ref()), binfo["forced"], evas, base.rng_for)

    # ---- write tables
    phase_start = {}
    for r in cal:
        phase_start.setdefault(r["phase"], r["day"])
    key = {phase_start["outbound"]: "Launch", phase_start["surface"]: "Mars landing", phase_start["return"]: "Mars departure", phase_start["recovery"]: "Earth landing"}
    key.update(labels)
    base.put(con, "day", [dict(day=r["day"], date_utc=r["date"].isoformat(), phase=r["phase"], phase_day=r["day"] - phase_start[r["phase"]], sol=r["sol"], mars_ls=r["ls"],
                               season=r["season"], gravity_g=r["g"], light_time_min=round(r["light_min"], 2), round_trip_min=round(r["round_trip_min"], 2), comm=r["comm"],
                               dist_earth_au=r["dist_earth_au"], dist_sun_au=r["dist_sun_au"], analog_date=r["analog"].isoformat(), key_label=key.get(r["day"])) for r in cal])
    base.put(con, "env_day", env_day); base.put(con, "env_hour", env_hour)
    base.put(con, "body_day", bday); base.put(con, "body_hour", bhour); base.put(con, "lab", labs)
    base.put(con, "readiness_cost", cost_rows)
    base.put(con, "event", [dict(e) for e in sorted(env_events + crew_events, key=lambda e: (e["day_start"], e["type"]))])
    base.put(con, "uplink", [dict(day=d, crew_id=c, status=u["status"], based_on_day=u["based_on_day"], age_days=u["age_days"], delay_min=u["delay_min"],
                                  headline=u["headline"], items_json=base.jdump(u["items"]), narrative=u["narrative"]) for (d, c), u in ups.items()])
    base.put(con, "snapshot", snaps)
    base.put(con, "eva", sorted(evas, key=lambda e: (e["day"], e["team"])))
    base.put(con, "variable", rules.variable_rows())
    teams = {m: t for t, ms in base.EVA_TEAMS.items() for m in ms}
    idx = {r["day"]: i for i, r in enumerate(cal)}
    crew_rows = []
    for cid, call, role, sex, age, hgt, m0 in base.CREW:
        h = H[cid]
        pre = lambda k: round(sum(x for x in h[k][:30] if x is not None) / max(1, sum(1 for x in h[k][:30] if x is not None)), 2)
        bl = {k: pre(k) for k in ("hr_rest_bpm", "hrv_rmssd_ms", "bp_sys_mmhg", "bp_dia_mmhg", "spo2_pct", "temp_core_c", "sleep_h", "pvt_rt_ms", "mood_who5", "body_mass_kg")}
        crew_rows.append(dict(crew_id=cid, call_sign=call, role=role, sex=sex, age=age, height_cm=hgt, launch_mass_kg=m0, eva_team=teams[cid],
                              baseline_json=base.jdump(bl), traits_json=base.jdump({k: v for k, v in body.PARAMS[cid].items() if k in ("bone", "sans", "e_adh", "x_adh", "ortho", "vo2")})))
    base.put(con, "crew", crew_rows)

    ref = base.ref()
    src = []
    for r in ref.execute("select dataset_id, title, kind, provenance, licence, source_url, redistribute from dataset"):
        how, used_for, note = USED.get(r["dataset_id"], ("not used", "", "Held for reference; not used in this simulation."))
        title = {"donki_sep_events": "NASA DONKI list of solar particle events", "noaa_sep_events": "NOAA list of solar proton events since 1976"}.get(r["dataset_id"], r["title"])
        src.append(dict(dataset_id=r["dataset_id"], title=title, kind=r["kind"], provenance=r["provenance"], licence=(r["licence"] or "") + ("" if r["redistribute"] else " (no redistribution)"),
                        source_url=r["source_url"], how=how, used_for=used_for, note=note, feeds=FEEDS.get(r["dataset_id"], "")))
    for x in EXTRA:
        src.append(dict(zip(["dataset_id", "title", "kind", "provenance", "licence", "source_url", "how", "used_for", "note"], x), feeds=FEEDS.get(x[0], "")))
    base.put(con, "source_use", src)
    ref.close()

    plan = json.loads(base.PLAN_JSON.read_text())
    h1 = H[base.FOCUS]
    d600 = next(r["day"] for r in cal if h1["dose_cum_msv"][idx[r["day"]]] >= 600)
    meta = {
        "name": plan["name"], "seed": base.SEED, "generator": "tools/generate_mission_sim.py",
        "launch_utc": plan["launch_utc"], "mars_arrival_utc": plan["mars_arrival_utc"], "mars_departure_utc": plan["mars_departure_utc"], "earth_return_utc": plan["earth_return_utc"],
        "landing_site": "Gale crater", "day_first": cal[0]["day"], "day_launch": phase_start["outbound"], "day_mars_landing": phase_start["surface"],
        "day_mars_departure": phase_start["return"], "day_earth_landing": phase_start["recovery"], "day_last": cal[-1]["day"],
        "focus_crew": base.FOCUS, "cabin_pressure_kpa": base.CABIN_KPA, "cabin_o2_pct": 34, "suit_pressure_kpa": base.SUIT_KPA,
        "dose_rate_transit_msv_day": base.DOSE_TRANSIT, "dose_rate_surface_msv_day": base.DOSE_SURFACE, "career_limit_msv": base.CAREER_LIMIT,
        "replay_shift_days": base.ANALOG_SHIFT_DAYS, "replay_window": f"{cal[30]['analog'].isoformat()} to {cal[30 + 923]['analog'].isoformat()}",
        "storm_shielding_assumption": f"storm dose in the cabin = {base.F_CABIN:.0%} and in the shelter = {base.F_SHELTER:.1%} of the thinly shielded measurement, times {base.Q_SPE} quality factor",
        "day_dose_600": d600, "dose_total_msv": round(h1["dose_cum_msv"][idx[phase_start["recovery"]]], 0),
        "label_legend": json.dumps({"REPLAY": "real measurement replayed on the matching day", "SIM": "stands for a sensor; model with sourced numbers",
                                    "MODEL": "an estimate, no direct sensor exists", "COMPUTED": "astronomy, exact"}),
        "disclaimer": "Simulated mission. Not a medical device. Rules decide; the AI assistant explains.",
    }
    base.put(con, "meta", [dict(key=k, value=str(v)) for k, v in meta.items()])
    con.commit()
    con.execute("VACUUM")
    con.commit()

    counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for (t,) in con.execute("select name from sqlite_master where type='table' order by 1").fetchall()}
    evasum = {r[0]: json.loads(r[1])["summary"] for r in con.execute("select scenario_id, context_json from eva_scenario")}
    con.close()
    base.publish()
    summary = dict(meta=meta, counts=counts, env=dict(cabin_windows=einfo["cabin_windows"], reference_level=einfo["ref_level"]), crew=binfo,
                   eva=evasum,
                   size_mb=round(base.OUT_DB.stat().st_size / 1e6, 1), seconds=round(time.time() - t0, 1))
    (base.OUT_DIR / "SUMMARY.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ("counts", "size_mb", "seconds")}, indent=1))
    for k, v in summary["eva"].items():
        print(k, v)


if __name__ == "__main__":
    main()
