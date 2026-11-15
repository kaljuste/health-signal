#!/usr/bin/env python3
"""Mars mission planner (planning research, not the hackathon app).

Finds Earth→Mars and Mars→Earth transfer windows from JPL Horizons ephemerides with a
Lambert solver, compares mission options, and writes the chosen mission plan plus a daily
calendar (distance, one-way light time, solar-conjunction angle, Mars season).

  python3 -I tools/mission_planner.py windows        # scan 2032–2050, write windows_*.csv
  python3 -I tools/mission_planner.py plan           # build the chosen mission + calendar
  python3 -I tools/mission_planner.py all

Outputs → data/mission/. Ephemeris files are cached; delete them to refetch.
Assumptions are printed and stored in mission_plan.json. Patched-conic, zero-revolution,
prograde transfers; planets treated as points (v∞ only); no propulsion model.
"""
import csv
import json
import math
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mission"
EPH = OUT / "ephemeris"

MU_SUN = 1.32712440018e11        # km^3/s^2
AU = 149597870.7                 # km
C_KM_S = 299792.458
DAY = 86400.0
SOL = 88775.244                  # s, mean Mars solar day
MU_EARTH, R_EARTH = 398600.4418, 6378.137
MU_MARS, R_MARS = 42828.37, 3396.19
EPH_START, EPH_STOP = "2026-11-01", "2052-01-01"
T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


# ----------------------------------------------------------------------------- ephemeris
def fetch_vectors(body, name):
    """Heliocentric ecliptic J2000 state vectors, daily, km and km/s (JPL Horizons)."""
    path = EPH / f"{name}_helio_ecliptic_{EPH_START[:4]}-{EPH_STOP[:4]}_daily.csv"
    if path.exists():
        return path
    q = {"format": "text", "COMMAND": f"'{body}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
         "EPHEM_TYPE": "'VECTORS'", "CENTER": "'500@10'", "REF_PLANE": "'ECLIPTIC'", "REF_SYSTEM": "'ICRF'",
         "START_TIME": f"'{EPH_START}'", "STOP_TIME": f"'{EPH_STOP}'", "STEP_SIZE": "'1d'",
         "VEC_TABLE": "'2'", "OUT_UNITS": "'KM-S'", "CSV_FORMAT": "'YES'", "VEC_LABELS": "'NO'"}
    url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(q, safe="'@")
    req = urllib.request.Request(url, headers={"User-Agent": "mission-planner/1.0"})
    with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as r:
        raw = r.read().decode()
    if "$$SOE" not in raw:
        raise SystemExit(f"Horizons returned no table for {name}:\n{raw[:600]}")
    block = raw.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    EPH.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["jd_tdb", "date_tdb", "x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"])
        for line in block:
            c = [x.strip() for x in line.split(",")]
            w.writerow([c[0], c[1].replace("A.D. ", "")] + c[2:8])
    (EPH / f"{path.stem}.source.txt").write_text(url + "\n")
    print(f"  fetched {name}: {len(block)} rows → {path.relative_to(ROOT)}")
    return path


def load_vectors(path):
    a = np.loadtxt(path, delimiter=",", skiprows=1, usecols=(0, 2, 3, 4, 5, 6, 7))
    return a[:, 0], a[:, 1:4], a[:, 4:7]


def date_of(i):
    return T0 + timedelta(days=float(i))


def iso(i):
    return date_of(i).strftime("%Y-%m-%d")


# ----------------------------------------------------------------------------- Lambert
def stumpff(z):
    C = np.empty_like(z)
    S = np.empty_like(z)
    pos, neg = z > 1e-6, z < -1e-6
    mid = ~(pos | neg)
    sz = np.sqrt(z[pos])
    C[pos] = (1 - np.cos(sz)) / z[pos]
    S[pos] = (sz - np.sin(sz)) / sz ** 3
    sn = np.sqrt(-z[neg])
    C[neg] = (np.cosh(sn) - 1) / (-z[neg])
    S[neg] = (np.sinh(sn) - sn) / sn ** 3
    C[mid] = 0.5 - z[mid] / 24
    S[mid] = 1 / 6 - z[mid] / 120
    return C, S


