"""What we measure and what follows from it: the variable dictionary, threshold rules, tomorrow's plan,
the daily instruction from Earth and the snapshot days.

Rules decide; the AI assistant only explains. Every threshold carries a tag: NASA (a NASA standard or
bulletin), CLIN (clinical guideline), RES (research paper), INF (our informed assumption). Sources: kb/13, kb/20."""
import json
from collections import defaultdict
from . import base

ORDER = {"ok": 0, "watch": 1, "warning": 2, "critical": 3}

# var_id, scope, group, label, unit, decimals, cadence, table, column, kind, method, sensor, region, catalog_id, hrp_risk, better,
# (watch_low, watch_high, warn_low, warn_high, crit_low, crit_high), rule_text, rule_tag, why, action, how_simulated, learned_from
V = []
def var(*a):
    V.append(a)

N = None
# ---------------------------------------------------------------- environment
var("cabin_co2_mmhg", "env", "Air", "Cabin carbon dioxide", "mmHg", 1, "hourly", "env_hour", "cabin_co2_mmhg", "REPLAY", "replay", "cabin gas analyser", "air", "cabin_ppco2", "CO2 exposure (part of the environment standards)", "low",
    (N, 2.5, N, 3.0, N, 4.5), "Watch: 24-hour or 7-day mean above 2.5 mmHg. Warning: any 1-hour mean above 3.0 mmHg. Critical: 4.5 mmHg or more.", "NASA V2 6004 (3 mmHg, 1 h); RES Law 2014 (2.5 mmHg, 7 days); 4.5 band is anecdotal",
    "Carbon dioxide builds up when the air cleaner cannot keep pace. Above 2.5 mmHg headaches become more likely; thinking and sleep suffer.",
    "Check the fan in the sleep station, move to a better ventilated module, ease off exertion, drink. Painkiller only as the crew doctor advises.",
    "Hour-by-hour pattern replayed from real ISS cabin records, rescaled so a ship built to today's limit is modelled. One scripted fault (outbound days 96-98).", "iss_cabin (NASA OSDR)")
var("cabin_pio2_mmhg", "env", "Air", "Oxygen you breathe in", "mmHg", 1, "hourly", "env_hour", "cabin_pio2_mmhg", "SIM", "model", "cabin gas analyser", "air", "cabin_ppo2_pressure", "Hypoxia", "high",
    (127, N, 127, N, 122, N), "Watch: under 127 mmHg for part of the day (airlock cycles). Warning: daily mean under 127. Critical: 122 mmHg or less at any moment.", "NASA V2 6003",
    "The ship and habitat run at low pressure with 34 % oxygen, so suits can be used after a 20-minute pre-breathe. That leaves only a small oxygen margin: about 128 mmHg, like living at 1,200 m.",
    "Put on an oxygen mask at the first symptom, check blood oxygen, find the leak, bring the pressure back.",
    "Steady 128.2 mmHg (8.2 psi, 34 % oxygen) with sensor noise; dips when the airlock cycles on EVA days.", "")
var("cabin_pressure_kpa", "env", "Air", "Cabin pressure", "kPa", 1, "daily", "env_day", "cabin_pressure_kpa", "SIM", "model", "pressure sensor", "air", "cabin_ppo2_pressure", "Hypoxia; decompression sickness", "band",
    (55, 58, 34.5, 103, N, N), "Watch: more than 1.5 kPa from the 56.5 kPa set point. Warning: outside 34.5 to 103 kPa.", "NASA V2 6006; INF (set-point band)",
    "A falling pressure means a leak. Pressure also sets how long the crew must pre-breathe before a Mars walk.", "Close hatches to find the leaking module; follow the leak procedure.",
    "Constant 56.5 kPa with sensor noise.", "")
var("cabin_temp_c", "env", "Air", "Cabin temperature", "°C", 1, "hourly", "env_hour", "cabin_temp_c", "REPLAY", "replay", "air temperature sensor", "air", "cabin_temp_humidity", "Thermal comfort (environment standards)", "band",
    (N, N, 18, 27, N, N), "Warning: outside 18 to 27 °C.", "NASA TB-003", "Too warm or too cold costs sleep and concentration.", "Adjust the thermal control; check airflow at the sleep station.",
    "Replayed from real ISS cabin records.", "iss_cabin (NASA OSDR)")
var("cabin_rh_pct", "env", "Air", "Cabin humidity", "%", 0, "hourly", "env_hour", "cabin_rh_pct", "REPLAY", "replay", "humidity sensor", "air", "cabin_temp_humidity", "Thermal comfort; microbes", "band",
    (N, N, 25, 75, N, N), "Warning: outside 25 to 75 %.", "NASA TB-003", "Dry air irritates eyes and skin; damp air lets microbes grow.", "Adjust the humidity control.",
    "Replayed from real ISS cabin records.", "iss_cabin (NASA OSDR)")
var("dose_rate_usv_h", "env", "Radiation", "Radiation dose rate", "µSv/h", 0, "hourly", "env_hour", "dose_rate_usv_h", "REPLAY", "replay", "area dosimeter", "skin", "rad_dose_rate", "Radiation carcinogenesis", "low",
    (N, N, N, 200, N, 1000), "Watch: twice the usual rate of this mission phase. Warning: above 200 µSv/h. Critical: above 1,000 µSv/h, go to the shelter.", "INF (rates); NASA V1 4033 is a design limit, not an alarm",
    "Cosmic radiation is steady and cannot be felt. A jump in the rate is the first sign of a solar storm.", "Sleep and work in the best shielded place. In a storm: shelter.",
    "Level: NASA's effective-dose rates (1.4 mSv/day in deep space, 0.5 on Mars). Day-to-day change: replay of real instruments on the matching day of the last solar cycle (CRaTER in deep space, Curiosity RAD on Mars).",
    "lro_crater, msl_rad")
var("dose_day_msv", "env", "Radiation", "Radiation dose today", "mSv", 2, "daily", "env_day", "dose_day_msv", "REPLAY", "replay", "personal dosimeter", "skin", "rad_dose_rate", "Radiation carcinogenesis", "low",
    (N, N, N, N, N, N), "Shown, not alarmed. A storm day shows the dose with and without the shelter.", "INF", "Each day adds to a total that never goes down.", "Follow shelter rules in storms.",
    "As the dose rate. Storm doses use assumed shielding factors (cabin 5 %, shelter 1.5 % of the thinly shielded measurement).", "lro_crater, msl_rad")
var("storm_level", "env", "Radiation", "Solar storm level", "S-scale", 0, "daily", "env_day", "storm_level", "REPLAY", "replay", "particle detector; space-weather relay", "skin", "rad_spe_event", "Radiation (acute)", "low",
    (N, 1, N, 2, N, 4), "Watch: S1. Warning: S2 or S3, prepare the shelter and end any EVA within 2 hours. Critical: S4 or more, shelter now.", "NOAA S-scale; NASA TB-020 (EVA rule); INF",
    "A solar storm can multiply the dose rate within hours. On Mars the thin air blunts most storms; in deep space only the shelter helps.",
    "Build or enter the shelter, end the EVA, stay until the rate falls, log the dose.", "Replay of the real storm list on the matching dates, as if the ship were near Earth. One scripted storm on Mars with Curiosity's measured curve.",
    "omni proton flux, NOAA and DONKI event lists, msl_rad")
var("out_temp_max_c", "env", "Outside", "Outside air, daily high", "°C", 0, "daily", "env_day", "out_temp_max_c", "REPLAY", "replay", "weather station", "air", "", "EVA operations", "info", (N,) * 6, "Shown for EVA planning.", "",
    "Sets the heating and cooling load of the suit.", "", "Curiosity weather at Gale crater, Mars year 33, matched by season.", "rems")
var("out_temp_min_c", "env", "Outside", "Outside air, nightly low", "°C", 0, "daily", "env_day", "out_temp_min_c", "REPLAY", "replay", "weather station", "air", "", "EVA operations", "info", (N,) * 6, "Shown for EVA planning.", "",
    "Nights fall below -70 °C; EVAs end well before sunset.", "", "Curiosity weather at Gale crater, Mars year 33, matched by season.", "rems")
var("out_pressure_pa", "env", "Outside", "Outside air pressure", "Pa", 0, "daily", "env_day", "out_pressure_pa", "REPLAY", "replay", "weather station", "air", "", "EVA operations", "info", (N,) * 6, "Shown.", "",
    "Under 1 % of Earth's pressure: a suit leak is an emergency.", "", "Curiosity weather at Gale crater, Mars year 33, matched by season.", "rems")
var("out_uv_index", "env", "Outside", "Outside ultraviolet", "index 1-4", 0, "daily", "env_day", "out_uv_index", "REPLAY", "replay", "weather station", "air", "", "EVA operations", "info", (N,) * 6, "Shown.", "", "Visor and suit material exposure.", "",
    "Curiosity weather at Gale crater, Mars year 33, matched by season.", "rems")
var("light_time_min", "env", "Link to Earth", "Signal time to Earth, one way", "min", 1, "daily", "day", "light_time_min", "COMPUTED", "computed", "none (astronomy)", "link", "", "Earth-independent operations", "info", (N,) * 6,
    "Shown. A question to Earth takes twice this time, plus the time people need to answer.", "", "Decides how much the crew must settle alone.", "", "Computed from JPL Horizons positions of Earth, Mars and the ship.", "jpl_horizons")
var("comm_state", "env", "Link to Earth", "Link to Earth", "", 0, "daily", "day", "comm", "COMPUTED", "computed", "none (astronomy)", "link", "", "Earth-independent operations", "info", (N,) * 6,
    "ok, degraded (Sun within 5 degrees) or blackout (within 2 degrees).", "our rule, to verify against JPL practice", "During the blackout no instruction arrives; the crew works from standing orders.", "", "Computed from the Sun-Earth-ship angle.", "jpl_horizons")
var("gravity_g", "env", "Link to Earth", "Gravity", "g", 2, "daily", "day", "gravity_g", "COMPUTED", "computed", "none", "whole", "", "all gravity risks", "info", (N,) * 6, "0 in transit, 0.38 on Mars, 1 on Earth.", "", "The driver of bone, muscle, heart, balance and eye changes.", "", "Mission phase.", "")
# ---------------------------------------------------------------- body, daily
var("readiness", "body", "Overall", "Readiness", "of 100", 0, "daily", "body_day", "readiness", "MODEL", "model", "computed from the values below", "whole", "", "all", "high",
    (85, N, 70, N, 50, N), "100 minus what costs points today. 85 or more: ready. 70 to 84: ready with limits. 50 to 69: restricted, no EVA and no critical task. Under 50: stand down.", "INF (our scoring)",
    "One number for 'am I fit for today's work', with the reasons listed beside it.", "Read what costs points; the plan for tomorrow addresses the largest items.", "Rule-based sum, see the readiness_cost table.", "")
