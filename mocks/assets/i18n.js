/* German layer for the site (runtime translation). Loaded by nav.js on every page with the navigation bar.
   The pages stay English at source. When the language is German, this script swaps English text for German
   from the dictionary in content/i18n/ (de.common.json for everything shared, de.<page>.json per page).
   A text that is not in the dictionary simply stays English, so a changed page never breaks.

   Language: localStorage["hs.lang"] ("en" default, "de"); ?lang=de / ?lang=en in the address sets it.
   Dictionary file: { "strings": { "<English, whitespace normalised>": "<German>" },
                      "patterns": { "Day {1} of {2}": "Tag {1} von {2}" },   {n} stands for a part without letters (numbers, times), {*n} for any text
                      "skip": [ "<CSS selector of parts that stay English>" ] }
   Sentences: an element whose content is only text and inline tags (b, strong, i, em, a, code, span, br, sup, sub,
   small, abbr, mark, u, s, q, time, kbd) is matched as a whole by its normalised innerHTML and replaced with German
   HTML that keeps the same tags (when tags and attributes are the same, only the text nodes are swapped, so
   elements a script holds on to stay in place). Elements with an id or holding elements with an id, data-* or on* attributes are
   never rebuilt: there only single text nodes are swapped. Never touched: script, style, code, pre, form controls,
   canvas, svg, [data-i18n-skip], the app screens and the page's own "skip" selectors
   (form fields outside those keep their value; only their placeholder and aria-label are translated).
   Option texts in a select are translated (their values stay).
   Dynamic content (pages drawn from the SQLite file, slides) is caught by a MutationObserver.
   window.HS_I18N.report() lists what was seen and not translated (used by tools/i18n_coverage.js). */
