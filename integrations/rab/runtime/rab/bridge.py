from __future__ import annotations
import json, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from .store import DATA

DEFAULTS = {"host":"127.0.0.1","http_port":8080,"timeout_seconds":12}
OPERATIONS = {
    "notify": {"path":"notify","fields":{"title":"string","message":"string"}},
    "stream": {"path":"stream","fields":{"message":"string"}},
    "clear": {"path":"clear","fields":{}},
    "screenshot": {"path":"screenshot","fields":{}},
    "tap": {"path":"tap","fields":{"x":"int","y":"int"}},
    "drag": {"path":"drag","fields":{"start_x":"int","start_y":"int","end_x":"int","end_y":"int","duration_ms":"int"}},
    "type": {"path":"type","fields":{"text":"string"}},
    "launch_app": {"path":"launch_app","fields":{"package":"package"}},
    "ping": {"path":"ping","fields":{}},
}

def settings() -> dict:
    path=DATA/"settings.json"
    current=dict(DEFAULTS)
    if path.exists():
        current.update(json.loads(path.read_text()))
    return current

def configure(**values) -> dict:
    current=settings()
    if "http_port" in values:
        port=int(values["http_port"])
        if not 1 <= port <= 65535:
            raise ValueError("HTTP port must be between 1 and 65535.")
        current["http_port"]=port
    if "timeout_seconds" in values:
        current["timeout_seconds"]=max(1,min(int(values["timeout_seconds"]),60))
    DATA.mkdir(parents=True,exist_ok=True)
    (DATA/"settings.json").write_text(json.dumps(current,indent=2)+"\n")
    return current

def _validate(operation: str, params: dict) -> dict:
    if operation not in OPERATIONS:
        raise ValueError(f"Unsupported bridge operation: {operation}")
    spec=OPERATIONS[operation]
    missing=set(spec["fields"])-set(params)
    extra=set(params)-set(spec["fields"])
    if missing: raise ValueError(f"Missing parameters: {sorted(missing)}")
    if extra: raise ValueError(f"Unexpected parameters: {sorted(extra)}")
    clean={}
    for key,kind in spec["fields"].items():
        value=params[key]
        if kind=="int":
            value=int(value)
            if value < 0: raise ValueError(f"{key} must be non-negative.")
            if key=="duration_ms" and not 50 <= value <= 10000:
                raise ValueError("duration_ms must be between 50 and 10000.")
        elif kind=="package":
            value=str(value)
            if not value or len(value)>255 or any(not (c.isalnum() or c in "._") for c in value):
                raise ValueError("package must be an Android package identifier.")
        else:
            value=str(value)
            if not value or len(value)>2000: raise ValueError(f"{key} must contain 1-2000 characters.")
        clean[key]=value
    return clean

def request(operation: str, params: dict | None = None) -> dict:
    clean=_validate(operation,params or {})
    cfg=settings()
    query=urllib.parse.urlencode(clean)
    path=OPERATIONS[operation]["path"]
    url=f"http://{cfg['host']}:{cfg['http_port']}/rab/{path}"
    if query: url += "?"+query
    req=urllib.request.Request(url,headers={"User-Agent":"RAB/0.1.0"})
    try:
        with urllib.request.urlopen(req,timeout=cfg["timeout_seconds"]) as response:
            body=response.read(4096).decode("utf-8","replace").strip()
            code=response.status
    except urllib.error.HTTPError as e:
        body=e.read(4096).decode("utf-8","replace").strip()
        code=e.code
    except Exception as e:
        raise ConnectionError(f"MacroDroid HTTP bridge unavailable at {url}: {e}") from e
    expected="RAB_"+operation.upper()+"_OK"
    return {"http_status":code,"body":body,"url":url,
            "accepted":200 <= code < 300 and body==expected,
            "operation":operation}

def probe() -> dict:
    try:
        result=request("ping")
        return {"reachable":result["accepted"],"response":result["body"],
                "http_status":result["http_status"],"port":settings()["http_port"]}
    except Exception as e:
        return {"reachable":False,"error":str(e),"port":settings()["http_port"]}