var("sleep_h", "body", "Sleep and mind", "Sleep last night", "h", 1, "daily", "body_day", "sleep_h", "SIM", "model", "wrist actigraph", "brain", "sleep_duration_efficiency", "Sleep loss, circadian desynchronisation and work overload", "high",
    (N, N, N, N, N, N), "Watch: under 5 h on one night. Warning: 7-day mean more than 1 h under your usual, or under 5 h. Critical: under 4 h in the 24 h before an EVA, landing or docking.", "RES Barger 2014, Jones 2022; INF",
    "Astronauts sleep about 6 hours on average. Lost sleep adds up as sleep debt and slows reactions before you feel it.", "Protect the sleep window, dim light in the evening, nap up to 30 minutes, move critical tasks.",
    "Person mean plus night-to-night noise (ISS statistics) plus events: launch, landing, storms in the shelter, bad air, illness, workload.", "nhanes (Earth baseline); catalog")
var("sleep_eff_pct", "body", "Sleep and mind", "Sleep efficiency", "%", 0, "daily", "body_day", "sleep_eff_pct", "SIM", "model", "wrist actigraph", "brain", "sleep_duration_efficiency", "Sleep loss, circadian desynchronisation and work overload", "high",
    (N,) * 6, "Watch: under 80 % on 3 nights in a row.", "RES; INF", "The share of time in bed actually asleep. It falls with noise, pain, bad air and worry.", "Check the sleep station: light, noise, airflow, temperature.",
    "About 88 % with night-to-night spread; lower on short nights, with pain and motion sickness.", "catalog (Barger 2014)")
var("sleep_debt_h", "body", "Sleep and mind", "Sleep debt", "h", 1, "daily", "body_day", "sleep_debt_h", "MODEL", "model", "computed from sleep", "brain", "alertness_pvt_b", "Sleep loss", "low",
    (N, N, N, N, N, N), "Feeds the reaction-speed rule and readiness.", "RES Van Dongen 2003", "Hours of wakefulness above the sustainable 15.8 h a day, with a slow leak of about six days.", "Extra sleep on the following nights pays it back.",
    "Leaky integrator of time awake beyond 15.84 h per day.", "")
var("pvt_z", "body", "Sleep and mind", "Reaction speed", "SD vs own usual", 1, "daily", "body_day", "pvt_z", "SIM", "learned", "3-minute reaction test on the tablet (PVT-B)", "brain", "alertness_pvt_b", "Sleep loss; cognitive decline", "high",
    (-1, N, -2, N, N, N), "Watch: 1 SD slower than your own usual. Warning: 2 SD slower, or 1 SD slower two tests in a row. Critical: 2 SD slower with under 5 h sleep before a critical task.", "RES Basner 2011; INF (SD rules)",
    "The simplest check of whether the brain is awake enough for a critical task. It drops before you notice.", "Nap, caffeine early in the shift, bright light, hand the critical task to a rested crewmate, retest.",
    "Reaction time rises with sleep debt. The size of the slowing is learned from a sleep-deprivation study (rested 318 ms, one night without sleep 356 ms).", "sleepdep_eeg_behaviour")
var("pvt_rt_ms", "body", "Sleep and mind", "Reaction time", "ms", 0, "daily", "body_day", "pvt_rt_ms", "SIM", "learned", "3-minute reaction test (PVT-B)", "brain", "alertness_pvt_b", "Sleep loss", "low",
    (N,) * 6, "See reaction speed.", "", "Raw value behind the reaction-speed score.", "", "As reaction speed.", "sleepdep_eeg_behaviour")
var("mood_who5", "body", "Sleep and mind", "Wellbeing (WHO-5)", "of 25", 0, "daily", "body_day", "mood_who5", "SIM", "model", "5-question check-in", "mood", "mood_stress_workload", "Behavioural conditions and psychiatric disorders", "high",
    (13, N, N, N, N, N), "Watch: under 13 of 25, or clearly under your usual for 3 days. Warning: 14-day mean under 13.", "CLIN (WHO-5 cut-off); INF",
    "Isolation, confinement and distance wear people down slowly. A short daily check-in catches a slide early.", "Talk to the crew doctor or a crewmate, protect sleep and exercise, lighten the schedule; Earth can arrange a private talk.",
    "Personal level plus slow day-to-day noise, pulled down by sleep debt, illness and the blackout; one scripted low stretch for one crew member.", "catalog")
var("stress_0_10", "body", "Sleep and mind", "Stress", "0-10", 1, "daily", "body_day", "stress_0_10", "SIM", "model", "self-rating", "mood", "mood_stress_workload", "Behavioural conditions; work overload", "low",
    (N, 6, N, 8, N, N), "Watch: 6 or more for 3 days. Warning: 8 or more for 3 days.", "INF", "Workload peaks and short nights show up here first.", "Cut optional tasks, add a rest block, check sleep.",
    "Baseline plus sleep debt, workload events, landings and storms.", "catalog")
var("hr_rest_bpm", "body", "Heart and lungs", "Resting heart rate", "bpm", 0, "daily", "body_day", "hr_rest_bpm", "SIM", "model", "chest strap or smart shirt, at rest", "heart", "hr_resting", "Cardiovascular adaptations", "low",
    (N, N, N, 111, 40, 131), "Watch: 10 bpm above your own 7-day level for 3 days, or 91 to 110. Warning: 111 to 130. Critical: 131 or more, or 40 or less.", "CLIN NEWS2; INF (personal baseline)",
    "Hardly changes in weightlessness. A rise of several beats for days points to fever, poor sleep, dehydration or overload.", "Measure again at rest, drink, check temperature and cabin CO2, ease exercise, protect sleep.",
    "Personal baseline, +2 bpm in flight, higher after each landing, plus fever, motion sickness and sleep debt.", "nhanes; catalog")
var("hrv_rmssd_ms", "body", "Heart and lungs", "Heart-rate variability", "ms", 0, "daily", "body_day", "hrv_rmssd_ms", "SIM", "model", "chest strap, during sleep", "heart", "hrv_lnrmssd", "Cardiovascular adaptations; sleep loss", "high",
    (N,) * 6, "Watch: 7-day mean more than 1 SD under your own 4-week level. Warning: a week under the band together with a second flag.", "INF; RES Plews 2013 (method)",
    "A sign of how well the body recovers overnight. It falls with strain, illness and after each landing.", "Lighter training day, more sleep.", "Personal baseline, about 15 % lower in flight, lower after landings and with illness.", "hdt_graded_hrv (direction); catalog")
var("bp_sys_mmhg", "body", "Heart and lungs", "Blood pressure, upper value", "mmHg", 0, "daily", "body_day", "bp_sys_mmhg", "SIM", "model", "arm cuff, morning", "heart", "bp_24h", "Cardiovascular adaptations", "band",
    (100, 130, 90, 140, N, 180), "Watch: under 100 or over 130. Warning: 90 to 99 or 140 and more on repeat. Critical: over 180, or under 90 with symptoms.", "CLIN AHA, NEWS2; INF",
    "Falls by about 10 mmHg in weightlessness. The danger is the drop on standing after landing.", "Repeat the measurement; with dizziness, sit or lie down and tell the crew doctor.", "Personal baseline, about 10 mmHg lower in flight, part of that on Mars.", "nhanes; catalog")
var("bp_dia_mmhg", "body", "Heart and lungs", "Blood pressure, lower value", "mmHg", 0, "daily", "body_day", "bp_dia_mmhg", "SIM", "model", "arm cuff, morning", "heart", "bp_24h", "Cardiovascular adaptations", "band",
    (N, N, N, 90, N, 120), "Warning: 90 or more on repeat. Critical: over 120.", "CLIN AHA", "Read together with the upper value.", "", "Personal baseline, about 5 mmHg lower in flight.", "nhanes; catalog")
var("spo2_pct", "body", "Heart and lungs", "Blood oxygen", "%", 1, "daily", "body_day", "spo2_pct", "SIM", "model", "finger or ear clip", "lungs", "spo2", "Hypoxia", "high",
    (95, N, 93, N, 91, N), "Watch: 95 % or less. Warning: 93 % or less. Critical: 91 % or less, or any drop with breathlessness or confusion.", "CLIN NEWS2; INF (exploration baseline)",
    "In the low-pressure cabin blood oxygen sits one to two points lower than on Earth, so the margin is smaller.", "Check the clip, then the cabin oxygen; mask oxygen at symptoms.", "Personal baseline minus 1.6 points in the 8.2 psi cabin; dips with airway infections.", "catalog")
var("resp_rate_bpm", "body", "Heart and lungs", "Breathing rate", "per min", 0, "daily", "body_day", "resp_rate_bpm", "SIM", "model", "smart shirt", "lungs", "resp_rate", "Medical conditions", "band",
    (11, 21, N, N, 8, 25), "Watch: 9 to 11 or 21 to 24. Critical: 8 or less, or 25 or more.", "CLIN NEWS2", "Rises with fever, infection and bad air.", "Check temperature, blood oxygen and cabin CO2.", "14 per minute plus fever and high CO2.", "catalog")
var("temp_core_c", "body", "Heart and lungs", "Core body temperature", "°C", 1, "daily", "body_day", "temp_core_c", "SIM", "model", "forehead heat-flux sensor", "whole", "core_temp", "Medical conditions; EVA heat strain", "band",
    (N, N, N, 39.1, 35.0, 40.0), "Watch: 0.5 °C above your own 4-week level, or 38.1 to 39.0. Warning: 39.1 or more at rest. Critical: 35.0 or less, or 40.0 or more.", "CLIN NEWS2, ACSM 2023; INF",
    "In weightlessness the body runs up to 1 °C warmer at rest. Fever comes on top of that, so the personal level matters.", "Rest, drink, cool; look for an infection.", "Personal baseline, rising over about 75 days in flight, part-way back on Mars; fever with infections.", "catalog (Stahn 2017)")
var("stand_dhr_bpm", "body", "Heart and lungs", "Stand test, heart-rate rise", "bpm", 0, "under gravity", "body_day", "stand_dhr_bpm", "SIM", "model", "3-minute stand test with chest strap", "heart", "orthostatic_tolerance", "Cardiovascular adaptations (orthostatic intolerance)", "low",
    (N, 20, N, 30, N, N), "Watch: 20 to 29 bpm. Warning: 30 bpm or more. Critical: near-fainting or fainting.", "CLIN Freeman 2011; RES NASA evidence report; INF",
    "After months without gravity the body cannot hold blood pressure when standing. Fainting during landing work is the risk.", "Fluid loading and compression garment before landing, stand up slowly, never alone in the first days.",
    "Only measured under gravity: daily after each landing, then weekly.", "catalog (Lee 2020)")
