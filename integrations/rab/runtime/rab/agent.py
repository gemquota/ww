from __future__ import annotations
import json, time, uuid
from .planner import plan_goal
from .store import connect, emit, read_manifest
from .discover import discover

def submit_goal(goal: str, objective_id: str | None = None) -> dict:
    objective_id = objective_id or str(uuid.uuid4())
    plan = plan_goal(goal, read_manifest())
    now = time.time()
    with connect() as db:
        existing = db.execute(
            "SELECT goal,status,plan_json FROM objectives WHERE objective_id=?",
            (objective_id,)
        ).fetchone()
        if existing:
            return {"objective_id":objective_id,"goal":existing[0],"status":existing[1],
                    "plan":json.loads(existing[2]),"replayed":True}
        db.execute("INSERT INTO objectives VALUES (?,?,?,?,?,?)",
                   (objective_id, goal, plan["status"], json.dumps(plan), now, now))
    emit("OBJECTIVE_CREATED", {
        "objective_id":objective_id,"goal":goal,"status":plan["status"],"plan":plan
    }, event_id="objective:"+objective_id)
    return {"objective_id":objective_id,"goal":goal,"status":plan["status"],
            "plan":plan,"replayed":False}

def list_objectives(limit: int = 20) -> list[dict]:
    with connect() as db:
        rows = db.execute(
            "SELECT objective_id,goal,status,plan_json,created_at,updated_at "
            "FROM objectives ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"objective_id":r[0],"goal":r[1],"status":r[2],
             "plan":json.loads(r[3]),"created_at":r[4],"updated_at":r[5]} for r in rows]


def run_objective(objective_id: str) -> dict:
    with connect() as db:
        row = db.execute(
            "SELECT goal,status,plan_json FROM objectives WHERE objective_id=?",
            (objective_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Unknown objective: {objective_id}")
        goal, status, raw_plan = row
        plan = json.loads(raw_plan)
        if status in ("executed","verified","failed","blocked","unmapped","awaiting_setup","awaiting_orchestrator"):
            return {"objective_id":objective_id,"status":status,"plan":plan,
                    "executed":False,"reason":"Objective is not in a runnable state."}
        if plan.get("status") != "ready":
            return {"objective_id":objective_id,"status":status,"plan":plan,
                    "executed":False,"reason":"Plan is not ready."}
        if any(step.get("kind") in ("external_tool","bridge_call") for step in plan.get("steps",[])):
            db.execute("UPDATE objectives SET status=?,updated_at=? WHERE objective_id=?",
                       ("awaiting_orchestrator",time.time(),objective_id))
            return {"objective_id":objective_id,"status":"awaiting_orchestrator","executed":False,
                    "plan":plan,"reason":"The orchestration layer must supply the operation arguments to the local bridge executor."}
        db.execute("UPDATE objectives SET status=?,updated_at=? WHERE objective_id=?",
                   ("running",time.time(),objective_id))
    emit("OBJECTIVE_STARTED",{"objective_id":objective_id,"goal":goal},
         event_id="objective-start:"+objective_id)
    results=[]
    try:
        for step in plan.get("steps",[]):
            if step.get("operation") == "refresh_capability_manifest":
                m=discover()
                results.append({"step":step,"result":{"capability_count":len(m["capabilities"])}})
            elif step.get("operation") == "read_runtime_status":
                m=read_manifest()
                with connect() as db:
                    events=db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                    executions=db.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
                results.append({"step":step,"result":{"capability_count":len(m["capabilities"]),
                    "events":events,"executions":executions}})
            else:
                raise RuntimeError(f"No executor for planned step: {step}")
        final="executed"
        detail={"steps":results,"note":"Executed; independent outcome verification has not yet been supplied."}
    except Exception as exc:
        final="failed"
        detail={"steps":results,"error":str(exc)}
    with connect() as db:
        db.execute("UPDATE objectives SET status=?,updated_at=? WHERE objective_id=?",
                   (final,time.time(),objective_id))
    emit("OBJECTIVE_FINISHED",{"objective_id":objective_id,"status":final,"result":detail},
         event_id="objective-finish:"+objective_id)
    return {"objective_id":objective_id,"status":final,"executed":True,"result":detail}


def reconcile_objectives() -> dict:
    manifest = read_manifest()
    with connect() as db:
        rows = db.execute(
            "SELECT objective_id,goal,status,plan_json FROM objectives "
            "WHERE status IN ('planned','ready','awaiting_setup','awaiting_orchestrator','blocked','unmapped')"
        ).fetchall()
    changed=[]
    for objective_id,goal,old_status,old_json in rows:
        new_plan=plan_goal(goal,manifest)
        new_json=json.dumps(new_plan,sort_keys=True)
        if new_json == old_json and new_plan["status"] == old_status:
            continue
        with connect() as db:
            db.execute("UPDATE objectives SET status=?,plan_json=?,updated_at=? WHERE objective_id=?",
                       (new_plan["status"],new_json,time.time(),objective_id))
        emit("OBJECTIVE_RECONCILED",{"objective_id":objective_id,"old_status":old_status,
             "new_status":new_plan["status"],"plan":new_plan})
        changed.append({"objective_id":objective_id,"from":old_status,"to":new_plan["status"],
                        "plan":new_plan})
    return {"reconciled":len(changed),"changes":changed}
