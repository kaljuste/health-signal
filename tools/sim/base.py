"""Shared constants, paths, random streams and the SQLite schema of the simulated mission."""
import csv, hashlib, json, sqlite3
from datetime import date, timedelta
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REF_DB = ROOT / "data/reference/mission_reference.sqlite"
CAL_CSV = ROOT / "data/mission/mission_calendar.csv"
PLAN_JSON = ROOT / "data/mission/mission_plan.json"
CATALOG = ROOT / "kb/raw/catalog/catalog_final.json"
OUT_DIR = ROOT / "data/sim"
OUT_DB = OUT_DIR / "mission_sim.sqlite"

SEED = 2037
# Replay window: mission date minus this many days gives the real day that is replayed.
# 2039-10-10 <-> 2017-09-10 (cycle 24 shifted by 265 months, kb/22 section 5).
ANALOG_SHIFT_DAYS = (date(2039, 10, 10) - date(2017, 9, 10)).days

# Habitat and ship atmosphere: NASA exploration atmosphere (kb/17). Suit: 29.6 kPa, oxygen.
CABIN_KPA, CABIN_O2_FRAC, CABIN_PIO2 = 56.5, 0.34, 128.2
SUIT_KPA = 29.6
# NASA effective-dose rates used by the apps (kb/13 rad_dose_rate, kb/22 section 6).
DOSE_TRANSIT, DOSE_SURFACE, CAREER_LIMIT = 1.4, 0.5, 600.0
# Storm shielding: OUR ASSUMPTION, not a transport calculation (kb/25 limits).
F_CABIN, F_SHELTER, Q_SPE = 0.05, 0.015, 1.5

CREW = [
    # id, call sign, role, sex, age, height cm, launch mass kg
    ("C1", "KESTREL", "flight engineer", "F", 41, 168, 72.9),
    ("C2", "HERON", "commander", "M", 47, 181, 82.0),
    ("C3", "OSPREY", "geologist", "M", 38, 176, 76.5),
    ("C4", "WREN", "physician, crew medical officer", "F", 44, 165, 63.0),
]
FOCUS = "C1"
EVA_TEAMS = {"A": ("C1", "C3"), "B": ("C2", "C4")}


def rng_for(name, seed=SEED):
    """Independent, reproducible random stream per purpose."""
    h = int.from_bytes(hashlib.sha256(f"{seed}:{name}".encode()).digest()[:8], "little")
    return np.random.default_rng(h)


def load_calendar():
    rows = []
    with open(CAL_CSV, newline="") as f:
        for r in csv.DictReader(f):
            d = date.fromisoformat(r["date_utc"])
            num = lambda k: float(r[k]) if r[k] not in ("", None) else None
            rows.append(dict(
                day=int(r["mission_day"]), date=d, phase=r["phase"], sol=int(r["sol"]) if r["sol"] else None,
                light_min=num("light_time_min") or 0.0, round_trip_min=num("round_trip_min") or 0.0,
                comm=r["comm"] or "ok", ls=num("mars_ls_deg"), season=r["mars_season"], mars_year=r["mars_year"],
                g=num("gravity_g"), dist_earth_au=num("dist_earth_au"), dist_sun_au=num("dist_sun_au"),
                sep_deg=num("sun_earth_probe_deg"), analog=d - timedelta(days=ANALOG_SHIFT_DAYS)))
    # Gravity felt by the crew: 1 g before launch and after return, 0 in transit, 0.38 on Mars.
    for r in rows:
        r["g"] = {"prelaunch": 1.0, "outbound": 0.0, "surface": 0.38, "return": 0.0, "recovery": 1.0}[r["phase"]]
    return rows