var("ortho_risk_pct", "body", "Heart and lungs", "Chance to fail a stand test if landing today", "%", 0, "daily", "body_day", "ortho_risk_pct", "MODEL", "model", "none: estimate", "heart", "orthostatic_tolerance", "Cardiovascular adaptations (orthostatic intolerance)", "low",
    (N, 50, N, 70, N, N), "Shown every day. Watch: 50 % or more in the 30 days before a landing. Warning: 70 % or more in the last 14 days.", "INF fit to NASA evidence (about 20 % after two weeks, about 75 % after six months, at 1 g)",
    "An estimate of how likely near-fainting would be in a 10-minute stand test on Earth today. At Mars gravity the load is smaller; nobody has measured it.", "Before landing: fluid loading, compression garment, plan the first hours seated or with a buddy.",
    "Grows with days in weightlessness (duration curve fitted to NASA data), higher for some people.", "catalog")
var("body_mass_kg", "body", "Food and body", "Body mass", "kg", 1, "daily", "body_day", "body_mass_kg", "SIM", "model", "body-mass device (spring in flight, scale on Mars)", "gut", "body_mass", "Inadequate food and nutrition", "band",
    (N,) * 6, "Watch: 3 % under your in-flight baseline (days 4 to 7, after the fluid loss). Warning: 5 % lost within a month. Critical: 10 % lost.", "CLIN AND/ASPEN; INF",
    "About 2 kg of fluid leave in the first days: that is normal. A slow loss after that means too little food.", "Eat to the energy target; log every meal.", "Fluid shift within days, tissue follows the energy balance.", "catalog")
var("energy_pct", "body", "Food and body", "Energy eaten vs need", "%", 0, "daily", "body_day", "energy_pct", "SIM", "model", "meal log (barcode scan)", "gut", "energy_protein_intake", "Inadequate food and nutrition", "high",
    (90, N, 70, N, 50, N), "Watch: 3-day mean under 90 %. Warning: 7-day mean under 70 %. Critical: 50 % or less for 5 days.", "NASA JSC-67378; CLIN; INF",
    "Crews tend to eat too little: no appetite at first, later the same menu for months. Under-eating costs muscle, bone and mood.", "Add an extra meal pouch and a snack, protein above 1.2 g per kg, pick favourite items.",
    "Personal habit with day-to-day spread, a dip in the first days, menu fatigue over months, fresh food from the greenhouse on Mars (assumed).", "catalog")
var("protein_g_kg", "body", "Food and body", "Protein", "g per kg", 2, "daily", "body_day", "protein_g_kg", "SIM", "model", "meal log", "gut", "energy_protein_intake", "Inadequate food and nutrition", "high",
    (1.2, N, 0.8, N, N, N), "Watch: under 1.2 g per kg. Warning: under 0.8 g per kg.", "NASA JSC-67378; CLIN RDA", "Protein protects muscle while it is unloaded.", "Add a protein item to two meals.", "Follows energy intake.", "catalog")
var("fluid_l", "body", "Food and body", "Fluids", "L", 1, "daily", "body_day", "fluid_l", "SIM", "model", "drink-bag log", "kidney", "fluid_intake_hydration", "Renal stone formation", "high",
    (N,) * 6, "Watch: under 32 mL per kg, or under 2.5 L (men) or 2.1 L (women). Warning: under 1.5 L two days running.", "NASA JSC-67378; INF",
    "Thirst is weak in space while bone releases calcium into the urine. Drinking enough is the main protection against kidney stones.", "Drink to the 3-litre plan; 250 mL each hour until evening.", "Mission target 2.9 L with personal habit and daily spread; more on EVA days.", "catalog")
var("urine_l", "body", "Food and body", "Urine volume", "L", 1, "daily", "body_day", "urine_l", "SIM", "model", "toilet flow meter", "kidney", "urine_output_stone_risk", "Renal stone formation", "high",
    (2.0, N, 1.5, N, N, N), "Watch: under 2.0 L. Warning: under 1.5 L. Critical: flank pain, blood in urine, or no urine for 8 to 12 hours.", "RES NASA renal stone report 2024; CLIN",
    "Low urine volume concentrates calcium: stones form. A stone on the way to Mars could end a mission.", "Drink more; report flank pain at once.", "Fluids minus losses through skin, breath and sweat.", "catalog")
var("stone_risk_irr", "body", "Food and body", "Kidney-stone risk vs pre-flight", "x", 2, "daily", "body_day", "stone_risk_irr", "MODEL", "model", "none: estimate from urine volume and calcium", "kidney", "urine_output_stone_risk", "Renal stone formation", "low",
    (N, 1.2, N, 1.5, N, N), "Watch: above 1.2 times the pre-flight risk. Warning: above 1.5.", "RES Goodenow-Messman 2022 (1.2 cut-off); INF", "Combines urine calcium and volume into a relative risk.", "Fluids to 3 L or more, less salt.",
    "Relative risk from urinary calcium and urine volume, calibrated to the published in-flight mean of 1.15.", "catalog")
var("exercise_pct", "body", "Muscle and bone", "Exercise done vs plan", "%", 0, "daily", "body_day", "exercise_pct", "SIM", "model", "exercise device log", "muscle", "exercise_dose", "Reduced fitness; bone fracture", "high",
    (N,) * 6, "Watch: 7-day mean under 80 %. Warning: under 60 % for a week, or no resistive training for 7 days. Critical: no resistive training for 14 days.", "INF",
    "Exercise is the only proven protection for bone, muscle and heart. Two hours a day are planned for it.", "Re-plan missed sessions within the week; resistive training first.", "Plan of about 600 minutes a week with personal adherence; lost on sick days, landings, storms and device faults.", "catalog")
var("exercise_min", "body", "Muscle and bone", "Exercise minutes", "min", 0, "daily", "body_day", "exercise_min", "SIM", "model", "exercise device log", "muscle", "exercise_dose", "Reduced fitness; bone fracture", "high",
    (N,) * 6, "See exercise done vs plan.", "INF", "Raw minutes behind the percentage; an EVA counts as 60 minutes of aerobic work.", "", "As exercise done vs plan.", "catalog")
var("vo2max_pct", "body", "Muscle and bone", "Aerobic fitness vs pre-flight", "%", 0, "daily", "body_day", "vo2max_pct", "MODEL", "model", "estimated from heart rate on the cycle; test monthly", "lungs", "vo2max", "Reduced cardiorespiratory and musculoskeletal fitness", "high",
    (90, N, 85, N, 80, N), "Watch: 90 % or less. Warning: 85 % or less. Critical: under 80 % (not fit for EVA).", "NASA V1 4003; INF", "Drops about 17 % in the first two weeks, then recovers partly with training. EVAs need it.", "Interval sessions on the cycle; keep the weekly plan.",
    "Early drop, slow recovery that depends on exercise done, small penalty after each landing.", "catalog (Moore 2014, Scott 2023)")
var("leg_strength_pct", "body", "Muscle and bone", "Leg strength vs pre-flight", "%", 0, "daily", "body_day", "leg_strength_pct", "MODEL", "model", "loads on the resistive device; test monthly", "muscle", "muscle_strength_lower_body", "Reduced cardiorespiratory and musculoskeletal fitness", "high",
    (90, N, 85, N, 80, N), "Watch: 90 % or less. Warning: 85 % or less. Critical: 80 % or less.", "NASA V1 4024; INF", "Legs carry no weight in transit. Strength is needed to leave the lander and to work in a suit.", "Heavy squats, deadlifts and heel raises; do not skip resistive days.",
    "Approaches a level set by the resistive training done; falls fast without it.", "catalog (Ploutz-Snyder 2018)")
var("bmd_hip_pct", "body", "Muscle and bone", "Hip bone density vs pre-flight", "%", 1, "daily", "body_day", "bmd_hip_pct", "MODEL", "model", "none in flight: estimate; scan before and after", "bone", "bmd_hip_spine_fn_est", "Bone fracture", "high",
    (97, N, N, N, 95, N), "Watch: under 97 %. Warning: on course to pass 95 % within 180 days. Critical: under 95 % (NASA limit).", "NASA V1 4027; INF (projection)",
    "Astronauts lose in a month what old people lose in a year. It cannot be felt and comes back slowly, if at all.", "Heavy resistive training six days a week, full energy intake, vitamin D, low salt.",
    "Steady monthly loss in weightlessness (personal rate inside NASA's range), 0.4 times that on Mars (assumed; no human data), faster when resistive training is missed, slow recovery on Earth.", "catalog (HRP 2024 fracture report); nhanes (reference)")
var("back_pain_0_10", "body", "Muscle and bone", "Back pain", "0-10", 0, "daily", "body_day", "back_pain_0_10", "SIM", "model", "self-rating", "bone", "back_pain_spine_length", "Medical conditions; disc damage", "low",
    (N, 1, N, 4, N, 7), "Watch: 1 to 3. Warning: 4 to 6, or pain after day 12. Critical: 7 or more, or pain with numbness or weakness.", "CLIN; INF", "The spine lengthens in weightlessness; most crew have back pain in the first days.", "Knees-to-chest stretch, exercise as tolerated, painkiller as the crew doctor advises.",
    "Starts in the first three days for most crew, fades within 12 days; milder after each gravity change.", "catalog (Kerstman 2012)")
var("sms_grade", "body", "Balance and eyes", "Motion sickness", "grade 0-3", 0, "daily", "body_day", "sms_grade", "SIM", "model", "self-rating", "balance", "space_motion_sickness", "Altered sensorimotor and vestibular function", "low",
    (N, 1, N, 2, N, 3), "Watch: grade 1. Warning: grade 2. Critical: grade 3, or vomiting in a suit.", "NASA MTB-004; INF", "Two in three get sick in the first days of weightlessness, and again after landing.", "Slow head movements, medication as planned, no EVA.",
    "Random onset after each gravity change with published odds; fades within three days.", "catalog (Davis 1988)")
var("balance_pct", "body", "Balance and eyes", "Balance, heel-to-toe walk", "% of pre-flight", 0, "under gravity", "body_day", "balance_pct", "SIM", "model", "tandem-walk test with motion sensors", "balance", "sensorimotor_balance_gait", "Altered sensorimotor and vestibular function", "high",
    (80, N, 50, N, 20, N), "Watch: under 80 %. Warning: under 50 %. Critical: cannot stand unaided.", "RES Clement 2022; INF (cut-offs)", "The balance organ re-learns gravity after landing. On the first day walking a line fails for most.", "No ladder, no EVA; a buddy within reach; test again each day.",
    "Not testable in weightlessness. After each landing a deficit that recovers within days (Mars: 0.8 times the Earth deficit, assumed).", "catalog (Clement 2022); balance_hbedb (healthy reference)")