(function () {
  if (window.HS_I18N) return;
  const KEY = "hs.lang";
  const q = new URLSearchParams(location.search).get("lang");
  try { if (q === "de" || q === "en") localStorage.setItem(KEY, q); } catch (e) {}
  let lang = "en"; try { lang = localStorage.getItem(KEY) === "de" ? "de" : "en"; } catch (e) {}
  const page = (location.pathname.split("/").pop() || "index.html").replace(/\.html$/, "") || "index";

  const API = window.HS_I18N = {
    lang, page,
    set(l) { try { localStorage.setItem(KEY, l); } catch (e) {} const u = new URL(location.href); u.searchParams.delete("lang"); location.replace(u.href); },
    t: s => s, report: () => ({ lang, page, misses: [], used: [] })
  };
  if (lang !== "de") return;
  document.documentElement.lang = "de";

  const INLINE = new Set(["B", "STRONG", "I", "EM", "A", "CODE", "SPAN", "BR", "SUP", "SUB", "SMALL", "ABBR", "MARK", "U", "S", "Q", "TIME", "KBD"]);
  const NEVER = "script,style,code,pre,textarea,input,canvas,svg,noscript,[data-i18n-skip],[contenteditable]";
  const ATTRS = ["title", "placeholder", "aria-label", "alt", "data-l"];   // data-l: labels a page shows through CSS content
  const norm = s => s.replace(/[ \t\n\r\f]+/g, " ").trim();
  const LETTERS = /[A-Za-z]{2}/;
  const strings = new Map(), patterns = [], used = new Set(), misses = new Map();
  let skipSel = NEVER, pageSkip = "[data-i18n-skip],[contenteditable]";   // pageSkip: without the form controls
  const done = new Set();   // German already put on the page (and every dictionary value): not a gap when seen again

  function addDict(d) {
    if (!d) return;
    for (const [k, v] of Object.entries(d.strings || {})) if (typeof v === "string") { strings.set(norm(k), v); done.add(norm(v)); }
    for (const [k, v] of Object.entries(d.patterns || {})) {
      const parts = norm(k).split(/(\{\*?\d+\})/), names = [];
      const re = parts.map(p => { const m = /^\{(\*?)(\d+)\}$/.exec(p); if (m) { names.push(m[2]); return m[1] ? "(.+?)" : "([^A-Za-z]+?)"; } return p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("");
      patterns.push({ key: k, re: new RegExp("^" + re + "$"), names, out: v });
    }
    if (d.skip && d.skip.length) { skipSel += "," + d.skip.join(","); pageSkip += "," + d.skip.join(","); }
  }
  function look(src) {
    const k = norm(src);
    if (!k || !LETTERS.test(k)) return null;
    if (strings.has(k)) { used.add(k); return strings.get(k); }
    for (const p of patterns) {
      const m = p.re.exec(k);
      if (m) { used.add(p.key); return p.out.replace(/\{\*?(\d+)\}/g, (_, n) => { const i = p.names.indexOf(n); return i < 0 ? "" : m[i + 1]; }); }
    }
    return null;
  }
  function miss(k, n) {   // remembers where a gap was seen: on a slide / the presenter's controls, or on the page
    k = norm(k); if (!k || !LETTERS.test(k)) return;
    const e = n && (n.nodeType === 1 ? n : n.parentElement);
    if (!misses.has(k)) misses.set(k, new Set());
    misses.get(k).add(e && e.closest && e.closest("#hsSlide,.hs-pres") ? "slide" : "page");
  }
  API.t = s => look(s) || s;

  const isSkipped = el => !!(el.closest && el.closest(skipSel));
  // An element is a sentence unit if all its content is text and harmless inline tags and it holds text of its own.
  function inlineOnly(el) {
    for (const c of el.childNodes) {
      if (c.nodeType === 3 || c.nodeType === 8) continue;
      if (c.nodeType !== 1 || !INLINE.has(c.tagName) || !inlineOnly(c)) return false;
    }
    return true;
  }
  const ownText = el => [...el.childNodes].some(c => c.nodeType === 3 && c.data.trim());
  const rebuildable = el => !el.id && !el.querySelector("[id]") && ![...el.querySelectorAll("*")].some(e => [...e.attributes].some(a => /^(data-|on)/.test(a.name)));
  const plain = el => !el.querySelector("*");   // text only (and comments)

  // Same tags and attributes in German as on the page: swap only the text, so elements a script holds stay in place.
  const kids = n => [...n.childNodes].filter(c => c.nodeType === 1 || c.nodeType === 3);
  function sameShape(a, b) {
    const x = kids(a), y = kids(b); if (x.length !== y.length) return false;
    return x.every((c, i) => { const d = y[i]; if (c.nodeType !== d.nodeType) return false; if (c.nodeType === 3) return true;
      if (c.tagName !== d.tagName || c.attributes.length !== d.attributes.length || [...c.attributes].some(at => d.getAttribute(at.name) !== at.value)) return false;
      return sameShape(c, d); });
  }
  function copyText(a, b) { const x = kids(a), y = kids(b); x.forEach((c, i) => { if (c.nodeType === 3) { if (c.data !== y[i].data) c.data = y[i].data; } else copyText(c, y[i]); }); }
  function inPlace(el, html) {
    const t = document.createElement("template"); t.innerHTML = html;
    if (!sameShape(el, t.content)) return false;
    copyText(el, t.content); return true;
  }

  function doText(node, quiet) {
    const src = node.data; if (!src.trim()) return;
    const de = look(src);
    if (de == null) { if (!quiet && !done.has(norm(src))) miss(src, node); return; }
    const lead = /^\s*/.exec(src)[0], tail = /\s*$/.exec(src)[0];
    const out = lead + de + tail; done.add(norm(de)); if (out !== src) node.data = out;
  }
  function doAttrs(el) {
    for (const a of ATTRS) {
      const v = el.getAttribute(a); if (!v) continue;
      const de = look(v); if (de == null) { if (!done.has(norm(v))) miss(v, el); continue; }
      done.add(norm(de)); const o = /^\s*/.exec(v)[0] + de + /\s*$/.exec(v)[0]; if (o !== v) el.setAttribute(a, o);
    }
  }
  function walk(el, quiet) {
    if (el.nodeType === 3) { if (el.parentElement && !isSkipped(el.parentElement)) doText(el, quiet); return; }
    if (el.nodeType !== 1) return;
    if (el.matches(skipSel)) { if ((el.tagName === "INPUT" || el.tagName === "TEXTAREA") && !el.closest(pageSkip)) doAttrs(el); return; }   // a field: its hint and label, never its value
    if (ATTRS.some(a => el.hasAttribute(a))) doAttrs(el);
    if (el.childNodes.length && (ownText(el) || el.children.length === 1) && inlineOnly(el) && !plain(el) && rebuildable(el)) {
      const k = norm(el.innerHTML);
      const de = look(k);
      if (de == null && done.has(k)) return;
      if (de != null) {
        if (k !== norm(de) && !inPlace(el, de)) el.innerHTML = de;
        done.add(norm(el.innerHTML)); el.querySelectorAll("*").forEach(e => { for (const c of e.childNodes) if (c.nodeType === 3 && c.data.trim()) done.add(norm(c.data)); });
        for (const c of el.childNodes) if (c.nodeType === 3 && c.data.trim()) done.add(norm(c.data));
        el.querySelectorAll("*").forEach(e => ATTRS.forEach(a => { const v = e.getAttribute(a); if (v) done.add(norm(v)); }));
        el.querySelectorAll("[title],[aria-label]").forEach(doAttrs); return;
      }
      if (LETTERS.test(el.textContent) && !quiet) { miss(k, el); quiet = true; }
    }
    for (const c of [...el.childNodes]) {
      if (c.nodeType === 3) doText(c, quiet); else if (c.nodeType === 1) walk(c, quiet);
    }
  }
  function run(root) { obs && obs.disconnect(); try { walk(root); } finally { obs && observe(); } }

  // Whole-tree pass, then the observer for content drawn later.
  let obs = null; const queued = new Set();
  const observe = () => obs.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  function flush() {
    const list = [...queued]; queued.clear();
    const roots = list.filter(n => n.isConnected && !list.some(o => o !== n && o.contains(n)));
    obs.disconnect();
    try { for (const r of roots) if (!isSkipped(r)) walk(r); } finally { observe(); }
  }
  function onMut(ms) {
    for (const m of ms) {
      const t = m.type === "characterData" ? m.target.parentElement : m.target;
      if (!t || t.nodeType !== 1) continue;
      if (m.type === "attributes") { if (!isSkipped(t)) queued.add(t); continue; }
      // a whole sentence may have been rewritten: re-check from the nearest inline-only ancestor
      let u = t; while (u.parentElement && u.parentElement !== document.body && INLINE.has(u.tagName)) u = u.parentElement;
      queued.add(u);
    }
    if (queued.size) flush();   // still inside the observer's microtask: German is in place before the next paint
  }

  function titleFix() { const t = document.querySelector("title"); if (t) { const de = look(t.textContent); if (de != null) document.title = de; else miss(t.textContent); } }
  const files = ["content/i18n/de.common.json", `content/i18n/de.${page}.json`];
  Promise.all(files.map(f => fetch(f, { cache: "no-cache" }).then(r => r.ok ? r.json() : null).catch(() => null))).then(ds => {
    ds.forEach(addDict);
    const start = () => {
      obs = new MutationObserver(onMut);
      titleFix(); run(document.body);
      API.ready = true; document.dispatchEvent(new CustomEvent("hs:i18n"));
    };
    if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
  });

  API.report = where => ({ lang, page, misses: [...misses.keys()].filter(k => !where || misses.get(k).has(where)), used: [...used] });
  API.rescan = () => run(document.body);
})();
