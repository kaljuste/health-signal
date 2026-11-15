"""Embed mocks/content/risks.json into mocks/risks.html (so the page also opens from file://).
Usage: python3 -I mocks/content/embed_risks.py      (run after editing risks.json)"""
import json, pathlib, re, sys
here = pathlib.Path(__file__).resolve().parent
data = json.loads((here / "risks.json").read_text(encoding="utf-8"))
page = here.parent / "risks.html"
html = page.read_text(encoding="utf-8")
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
block = '<!--RISKS_JSON_START--><script type="application/json" id="risks-data">' + blob + "</script><!--RISKS_JSON_END-->"
new, n = re.subn(r"<!--RISKS_JSON_START-->.*?<!--RISKS_JSON_END-->", lambda m: block, html, flags=re.S)
if n != 1:
    sys.exit("marker not found in risks.html")
page.write_text(new, encoding="utf-8")
print(f"embedded {len(data)} risks ({len(blob):,} bytes) into {page.name}")