var("sans_trt_um", "body", "Balance and eyes", "Optic disc swelling", "µm", 0, "daily", "body_day", "sans_trt_um", "MODEL", "model", "eye scan (OCT) monthly; estimate between scans", "eyes", "sans_vision", "Spaceflight Associated Neuro-ocular Syndrome (SANS)", "low",
    (N, 15, N, 19.4, N, 55), "Watch: 15 µm or more. Warning: above 19.4 µm (earliest sign). Critical: 55 µm or more.", "NASA MTB-001; INF (watch level)", "Fluid moves to the head and presses on the back of the eye. Seven in ten long-stay crew show signs.", "Report any change in vision at once; eye scan weekly; Earth reviews the images.",
    "Rises over months in weightlessness to a personal level, falls part-way on Mars (assumed), rises again on the way home.", "catalog (Macias 2020); hdt_ocular_mri (direction)")
var("dose_cum_msv", "body", "Radiation", "Radiation dose this mission", "mSv", 0, "daily", "body_day", "dose_cum_msv", "MODEL", "replay", "personal dosimeter, converted to effective dose", "skin", "rad_cumulative_dose", "Radiation carcinogenesis", "low",
    (N, 300, N, 480, N, 600), "Watch from 300 mSv (half the career limit), warning from 480 mSv, critical at 600 mSv. The mission total (about 790 mSv) was known to pass the limit before launch: it is shown, not alarmed.", "NASA V1 4030; INF (staging)",
    "Cosmic radiation raises the lifetime cancer risk. NASA's career limit is 600 mSv; this mission passes it on the way home.", "Keep every avoidable dose low: shelter in storms, sleep in the best shielded place.", "Sum of the daily doses.", "lro_crater, msl_rad")
# ---------------------------------------------------------------- body, labs
LAB = [
    ("hemoglobin_g_dl", "Hemoglobin", "g/dL", 1, "blood", "hemoglobin_space_anemia", "Medical conditions (space anemia)", "high", "Watch: under 12.0 (women) or 13.0 (men). Warning: under 11.0. Critical: under 8.0.", "CLIN WHO",
     "The body breaks down more red cells in space. It hides while blood is concentrated and shows after landing, when the fluid returns.", "Iron-aware diet; no hard exertion with dizziness after landing.", "Red-cell mass falls about 12 %, plasma volume about 16 %: the measured value rises in flight and drops after each landing."),
    ("wbc_k_ul", "White blood cells", "10³/µL", 1, "blood", "immune_leukocytes", "Altered immune response", "band", "Watch: under 3.8, or 30 % under your baseline. Warning: under 3.0 or above 15.", "CLIN lab range, CTCAE; INF",
     "The immune system is shifted in flight; old viruses can wake up.", "Report rashes, sores and fevers; hygiene.", "About 15 % higher in flight; higher with infections."),
    ("lymph_k_ul", "Lymphocytes", "10³/µL", 2, "blood", "immune_leukocytes", "Altered immune response", "high", "Watch: under 0.85. Warning: under 0.8. Critical: under 0.5.", "CLIN CTCAE", "Low counts mean weaker defence, also after high radiation doses.", "As for white cells.", "Around the personal baseline."),
    ("vitd_ng_ml", "Vitamin D", "ng/mL", 0, "blood", "vitamin_d_25oh", "Bone fracture; inadequate nutrition", "high", "Watch: under 35. Warning: 20 to 34 (NASA repletion band). Critical: under 20.", "NASA MTB-013",
     "No sunlight on the skin for years: vitamin D comes only from tablets. Bone needs it.", "Take the supplement daily; Earth sets the dose.", "Drifts toward the level the supplement dose supports; Earth raises the dose once."),
    ("ferritin_ng_ml", "Iron stores (ferritin)", "ng/mL", 0, "blood", "iron_ferritin", "Inadequate food and nutrition", "band", "Warning: above 200 (men) or 150 (women). Critical: above 500 or under 15.", "CLIN WHO 2020",
     "Iron stores rise in flight; too much iron may speed bone loss.", "Avoid iron-fortified items when high.", "Rises about a third in flight. Direction is solid, the size is our assumption."),
    ("creatinine_mg_dl", "Creatinine (kidney)", "mg/dL", 2, "kidney", "kidney_function_egfr", "Renal stone formation; medical conditions", "low", "Watch: 0.2 above baseline. Warning: 0.3 above baseline within 48 hours.", "CLIN KDIGO; INF",
     "A check that the kidneys clear the blood, for example after dehydration or a stone.", "Fluids; tell the crew doctor.", "Around the personal baseline, slightly lower with muscle loss."),
    ("crp_mg_l", "Inflammation (CRP)", "mg/L", 1, "blood", "inflammation_crp_il6", "Altered immune response", "low", "Watch: above 3. Warning: above 10.", "CLIN AHA/CDC", "Shows infection or tissue stress; spikes after landing.", "Look for the cause: infection, injury, overload.", "Slightly raised in flight; high with infections and after Earth landing."),
    ("glucose_mg_dl", "Fasting blood sugar", "mg/dL", 0, "blood", "glucose_insulin_resistance", "Inadequate nutrition", "band", "Watch: 100 to 125. Warning: 126 or more, or under 70. Critical: under 54.", "CLIN ADA", "Inactive muscle handles sugar worse.", "Keep the exercise plan.", "Personal baseline, a few points higher in flight for men."),
    ("urine_ca_mg_day", "Calcium in urine", "mg/day", 0, "kidney", "bone_turnover_urine_ca_markers", "Bone fracture; renal stone formation", "low", "Watch: above 190, or 30 % above baseline. Warning: above 300 (men) or 250 (women).", "RES NASA renal stone report; CLIN",
     "Bone that breaks down leaves through the urine: the earliest sign of bone loss, and the raw material of kidney stones.", "Resistive training, fluids, low salt.", "About 40 % above baseline in flight, 20 % on Mars."),
]
for (vid, label, unit, dec, region, cat, risk, better, rule, tag, why, action, how) in LAB:
    var(vid, "lab", "Blood and urine", label, unit, dec, "every 28 days", "lab", vid, "SIM", "model", "on-board blood and urine analyser", region, cat, risk, better, (N,) * 6, rule, tag, why, action,
        how, "i4_cbc, i4_cmp (astronaut pre-flight values); nhanes (healthy ranges)")
# ---------------------------------------------------------------- arm unit, every second
EVA_V = [
    ("stay_min", "You can stay", "min", 0, "MODEL", "computed", "whole", "The shortest resource minus the walk back and a 30-minute reserve.", "INF", "One number answers the only question that matters outside.", "Rule: smallest time left of oxygen, battery, cooling water, CO2 scrubber, daylight, stamina and any coming event."),
    ("hr_bpm", "Heart rate", "bpm", 0, "SIM", "learned", "heart", "Caution: above 140 bpm for 2 minutes.", "NASA V2 11011 (impairment cue)", "Shows how hard the body works in the suit.", "Follows the work rate; slope learned from cycle tests (52 bpm per litre of oxygen a minute), plus heat and day-form."),
    ("core_c", "Core temperature", "°C", 1, "SIM", "model", "whole", "Caution: 0.6 °C above the value before the EVA. Return: 39.0 °C. Emergency: 39.5 °C.", "NASA V2 11011; INF", "A suit is a sealed bag: heat that the cooling does not remove stays in the body.", "Heat balance: work rate minus what the cooling garment removes."),
    ("heat_kj_kg", "Stored heat", "kJ/kg", 1, "MODEL", "model", "whole", "Caution: 2.4 kJ/kg. Emergency: 3.0 kJ/kg (NASA limit).", "NASA V2 11011; INF (80 %)", "NASA's limit for heat stored in the body during an EVA.", "3.5 kJ/kg per °C of core rise."),
    ("met_w", "Work rate", "W", 0, "MODEL", "model", "muscle", "Shown.", "", "How much energy the body burns: walking about 300 W, heavy work 500 W.", "Scripted per task with random variation."),
    ("lactate_mmol", "Lactate", "mmol/L", 1, "MODEL", "learned", "muscle", "Caution: 4 mmol/L or more.", "INF", "Lactate rises when muscles work harder than oxygen supply allows: a sign that the pace cannot be held.", "Curve of lactate against relative heart rate learned from 833 graded exercise tests, shifted for an unfit day."),
    ("stamina_pct", "Stamina left", "%", 0, "MODEL", "model", "muscle", "Caution: under 35 %. Return: under 20 %.", "INF", "An estimate of the energy reserve for the walk back.", "Falls with work done and faster above the sustainable pace; scaled by the day's readiness."),
    ("balance_score", "Balance", "of 100", 0, "MODEL", "model", "balance", "Caution: under 65.", "INF", "A fall in a suit can damage the suit. Balance worsens with fatigue and in the first sols after landing.", "The day's balance test minus fatigue."),
    ("faint_risk_pct", "Chance to faint", "%", 0, "MODEL", "model", "heart", "Caution: 10 % or more. Return: 20 % or more.", "INF", "Heat, low fluid and a deconditioned heart together can make a crew member faint.", "From heat stored, heart-rate reserve used, fluid deficit and days since landing."),
    ("suit_p_kpa", "Suit pressure", "kPa", 1, "SIM", "model", "air", "Emergency: under 27 kPa.", "INF", "The suit holds 29.6 kPa of oxygen.", "Constant with sensor noise."),
    ("suit_o2_pct", "Oxygen tank", "%", 0, "SIM", "model", "air", "Feeds the stay time.", "", "Oxygen use follows the work rate.", "Tank for 8 hours at average work."),
    ("suit_co2_mmhg", "CO2 in the helmet", "mmHg", 1, "SIM", "model", "air", "Caution: above 8 mmHg, or rising 0.2 mmHg a minute for 3 minutes. Return: on course for 20 mmHg before the airlock. Limit: 20 mmHg for at most 1 hour.", "NASA V2 11040 (20 mmHg contingency); INF", "CO2 the scrubber fails to remove is breathed in again: headache, then confusion.", "Rises with work rate; a scrubber fault adds a steady climb."),
    ("suit_temp_c", "Suit temperature", "°C", 1, "SIM", "model", "air", "Shown.", "", "Comfort and cooling state.", "Follows work rate and cooling level."),
    ("battery_pct", "Battery", "%", 0, "SIM", "model", "air", "Feeds the stay time.", "", "Runs fans, pump, radio and this display.", "8.5 hours nominal."),
    ("water_pct", "Cooling water", "%", 0, "SIM", "model", "air", "Feeds the stay time.", "", "Water carries body heat away.", "Used faster at high cooling levels."),
    ("scrubber_pct", "CO2 scrubber", "%", 0, "SIM", "model", "air", "Feeds the stay time.", "", "Capacity left to remove CO2.", "Used with the CO2 produced."),
    ("dose_rate_usv_h", "Dose rate outside", "µSv/h", 0, "REPLAY", "replay", "skin", "Caution: twice the usual surface rate, or a storm warning. Return on a storm warning.", "NASA TB-020; INF", "Outside there is only the suit between the crew and the sky.", "Curiosity's surface rate; the storm scenario replays its record of 10-13 Sep 2017."),
    ("eva_dose_usv", "Dose this EVA", "µSv", 0, "MODEL", "replay", "skin", "Shown.", "", "Adds to the mission total.", "Sum of the dose rate."),
    ("dist_m", "Walk back to the airlock", "m", 0, "SIM", "model", "whole", "Feeds the stay time.", "", "Distance along the route home.", "Scripted route."),
]
for (vid, label, unit, dec, kind, method, region, rule, tag, why, how) in EVA_V:
    var("eva." + vid, "eva", "Arm unit", label, unit, dec, "every second", "eva_sample", vid, kind, method, "suit sensor" if kind == "SIM" else "estimate", region,
        {"core_c": "eva_heat_strain", "heat_kj_kg": "eva_heat_strain", "suit_co2_mmhg": "eva_heat_strain"}.get(vid, ""), "EVA operations", "info", (N,) * 6, rule, tag, why, "",
        how, {"hr_bpm": "cycle_graded_actes", "lactate_mmol": "graded_tests_lactate_tcd", "dose_rate_usv_h": "msl_rad", "eva_dose_usv": "msl_rad"}.get(vid, ""))


