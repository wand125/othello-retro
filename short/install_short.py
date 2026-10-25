"""Add only /short routes to the deployed image; never copy a shared workspace app."""
from pathlib import Path

path = Path("/app/cloud/app.py")
text = path.read_text()
assets = '''        "/short/app.js": ("short.js", "text/javascript; charset=utf-8"),
        "/short/app.css": ("short.css", "text/css; charset=utf-8"),
'''
route = '''        if path.path in {"/short", "/short/"}:
            html = (Path(local.HERE) / "short.html").read_text()
            return self.send(200, html.replace("__SHORT_CONFIG__", json.dumps({"maxSeconds": MAX_SECONDS})), "text/html; charset=utf-8")
'''
if '"/short/app.js"' not in text:
    anchor = "    PUBLIC_ASSETS = {\n"
    assert text.count(anchor) == 1, "Unexpected deployed static asset layout"
    text = text.replace(anchor, anchor + assets, 1)
if 'path.path in {"/short", "/short/"}' not in text:
    anchor = '        if path.path in {"/paper", "/paper/"}:\n'
    assert text.count(anchor) == 1, "Unexpected deployed route layout"
    text = text.replace(anchor, route + anchor, 1)
compile(text, str(path), "exec")
path.write_text(text)
