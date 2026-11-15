/* Top navigation for the site. Usage: <script src="assets/nav.js" defer></script>
   The tabs follow the story: the problem, how it works, the mission, the risks, what is measured,
   then where the data comes from (real data, the simulation, the database).
   The two apps are what we built: they are not tabs but two app buttons with their icons, always in view at the right.
   For the presenter it also loads the presentation layer (assets/present.js): slides for each tab and the live view. */
(function () {
  if (window.NO_SITENAV) return;       // full-screen views (the live audience view) carry no site navigation
  /* Pass link with visitor keys (#or=…&el=…, the public site): assets/assistant.js stores them and removes the fragment.
     The two apps load it themselves; every other page loads it only when such a fragment is there. */
  if (/(?:^#|&)(?:or|el)=/.test(location.hash) && !window.Assistant) { const s = document.createElement("script"); s.src = "assets/assistant.js"; document.head.append(s); }
  const PAGES = [
    ["index.html", "Overview"], ["system.html", "How it works"], ["mission.html", "Mission"], ["risks.html", "Risks"], ["measures.html", "Measures"],
    null,
    ["sources.html", "Data"], ["simulation.html", "Simulation"], ["database.html", "Database"]
  ];
  const APPS = [["habitat.html", "Habitat App", "assets/hs/app-habitat.svg", "Open the Habitat App: the crew's health, every day of the mission"],
                ["arm_unit.html", "Arm Unit", "assets/hs/app-arm.svg", "Open the Arm Unit: the suit's forearm screen on a Mars walk"]];
  const here = (location.pathname.split("/").pop() || "index.html");
  const bar = document.createElement("header"); bar.className = "sitenav";
  const name = document.createElement("a"); name.className = "name"; name.href = "index.html"; name.setAttribute("aria-label", "Health Signal, overview");
  { const m = document.createElement("img"); m.src = "assets/hs/mark.svg"; m.alt = ""; m.width = 24; m.height = 24; const t = document.createElement("span"); t.textContent = "Health Signal"; name.append(m, t); }
  const nav = document.createElement("nav"); nav.setAttribute("aria-label", "Site");
  PAGES.forEach(p => {
    if (!p) { const s = document.createElement("span"); s.className = "sep"; nav.append(s); return; }
    const a = document.createElement("a"); a.href = p[0]; a.textContent = p[1];
    if (p[0] === here) a.setAttribute("aria-current", "page");
    nav.append(a);
  });
  const apps = document.createElement("div"); apps.className = "navapps"; apps.setAttribute("role", "navigation"); apps.setAttribute("aria-label", "The two apps");
  APPS.forEach(p => {
    const a = document.createElement("a"); a.className = "navapp"; a.href = p[0]; a.title = p[3];
    const ic = document.createElement("img"); ic.src = p[2]; ic.alt = ""; ic.width = 26; ic.height = 26;
    const t = document.createElement("span"); t.textContent = p[1]; a.append(ic, t);
    if (p[0] === here) a.setAttribute("aria-current", "page");
    apps.append(a);
  });
  const note = document.createElement("span"); note.className = "note"; note.textContent = "Simulated data";
  bar.append(name, nav, apps, note);
  /* Language: German is a layer (assets/i18n.js + content/i18n/); the tiny switch sits in the bar's lower right corner (takes no room). */
  const lang = (() => { try { return new URLSearchParams(location.search).get("lang") || localStorage.getItem("hs.lang") || "en"; } catch (e) { return "en"; } })() === "de" ? "de" : "en";
  const ls = document.createElement("span"); ls.className = "lang"; ls.setAttribute("data-i18n-skip", ""); ls.title = "Deutsch (KI-Übersetzung, noch nicht geprüft)";
  ["de", "en"].forEach((l, i) => { if (i) ls.append(" · "); const b = document.createElement("a"); b.href = "?lang=" + l; b.textContent = l.toUpperCase(); if (l === lang) b.setAttribute("aria-current", "true"); b.onclick = e => { e.preventDefault(); try { localStorage.setItem("hs.lang", l); } catch (x) {} const u = new URL(location.href); u.searchParams.delete("lang"); location.replace(u.href); }; ls.append(b); });
  bar.insertBefore(ls, note); { const s = document.createElement("script"); s.src = "assets/i18n.js"; document.head.append(s); }
  if (!document.querySelector('link[href$="assets/site.css"]') && !getComputedStyle(document.documentElement).getPropertyValue("--x-nav-h")) {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "assets/site.css"; document.head.append(l);
  }
  if (!document.querySelector('link[rel="icon"]')) {
    for (const [rel, href, type, sizes] of [["icon", "assets/hs/favicon.svg", "image/svg+xml", "any"], ["icon", "assets/hs/icon-32.png", "image/png", "32x32"], ["apple-touch-icon", "assets/hs/apple-touch-icon.png", "", ""]]) {
      const ic = document.createElement("link"); ic.rel = rel; ic.href = href; if (type) ic.type = type; if (sizes) ic.setAttribute("sizes", sizes); document.head.append(ic);
    }
  }
  const st = document.createElement("style");
  st.textContent = ".sitenav{position:fixed;inset:0 0 auto 0;height:44px;z-index:50;display:flex;align-items:stretch;gap:20px;padding:0 20px;background:rgba(6,6,6,.94);backdrop-filter:blur(6px);border-bottom:1px solid #2b2b2b}"
    + ".sitenav .name{display:flex;align-items:center;gap:8px;flex:none;font:600 13px/1.2 'Chakra Petch',sans-serif;letter-spacing:1.56px;text-transform:uppercase;color:#ddd6c5;text-decoration:none;white-space:nowrap}"
    + ".sitenav .name img{display:block}"
    + ".sitenav nav{display:flex;align-items:stretch;gap:2px;overflow-x:auto;scrollbar-width:none;min-width:0;flex:1 1 auto}"
    + ".sitenav .navapps{display:flex;align-items:center;gap:8px;flex:none}"
    + ".sitenav .navapp{display:flex;align-items:center;gap:8px;height:34px;padding:0 12px 0 4px;border:1px solid #4a4640;border-radius:10px;background:#181716;color:#e8e4d8;font:600 13px/1 'Manrope',sans-serif;text-decoration:none;white-space:nowrap;transition:border-color .15s,background .15s}"
    + ".sitenav .navapp img{display:block;border-radius:7px}"
    + ".sitenav .navapp:hover{border-color:#e5522c;background:#211f1d;color:#fff}"
    + ".sitenav .navapp[aria-current=page]{border-color:#e5522c;box-shadow:inset 0 0 0 1px #e5522c}"
    + ".sitenav nav a{display:flex;align-items:center;padding:3px 10px 0;font:400 13px/1.4 'Manrope',sans-serif;color:#9a968c;text-decoration:none;border-bottom:3px solid transparent;white-space:nowrap}"
    + ".sitenav nav a:hover{color:#e8e4d8}.sitenav nav a[aria-current=page]{color:#ddd6c5;border-bottom-color:#e5522c}"
    + ".sitenav .sep{width:1px;background:#2b2b2b;margin:10px 4px;flex:none}"
    + ".sitenav .note{display:flex;align-items:center;font:600 11px/1 'Chakra Petch',sans-serif;letter-spacing:1px;text-transform:uppercase;color:#9a968c;white-space:nowrap}"
    + ".sitenav .lang{position:absolute;right:6px;bottom:0;font:400 9px/1 'Manrope',sans-serif;letter-spacing:.5px;color:#57554f;white-space:nowrap}.sitenav .lang a{color:#706e68;text-decoration:none;padding:1px 2px}.sitenav .lang a:hover{color:#e8e4d8}.sitenav .lang a[aria-current]{color:#b3aea2}body.hs-presenting .sitenav .lang{display:none}"
    + "@media (max-width:1320px){.sitenav .name span{display:none}}body.hs-presenting .sitenav .name span{display:none}"
    + "@media (max-width:1120px){.sitenav .note{display:none}.sitenav{gap:14px}.sitenav nav a{padding:3px 7px 0}}"
    + "@media (max-width:760px){.sitenav{gap:10px;padding:0 10px}.sitenav .navapp{padding:0 3px;border-radius:9px}.sitenav .navapp span{display:none}}"
    + "body{padding-top:44px}";
  document.head.append(st);
  document.body.classList.add("has-sitenav");
  document.body.prepend(bar);
  const cur = nav.querySelector("[aria-current]"); if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest", inline: "nearest" });

  /* Presentation layer: for the presenter only (this machine, the team's tailnet, or a browser holding the presenter key),
     or for anyone who opens a page with ?present=1 (slides only; the live stream still needs the key). */
  const load = src => new Promise(res => { const s = document.createElement("script"); s.src = src; s.onload = s.onerror = res; document.head.append(s); });
  const want = new URLSearchParams(location.search).get("present");
  try { if (want === "1") localStorage.setItem("hs.present", "1"); if (want === "0") localStorage.removeItem("hs.present"); } catch (e) {}
  (async function () {
    let ok = false; try { ok = localStorage.getItem("hs.present") === "1"; } catch (e) {}
    if (!ok) {
      let k = null; try { k = sessionStorage.getItem("presenterKey"); } catch (e) {}
      try { const h = await (await fetch("api/health", { cache: "no-store", headers: k ? { "X-Presenter-Key": k } : {} })).json(); ok = !!h.presenter; } catch (e) {}
    }
    if (!ok) return;
    if (!window.HS_BODY) await load("assets/bodyfig.js");      // the body figure on two slides (the habitat app loads it itself)
    await load("assets/slides.js"); await load("assets/sr1.js"); await load("assets/present.js");
    if (window.HSPresent) window.HSPresent.init(bar, here);
  })();
})();