def lambert(r1, r2, dt, mu=MU_SUN):
    """Zero-revolution prograde Lambert solution (universal variables, bisection on z).
    r1, r2: (..., 3) km; dt: (...) s. Returns v1, v2 (..., 3) km/s."""
    r1n = np.linalg.norm(r1, axis=-1)
    r2n = np.linalg.norm(r2, axis=-1)
    cosd = np.clip(np.sum(r1 * r2, axis=-1) / (r1n * r2n), -1, 1)
    crossz = r1[..., 0] * r2[..., 1] - r1[..., 1] * r2[..., 0]
    dth = np.arccos(cosd)
    dth = np.where(crossz < 0, 2 * math.pi - dth, dth)
    A = np.sin(dth) * np.sqrt(r1n * r2n / np.maximum(1 - np.cos(dth), 1e-12))
    lo = np.full(dt.shape, -200.0)
    hi = np.full(dt.shape, 4 * math.pi ** 2 - 1e-6)
    sq = math.sqrt(mu)
    for _ in range(64):
        z = 0.5 * (lo + hi)
        C, S = stumpff(z)
        y = r1n + r2n + A * (z * S - 1) / np.sqrt(C)
        yy = np.maximum(y, 0)
        F = (yy / C) ** 1.5 * S + A * np.sqrt(yy) - sq * dt
        low = (y < 0) | (F < 0)
        lo = np.where(low, z, lo)
        hi = np.where(low, hi, z)
    z = 0.5 * (lo + hi)
    C, S = stumpff(z)
    y = np.maximum(r1n + r2n + A * (z * S - 1) / np.sqrt(C), 1e-9)
    f = 1 - y / r1n
    g = A * np.sqrt(y / mu)
    gd = 1 - y / r2n
    v1 = (r2 - f[..., None] * r1) / g[..., None]
    v2 = (gd[..., None] * r2 - r1) / g[..., None]
    return v1, v2, dth


def kepler(r0, v0, dt, mu=MU_SUN):
    """Propagate a heliocentric two-body orbit by dt seconds (universal variable, Newton)."""
    r0n = float(np.linalg.norm(r0))
    vr0 = float(np.dot(r0, v0)) / r0n
    alpha = 2 / r0n - float(np.dot(v0, v0)) / mu
    x = math.sqrt(mu) * abs(alpha) * dt
    for _ in range(200):
        z = alpha * x * x
        C, S = stumpff(np.array([z]))
        C, S = float(C[0]), float(S[0])
        F = r0n * vr0 / math.sqrt(mu) * x * x * C + (1 - alpha * r0n) * x ** 3 * S + r0n * x - math.sqrt(mu) * dt
        dF = r0n * vr0 / math.sqrt(mu) * x * (1 - z * S) + (1 - alpha * r0n) * x * x * C + r0n
        dx = F / dF
        x -= dx
        if abs(dx) < 1e-7:
            break
    z = alpha * x * x
    C, S = stumpff(np.array([z]))
    C, S = float(C[0]), float(S[0])
    f = 1 - x * x / r0n * C
    g = dt - x ** 3 / math.sqrt(mu) * S
    return f * r0 + g * v0


# ----------------------------------------------------------------------------- Mars season
def mars_ls(dt_utc):
    """Areocentric solar longitude Ls (deg), Allison & McEwen 2000 (accuracy ~0.1°)."""
    jd = dt_utc.timestamp() / DAY + 2440587.5 + 69.184 / DAY
    d = jd - 2451545.0
    M = math.radians((19.3871 + 0.52402073 * d) % 360)
    afms = (270.3871 + 0.524038496 * d) % 360
    pbs = sum(a * math.cos(math.radians(0.985626 * d / tau + phi)) for a, tau, phi in (
        (0.0071, 2.2353, 49.409), (0.0057, 2.7543, 168.173), (0.0039, 1.1177, 191.837),
        (0.0037, 15.7866, 21.736), (0.0021, 2.1354, 15.704), (0.0020, 2.4694, 95.528), (0.0018, 32.8493, 49.095)))
    eoc = ((10.691 + 3.0e-7 * d) * math.sin(M) + 0.623 * math.sin(2 * M) + 0.050 * math.sin(3 * M)
           + 0.005 * math.sin(4 * M) + 0.0005 * math.sin(5 * M) + pbs)
    return (afms + eoc) % 360


