"""Open an existing FORGE server, or run the local CAD service."""
import json
import runpy
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8767'
def ready():
    try:
        with urllib.request.urlopen(URL+'/api/health',timeout=1) as response:
            return json.load(response).get('kernel')=='build123d / Open Cascade'
    except Exception:return False

if ready():
    webbrowser.open(URL)
else:
    if not (ROOT/'web/default-model.json').exists():
        import kernel,yaml
        model=kernel.build(yaml.safe_load((ROOT/'spec.yaml').read_text()))
        (ROOT/'web/default-model.json').write_text(json.dumps(model,ensure_ascii=False))
    def open_when_ready():
        for _ in range(30):
            if ready():webbrowser.open(URL);return
            time.sleep(.5)
    threading.Thread(target=open_when_ready,daemon=True).start()
    runpy.run_path(str(ROOT/'server.py'),run_name='__main__')