def variable_rows():
    cols = ["var_id", "scope", "grp", "label", "unit", "decimals", "cadence", "table_name", "column_name", "kind", "method", "sensor", "region",
            "catalog_id", "hrp_risk", "better"]
    out = []
    for i, a in enumerate(V):
        d = dict(zip(cols, a[:16]))
        d.update(dict(zip(["watch_low", "watch_high", "warn_low", "warn_high", "crit_low", "crit_high"], a[16])))
        d.update(rule_text=a[17], rule_tag=a[18], why=a[19], action=a[20], how_simulated=a[21], learned_from=a[22], sort=i)
        out.append(d)
    return out


LABEL = {a[0]: a[3] for a in V}
ACTION = {a[0]: a[20] for a in V}


def _m(xs, i, n, skip=0):
    v = [x for x in xs[max(0, i - n - skip + 1): i - skip + 1] if x is not None]
    return sum(v) / len(v) if v else None


def assess(cal, envd, H, labs):
    """Apply the rules to every person and day. Returns {(day, crew_id): {var_id: (status, value, reason)}} ('ENV' for the environment)."""
    A = defaultdict(dict)
    idx = {r["day"]: i for i, r in enumerate(cal)}
    sexes = {c[0]: c[3] for c in base.CREW}
    m0 = {c[0]: c[6] for c in base.CREW}
    co2 = [envd[r["day"]]["cabin_co2_mmhg"] for r in cal]
    rate = [envd[r["day"]]["dose_rate_usv_h"] for r in cal]
    idx_launch = idx[0]
    for i, r in enumerate(cal):
        d, e, ph = r["day"], envd[r["day"]], r["phase"]
        a = A[(d, "ENV")]
        flight = ph in ("outbound", "surface", "return")
        if flight:
            c7 = _m(co2, i, 7)
            if e["cabin_co2_max1h"] >= 4.5: a["cabin_co2_mmhg"] = ("critical", e["cabin_co2_max1h"], f"1-hour peak {e['cabin_co2_max1h']:.1f} mmHg, limit 3.0")
            elif e["cabin_co2_max1h"] > 3.0: a["cabin_co2_mmhg"] = ("warning", e["cabin_co2_max1h"], f"1-hour peak {e['cabin_co2_max1h']:.1f} mmHg, over the 3.0 limit")
            elif e["cabin_co2_mmhg"] > 2.5 or c7 > 2.5: a["cabin_co2_mmhg"] = ("watch", e["cabin_co2_mmhg"], f"24-hour mean {e['cabin_co2_mmhg']:.1f} mmHg, 7-day mean {c7:.1f}")
            if e["cabin_pio2_min"] < 122: a["cabin_pio2_mmhg"] = ("critical", e["cabin_pio2_min"], f"low point {e['cabin_pio2_min']:.0f} mmHg, under the 122 floor")
            elif e["cabin_pio2_mmhg"] < 127: a["cabin_pio2_mmhg"] = ("warning", e["cabin_pio2_mmhg"], f"daily mean {e['cabin_pio2_mmhg']:.0f} mmHg, under 127")
            elif e["cabin_pio2_min"] < 127: a["cabin_pio2_mmhg"] = ("watch", e["cabin_pio2_min"], f"{e['cabin_pio2_min']:.0f} mmHg for about an hour during the airlock cycle")
            if not 18 <= e["cabin_temp_c"] <= 27: a["cabin_temp_c"] = ("warning", e["cabin_temp_c"], f"{e['cabin_temp_c']:.1f} °C, outside 18 to 27")
            if not 25 <= e["cabin_rh_pct"] <= 75: a["cabin_rh_pct"] = ("warning", e["cabin_rh_pct"], f"{e['cabin_rh_pct']:.0f} %, outside 25 to 75")
            lvl = e["storm_level"]
            if lvl >= 4: a["storm_level"] = ("critical", lvl, f"storm level S{lvl}: shelter now")
            elif lvl >= 2: a["storm_level"] = ("warning", lvl, f"storm level S{lvl}: shelter, no EVA")
            elif lvl == 1: a["storm_level"] = ("watch", lvl, "storm level S1: minor, watch the dose rate")
            same = [rate[k] for k in range(max(0, i - 30), i) if cal[k]["phase"] == ph]
            usual = sum(same) / len(same) if len(same) >= 3 else None
            if e["dose_rate_usv_h"] > 1000: a["dose_rate_usv_h"] = ("critical", e["dose_rate_usv_h"], f"{e['dose_rate_usv_h']:.0f} µSv/h")
            elif e["dose_rate_usv_h"] > 200: a["dose_rate_usv_h"] = ("warning", e["dose_rate_usv_h"], f"{e['dose_rate_usv_h']:.0f} µSv/h" + (f", usual {usual:.0f}" if usual else ""))
            elif usual and e["dose_rate_usv_h"] > 2 * usual: a["dose_rate_usv_h"] = ("watch", e["dose_rate_usv_h"], f"{e['dose_rate_usv_h']:.0f} µSv/h, more than twice the usual {usual:.0f}")
        for cid in H:
            h, a = H[cid], A[(d, cid)]
            g = lambda k: h[k][i]
            def put(v, status, value, reason):
                if status != "ok": a[v] = (status, value, reason)
            # sleep
            s7, s28 = _m(h["sleep_h"], i, 7), _m(h["sleep_h"], i, 28, 7) or _m(h["sleep_h"], i, 7)
            critical_task = (ph == "surface" and "EVA" in g("activity")) or g("activity") in ("Mars landing", "Earth landing", "Mars departure")
            if g("sleep_h") < 4 and critical_task: put("sleep_h", "critical", g("sleep_h"), f"{g('sleep_h'):.1f} h before a critical task")
            elif s7 < s28 - 1 or s7 < 5.0: put("sleep_h", "warning", s7, f"7-day mean {s7:.1f} h, {s28 - s7:.1f} h under your usual {s28:.1f} h")
            elif g("sleep_h") < 5: put("sleep_h", "watch", g("sleep_h"), f"{g('sleep_h'):.1f} h last night")
            # reaction
            z, zp = g("pvt_z"), (h["pvt_z"][i - 1] if i else 0)
            if z <= -2 and g("sleep_h") < 5 and critical_task: put("pvt_z", "critical", z, f"{-z:.1f} SD slower with {g('sleep_h'):.1f} h sleep before a critical task")
            elif z <= -2 or (z <= -1 and zp <= -1): put("pvt_z", "warning", z, f"{-z:.1f} SD slower than your usual" + (", second test in a row" if z > -2 else ""))
            elif z <= -1: put("pvt_z", "watch", z, f"{-z:.1f} SD slower than your usual")
            # mood, stress
            w14, w3 = _m(h["mood_who5"], i, 14), _m(h["mood_who5"], i, 3)
            if w14 < 13: put("mood_who5", "warning", w14, f"14-day mean {w14:.0f} of 25")
            elif w3 < 13: put("mood_who5", "watch", g("mood_who5"), f"3-day mean {w3:.0f} of 25, under 13")
            st3 = min(h["stress_0_10"][max(0, i - 2): i + 1])
            if st3 >= 8: put("stress_0_10", "warning", g("stress_0_10"), "8 or more for 3 days")
            elif st3 >= 6: put("stress_0_10", "watch", g("stress_0_10"), "6 or more for 3 days")
            # heart
            hr, hr7 = g("hr_rest_bpm"), _m(h["hr_rest_bpm"], i, 7, 3)
            up3 = hr7 is not None and min(h["hr_rest_bpm"][max(0, i - 2): i + 1]) >= hr7 + 10
            if hr >= 131 or hr <= 40: put("hr_rest_bpm", "critical", hr, f"{hr:.0f} bpm at rest")
            elif hr >= 111: put("hr_rest_bpm", "warning", hr, f"{hr:.0f} bpm at rest")
            elif hr >= 91 or up3: put("hr_rest_bpm", "watch", hr, f"{hr:.0f} bpm, {hr - hr7:.0f} above your level for 3 days" if up3 else f"{hr:.0f} bpm at rest")
            v7, v28 = _m(h["hrv_rmssd_ms"], i, 7), _m(h["hrv_rmssd_ms"], i, 28, 7)
            if v28 and v7 < 0.85 * v28: put("hrv_rmssd_ms", "watch", v7, f"7-day mean {v7:.0f} ms, usual {v28:.0f} ms")
            sy = g("bp_sys_mmhg")
            if sy > 180: put("bp_sys_mmhg", "critical", sy, f"{sy:.0f} mmHg")
            elif sy >= 140 or sy < 90: put("bp_sys_mmhg", "warning", sy, f"{sy:.0f} mmHg, repeat the measurement")
            elif sy > 130: put("bp_sys_mmhg", "watch", sy, f"{sy:.0f} mmHg")
            sp = g("spo2_pct")
            put("spo2_pct", "critical" if sp <= 91 else "warning" if sp <= 93 else "watch" if sp <= 95 else "ok", sp, f"{sp:.1f} %")
            rr = g("resp_rate_bpm")
            put("resp_rate_bpm", "critical" if (rr >= 25 or rr <= 8) else "watch" if (rr >= 21 or rr <= 11) else "ok", rr, f"{rr:.0f} breaths a minute")
            t, t28 = g("temp_core_c"), _m(h["temp_core_c"], i, 28, 2) or g("temp_core_c")
            if t >= 40 or t <= 35: put("temp_core_c", "critical", t, f"{t:.1f} °C")
            elif t >= 39.1: put("temp_core_c", "warning", t, f"{t:.1f} °C at rest")
            elif t >= 38.1 or t > t28 + 0.5: put("temp_core_c", "watch", t, f"{t:.1f} °C, {t - t28:.1f} above your level")
            sd = g("stand_dhr_bpm")
            if sd is not None:
                put("stand_dhr_bpm", "warning" if sd >= 30 else "watch" if sd >= 20 else "ok", sd, f"heart rate rises {sd:.0f} bpm on standing")
            orr = g("ortho_risk_pct")
            to_landing = min([x for x in (idx_day(cal, "surface") - d, idx_day(cal, "recovery") - d) if x >= 0] or [999])
            if ph in ("outbound", "return"):
                when = "landing tomorrow" if to_landing == 1 else f"landing in {to_landing} days"
                if orr >= 70 and to_landing <= 14: put("ortho_risk_pct", "warning", orr, f"{orr:.0f} % chance to fail a stand test at Earth gravity; {when}")
                elif orr >= 50 and to_landing <= 30: put("ortho_risk_pct", "watch", orr, f"{orr:.0f} % chance to fail a stand test at Earth gravity; {when}")
            # food, fluids
            bm, e3, e7 = g("body_mass_kg"), _m(h["energy_pct"], i, 3), _m(h["energy_pct"], i, 7)
            bm30 = h["body_mass_kg"][i - 30] if i >= 30 else bm
            ref_mass = _m(h["body_mass_kg"], idx_launch + 7, 4) if i > idx_launch + 7 else m0[cid]      # in-flight baseline, days 4 to 7: the fluid loss is not counted
            loss = 100 * (1 - _m(h["body_mass_kg"], i, 5) / ref_mass)
            if flight or ph == "recovery":
                if loss >= 10: put("body_mass_kg", "critical", bm, f"{loss:.0f} % under your in-flight baseline")
                elif _m(h["body_mass_kg"], i, 3) < 0.95 * bm30: put("body_mass_kg", "warning", bm, "5 % lost within a month")
                elif loss >= 3: put("body_mass_kg", "watch", bm, f"{loss:.1f} % under your in-flight baseline")
            if max(h["energy_pct"][max(0, i - 4): i + 1]) <= 50 and i >= 4: put("energy_pct", "critical", g("energy_pct"), "50 % or less for 5 days")
            elif e7 < 70: put("energy_pct", "warning", e7, f"7-day mean {e7:.0f} % of need")
            elif e3 < 90: put("energy_pct", "watch", e3, f"3-day mean {e3:.0f} % of need")
            pr = _m(h["protein_g_kg"], i, 3)
            put("protein_g_kg", "warning" if pr < 0.8 else "watch" if pr < 1.2 else "ok", pr, f"3-day mean {pr:.2f} g per kg")
            fl, floor = g("fluid_l"), max(0.032 * m0[cid], 2.5 if sexes[cid] == "M" else 2.1)
            if i and fl < 1.5 and h["fluid_l"][i - 1] < 1.5: put("fluid_l", "warning", fl, "under 1.5 L two days running")
            elif _m(h["fluid_l"], i, 2) < floor: put("fluid_l", "watch", fl, f"2-day mean {_m(h['fluid_l'], i, 2):.1f} L, your floor is {floor:.1f} L")
            u2 = _m(h["urine_l"], i, 2)
            put("urine_l", "warning" if u2 < 1.5 else "watch" if u2 < 2.0 and g("stone_risk_irr") > 1.1 else "ok", u2, f"2-day mean {u2:.1f} L")
            irr = _m(h["stone_risk_irr"], i, 3)
            put("stone_risk_irr", "warning" if irr > 1.5 else "watch" if irr > 1.2 else "ok", irr, f"{irr:.2f} times the pre-flight risk (3-day mean)")
            # exercise and fitness
            x7 = _m(h["exercise_pct"], i, 7)
            nores = 0
            for k in range(i, max(-1, i - 20), -1):
                if h["resist_min"][k] > 5: break
                nores += 1
            if flight:
                if nores >= 14: put("exercise_pct", "critical", x7, f"no resistive training for {nores} days")
                elif x7 < 60 or nores > 7: put("exercise_pct", "warning", x7, f"7-day mean {x7:.0f} % of plan" + (f", no resistive training for {nores} days" if nores > 7 else ""))
                elif x7 < 80: put("exercise_pct", "watch", x7, f"7-day mean {x7:.0f} % of plan")
            vo, ls, bd = _m(h["vo2max_pct"], i, 5), _m(h["leg_strength_pct"], i, 5), g("bmd_hip_pct")
            put("vo2max_pct", "critical" if vo < 80 else "warning" if vo <= 85 else "watch" if vo <= 90 else "ok", vo, f"{vo:.0f} % of pre-flight")
            put("leg_strength_pct", "critical" if ls <= 80 else "warning" if ls <= 85 else "watch" if ls <= 90 else "ok", ls, f"{ls:.0f} % of pre-flight")
            slope = (bd - h["bmd_hip_pct"][i - 30]) / 30 if i >= 30 else 0.0
            proj = bd + slope * 180
            if ph != "prelaunch":
                if bd < 95: put("bmd_hip_pct", "critical", bd, f"{bd:.1f} % of pre-flight, under the NASA limit of 95 %")
                elif proj < 95 and ph != "recovery": put("bmd_hip_pct", "warning", bd, f"{bd:.1f} %, on course for {proj:.1f} % in 180 days")
                elif bd < 97: put("bmd_hip_pct", "watch", bd, f"{bd:.1f} % of pre-flight, losing {-slope * 30.4:.2f} % a month")
            bp = g("back_pain_0_10")
            put("back_pain_0_10", "critical" if bp >= 7 else "warning" if bp >= 4 else "watch" if bp >= 1 else "ok", bp, f"pain {bp:.0f} of 10")
            sg = g("sms_grade")
            put("sms_grade", "critical" if sg >= 3 else "warning" if sg >= 2 else "watch" if sg >= 1 else "ok", sg, f"grade {sg:.0f}")
            bl = g("balance_pct")
            if bl is not None and ph != "prelaunch":
                put("balance_pct", "critical" if bl < 20 else "warning" if bl < 50 else "watch" if bl < 80 else "ok", bl, f"{bl:.0f} % of pre-flight steps")
            sn = _m(h["sans_trt_um"], i, 7)
            put("sans_trt_um", "critical" if sn >= 55 else "warning" if sn > 19.4 else "watch" if sn >= 15 else "ok", sn, f"+{sn:.0f} µm" + (", past the earliest-sign level of 19.4" if sn > 19.4 else ""))
            dc = g("dose_cum_msv")
            put("dose_cum_msv", "critical" if dc >= 600 else "warning" if dc >= 480 else "watch" if dc >= 300 else "ok", dc, f"{dc:.0f} mSv of the 600 mSv career limit")
            rd = g("readiness")
            put("readiness", "critical" if rd < 50 else "warning" if rd < 70 else "watch" if rd < 85 else "ok", rd, f"{rd:.0f} of 100: {g('readiness_band').lower()}")
    # labs: the latest panel stays valid until the next one
    by = defaultdict(lambda: defaultdict(list))
    for l in labs:
        by[l["crew_id"]][l["var_id"]].append((l["day"], l["value"]))
    for cid, vs in by.items():
        for vid, seq in vs.items():
            seq.sort()
            b0 = seq[0][1]
            for k, (d0, val) in enumerate(seq):
                d1 = seq[k + 1][0] if k + 1 < len(seq) else cal[-1]["day"] + 1
                st = lab_status(vid, val, b0, sexes[cid])
                if st[0] != "ok":
                    for d in range(d0, d1):
                        A[(d, cid)][vid] = (st[0], val, st[1] + (f" (panel of day {d0})" if d > d0 else ""))
    return A