def mars_year(dt_utc):
    """Mars Year (Clancy convention: MY 1 began 1955-04-11 at Ls 0)."""
    my1 = datetime(1955, 4, 11, tzinfo=timezone.utc)
    return int((dt_utc - my1).total_seconds() / (686.9726 * DAY)) + 1


def season(ls):
    return ("N spring / S autumn", "N summer / S winter", "N autumn / S spring (dust season)",
            "N winter / S summer (dust season)")[int(ls // 90) % 4]


# ----------------------------------------------------------------------------- helpers
def tmi_dv(vinf, mu=MU_EARTH, r=R_EARTH + 400):
    """ΔV from a 400 km circular parking orbit to reach v∞ (km/s)."""
    return math.sqrt(vinf ** 2 + 2 * mu / r) - math.sqrt(mu / r)


def entry_speed(vinf, mu, r):
    return math.sqrt(vinf ** 2 + 2 * mu / r)


def oppositions(re, rm):
    lon_e = np.degrees(np.arctan2(re[:, 1], re[:, 0]))
    lon_m = np.degrees(np.arctan2(rm[:, 1], rm[:, 0]))
    d = (lon_e - lon_m + 180) % 360 - 180
    idx = [i for i in range(1, len(d)) if d[i - 1] < 0 <= d[i] and abs(d[i]) < 5]
    return idx


def grid(ra, va, rb, vb, tofs):
    """v∞ at departure from body a and arrival at body b for every (departure day, tof)."""
    n = len(ra)
    dep = np.arange(n)[:, None]
    arr = dep + tofs[None, :]
    ok = arr < n
    arrc = np.minimum(arr, n - 1)
    r1 = np.broadcast_to(ra[:, None, :], (n, len(tofs), 3))
    r2 = rb[arrc]
    dt = np.broadcast_to(tofs[None, :] * DAY, (n, len(tofs))).astype(float)
    v1, v2, dth = lambert(r1, r2, dt)
    vd = np.linalg.norm(v1 - va[:, None, :], axis=-1)
    va_ = np.linalg.norm(v2 - vb[arrc], axis=-1)
    vd[~ok] = np.nan
    va_[~ok] = np.nan
    return vd, va_, np.degrees(dth)


def load_all():
    print("Ephemeris (JPL Horizons, heliocentric ecliptic J2000)")
    pe, pm = fetch_vectors("399", "earth"), fetch_vectors("499", "mars")
    _, re, ve = load_vectors(pe)
    _, rm, vm = load_vectors(pm)
    return re, ve, rm, vm


# ----------------------------------------------------------------------------- windows
TOFS = np.arange(70, 401, 2)
FAST = (210, 180, 150, 120, 100)


def scan(re, ve, rm, vm):
    opp = oppositions(re, rm)
    print("Oppositions:", ", ".join(iso(i) for i in opp))
    vd_o, va_o, th_o = grid(re, ve, rm, vm, TOFS)     # Earth → Mars
    vd_r, va_r, th_r = grid(rm, vm, re, ve, TOFS)     # Mars → Earth
    rows_o, rows_r = [], []
    for k, io in enumerate(opp):
        dist_au = float(np.linalg.norm(rm[io] - re[io]) / AU)
        for label, vd, va, th, lo, hi, rows in (("out", vd_o, va_o, th_o, io - 260, io - 10, rows_o),
                                                ("ret", vd_r, va_r, th_r, io - 330, io - 40, rows_r)):
            lo, hi = max(lo, 0), min(hi, len(re) - 1)
            if hi - lo < 60:
                continue
            sub_d, sub_a = vd[lo:hi], va[lo:hi]
            total = sub_d + sub_a
            if np.all(np.isnan(total)):
                continue
            picks = [("min-energy", None)] + [(f"{t} d", t) for t in FAST]
            for name, tof in picks:
                if tof is None:
                    i, j = np.unravel_index(np.nanargmin(total), total.shape)
                else:
                    j = int(np.argmin(np.abs(TOFS - tof)))
                    col = total[:, j]
                    if np.all(np.isnan(col)):
                        continue
                    i = int(np.nanargmin(col))
                d, t = lo + int(i), int(TOFS[j])
                rows.append({"opposition": iso(io), "opp_dist_au": round(dist_au, 3), "leg": label, "option": name,
                             "depart": iso(d), "arrive": iso(d + t), "tof_d": t,
                             "vinf_dep": round(float(sub_d[i, j]), 2), "vinf_arr": round(float(sub_a[i, j]), 2),
                             "c3_dep": round(float(sub_d[i, j]) ** 2, 1), "transfer_deg": round(float(th[d, j]), 0),
                             "dep_idx": d})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("windows_outbound.csv", rows_o), ("windows_return.csv", rows_r)):
        with (OUT / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return opp, rows_o, rows_r, (vd_o, va_o, vd_r, va_r)


def show(rows, title):
    print(f"\n{title}")
    print(f"{'opposition':<11}{'option':<11}{'depart':<11}{'arrive':<11}{'tof':>4}{'v∞dep':>7}{'v∞arr':>7}{'C3':>6}{'θ°':>5}")
    last = None
    for r in rows:
        if r["opposition"] != last:
            print(f"-- opposition {r['opposition']} ({r['opp_dist_au']} AU)")
            last = r["opposition"]
        print(f"{'':<11}{r['option']:<11}{r['depart']:<11}{r['arrive']:<11}{r['tof_d']:>4}{r['vinf_dep']:>7}{r['vinf_arr']:>7}{r['c3_dep']:>6}{r['transfer_deg']:>5.0f}")


# ----------------------------------------------------------------------------- missions
CAPS = {"earth_dep_vinf": 4.47, "mars_arr_vinf": 4.0, "mars_dep_vinf": 4.5, "earth_arr_vinf": 4.5}
CAPS_NOTE = ("Assumed transport capability (ours, adjustable): Earth departure C3 ≤ 20 km²/s², Mars arrival v∞ ≤ 4.0 km/s, "
             "Mars departure v∞ ≤ 4.5 km/s, Earth arrival v∞ ≤ 4.5 km/s (entry ≈ 12 km/s). Within these caps the planner "
             "picks the shortest transfer in each window.")
LANDING_SITE = {"name": "Gale crater (Aeolis Palus)", "lat": -4.59, "lon_e": 137.44,
                "why": "Curiosity has measured weather (REMS) and radiation (RAD) here since 2012, so the simulated "
                       "environment can replay real measurements from the same place and season."}


def fastest(vd, va, lo, hi, cap_d, cap_a):
    """Shortest transfer within the v∞ caps for departures in [lo, hi). Returns (dep_idx, tof, vd, va) or None."""
    lo, hi = max(lo, 0), min(hi, vd.shape[0])
    sd, sa = vd[lo:hi], va[lo:hi]
    ok = (sd <= cap_d) & (sa <= cap_a)
    if not ok.any():
        return None
    j = int(np.argmax(ok.any(axis=0)))                 # first (shortest) feasible tof column
    col = np.where(ok[:, j], sd[:, j] + sa[:, j], np.inf)
    i = int(np.argmin(col))
    return lo + i, int(TOFS[j]), float(sd[i, j]), float(sa[i, j])


def fixed(vd, va, lo, hi, tof):
    lo, hi = max(lo, 0), min(hi, vd.shape[0])
    j = int(np.argmin(np.abs(TOFS - tof)))
    col = vd[lo:hi, j] + va[lo:hi, j]
    if np.all(np.isnan(col)):
        return None
    i = int(np.nanargmin(col))
    return lo + i, int(TOFS[j]), float(vd[lo + i, j]), float(va[lo + i, j])


def minimum(vd, va, lo, hi):
    lo, hi = max(lo, 0), min(hi, vd.shape[0])
    tot = vd[lo:hi] + va[lo:hi]
    if np.all(np.isnan(tot)):
        return None
    i, j = np.unravel_index(np.nanargmin(tot), tot.shape)
    return lo + int(i), int(TOFS[j]), float(vd[lo + i, j]), float(va[lo + i, j])


def mission(out, ret, label):
    if not out or not ret:
        return None
    d0, t0, vd0, va0 = out
    d1, t1, vd1, va1 = ret
    arr, back = d0 + t0, d1 + t1
    stay = d1 - arr
    if stay < 20:
        return None
    return {"option": label, "launch": iso(d0), "mars_arrival": iso(arr), "mars_departure": iso(d1), "earth_return": iso(back),
            "outbound_days": t0, "surface_days": stay, "return_days": t1, "total_days": back - d0,
            "deep_space_days": t0 + t1, "earth_dep_vinf": round(vd0, 2), "earth_dep_c3": round(vd0 ** 2, 1),
            "tmi_dv_from_leo": round(tmi_dv(vd0), 2), "mars_arr_vinf": round(va0, 2),
            "mars_entry_speed": round(entry_speed(va0, MU_MARS, R_MARS + 125), 2), "mars_dep_vinf": round(vd1, 2),
            "earth_arr_vinf": round(va1, 2), "earth_entry_speed": round(entry_speed(va1, MU_EARTH, R_EARTH + 122), 2),
            "_idx": (d0, t0, d1, t1)}


def compare(opp, grids):
    vd_o, va_o, vd_r, va_r = grids
    rows = []
    for k in range(len(opp) - 1):
        io, inext = opp[k], opp[k + 1]
        wo, wr = (io - 260, io - 10), (inext - 330, inext - 40)
        variants = (
            ("reference (shortest within caps)",
             fastest(vd_o, va_o, *wo, CAPS["earth_dep_vinf"], CAPS["mars_arr_vinf"]),
             fastest(vd_r, va_r, *wr, CAPS["mars_dep_vinf"], CAPS["earth_arr_vinf"])),
            ("minimum energy", minimum(vd_o, va_o, *wo), minimum(vd_r, va_r, *wr)),
            ("fast 150 d legs", fixed(vd_o, va_o, *wo, 150), fixed(vd_r, va_r, *wr, 150)),
            ("fast 120 d legs", fixed(vd_o, va_o, *wo, 120), fixed(vd_r, va_r, *wr, 120)),
        )
        for label, o, r in variants:
            m = mission(o, r, label)
            if m:
                m["window"] = date_of(io - 96).year          # opportunity named by its Hohmann launch year
                m["opposition"] = iso(io)
                rows.append(m)
    return rows


def short_stay(grids, m, stays=(30, 45, 60)):
    """Direct (no Venus swing-by) return after a short stay: shows why short-stay missions cost so much."""
    _, _, vd_r, va_r = grids
    d0, t0, _, _ = m["_idx"]
    arr = d0 + t0
    out = []
    for s in stays:
        r = minimum(vd_r, va_r, arr + s, arr + s + 1)
        if r:
            out.append({"stay_days": s, "return_days": r[1], "mars_dep_vinf": round(r[2], 2), "earth_arr_vinf": round(r[3], 2),
                        "earth_entry_speed": round(entry_speed(r[3], MU_EARTH, R_EARTH + 122), 2),
                        "total_days": t0 + s + r[1]})
    return out


def angle(a, b):
    return math.degrees(math.acos(max(-1, min(1, float(np.dot(a, b)) / (float(np.linalg.norm(a)) * float(np.linalg.norm(b)))))))


def calendar(m, re, ve, rm, vm, pre=30, post=45):
    d0, t0, d1, t1 = m["_idx"]
    arr, back = d0 + t0, d1 + t1
    v_out, _, _ = lambert(re[d0][None, :], rm[arr][None, :], np.array([t0 * DAY]))
    v_ret, _, _ = lambert(rm[d1][None, :], re[back][None, :], np.array([t1 * DAY]))
    rows, track = [], {"outbound": [], "return": [], "earth": [], "mars": [], "ship": []}
    landing = date_of(arr)
    for i in range(d0 - pre, back + post + 1):
        day = i - d0
        dt = date_of(i)
        if i < d0:
            phase, rp = "prelaunch", re[i]
        elif i < arr:
            phase, rp = "outbound", kepler(re[d0], v_out[0], (i - d0) * DAY)
            track["outbound"].append(rp)
        elif i <= d1:
            phase, rp = "surface", rm[i]
        elif i < back:
            phase, rp = "return", kepler(rm[d1], v_ret[0], (i - d1) * DAY)
            track["return"].append(rp)
        else:
            phase, rp = "recovery", re[i]
        for key, vec in (("earth", re[i]), ("mars", rm[i]), ("ship", rp)):
            track[key].append([round(float(vec[0]) / AU, 4), round(float(vec[1]) / AU, 4)])
        on_earth = phase in ("prelaunch", "recovery")
        d_e = 0.0 if on_earth else float(np.linalg.norm(rp - re[i]))
        d_s = float(np.linalg.norm(rp))
        near = on_earth or d_e < 1e5            # on or just leaving Earth: no Sun-angle geometry yet
        sep = "" if near else round(angle(-re[i], rp - re[i]), 2)
        spe = "" if near else round(angle(-rp, re[i] - rp), 2)
        lt = d_e / C_KM_S / 60
        sol = int((dt - landing).total_seconds() // SOL) + 1 if phase == "surface" else ""
        ls = mars_ls(dt)
        comm = "" if on_earth else "ok" if near else ("blackout" if sep < 2 else "degraded" if sep < 5 else "ok")
        rows.append({"date_utc": dt.strftime("%Y-%m-%d"), "mission_day": day, "phase": phase, "sol": sol,
                     "dist_earth_au": round(d_e / AU, 5), "dist_sun_au": round(d_s / AU, 5),
                     "light_time_min": round(lt, 3), "sun_earth_probe_deg": sep, "mars_ls_deg": round(ls, 2),
                     "round_trip_min": round(2 * lt, 3), "sun_probe_earth_deg": spe, "comm": comm,
                     "mars_year": mars_year(dt), "mars_season": season(ls),
                     "gravity_g": 1.0 if on_earth else 0.38 if phase == "surface" else 0.0,
                     "solar_flux_rel_1au": round((AU / d_s) ** 2, 4),
                     "earth_mars_au": round(float(np.linalg.norm(rm[i] - re[i])) / AU, 5)})
    end_out = float(np.linalg.norm(kepler(re[d0], v_out[0], t0 * DAY) - rm[arr]))
    end_ret = float(np.linalg.norm(kepler(rm[d1], v_ret[0], t1 * DAY) - re[back]))
    return rows, track, (end_out, end_ret)


def lighttime_table(re, rm):
    """Earth–Mars one-way light time for every day of the ephemeris span (geometric range)."""
    path = OUT / f"earth_mars_lighttime_{EPH_START[:4]}-{int(EPH_STOP[:4]) - 1}_daily.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date_utc", "earth_mars_au", "one_way_light_min", "sun_earth_mars_deg", "comm", "mars_ls_deg", "mars_year"])
        for i in range(len(re) - 1):
            d = float(np.linalg.norm(rm[i] - re[i]))
            sep = angle(-re[i], rm[i] - re[i])
            dt = date_of(i)
            w.writerow([dt.strftime("%Y-%m-%d"), round(d / AU, 5), round(d / C_KM_S / 60, 3), round(sep, 2),
                        "blackout" if sep < 2 else "degraded" if sep < 5 else "ok", round(mars_ls(dt), 2), mars_year(dt)])
    return path


def solar_context():
    """Smoothed sunspot number, observed + projected, if the environment lane has written it."""
    path = ROOT / "data" / "reference" / "solar_cycle_projection.json"
    return json.loads(path.read_text()) if path.exists() else None


def render_html(doc, cal, track, re, rm):
    tpl = (ROOT / "tools" / "mission_plan_template.html").read_text()
    d0 = int((datetime.strptime(doc["launch_utc"], "%Y-%m-%d").replace(tzinfo=timezone.utc) - T0).days)
    xy = lambda arr: [[round(float(v[0]) / AU, 4), round(float(v[1]) / AU, 4)] for v in arr]
    keep = ("date_utc", "mission_day", "phase", "sol", "dist_earth_au", "light_time_min", "round_trip_min", "comm",
            "mars_ls_deg", "mars_season", "gravity_g")
    data = {"plan": doc, "calendar": [{k: c[k] for k in keep} for c in cal], "caps_note": CAPS_NOTE,
            "orbit_earth": xy(re[d0:d0 + 366:3]), "orbit_mars": xy(rm[d0:d0 + 688:3]),
            "track_out": xy(track["outbound"]), "track_ret": xy(track["return"]),
            "pos_earth": track["earth"], "pos_mars": track["mars"], "pos_ship": track["ship"], "solar": solar_context()}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out = OUT / "mission_plan.html"
    page = tpl.replace("/*__DATA__*/null", blob)
    out.write_text(page)
    print(f"  page → {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    site = ROOT / "mocks" / "mission.html"                # same page inside the preview site, with its navigation
    if site.parent.exists():
        site.write_text(page.replace("</body>", '<script src="assets/nav.js" defer></script>\n</body>'))
        print(f"  page → {site.relative_to(ROOT)}")


def plan(re, ve, rm, vm, opp, grids, window=2037):
    rows = compare(opp, grids)
    pub = [{k: v for k, v in r.items() if k != "_idx"} for r in rows]
    with (OUT / "missions_compared.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["window", "opposition"] + [k for k in pub[0] if k not in ("window", "opposition")])
        w.writeheader()
        w.writerows(pub)
    print(f"\nMissions compared (long-stay, return in the next window)\n{CAPS_NOTE}")
    print(f"{'win':<5}{'option':<34}{'launch':<11}{'land':<11}{'leave':<11}{'back':<11}{'out':>4}{'stay':>5}{'ret':>4}{'tot':>5}{'v∞E':>6}{'v∞M':>6}{'v∞M↑':>6}{'v∞E↓':>6}")
    for r in rows:
        print(f"{r['window']:<5}{r['option']:<34}{r['launch']:<11}{r['mars_arrival']:<11}{r['mars_departure']:<11}{r['earth_return']:<11}"
              f"{r['outbound_days']:>4}{r['surface_days']:>5}{r['return_days']:>4}{r['total_days']:>5}"
              f"{r['earth_dep_vinf']:>6}{r['mars_arr_vinf']:>6}{r['mars_dep_vinf']:>6}{r['earth_arr_vinf']:>6}")
    chosen = next(r for r in rows if r["window"] == window and r["option"].startswith("reference"))
    cal, track, err = calendar(chosen, re, ve, rm, vm)
    with (OUT / "mission_calendar.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cal[0].keys()))
        w.writeheader()
        w.writerows(cal)
    surf = [c for c in cal if c["phase"] == "surface"]
    away = [c for c in cal if c["phase"] in ("outbound", "surface", "return")]
    black = [c["date_utc"] for c in away if c["comm"] == "blackout"]
    degr = [c["date_utc"] for c in away if c["comm"] in ("blackout", "degraded")]
    mx = max(away, key=lambda c: c["light_time_min"])
    mn_s = min(surf, key=lambda c: c["light_time_min"])
    dust = [c for c in surf if 180 <= c["mars_ls_deg"] < 360]
    d0, t0, d1, t1 = chosen["_idx"]
    lt_path = lighttime_table(re, rm)
    doc = {
        "name": f"Mars {window} long-stay reference mission", "class": "conjunction class (long stay)",
        "launch_utc": chosen["launch"], "mars_arrival_utc": chosen["mars_arrival"],
        "mars_departure_utc": chosen["mars_departure"], "earth_return_utc": chosen["earth_return"],
        "outbound_days": chosen["outbound_days"], "surface_days": chosen["surface_days"],
        "surface_sols": round(chosen["surface_days"] * DAY / SOL), "return_days": chosen["return_days"],
        "total_days": chosen["total_days"], "deep_space_days": chosen["deep_space_days"],
        "landing_site": LANDING_SITE,
        "energy": {k: chosen[k] for k in ("earth_dep_vinf", "earth_dep_c3", "tmi_dv_from_leo", "mars_arr_vinf",
                                          "mars_entry_speed", "mars_dep_vinf", "earth_arr_vinf", "earth_entry_speed")},
        "communication": {
            "max_one_way_light_min": mx["light_time_min"], "max_light_date": mx["date_utc"],
            "min_one_way_light_min_on_surface": mn_s["light_time_min"], "min_light_date_on_surface": mn_s["date_utc"],
            "light_min_at_landing": surf[0]["light_time_min"], "light_min_at_mars_departure": surf[-1]["light_time_min"],
            "conjunction_blackout": {"rule": "Sun–Earth–Mars angle < 2° (commanding moratorium), < 5° degraded",
                                     "blackout_first": black[0] if black else None, "blackout_last": black[-1] if black else None,
                                     "blackout_days": len(black), "degraded_first": degr[0] if degr else None,
                                     "degraded_last": degr[-1] if degr else None, "degraded_days": len(degr)}},
        "mars_season": {"ls_at_landing": surf[0]["mars_ls_deg"], "season_at_landing": surf[0]["mars_season"],
                        "mars_year_at_landing": surf[0]["mars_year"], "ls_at_departure": surf[-1]["mars_ls_deg"],
                        "dust_season_days_on_surface": len(dust),
                        "dust_season_first": dust[0]["date_utc"] if dust else None,
                        "dust_season_last": dust[-1]["date_utc"] if dust else None},
        "assumptions": [CAPS_NOTE, "Patched conics, zero-revolution prograde Lambert arcs between planet centres; "
                        "JPL Horizons ephemerides (DE441), daily steps; dates are UTC days (TDB vectors, ≤ 70 s offset).",
                        "No launch-period, parking-orbit, aerocapture or propulsion design: dates are a reference, not a flight plan.",
                        f"Lambert arc closure check: {err[0]:.0f} km (outbound), {err[1]:.0f} km (return)."],
        "short_stay_direct_return_for_comparison": short_stay(grids, chosen),
        "alternatives": [r for r in pub if r["option"].startswith("reference")],
        "variants_this_window": [r for r in pub if r["window"] == window],
        "files": {"calendar": "data/mission/mission_calendar.csv", "windows_outbound": "data/mission/windows_outbound.csv",
                  "windows_return": "data/mission/windows_return.csv", "missions_compared": "data/mission/missions_compared.csv",
                  "lighttime_daily": str(lt_path.relative_to(ROOT))},
    }
    (OUT / "mission_plan.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"\nChosen: {doc['name']}")
    for k in ("launch_utc", "mars_arrival_utc", "mars_departure_utc", "earth_return_utc", "outbound_days", "surface_days",
              "surface_sols", "return_days", "total_days"):
        print(f"  {k}: {doc[k]}")
    print("  energy:", doc["energy"])
    print("  communication:", json.dumps(doc["communication"], ensure_ascii=False))
    print("  mars_season:", doc["mars_season"])
    print("  short stay (direct return):", doc["short_stay_direct_return_for_comparison"])
    print("  closure km:", [round(e) for e in err])
    render_html(doc, cal, track, re, rm)
    print("  Ls check 2024-11-12 (expect ≈0):", round(mars_ls(datetime(2024, 11, 12, 12, tzinfo=timezone.utc)), 2),
          "| MY", mars_year(datetime(2024, 11, 13, tzinfo=timezone.utc)))
    return doc, cal, track, rows




if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    re_, ve_, rm_, vm_ = load_all()
    opp_, ro_, rr_, grids_ = scan(re_, ve_, rm_, vm_)
    if cmd in ("windows", "all"):
        show(ro_, "Earth → Mars (v∞ km/s, C3 km²/s²)")
        show(rr_, "Mars → Earth")
    if cmd in ("plan", "all"):
        plan(re_, ve_, rm_, vm_, opp_, grids_)
