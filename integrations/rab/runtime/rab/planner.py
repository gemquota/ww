from __future__ import annotations

def _cap(manifest, capability_id):
    return next((c for c in manifest.get("capabilities", [])
                 if c.get("id") == capability_id), None)

def _bridge_plan(manifest, tool_name, purpose):
    bridge = _cap(manifest, "automation.rab_android_bridge")
    if bridge and bridge.get("state") in ("executable","verified"):
        return {"status":"ready","steps":[{"kind":"bridge_call","capability_id":bridge["id"],
                                           "tool_name":tool_name}],
                "reason":f"The connected Android bridge exposes {tool_name}."}
    if bridge and bridge.get("state") == "awaiting_setup":
        return {"status":"awaiting_setup","steps":[
            {"kind":"connect","capability_id":bridge["id"],"tool_name":tool_name}
        ],"reason":f"The RAB Android Bridge has been built, but must be imported and connected before {purpose} can run."}
    return {"status":"blocked","steps":[],"reason":"The RAB Android bridge is not registered."}

def plan_goal(goal: str, manifest: dict) -> dict:
    text = goal.strip().lower()
    if not text:
        return {"status":"rejected","steps":[],"reason":"An objective cannot be empty."}
    if any(word in text for word in ("discover", "inventory", "capabilities", "manifest")):
        return {"status":"ready","steps":[{"kind":"discover","operation":"refresh_capability_manifest"}],
                "reason":"Capability discovery is available locally."}
    if any(word in text for word in ("notification", "notify", "alert")):
        cap = _cap(manifest, "android.notification")
        if cap and cap.get("state") in ("executable", "verified"):
            return {"status":"ready","steps":[{"kind":"execute","capability_id":"android.notification"}],
                    "reason":"A local notification adapter is executable."}
        return _bridge_plan(manifest,"rab_notify","notification delivery")
    if "screenshot" in text or "screen capture" in text:
        cap = _cap(manifest, "android.screenshot")
        if cap and cap.get("state") in ("executable", "verified"):
            return {"status":"ready","steps":[{"kind":"execute","capability_id":"android.screenshot"}],
                    "reason":"A screenshot adapter is executable."}
        return _bridge_plan(manifest,"rab_screenshot","screen capture")
    if any(word in text for word in ("tap", "click", "press", "touch")):
        return _bridge_plan(manifest,"rab_tap","screen tapping")
    if any(word in text for word in ("drag", "swipe")):
        return _bridge_plan(manifest,"rab_drag","screen gestures")
    if any(word in text for word in ("type", "enter text", "paste")):
        return _bridge_plan(manifest,"rab_type","text entry")
    if any(word in text for word in ("launch app", "open app", "start app")):
        return _bridge_plan(manifest,"rab_launch_app","app launching")
    if any(word in text for word in ("status", "health", "state of rab")):
        return {"status":"ready","steps":[{"kind":"inspect","operation":"read_runtime_status"}],
                "reason":"Runtime status is available locally."}
    return {"status":"unmapped","steps":[],"reason":"No registered plan template matches this objective yet. A new capability or planner rule is required."}
