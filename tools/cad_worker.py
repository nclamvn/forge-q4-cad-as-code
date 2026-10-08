"""Fixed core CAD worker; input is a bounded validated spec, never Python."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from kernel import build,validate
job=Path(sys.argv[1]).resolve()
try:
    data=(job/'spec.json').read_bytes()
    if not 0<len(data)<8192:raise ValueError('CAD spec size exceeded')
    spec=validate(json.loads(data))
    (job/'answer.json').write_text(json.dumps(build(spec),ensure_ascii=False,allow_nan=False))
except Exception as error:
    (job/'error.txt').write_text(str(error));raise
