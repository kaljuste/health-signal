"""Environment of the simulated mission: radiation, storms, cabin air, Mars weather, link to Earth.

Levels come from NASA's published rates; day-to-day variation is a replay of real measurements
on the matching day of the last solar cycle (mission date minus 8,065 days)."""
from collections import defaultdict
from datetime import date, datetime, timedelta
import numpy as np
from . import base

EARTH = dict(co2=0.5, pio2=149.4, kpa=101.3, temp=22.0, rh=45.0, dose=0.0066)
SCRUBBER_FAULT_DAYS = {                                     # outbound: scripted CO2 removal fault; cabin CO2 (mmHg) by hour
    96: lambda h: 2.4 + 1.3 * h / 23.0,                    # bed A degrades through the day
    97: lambda h: 3.7 + 0.7 * np.sin(np.pi * h / 23.0),    # worst day
    98: lambda h: 3.7 - 2.3 * min(1.0, h / 10.0),          # bed swapped in the morning
}
SURFACE_STORM_DATE = date(2039, 5, 18)                       # scripted; real far-side event on the replayed date (2017-04-18)
STORM_REAL_ONSET = datetime(2017, 9, 10, 16)                 # hour when Curiosity's dose rate began to rise
STORM_EVA_ONSET_H = 10.0 + 0.75                              # local hour of that onset on the scripted sol (EVA starts 10:00)


def _daily(con, sid):
    return {t[:10]: v for t, v in base.series(con, sid)}


def storm_profile(con):
    """Hourly ratio of Curiosity's surface dose rate to its pre-storm level, 10-13 Sep 2017. Index 0 = onset hour."""
    rows = base.series(con, "msl_rad.surface.dose_e.hourly", "2017-09-09T00", "2017-09-14T00")
    pre = np.median([v for t, v in rows if t < "2017-09-10T12"])
    return [max(v / pre, 0.8) for t, v in rows if t[:13] >= STORM_REAL_ONSET.strftime("%Y-%m-%dT%H")][:72]


def _level(pfu):
    if pfu is None: return 0
    return 0 if pfu < 10 else 1 if pfu < 100 else 2 if pfu < 1000 else 3 if pfu < 1e4 else 4


