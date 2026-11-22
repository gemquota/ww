from __future__ import annotations
import re, time
from .store import emit, read_manifest, write_manifest

VALID_STATES = {"discovered","executable","verified","unavailable","awaiting_setup"}
ALLOWED_ADAPTERS = {"local_process","local_http","android_package","external_connector","chat_tool","macrodroid_mcp"}

def register_capability(spec: dict, replace: bool = False) -> dict:
    required = {"id","description","state","adapter","dependencies","permissions","details"}
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Missing capability fields: {sorted(missing)}")
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,95}", spec["id"]):
        raise ValueError("Capability id must be a stable lowercase identifier.")
    if spec["state"] not in VALID_STATES:
        raise ValueError("Unknown capability state.")
    if spec["adapter"] is not None and spec["adapter"] not in ALLOWED_ADAPTERS:
        raise ValueError("Adapter is not in the runtime allowlist.")
    if spec["state"] in {"executable","verified"} and spec["permissions"]:
        raise ValueError("A capability requiring new permissions cannot be executable before approval.")
    manifest = read_manifest()
    known = {c["id"] for c in manifest.get("capabilities", [])}
    missing_deps = set(spec["dependencies"]) - known
    if missing_deps:
        raise ValueError(f"Unknown dependencies: {sorted(missing_deps)}")
    caps = manifest.setdefault("capabilities", [])
    existing = next((i for i,c in enumerate(caps) if c["id"] == spec["id"]), None)
    if existing is not None and not replace:
        return {"registered":False,"reason":"already_exists","capability":caps[existing]}
    record = dict(spec)
    record.setdefault("verified_at", None)
    record.setdefault("registered_at", time.time())
    if existing is None:
        caps.append(record)
    else:
        caps[existing] = record
    manifest["generated_at"] = time.time()
    write_manifest(manifest)
    emit("CAPABILITY_REGISTERED", {"id":record["id"],"state":record["state"],
                                   "dependencies":record["dependencies"]},
         event_id="capability:"+record["id"])
    return {"registered":True,"capability":record}