def idx_day(cal, phase):
    return next(r["day"] for r in cal if r["phase"] == phase)


def lab_status(vid, v, b0, sex):
    f = sex == "F"
    if vid == "hemoglobin_g_dl":
        cut = 12.0 if f else 13.0
        return ("critical" if v < 8 else "warning" if v < 11 else "watch" if v < cut else "ok", f"{v:.1f} g/dL, cut-off {cut:.1f}")
    if vid == "wbc_k_ul":
        return ("warning" if (v < 3.0 or v > 15) else "watch" if (v < 3.8 or v < 0.7 * b0) else "ok", f"{v:.1f} thousand per µL")
    if vid == "lymph_k_ul":
        return ("critical" if v < 0.5 else "warning" if v < 0.8 else "watch" if v < 0.85 else "ok", f"{v:.2f} thousand per µL")
    if vid == "vitd_ng_ml":
        return ("critical" if v < 20 else "warning" if v < 35 else "ok", f"{v:.0f} ng/mL, NASA repletion band is 20 to 34")
    if vid == "ferritin_ng_ml":
        hi = 150 if f else 200
        return ("critical" if (v > 500 or v < 15) else "warning" if v > hi else "ok", f"{v:.0f} ng/mL, upper level {hi}")
    if vid == "creatinine_mg_dl":
        return ("warning" if v >= b0 + 0.3 else "watch" if v >= b0 + 0.2 else "ok", f"{v:.2f} mg/dL, baseline {b0:.2f}")
    if vid == "crp_mg_l":
        return ("warning" if v > 10 else "watch" if v > 3 else "ok", f"{v:.1f} mg/L")
    if vid == "glucose_mg_dl":
        return ("critical" if v < 54 else "warning" if (v >= 126 or v < 70) else "watch" if v >= 100 else "ok", f"{v:.0f} mg/dL fasting")
    if vid == "urine_ca_mg_day":
        hi = 250 if f else 300
        return ("warning" if v > hi else "watch" if (v > 190 or v > 1.3 * b0) else "ok", f"{v:.0f} mg/day, baseline {b0:.0f}")
    return ("ok", "")


