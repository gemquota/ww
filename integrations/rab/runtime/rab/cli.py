from __future__ import annotations
import argparse, json, platform, shutil, time
from . import __version__
from .discover import discover
from .store import read_manifest, connect, get_action_record, list_action_records, record_observation
from .runtime import execute
from .agent import submit_goal, list_objectives, run_objective, reconcile_objectives
from .bridge import OPERATIONS, probe as bridge_probe, configure as bridge_configure

def main():
    p = argparse.ArgumentParser(prog="rab", description="Recursive Agent Bootstrap")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover")
    sub.add_parser("manifest")
    sub.add_parser("status")
    action = sub.add_parser("action", help="Inspect or record action verification evidence")
    action_sub = action.add_subparsers(dest="action_cmd", required=True)
    action_show = action_sub.add_parser("show")
    action_show.add_argument("action_id")
    action_list = action_sub.add_parser("list")
    action_list.add_argument("--limit", type=int, default=20)
    action_observe = action_sub.add_parser("observe")
    action_observe.add_argument("action_id")
    action_observe.add_argument("--state", required=True)
    action_observe.add_argument("--source", default="Termalin-VNC")
    action_observe.add_argument("--match", choices=("yes", "no", "unknown"), default="unknown",
                                help="operator-supplied comparison claim only; cannot mark an action VERIFIED")
    action_observe.add_argument("--captured-at", type=float)
    action_observe.add_argument("--received-at", type=float)
    action_observe.add_argument("--confidence", type=float, default=0.9)
    action_observe.add_argument("--artifact-reference")
    action_observe.add_argument("--integrity-hash")
    sub.add_parser("validate")
    g = sub.add_parser("goal")
    g.add_argument("description")
    g.add_argument("--id", dest="objective_id")
    sub.add_parser("objectives")
    sub.add_parser("graph")
    sub.add_parser("reconcile")
    bp = sub.add_parser("bridge-probe")
    bc = sub.add_parser("bridge-config")
    bc.add_argument("--port", type=int)
    b = sub.add_parser("bridge")
    b.add_argument("operation", choices=list(OPERATIONS))
    b.add_argument("--title")
    b.add_argument("--message")
    b.add_argument("--x", type=int)
    b.add_argument("--y", type=int)
    b.add_argument("--start-x", dest="start_x", type=int)
    b.add_argument("--start-y", dest="start_y", type=int)
    b.add_argument("--end-x", dest="end_x", type=int)
    b.add_argument("--end-y", dest="end_y", type=int)
    b.add_argument("--duration-ms", dest="duration_ms", type=int)
    b.add_argument("--text")
    b.add_argument("--package")
    b.add_argument("--id", dest="operation_id")
    run = sub.add_parser("run")
    run.add_argument("objective_id")
    n = sub.add_parser("notify")
    n.add_argument("--title", default="RAB")
    n.add_argument("--content", required=True)
    n.add_argument("--id", default="rab-status")
    t = sub.add_parser("toast")
    t.add_argument("--message", required=True)
    a = p.parse_args()
    if a.cmd == "discover":
        m = discover()
        print(json.dumps({"discovered":len(m["capabilities"]), "manifest":"~/.local/share/rab/capabilities.json"}, indent=2))
    elif a.cmd == "manifest":
        print(json.dumps(read_manifest(), indent=2))
    elif a.cmd == "status":
        m = read_manifest()
        states = {}
        for c in m["capabilities"]: states[c["state"]] = states.get(c["state"],0)+1
        with connect() as db:
            events = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            runs = db.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
            actions = db.execute("SELECT COUNT(*) FROM action_records").fetchone()[0]
            verified = db.execute("SELECT COUNT(*) FROM action_records WHERE verification_status='verified'").fetchone()[0]
        print(json.dumps({"name":"RAB","version":__version__,"platform":platform.platform(),
                          "capabilities":states,"events":events,"executions":runs,
                          "actions":actions,"verified_actions":verified},indent=2))
    elif a.cmd == "action":
        if a.action_cmd == "show":
            result = get_action_record(a.action_id)
            if result is None:
                p.error(f"Unknown action_id: {a.action_id}")
            print(json.dumps(result, indent=2))
        elif a.action_cmd == "list":
            print(json.dumps(list_action_records(a.limit), indent=2))
        elif a.action_cmd == "observe":
            match = {"yes": True, "no": False, "unknown": None}[a.match]
            result = record_observation(
                a.action_id, a.state, a.source, match,
                captured_at=a.captured_at, received_at=a.received_at,
                confidence=a.confidence, artifact_reference=a.artifact_reference,
                integrity_hash=a.integrity_hash,
            )
            print(json.dumps(result, indent=2))
    elif a.cmd == "validate":
        m = discover()
        checks = []
        for c in m["capabilities"]:
            if c["state"] in ("executable","verified"):
                checks.append({"id":c["id"],"check":"discovery","passed":True})
        print(json.dumps({"passed":len(checks),"checks":checks,
                          "note":"Discovery validates executable presence, not end-to-end effects."},indent=2))
    elif a.cmd == "goal":
        print(json.dumps(submit_goal(a.description, a.objective_id), indent=2))
    elif a.cmd == "objectives":
        print(json.dumps(list_objectives(), indent=2))
    elif a.cmd == "run":
        print(json.dumps(run_objective(a.objective_id), indent=2))
    elif a.cmd == "reconcile":
        print(json.dumps(reconcile_objectives(), indent=2))
    elif a.cmd == "bridge-probe":
        print(json.dumps(bridge_probe(), indent=2))
    elif a.cmd == "bridge-config":
        print(json.dumps(bridge_configure(**({"http_port":a.port} if a.port else {})), indent=2))
    elif a.cmd == "bridge":
        params={k:v for k,v in vars(a).items() if k in OPERATIONS[a.operation]["fields"] and v is not None}
        from .runtime import execute
        print(json.dumps(execute("automation.rab_android_bridge",{"operation":a.operation,**params},a.operation_id),indent=2))
    elif a.cmd == "graph":
        m = read_manifest()
        print(json.dumps([{"capability":c["id"],"state":c["state"],
                           "depends_on":c.get("dependencies",[])}
                          for c in m["capabilities"]], indent=2))
    elif a.cmd == "notify":
        print(json.dumps(execute("android.notification",{"title":a.title,"content":a.content,"notification_id":a.id}),indent=2))
    elif a.cmd == "toast":
        print(json.dumps(execute("android.toast",{"message":a.message}),indent=2))

if __name__ == "__main__": main()
