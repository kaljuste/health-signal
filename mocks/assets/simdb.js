/* Reads the simulated mission (SQLite) in the browser with sql.js.
   Usage:
     <script src="vendor/sqljs/sql-wasm.js"></script>
     <script src="assets/simdb.js"></script>
     SimDB.ready.then(() => { const rows = SimDB.q("select * from day where day = ?", [356]); });
   The page must be opened through the preview server (python3 -I tools/serve_preview.py): browsers do not let a
   file:// page read a database file. */
(function () {
  const DB_URLS = ["db/mission_sim.sqlite", "../data/sim/mission_sim.sqlite"];
  const S = { status: "loading", error: null, db: null, meta: {}, vars: {}, crew: {} };
  if (window.SIM_AUDIENCE) {            // the audience view of the arm unit gets a light data pack from the server, not the database
    S.status = "audience"; S.q = () => []; S.one = () => null; S.ready = new Promise(() => {});
    window.SimDB = S; return;
  }

  async function fetchFirst(urls) {
    let last;
    for (const u of urls) {
      try {
        const r = await fetch(u, { cache: "no-cache" });
        if (r.ok) return new Uint8Array(await r.arrayBuffer());
        last = new Error(u + ": HTTP " + r.status);
      } catch (e) { last = e; }
    }
    throw last || new Error("database not found");
  }

  S.q = function (sql, params) {
    const st = S.db.prepare(sql);
    try {
      if (params) st.bind(params);
      const out = [];
      while (st.step()) out.push(st.getAsObject());
      return out;
    } finally { st.free(); }
  };
  S.one = (sql, params) => S.q(sql, params)[0] || null;
  S.col = (sql, params) => S.q(sql, params).map(r => Object.values(r)[0]);

  /* Small helpers both apps use */
  S.fmt = function (varId, v) {
    if (v === null || v === undefined) return "–";
    const d = (S.vars[varId] || {}).decimals;
    return Number(v).toFixed(d === undefined || d === null ? 1 : d);
  };
  S.dayRow = d => S.one("select * from day where day = ?", [d]);
  S.dayOfDate = iso => { const r = S.one("select day from day where date_utc = ?", [iso]); return r ? r.day : null; };
  S.clampDay = d => Math.max(+S.meta.day_first, Math.min(+S.meta.day_last, Math.round(d)));
  /* Label for a mission day: "Day 356 · Sol 180 · 25 Aug 2038" */
  S.dayLabel = function (d) {
    const r = S.dayRow(d); if (!r) return "";
    const dt = new Date(r.date_utc + "T12:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
    const where = r.phase === "prelaunch" ? "before launch" : r.phase === "recovery" ? "back on Earth, day " + r.phase_day
      : r.phase === "surface" ? "sol " + r.sol : (r.phase === "outbound" ? "outbound" : "homebound") + " day " + r.phase_day;
    return { day: d, date: dt, where, phase: r.phase, text: (d < 0 ? "Launch minus " + (-d) : "Mission day " + d) + " · " + where + " · " + dt };
  };

  function banner(msg) {
    const b = document.createElement("div");
    b.setAttribute("role", "alert");
    b.style.cssText = "position:fixed;left:16px;right:16px;bottom:16px;z-index:99;padding:14px 18px;border:1px solid #706e68;border-left:3px solid #e5522c;border-radius:12px;background:#171717;color:#e8e4d8;font:400 14px/1.5 Manrope,sans-serif";
    const t = document.createElement("b"); t.textContent = "The simulated mission could not be loaded. ";
    const s = document.createElement("span"); s.textContent = msg;
    const c = document.createElement("code"); c.textContent = " python3 -I tools/serve_preview.py"; c.style.color = "#ffb39e";
    const e = document.createElement("span"); e.textContent = "  then open http://127.0.0.1:8037/";
    b.append(t, s, c, e); document.body.append(b);
  }

  S.ready = (async function () {
    try {
      if (typeof initSqlJs !== "function") throw new Error("sql.js is not loaded");
      const SQL = await initSqlJs({ locateFile: f => "vendor/sqljs/" + f });
      S.db = new SQL.Database(await fetchFirst(DB_URLS));
      S.q("select key, value from meta").forEach(r => { S.meta[r.key] = r.value; });
      S.q("select * from variable order by sort").forEach(r => { S.vars[r.var_id] = r; });
      S.q("select * from crew").forEach(r => { r.baseline = JSON.parse(r.baseline_json); S.crew[r.crew_id] = r; });
      S.status = "ok";
      document.dispatchEvent(new CustomEvent("simdb-ready"));
      return S;
    } catch (e) {
      S.status = "error"; S.error = e;
      const reason = location.protocol === "file:" ? "This page was opened as a file. Start the preview server:" : "Start the preview server (" + (e && e.message || e) + "):";
      if (document.body) banner(reason); else addEventListener("DOMContentLoaded", () => banner(reason));
      throw e;
    }
  })();
  S.ready.catch(() => {});
  window.SimDB = S;
})();