# ---------------------------------------------------------------------------------------------------------------------
# Tomorrow's plan (on-board rules) and the daily instruction from Earth (ground rules on yesterday's data)
# ---------------------------------------------------------------------------------------------------------------------
def worst(a):
    return max((v[0] for v in a.values()), key=lambda s: ORDER[s], default="ok")


def plan_for(cal, i, cid, H, A, eva_days, envd):
    r, h = cal[i], H[cid]
    d, ph = r["day"], r["phase"]
    a, env_a = A[(d, cid)], A[(d, "ENV")]
    nxt = cal[i + 1] if i + 1 < len(cal) else None
    items = []
    add = lambda topic, text, why: items.append(dict(topic=topic, text=text, why=why))
    if ph == "prelaunch":
        add("Routine", "Quarantine routine: sleep 8 h, training as scheduled, baseline tests.", "Baselines taken now are what every later value is compared with.")
        return items
    ready, debt = h["readiness"][i], h["sleep_debt_h"][i]
    surf_next = nxt is not None and nxt["phase"] == "surface"
    eva_next = surf_next and (d + 1) in eva_days.get(cid, set())
    landing_next = nxt is not None and nxt["phase"] in ("surface", "recovery") and ph in ("outbound", "return")
    depart_next = nxt is not None and nxt["phase"] == "return" and ph == "surface"
    # sleep
    if "sleep_h" in a or "pvt_z" in a or debt > 8:
        add("Sleep", "In bed by 22:00, screens off at 21:30, 8.5 h in bed. Nap up to 30 min after lunch.", f"Sleep debt {debt:.0f} h" + (f"; reaction test {a['pvt_z'][2]}" if "pvt_z" in a else "") + ".")
    elif landing_next:
        add("Sleep", "Early night: in bed by 21:00. Sleep aid only as the crew doctor agreed.", "Landing day is long and cannot be repeated.")
    else:
        add("Sleep", "Usual window, 23:00 to 06:30.", "Sleep is inside your usual range.")
    # exercise
    ill = h["symptoms"][i] and any(s in h["symptoms"][i] for s in ("infection", "upset", "decompression", "motion sickness"))
    in_shelter = (envd[d]["shelter_h"] or 0) >= 12 and nxt is not None and (envd[nxt["day"]]["shelter_h"] or 0) >= 12
    if in_shelter:
        add("Exercise", "No session in the shelter. Stretching and isometric holds for 15 min, twice.", "Shelter rules come first; missed sessions are made up next week.")
    elif landing_next:
        add("Exercise", "Light cycle 20 min in the morning, no resistive session.", "Arrive rested; avoid sore muscles for the landing.")
    elif ill or ready < 60:
        add("Exercise", "Rest day or 20 min easy cycling if you feel up to it.", "Illness or low readiness: recovery comes first.")
    elif i >= 2 and all(h["resist_min"][k] < 1 for k in (i, i - 1, i - 2)) and h["exercise_min"][i] > 10:
        add("Exercise", "Elastic bands and body-weight squats 40 min, cycle intervals 30 min.", "The resistive device is out: this keeps part of the load on legs and hips.")
    elif any(k in a for k in ("leg_strength_pct", "bmd_hip_pct")):
        add("Exercise", ("EVA counts as the aerobic session; " if eva_next else "") + "Resistive 45 min with one extra heavy set of squats, deadlifts and heel raises" + ("" if eva_next else "; cycle or treadmill 30 min") + ".",
            "; ".join(a[k][2] for k in ("leg_strength_pct", "bmd_hip_pct") if k in a) + ".")
    elif "exercise_pct" in a:
        add("Exercise", "Full session and make up one missed resistive session this week.", a["exercise_pct"][2] + ".")
    else:
        add("Exercise", ("EVA counts as the aerobic session; resistive 30 min in the evening." if eva_next else "Resistive 45 min, cycle or treadmill 30 min."), "On plan.")
    # food and fluids
    if "energy_pct" in a or "body_mass_kg" in a or "protein_g_kg" in a:
        add("Food", "Add one meal pouch and a snack (about 500 kcal), with a protein item at two meals.", "; ".join(a[k][2] for k in ("energy_pct", "body_mass_kg", "protein_g_kg") if k in a) + ".")
    else:
        add("Food", "Menu as planned.", "Energy intake is on target.")
    if any(k in a for k in ("fluid_l", "urine_l", "stone_risk_irr")) or eva_next:
        add("Fluids", "Drink 3.2 L: 250 mL each hour until 19:00" + (", and 500 mL before the EVA" if eva_next else "") + ".",
            "; ".join(a[k][2] for k in ("fluid_l", "urine_l", "stone_risk_irr") if k in a) + "." if any(k in a for k in ("fluid_l", "urine_l", "stone_risk_irr")) else "EVA day: sweat losses.")
    # work and EVA
    if landing_next:
        tgt = "Mars" if nxt["phase"] == "surface" else "Earth"
        add("Landing", f"{tgt} landing tomorrow. Salt tablets and 1 L of fluid two hours before entry; compression garment on; anti-nausea medication ready. After touchdown: stay seated, stand up with a buddy, stand test before any walking.",
            f"Chance to fail a stand test at Earth gravity {h['ortho_risk_pct'][i]:.0f} %. Balance will be poor for one to three days.")
    elif depart_next:
        add("Departure", "Mars ascent tomorrow. Light breakfast, anti-nausea medication ready, stow loose items.", "Motion sickness returns in half of all crew when gravity changes.")
    if eva_next:
        if ready < 70 or ill:
            add("EVA", "EVA tomorrow: NO-GO by rule. It moves to the next slot.", f"Readiness {ready:.0f}, under 70." if ready < 70 else "Not fit while ill.")
        elif ready < 85 or "sleep_h" in a or "pvt_z" in a:
            add("EVA", "EVA tomorrow: GO with limits. Short traverse, body check every 20 min, ease off at the first heat cue.", f"Readiness {ready:.0f}: ready with limits.")
        else:
            add("EVA", "EVA tomorrow: GO.", f"Readiness {ready:.0f}.")
    elif "pvt_z" in a and a["pvt_z"][0] in ("warning", "critical"):
        add("Work", "No critical task before a retest of the reaction test; move such work to after 10:30.", a["pvt_z"][2] + ".")
    # air and radiation
    if "cabin_co2_mmhg" in env_a:
        add("Air", "Sleep in the module with the best airflow; check the sleep-station fan; easy exercise only.", env_a["cabin_co2_mmhg"][2] + ".")
    if "storm_level" in env_a and env_a["storm_level"][0] != "watch":
        add("Radiation", "Stay in the shelter until the dose rate is back under twice the usual level. No EVA.", env_a["storm_level"][2] + ".")
    # tests due
    due = []
    if nxt is not None and nxt["phase"] in ("outbound", "surface", "return") and (d + 1) % 28 == 14: due.append("blood and urine panel (fasting)")
    if nxt is not None and nxt["phase"] in ("outbound", "return") and (d + 1) % 30 == 0: due.append("eye scan")
    if h["stand_dhr_bpm"][i] is not None and ph in ("surface", "recovery"): due.append("stand test")
    if h["balance_pct"][i] is not None and h["balance_pct"][i] < 95 and ph in ("surface", "recovery"): due.append("balance walk")
    if due:
        add("Tests", "Due tomorrow: " + ", ".join(due) + ".", "Scheduled checks.")
    for k in ("mood_who5", "sans_trt_um", "spo2_pct", "temp_core_c", "hr_rest_bpm"):
        if k in a and a[k][0] in ("warning", "critical"):
            add("Medical", f"See the crew doctor about: {LABEL[k].lower()} ({a[k][2]}).", ACTION[k])
    return items