def build(cal, rng):
    con = base.ref()
    crater, rad = _daily(con, "lro_crater.microdosimeter.dose.daily"), _daily(con, "msl_rad.surface.dose_e.daily")
    pfu = _daily(con, "omni.p_gt10.daily_max")
    prof = storm_profile(con)

    # ---- cabin air: replay of real ISS hourly records (CO2, temperature, humidity), tiled over the mission
    wins = sorted({r[0].split(".")[1] for r in con.execute("select series_id from series where series_id like 'iss_cabin.%.co2.hourly'")})
    tiles = []
    for w in wins:
        c = dict(base.series(con, f"iss_cabin.{w}.co2.hourly")); t = dict(base.series(con, f"iss_cabin.{w}.temp.hourly")); h = dict(base.series(con, f"iss_cabin.{w}.rh.hourly"))
        rows = [(c[k] * 760e-6, t[k], h[k]) for k in sorted(c) if k in t and k in h and 300 < c[k] < 9000]
        if len(rows) > 200:
            # Older ISS records run above today's 3 mmHg limit. A ship built to today's standard: rescale each window
            # so that its 95th percentile is at most 2.6 mmHg. The hour-to-hour pattern stays real.
            k95 = float(np.percentile([x[0] for x in rows], 95))
            f = min(1.0, 2.6 / k95)
            tiles.append((w, [(x[0] * f, x[1], x[2]) for x in rows]))
    order = list(rng.permutation(len(tiles)))
    stream = [x for i in order for x in tiles[i][1]]

    # ---- Mars weather: Curiosity REMS, Mars year 33, matched by season (solar longitude)
    names = ["air_temp_max", "air_temp_min", "pressure", "uv_index", "sunrise_lmst", "sunset_lmst", "solar_longitude"]
    rems = defaultdict(dict)
    for n in names:
        for t, v in base.series(con, f"rems.{n}", "2015-06-18", "2017-05-06"):
            rems[t[:10]][n] = v
    rrows = [d for d in rems.values() if "solar_longitude" in d]
    def weather(ls, key):
        best = min((r for r in rrows if key in r), key=lambda r: min(abs(r["solar_longitude"] - ls), 360 - abs(r["solar_longitude"] - ls)))
        return best[key]

    # ---- radiation level per phase
    def med(d, days):
        v = [d.get(x["analog"].isoformat()) for x in days]; v = [x for x in v if x]
        return float(np.median(v))
    ph = defaultdict(list)
    for r in cal: ph[r["phase"]].append(r)
    ref_level = {"outbound": med(crater, ph["outbound"]), "return": med(crater, ph["return"]), "surface": med(rad, ph["surface"])}

    storm_day0 = next(r["day"] for r in cal if r["date"] == SURFACE_STORM_DATE)
    env_day, env_hour, events, by_day = [], [], [], {}
    hi = 0
    for r in cal:
        d, phase, a = r["day"], r["phase"], r["analog"].isoformat()
        e = dict(day=d)
        hourly_mult = np.ones(24)
        flux = pfu.get(a)
        if phase in ("prelaunch", "recovery"):
            e.update(cabin_co2_mmhg=EARTH["co2"], cabin_co2_max1h=EARTH["co2"] + 0.2, cabin_pio2_mmhg=EARTH["pio2"], cabin_pio2_min=EARTH["pio2"],
                     cabin_pressure_kpa=EARTH["kpa"], cabin_temp_c=EARTH["temp"], cabin_rh_pct=EARTH["rh"],
                     dose_day_msv=EARTH["dose"], dose_unsheltered_msv=EARTH["dose"], shelter_h=0, storm_level=0, proton_flux_pfu=None)
            hours = [(EARTH["co2"] + 0.15 * np.sin(h / 24 * 6.283), EARTH["pio2"], EARTH["temp"] + 0.6 * np.sin((h - 9) / 24 * 6.283), EARTH["rh"]) for h in range(24)]
        else:
            hours = []
            for h in range(24):
                c, t, rh = stream[hi % len(stream)]; hi += 1
                if d in SCRUBBER_FAULT_DAYS:
                    c = max(c, float(SCRUBBER_FAULT_DAYS[d](h)) + rng.normal(0, 0.05))
                hours.append([c, base.CABIN_PIO2 + rng.normal(0, 0.22), t, rh])
            if phase in ("outbound", "return"):
                x = crater.get(a) or ref_level[phase]
                ratio = x / ref_level[phase]
                gcr = float(np.clip(ratio, 0.75, 1.25))
                excess = max(0.0, x - 1.6 * ref_level[phase])                      # mGy/day behind thin shielding (storm part)
                sh = 20 if excess > 5 else 12 if excess > 1 else 0
                unshel = base.DOSE_TRANSIT * gcr + excess * base.F_CABIN * base.Q_SPE
                dose = base.DOSE_TRANSIT * gcr + excess * base.Q_SPE * (base.F_SHELTER * sh / 24 + base.F_CABIN * (1 - sh / 24))
                lvl = max(_level(flux), 1 if excess > 1 else 0)
                if excess > 1:
                    hourly_mult = 1 + (excess * base.F_CABIN * base.Q_SPE / (base.DOSE_TRANSIT * gcr)) * np.exp(-((np.arange(24) - 14) / 7.0) ** 2) * 1.9
            else:
                x = rad.get(a) or ref_level["surface"]
                dose = unshel = base.DOSE_SURFACE * x / ref_level["surface"]
                sh, lvl = 0, 0                                                     # Earth-side storms of the replay are not applied on Mars
                flux = None
                k = d - storm_day0
                if 0 <= k <= 2:                                                    # scripted surface storm with the real Mars profile
                    off = int(round(STORM_EVA_ONSET_H))
                    hourly_mult = np.array([prof[k * 24 + h - off] if 0 <= k * 24 + h - off < len(prof) else 1.0 for h in range(24)])
                    sh = [10, 20, 6][k]
                    unshel = base.DOSE_SURFACE * float(hourly_mult.mean())
                    dose = base.DOSE_SURFACE * (1 + (float(hourly_mult.mean()) - 1) * (1 - 0.6 * sh / 24))   # shelter stops about 60 % of the storm part (assumed)
                    lvl = [2, 2, 1][k]
            e.update(dose_day_msv=dose, dose_unsheltered_msv=unshel, shelter_h=sh, storm_level=lvl, proton_flux_pfu=flux)
        co2 = np.array([h[0] for h in hours])
        pio2 = np.array([h[1] for h in hours])
        e.update(cabin_co2_mmhg=float(co2.mean()), cabin_co2_max1h=float(co2.max()), cabin_pio2_mmhg=float(pio2.mean()), cabin_pio2_min=float(pio2.min()),
                 cabin_pressure_kpa=(base.CABIN_KPA + rng.normal(0, 0.12)) if phase not in ("prelaunch", "recovery") else EARTH["kpa"],
                 cabin_temp_c=float(np.mean([h[2] for h in hours])), cabin_rh_pct=float(np.mean([h[3] for h in hours])))
        rate = e["dose_unsheltered_msv"] * 1000 / 24 if phase != "surface" else base.DOSE_SURFACE * (rad.get(a) or ref_level["surface"]) / ref_level["surface"] * 1000 / 24
        hm = hourly_mult / hourly_mult.mean() if phase != "surface" else hourly_mult
        e["dose_rate_usv_h"] = float(rate * hm.mean())
        if phase == "surface":
            ls = r["ls"]
            e.update(out_temp_max_c=weather(ls, "air_temp_max"), out_temp_min_c=weather(ls, "air_temp_min"), out_pressure_pa=weather(ls, "pressure"),
                     out_uv_index=weather(ls, "uv_index"), sunrise_h=weather(ls, "sunrise_lmst"), sunset_h=weather(ls, "sunset_lmst"))
        else:
            e.update(out_temp_max_c=None, out_temp_min_c=None, out_pressure_pa=None, out_uv_index=None, sunrise_h=None, sunset_h=None)
        env_day.append({k: (base.r_(v, 3) if isinstance(v, float) else v) for k, v in e.items()})
        for h in range(24):
            env_hour.append(dict(day=d, hour=h, cabin_co2_mmhg=base.r_(hours[h][0], 2), cabin_pio2_mmhg=base.r_(hours[h][1], 1),
                                 cabin_temp_c=base.r_(hours[h][2], 1), cabin_rh_pct=base.r_(hours[h][3], 0),
                                 dose_rate_usv_h=base.r_(rate * hm[h] * (1 + rng.normal(0, 0.03)), 1)))
        by_day[d] = dict(e, hourly_mult=hourly_mult, hours=hours)

    # ---- environment events
    def runs(pred):
        out, cur = [], None
        for r in cal:
            if pred(r):
                cur = [r["day"], r["day"]] if cur is None else [cur[0], r["day"]]
            elif cur:
                out.append(cur); cur = None
        if cur: out.append(cur)
        return out
    dmap = {r["day"]: r for r in cal}
    for a, b in runs(lambda r: by_day[r["day"]]["storm_level"] >= 1 and r["phase"] in ("outbound", "return")):
        peak = max(range(a, b + 1), key=lambda k: by_day[k]["dose_unsheltered_msv"])
        extra_un = sum(by_day[k]["dose_unsheltered_msv"] for k in range(a, b + 1)) - base.DOSE_TRANSIT * (b - a + 1)
        extra = sum(by_day[k]["dose_day_msv"] for k in range(a, b + 1)) - base.DOSE_TRANSIT * (b - a + 1)
        lvl = max(by_day[k]["storm_level"] for k in range(a, b + 1))
        sheltered = any(by_day[k]["shelter_h"] for k in range(a, b + 1))
        events.append(dict(day_start=a, day_end=b, scope="env", crew_id=None, type="solar_storm", severity="warning" if lvl >= 2 else "watch",
                           title=f"Solar particle event, level S{lvl}",
                           detail=(f"Replay of the real event of {dmap[a]['analog'].isoformat()} to {dmap[b]['analog'].isoformat()}. "
                                   + (f"Crew in the storm shelter on the peak days. Extra dose about {max(extra, 0):.1f} mSv; without the shelter about {max(extra_un, 0):.1f} mSv. "
                                      if sheltered else "Too weak to need the shelter. ")
                                   + f"Peak on mission day {peak}."), origin="REAL replay; shielding factors assumed"))
    events.append(dict(day_start=storm_day0, day_end=storm_day0 + 2, scope="env", crew_id=None, type="solar_storm", severity="warning",
                       title="Solar particle event at Mars",
                       detail="Scripted. The replayed date holds a real far-side event (18 Apr 2017, seen by STEREO-A). The dose-rate curve is Curiosity's measurement of the 10-13 Sep 2017 storm at Gale crater: the rate doubles within five hours. EVA ended early; crew indoors.",
                       origin="scripted, REAL shape"))
    events.append(dict(day_start=min(SCRUBBER_FAULT_DAYS), day_end=max(SCRUBBER_FAULT_DAYS), scope="env", crew_id=None, type="co2_removal_fault", severity="warning",
                       title="CO2 removal bed degraded",
                       detail="Scripted device fault. Cabin CO2 passed the 3 mmHg one-hour limit until the bed was swapped on the third day.", origin="scripted"))
    for a, b in runs(lambda r: r["comm"] == "blackout"):
        events.append(dict(day_start=a, day_end=b, scope="mission", crew_id=None, type="comm_blackout", severity="info",
                           title="No link to Earth (Sun in the way)", detail=f"Solar conjunction. No uplink or downlink for {b - a + 1} days. The crew works from standing orders.", origin="REAL astronomy"))
    for a, b in runs(lambda r: r["comm"] == "degraded"):
        events.append(dict(day_start=a, day_end=b, scope="mission", crew_id=None, type="comm_degraded", severity="info",
                           title="Weak link to Earth", detail="Sun within 5 degrees of the line of sight. Short text only.", origin="REAL astronomy"))
    con.close()
    info = dict(cabin_windows=[w for w, _ in tiles], cabin_hours=len(stream), ref_level=ref_level, storm_day0=storm_day0,
                storm_profile=[round(x, 2) for x in prof[:30]])
    return env_day, env_hour, events, by_day, info