def ref():
    con = sqlite3.connect(f"file:{REF_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def series(con, series_id, t0=None, t1=None):
    q, a = "select t_utc, value from obs where series_id=?", [series_id]
    if t0: q += " and t_utc>=?"; a.append(str(t0))
    if t1: q += " and t_utc<?"; a.append(str(t1))
    return [(r[0], r[1]) for r in con.execute(q + " order by t_utc", a) if r[1] is not None]


SCHEMA = """
PRAGMA journal_mode=OFF;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE crew (crew_id TEXT PRIMARY KEY, call_sign TEXT, role TEXT, sex TEXT, age INTEGER, height_cm REAL,
  launch_mass_kg REAL, eva_team TEXT, baseline_json TEXT, traits_json TEXT);
CREATE TABLE variable (var_id TEXT PRIMARY KEY, scope TEXT, grp TEXT, label TEXT, unit TEXT, decimals INTEGER, cadence TEXT,
  table_name TEXT, column_name TEXT, kind TEXT, method TEXT, sensor TEXT, region TEXT, catalog_id TEXT, hrp_risk TEXT,
  better TEXT, watch_low REAL, watch_high REAL, warn_low REAL, warn_high REAL, crit_low REAL, crit_high REAL,
  rule_text TEXT, rule_tag TEXT, why TEXT, action TEXT, how_simulated TEXT, learned_from TEXT, sort INTEGER);
CREATE TABLE day (day INTEGER PRIMARY KEY, date_utc TEXT, phase TEXT, phase_day INTEGER, sol INTEGER, mars_ls REAL, season TEXT,
  gravity_g REAL, light_time_min REAL, round_trip_min REAL, comm TEXT, dist_earth_au REAL, dist_sun_au REAL,
  analog_date TEXT, key_label TEXT);
CREATE TABLE env_day (day INTEGER PRIMARY KEY, cabin_co2_mmhg REAL, cabin_co2_max1h REAL, cabin_pio2_mmhg REAL, cabin_pio2_min REAL,
  cabin_pressure_kpa REAL, cabin_temp_c REAL, cabin_rh_pct REAL, dose_rate_usv_h REAL, dose_day_msv REAL, dose_unsheltered_msv REAL,
  shelter_h REAL, storm_level INTEGER, proton_flux_pfu REAL, out_temp_max_c REAL, out_temp_min_c REAL, out_pressure_pa REAL,
  out_uv_index REAL, sunrise_h REAL, sunset_h REAL);
CREATE TABLE env_hour (day INTEGER, hour INTEGER, cabin_co2_mmhg REAL, cabin_pio2_mmhg REAL, cabin_temp_c REAL, cabin_rh_pct REAL,
  dose_rate_usv_h REAL, PRIMARY KEY (day, hour)) WITHOUT ROWID;
CREATE TABLE body_day (day INTEGER, crew_id TEXT, hr_rest_bpm REAL, hrv_rmssd_ms REAL, bp_sys_mmhg REAL, bp_dia_mmhg REAL, spo2_pct REAL,
  resp_rate_bpm REAL, temp_core_c REAL, stand_dhr_bpm REAL, ortho_risk_pct REAL, sleep_h REAL, sleep_eff_pct REAL, sleep_debt_h REAL,
  pvt_rt_ms REAL, pvt_z REAL, mood_who5 REAL, stress_0_10 REAL, body_mass_kg REAL, energy_pct REAL, protein_g_kg REAL, fluid_l REAL,
  urine_l REAL, stone_risk_irr REAL, exercise_min REAL, exercise_pct REAL, resist_min REAL, vo2max_pct REAL, leg_strength_pct REAL,
  bmd_hip_pct REAL, back_pain_0_10 REAL, sms_grade REAL, balance_pct REAL, sans_trt_um REAL, dose_day_msv REAL, dose_cum_msv REAL,
  readiness REAL, readiness_band TEXT, activity TEXT, symptoms TEXT, PRIMARY KEY (day, crew_id)) WITHOUT ROWID;
CREATE TABLE body_hour (day INTEGER, crew_id TEXT, hour INTEGER, hr_bpm REAL, temp_core_c REAL, activity TEXT,
  PRIMARY KEY (day, crew_id, hour)) WITHOUT ROWID;
CREATE TABLE lab (day INTEGER, crew_id TEXT, var_id TEXT, value REAL, PRIMARY KEY (day, crew_id, var_id)) WITHOUT ROWID;
CREATE TABLE assessment (day INTEGER, crew_id TEXT, var_id TEXT, status TEXT, value REAL, reason TEXT,
  PRIMARY KEY (day, crew_id, var_id)) WITHOUT ROWID;
CREATE TABLE readiness_cost (day INTEGER, crew_id TEXT, item TEXT, points REAL, PRIMARY KEY (day, crew_id, item)) WITHOUT ROWID;
CREATE TABLE event (event_id INTEGER PRIMARY KEY, day_start INTEGER, day_end INTEGER, scope TEXT, crew_id TEXT, type TEXT,
  severity TEXT, title TEXT, detail TEXT, origin TEXT);
CREATE TABLE plan (day INTEGER, crew_id TEXT, seq INTEGER, topic TEXT, text TEXT, why TEXT, PRIMARY KEY (day, crew_id, seq)) WITHOUT ROWID;
CREATE TABLE uplink (day INTEGER, crew_id TEXT, status TEXT, based_on_day INTEGER, age_days INTEGER, delay_min REAL, headline TEXT,
  items_json TEXT, narrative TEXT, PRIMARY KEY (day, crew_id)) WITHOUT ROWID;
CREATE TABLE snapshot (day INTEGER, crew_id TEXT, title TEXT, why TEXT, analysis TEXT, questions_json TEXT,
  PRIMARY KEY (day, crew_id)) WITHOUT ROWID;
CREATE TABLE eva (eva_id INTEGER PRIMARY KEY, day INTEGER, sol INTEGER, team TEXT, crew_ids TEXT, number INTEGER, planned_min REAL,
  actual_min REAL, distance_m REAL, peak_hr REAL, dose_usv REAL, outcome TEXT, summary TEXT, scenario_id TEXT);
CREATE TABLE eva_scenario (scenario_id TEXT PRIMARY KEY, eva_id INTEGER, sort INTEGER, title TEXT, day INTEGER, sol INTEGER, date_utc TEXT,
  crew_id TEXT, start_local_h REAL, duration_s INTEGER, snapshot_t_s INTEGER, outcome TEXT, summary TEXT, context_json TEXT);
CREATE TABLE eva_sample (scenario_id TEXT, t_s INTEGER, phase TEXT, task TEXT, seg_left_s INTEGER, state TEXT, limiter TEXT, stay_min REAL, walk_back_min REAL,
  dist_m REAL, x_m REAL, y_m REAL, met_w REAL, hr_bpm REAL, core_c REAL, lactate_mmol REAL, stamina_pct REAL, balance_score REAL,
  faint_risk_pct REAL, heat_kj_kg REAL, suit_p_kpa REAL, suit_o2_pct REAL, suit_co2_mmhg REAL, suit_temp_c REAL, battery_pct REAL,
  water_pct REAL, scrubber_pct REAL, cooling_level INTEGER, dose_rate_usv_h REAL, eva_dose_usv REAL, drink_ml REAL,
  left_o2_min REAL, left_battery_min REAL, left_water_min REAL, left_scrubber_min REAL, left_daylight_min REAL, left_stamina_min REAL,
  left_event_min REAL, next_id INTEGER, PRIMARY KEY (scenario_id, t_s)) WITHOUT ROWID;
CREATE TABLE eva_text (scenario_id TEXT, next_id INTEGER, text TEXT, PRIMARY KEY (scenario_id, next_id)) WITHOUT ROWID;
CREATE TABLE eva_event (scenario_id TEXT, t_s INTEGER, kind TEXT, severity TEXT, var_id TEXT, text TEXT);
CREATE TABLE learned_param (param_id TEXT PRIMARY KEY, value_json TEXT, dataset_id TEXT, n INTEGER, method TEXT, used_for TEXT);
CREATE TABLE source_use (dataset_id TEXT, title TEXT, kind TEXT, provenance TEXT, licence TEXT, source_url TEXT, how TEXT, used_for TEXT,
  note TEXT, feeds TEXT, PRIMARY KEY (dataset_id, how)) WITHOUT ROWID;
CREATE INDEX ix_event_day ON event (day_start, day_end);
CREATE INDEX ix_evaevent ON eva_event (scenario_id, t_s);
CREATE INDEX ix_lab ON lab (crew_id, var_id, day);
"""


TMP_DB = OUT_DIR / "mission_sim.sqlite.tmp"


def new_db():
    """Build into a temporary file; publish() swaps it in at the end, so a page that is loading never sees half a database."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if TMP_DB.exists():
        TMP_DB.unlink()
    con = sqlite3.connect(TMP_DB)
    con.executescript(SCHEMA)
    return con


def publish():
    TMP_DB.replace(OUT_DB)


def put(con, table, rows):
    """Insert a list of dicts (all with the same keys)."""
    if not rows:
        return
    keys = list(rows[0].keys())
    con.executemany(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
                    [[r[k] for k in keys] for r in rows])


def r_(x, n=2):
    return None if x is None else round(float(x), n)


def jdump(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