def uplink_for(cal, i, cid, H, A, envd, labs_by_day, eva_days, state):
    """The instruction Earth sends for day i, written from the data of day i-1 (received next morning)."""
    r = cal[i]
    d, ph = r["day"], r["phase"]
    call = next(c[1] for c in base.CREW if c[0] == cid)
    if ph in ("prelaunch", "recovery"):
        return dict(status="in_person", based_on_day=d, age_days=0, delay_min=0.0, headline="Flight surgeon on site.", items=[], narrative=None)
    if r["comm"] == "blackout":
        state["age"] = state.get("age", 0) + 1
        return dict(status="none", based_on_day=state.get("last_based"), age_days=state["age"], delay_min=None,
                    headline=f"No link to Earth. Standing orders of day {state.get('last_day')} apply.", items=state.get("standing", []), narrative=None)
    j = max(i - 1, 0)
    p, h = cal[j], H[cid]
    a, env_a = A[(p["day"], cid)], A[(p["day"], "ENV")]
    items = []
    add = lambda topic, text, why, prio=2: items.append(dict(topic=topic, text=text, why=why, priority=prio))
    g = lambda k: h[k][j]
    s7, s28 = _m(h["sleep_h"], j, 7), _m(h["sleep_h"], j, 28, 7) or _m(h["sleep_h"], j, 7)
    # ---- what Earth looks at beyond the on-board rules: weeks, projections, what is coming
    if "sleep_h" in a and a["sleep_h"][0] in ("warning", "critical"):
        add("Sleep", f"Your sleep fell to {s7:.1f} h a night this week. We have cleared the evening reports from your schedule for five days and moved your first task to 09:00. Hold 8.5 h in bed.",
            "A week of short sleep slows reactions by an amount you do not feel; your test shows it.", 1)
    if "pvt_z" in a and a["pvt_z"][0] in ("warning", "critical"):
        add("Alertness", "Until two reaction tests in a row are back inside your range: no vehicle driving, no EVA lead, a crewmate checks critical switch settings.", a["pvt_z"][2] + ".", 1)
    if "energy_pct" in a or ("body_mass_kg" in a):
        e7 = _m(h["energy_pct"], j, 7)
        add("Food", f"You ate {e7:.0f} % of your need this week. Add the high-energy items we marked in your menu; target about 500 kcal more a day until your mass is stable.",
            "Under-eating first costs muscle, then bone and mood.")
    if "stone_risk_irr" in a or "urine_l" in a:
        add("Fluids", "Raise fluids to 3.2 L a day for the next two weeks and keep salt low.", "Low urine volume with high urinary calcium raises the kidney-stone risk.")
    device_out = j >= 2 and all(h["resist_min"][k] < 1 for k in (j, j - 1, j - 2)) and h["exercise_min"][j] > 10
    if "exercise_pct" in a or device_out:
        if device_out:
            add("Exercise", "Resistive device still out. Follow the fall-back programme: elastic bands, body-weight squats, cycle intervals six days a week. Repair steps are in the maintenance uplink.",
                "Without loading, leg strength falls within days and bone loss speeds up.", 1)
        else:
            add("Exercise", "You are behind the weekly exercise plan. We have moved two low-priority tasks so that the full session fits tomorrow and the day after.", a["exercise_pct"][2] + ".")
    if "leg_strength_pct" in a and "exercise_pct" not in a:
        add("Exercise", "Raise squat and deadlift loads by 5 % this week if the last sets felt easy.", a["leg_strength_pct"][2] + ".")
    if "bmd_hip_pct" in a and d % 28 == 3:
        slope = (g("bmd_hip_pct") - h["bmd_hip_pct"][j - 30]) / 30 if j >= 30 else 0
        end_day = idx_day(cal, "recovery")
        proj_end = g("bmd_hip_pct") + slope * max(0, end_day - p["day"])
        add("Bone", f"Monthly bone review: hip estimate {g('bmd_hip_pct'):.1f} % of pre-flight, on course for about {proj_end:.0f} % at Earth return on today's rate. Keep six resistive days a week, full energy intake and the vitamin D dose.",
            "Bone loss cannot be felt and is slow to return. NASA's limit is 95 %.")
    if "sans_trt_um" in a and a["sans_trt_um"][0] in ("warning", "critical") and d % 14 == 5:
        add("Eyes", f"Optic disc swelling is estimated at +{g('sans_trt_um'):.0f} µm. Eye scan weekly from now; send the images with the evening packet. Tell us at once about any blur, distortion or blind spot.",
            "Above 19.4 µm is the earliest sign of the eye syndrome that affects most long-stay crew.", 1 if a["sans_trt_um"][0] == "critical" else 2)
    if "mood_who5" in a:
        add("Wellbeing", "Your check-ins have been low for several days. We have set a private talk with the flight surgeon for your next free evening and taken one task off each day this week.",
            a["mood_who5"][2] + ".", 1 if a["mood_who5"][0] == "warning" else 2)
    for l in labs_by_day.get((p["day"], cid), []):
        if l["var_id"] == "vitd_ng_ml" and l["value"] < 35:
            add("Blood panel", f"Vitamin D {l['value']:.0f} ng/mL, in NASA's repletion band. " + ("Raise the dose to 2,000 IU a day." if p["day"] < 135 else "Stay on 2,000 IU a day."), "No sunlight on the skin: bone needs the supplement.")
        if l["var_id"] == "urine_ca_mg_day" and "urine_ca_mg_day" in a:
            add("Blood panel", f"Calcium in urine {l['value']:.0f} mg a day. Fluids at 3 L or more, salt low, resistive training as planned.", "This is bone leaving the body, and the raw material of kidney stones.")
        if l["var_id"] == "hemoglobin_g_dl" and "hemoglobin_g_dl" in a:
            add("Blood panel", f"Hemoglobin {l['value']:.1f} g/dL. Expected after a landing: the blood dilutes as fluid returns. No hard exertion while dizzy; next panel in a week.", "Red-cell mass falls in flight and shows only when plasma volume recovers.")
        if l["var_id"] == "crp_mg_l" and l["value"] > 3:
            add("Blood panel", f"Inflammation marker {l['value']:.1f} mg/L. Tell us about any fever, sore throat, wound or pain.", "Raised values need a cause.")
    if (p["day"], cid) in labs_by_day and not any(it["topic"] == "Blood panel" for it in items):
        add("Blood panel", "Yesterday's blood and urine panel is inside your ranges. Nothing to change.", "Reviewed by the laboratory team.", 3)
    # environment
    if "cabin_co2_mmhg" in env_a and env_a["cabin_co2_mmhg"][0] != "watch":
        add("Air", "Cabin CO2 passed the limit. Swap the removal bed as in the maintenance uplink; sleep where airflow is best; report headaches.", env_a["cabin_co2_mmhg"][2] + ".", 1)
    lvl = envd[d]["storm_level"]
    if lvl >= 2 or envd[p["day"]]["storm_level"] >= 2:
        e = envd[p["day"]]
        add("Radiation", f"Solar storm in progress. Shelter rules apply until we call the end. Yesterday's dose was {e['dose_day_msv']:.1f} mSv" + (f"; outside the shelter it would have been {e['dose_unsheltered_msv']:.1f} mSv." if e["shelter_h"] else "."),
            "The shelter is the only protection that works in deep space.", 1)
    dc = g("dose_cum_msv")
    for mark, txt in ((300, "half of"), (480, "four fifths of"), (600, "above")):
        if h["dose_cum_msv"][j] >= mark > (h["dose_cum_msv"][j - 1] if j else 0):
            add("Radiation", f"Your mission dose passed {mark} mSv, {txt} NASA's career limit of 600 mSv. This was expected. Nothing changes in your day; shelter discipline in storms matters more than ever.",
                "The total cannot be lowered, only its growth.", 2)
    # what is coming
    for name, phase in (("Mars landing", "surface"), ("Earth landing", "recovery")):
        k = idx_day(cal, phase) - d
        if phase == "recovery" and ph != "return": continue
        if phase == "surface" and ph != "outbound": continue
        if k in (14, 7, 3, 2, 1):
            txt = {14: f"{name} in 14 days. From today: no missed resistive session, full energy intake, 3 L of fluid.",
                   7: f"{name} in 7 days. Shift your sleep 20 minutes earlier each night; practise the standing-up sequence in the seat.",
                   3: f"{name} in 3 days. Taper exercise to light sessions. Check the fit of the compression garment.",
                   2: f"{name} in 2 days. Fluids 3.2 L, salt as tolerated. Pack the first-days kit within reach.",
                   1: f"{name} tomorrow. Protocol: salt tablets and 1 L of fluid two hours before entry, compression garment on, anti-nausea medication ready. After touchdown stay seated until the stand test."}[k]
            add("Landing", txt, f"After {d - idx_day(cal, 'outbound' if phase == 'surface' else 'return')} days without gravity the body needs help in the first hours: estimated {g('ortho_risk_pct'):.0f} % chance to fail a stand test at Earth gravity.", 1)
    if ph == "surface" and d == idx_day(cal, "surface"):
        add("Landing", "Landing day. The rules on board decide today: stay seated until the stand test, walk only with a crewmate at your side, no ladder, no EVA. Drink, eat what you can, sleep early.",
            "Balance and blood pressure are at their weakest in the first hours at gravity.", 1)
    if ph == "return" and d == idx_day(cal, "return"):
        add("Departure", "Ascent day. Anti-nausea medication before launch; from tomorrow the weightless routine applies again, with the resistive plan from day two.",
            "The body re-learns weightlessness in about a week.", 1)
    k = next((x["day"] for x in cal if x["comm"] == "blackout"), None)
    last_before_blackout = k is not None and k - d == 1
    if k is not None and 0 < k - d <= 14 and (k - d) in (14, 7, 3, 1):
        add("Link", f"The Sun cuts the link in {k - d} day{'s' if k - d != 1 else ''}, for 12 days. Today's instructions are written to stand through the blackout: keep the routine, the on-board rules decide, log everything for our review afterwards.",
            "No message can pass while the Sun is in the way.", 1)
    if last_before_blackout:                               # standing orders for the days without a link
        add("Standing order: routine", "Keep the sleep window, the exercise plan, 3 L of fluids and the meal plan exactly as now.", "A steady routine is the best protection while nobody can advise you.", 1)
        add("Standing order: warnings", "If an on-board rule calls a warning, follow its action list and the crew medical officer. Do not wait for Earth.", "The rules were written for this case.", 1)
        add("Standing order: EVA", "No EVA until the link is back.", "Mission rule for the blackout.", 1)
        add("Standing order: log", "Log symptoms, meals and tests every day, even when all is well.", "We review all 12 days when the link returns.", 2)
    if ph == "surface" and idx_day(cal, "return") - d in (7, 3, 1):
        add("Departure", f"Mars ascent in {idx_day(cal, 'return') - d} days. Expect motion sickness and back pain again in the first week without gravity; medication is in the first-days kit.", "The body has to re-learn weightlessness.")
    if h["symptoms"][j]:
        add("Symptoms", f"Logged yesterday: {h['symptoms'][j]}. The crew doctor's treatment plan stands; tell us if it is not better in three days.", "Small problems are followed until they are gone.", 3)
    items.sort(key=lambda x: x["priority"])
    st = worst(a)
    n_flag = sum(1 for v in a.values() if v[0] != "ok")
    if not items:
        headline = f"All of yesterday's values are inside your ranges. No change to the plan, {call}."
        add("Routine", "Keep sleep, exercise, food and fluids as planned.", "Nothing moved.", 3)
    else:
        headline = f"{len(items)} point{'s' if len(items) != 1 else ''} for you today, {call}. " + ("Most important: " + items[0]["topic"].lower() + "." if items[0]["priority"] == 1 else "Nothing urgent.")
    status = "short" if r["comm"] == "degraded" else "received"
    if status == "short" and not last_before_blackout:
        items = items[:2]
    state.update(age=0, last_based=p["day"], last_day=d, standing=[dict(it, standing=True) for it in items])
    return dict(status=status, based_on_day=p["day"], age_days=0, delay_min=r["light_min"], headline=headline, items=items, narrative=None)


def write_all(con, cal, envd, H, A, labs, evas, forced):
    labs_by_day = defaultdict(list)
    for l in labs:
        labs_by_day[(l["day"], l["crew_id"])].append(l)
    eva_days = defaultdict(set)
    for e in evas:
        if e["outcome"] != "postponed":
            for c in e["crew_ids"].split(","):
                eva_days[c].add(e["day"])
    planned = defaultdict(set)                         # what was planned the evening before (includes days later postponed)
    for e in evas:
        for c in e["crew_ids"].split(","):
            planned[c].add(e["day"])
    arows, prows, urows = [], [], []
    for (d, cid), a in A.items():
        for vid, (status, value, reason) in a.items():
            arows.append(dict(day=d, crew_id=cid, var_id=vid, status=status, value=base.r_(value, 2), reason=reason))
    ups = {}
    for cid in H:
        state = {}
        for i, r in enumerate(cal):
            for k, it in enumerate(plan_for(cal, i, cid, H, A, planned, envd)):
                prows.append(dict(day=r["day"], crew_id=cid, seq=k, topic=it["topic"], text=it["text"], why=it["why"]))
            u = uplink_for(cal, i, cid, H, A, envd, labs_by_day, eva_days, state)
            ups[(r["day"], cid)] = u
    base.put(con, "assessment", arows)
    base.put(con, "plan", prows)
    return ups
