from __future__ import annotations
import os, platform, shutil, subprocess, time
from .store import emit, read_manifest, write_manifest
from .bridge import probe as probe_android_bridge

COMMANDS = {
    "runtime.python": ("python3", "Execute Python programs"),
    "runtime.node": ("node", "Execute JavaScript programs"),
    "storage.sqlite": ("sqlite3", "Persist structured local state"),
    "shell.ssh": ("ssh", "Connect to remote hosts from Termux"),
    "dev.git": ("git", "Version control"),
    "net.curl": ("curl", "HTTP client"),
    "android.notification": ("termux-notification", "Post Android notifications"),
    "android.toast": ("termux-toast", "Display Android toast messages"),
    "android.camera_info": ("termux-camera-info", "Query camera metadata"),
    "android.screenshot": ("termux-screenshot", "Capture Android screen"),
    "android.adb": ("adb", "Android Debug Bridge"),
    "android.activity_manager": ("am", "Launch Android activities and send intents"),
    "android.input": ("input", "Send Android input events"),
}

def _run(args, timeout=5):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 127, str(e)

def discover():
    _, package_text = _run(["/data/data/com.termux/files/usr/bin/pm", "list", "packages"], timeout=8)
    packages = {line.removeprefix("package:").strip()
                for line in package_text.splitlines() if line.startswith("package:")}
    caps = []
    for cid, (binary, purpose) in COMMANDS.items():
        path = shutil.which(binary)
        state = "executable" if path else "unavailable"
        details = {"binary": binary, "path": path, "purpose": purpose}
        dependencies = []
        if cid in ("android.notification", "android.toast", "android.camera_info"):
            details["requires_package"] = "com.termux.api"
            details["companion_installed"] = "com.termux.api" in packages
            dependencies = ["android.termux_api_app"]
            if path and "com.termux.api" not in packages:
                state = "unavailable"
                details["blocked_reason"] = "Termux:API companion app is not installed"
        if cid == "android.adb" and path:
            rc, out = _run([path, "devices"], timeout=8)
            devices = [x for x in out.splitlines()[1:] if x.strip() and "\tdevice" in x]
            details.update({"device_count": len(devices), "probe_exit_code": rc})
            if devices:
                state = "verified"
        caps.append({"id": cid, "description": purpose, "state": state,
                     "adapter": "local_process" if path and state != "unavailable" else None,
                     "dependencies": dependencies, "permissions": [], "details": details,
                     "verified_at": time.time() if state == "verified" else None})
    caps.extend([
        {"id":"android.termux_api_app","description":"Termux:API companion Android app",
         "state":"verified" if "com.termux.api" in packages else "unavailable",
         "adapter":"android_package" if "com.termux.api" in packages else None,
         "dependencies":[],"permissions":[],
         "details":{"package":"com.termux.api","installed":"com.termux.api" in packages},
         "verified_at":time.time() if "com.termux.api" in packages else None},
        {"id":"android.google_play_services","description":"Google Play services installed (not required by the local HTTP bridge)",
         "state":"verified" if "com.google.android.gms" in packages else "unavailable",
         "adapter":"android_package" if "com.google.android.gms" in packages else None,
         "dependencies":[],"permissions":[],
         "details":{"package":"com.google.android.gms","installed":"com.google.android.gms" in packages},
         "verified_at":time.time() if "com.google.android.gms" in packages else None},
        {"id":"android.macrodroid_app","description":"MacroDroid is installed on this Android device",
         "state":"verified" if "com.arlosoft.macrodroid" in packages else "unavailable",
         "adapter":"android_package","dependencies":[],"permissions":[],
         "details":{"package":"com.arlosoft.macrodroid","installed":"com.arlosoft.macrodroid" in packages},
         "verified_at":time.time() if "com.arlosoft.macrodroid" in packages else None},
        {"id":"transport.termalin","description":"Remote command and SFTP transport to this Termux host",
         "state":"verified","adapter":"external_connector","dependencies":[],"permissions":["existing Termalin connection"],
         "details":{"host_alias":"debuerreotype","evidence":"successful identity and environment probe"},
         "verified_at":time.time()},
        {"id":"automation.macrodroid_builder","description":"Construct, validate and share MacroDroid macro definitions",
         "state":"executable","adapter":"chat_tool","dependencies":["android.macrodroid_app"],"permissions":["user action required to import/save macro"],
         "details":{"evidence":"MacroDroid feature catalog and validation/share tools available; no direct device execution interface discovered"}},
        {"id":"android.remote_desktop","description":"Visual Android UI control through a remote desktop session",
         "state":"unavailable","adapter":None,"dependencies":[],"permissions":["user must start or save an AI desktop session"],
         "details":{"evidence":"Termalin desktop session list empty"}},
    ])
    # Preserve capabilities created by the factory (e.g. a shared macro bridge).
    discovered_ids = {c["id"] for c in caps}
    for existing in read_manifest().get("capabilities", []):
        if existing.get("id") not in discovered_ids and existing.get("id") != "automation.macrodroid_mcp":
            caps.append(existing)
    bridge = next((c for c in caps if c.get("id") == "automation.rab_android_bridge"), None)
    if bridge is None:
        bridge = {
            "id":"automation.rab_android_bridge",
            "description":"Local MacroDroid HTTP bridge exposing Android automation endpoints",
            "state":"awaiting_setup" if "com.arlosoft.macrodroid" in packages else "unavailable",
            "adapter":"local_http" if "com.arlosoft.macrodroid" in packages else None,
            "dependencies":["android.macrodroid_app"],
            "permissions":["import and enable the bridge macro","enable MacroDroid HTTP server"],
            "details":{"host":"127.0.0.1","endpoints":["rab/notify","rab/screenshot","rab/tap","rab/drag","rab/type","rab/launch_app","rab/ping"]},
            "verified_at":None
        }
        caps.append(bridge)
    if "com.arlosoft.macrodroid" in packages:
        probe_result = probe_android_bridge()
        bridge["state"] = "executable" if probe_result.get("reachable") else "awaiting_setup"
        bridge["adapter"] = "local_http"
        bridge.setdefault("dependencies", ["android.macrodroid_app"])
        bridge.setdefault("permissions", ["import and enable the bridge macro","enable MacroDroid HTTP server"])
        bridge.setdefault("details", {}).update({
            "host":"127.0.0.1","port":probe_result.get("port",8080),
            "probe":probe_result,
            "endpoints":["rab/notify","rab/screenshot","rab/tap","rab/drag","rab/type","rab/launch_app","rab/ping"]
        })
        bridge["verified_at"] = time.time() if probe_result.get("reachable") else None
    else:
        bridge["state"] = "unavailable"
        bridge["adapter"] = None
    manifest = {
        "schema_version": 1, "name": "Recursive Agent Bootstrap",
        "version": "0.1.0", "platform": platform.platform(),
        "device": {"hostname": platform.node(), "home": os.path.expanduser("~"),
                   "termux_prefix": os.environ.get("PREFIX")},
        "android_packages": sorted(packages & {"com.termux", "com.termux.api", "com.arlosoft.macrodroid", "com.google.android.gms"}),
        "generated_at": time.time(), "capabilities": caps
    }
    write_manifest(manifest)
    emit("CAPABILITY_DISCOVERY_COMPLETED", {
        "capability_count": len(caps),
        "states": {s: sum(1 for c in caps if c["state"] == s)
                   for s in ("discovered","executable","verified","unavailable")}
    })
    return manifest
