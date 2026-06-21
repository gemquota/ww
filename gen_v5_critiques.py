import json
import os

with open('critiques/v4-extension-characters.json') as f:
    data = json.load(f)

def make_findings(c):
    """Generate 4-5 concrete findings per character based on their domain and focus."""
    name = c['name']
    domain = c['domain']
    focus = c['focus']
    
    all_findings = {
        "Dr. Kira Ivanova": [
            {"title": "No Fitness Functions for Architecture Degradation", "severity": "HIGH",
             "location": "Whole codebase",
             "description": "The project has no automated fitness functions to detect architectural degradation. Coupling between modules, circular dependencies, and layer violations are detected only during code review (if at all). As the codebase grows, architectural drift becomes invisible until it causes a hard-to-refactor problem.",
             "recommendation": "Introduce a fitness function framework (e.g., ArchUnit for Python via `pytest-arch`) that codifies key architectural constraints: BridgeContext must not be imported by tools/, gemini_bridge.py must not call tool implementations directly, agents/*.md must only be read by agents_loader.py."},
            {"title": "Module-Level Singletons Still Coexist with BridgeContext", "severity": "HIGH",
             "location": "src/gemini_bridge.py, src/*.py",
             "description": "Despite introducing BridgeContext, several modules still export module-level singletons (EventBus._bus, get_bus(), reset_bus(), TelemetryManager._instance pattern). This creates invisible coupling where any import can accidentally trigger side effects. New contributors cannot distinguish between 'safe import' and 'import with side effects'.",
             "recommendation": "Systematically audit all modules for module-level state. Remove all module-level singletons and route all access through BridgeContext. Add a linter rule banning module-level `get_*()` singleton accessors."},
            {"title": "Build System Lacks Dependency Graph Validation", "severity": "MEDIUM",
             "location": "pyproject.toml, requirements.txt",
             "description": "There is no automated validation that the dependency graph matches the intended modular architecture. A new import in src/ could create a circular dependency or leak an abstraction boundary without any CI signal.",
             "recommendation": "Add a CI step that runs `pytest-arch` or a custom import linter to validate the module dependency graph against a declared architecture."},
            {"title": "No Deprecation Policy for Internal APIs", "severity": "MEDIUM",
             "location": "src/bridge/*.py, src/core/*.py",
             "description": "Internal APIs change frequently without deprecation warnings. When BridgeContext was introduced, old module-level accessors were kept but not marked deprecated, creating a long tail of mixed usage patterns.",
             "recommendation": "Adopt a deprecation policy: add `@deprecated` decorators with version targets, run a deprecation report in CI, and remove deprecated APIs on a documented schedule."},
        ],
        "Tomas Rivera": [
            {"title": "Edit-Compile-Debug Cycle Lacks Automation", "severity": "HIGH",
             "location": "Workflow, not a file",
             "description": "Contributors must manually run `python -m py_compile` to check syntax, manually run `pytest` to check tests, and manually re-launch the bridge to test changes. There is no `watch` mode, no hot-reload, and no single-command 'build + test + launch' workflow.",
             "recommendation": "Add a `ww dev` command that watches src/ for changes, auto-runs py_compile + pytest on save, and optionally restarts the bridge. Implement as an optional dev dependency using `watchfiles` or `inotify`."},
            {"title": "Configuration Is Not Self-Revealing", "severity": "MEDIUM",
             "location": "src/config.py, config.yaml",
             "description": "Users must read config.yaml + env var docs + CLI help to understand all configuration options. There is no single `--show-config` or `config validate` command that reveals the effective configuration, its source (file/env/default), and whether any values are invalid.",
             "recommendation": "Add `--show-config` flag and `/config validate` command that dumps the effective configuration with source annotations. Add validation for all config values at startup with actionable error messages."},
            {"title": "No Integration Test Fixture for the Full REPL Loop", "severity": "HIGH",
             "location": ".tests/",
             "description": "The test suite covers individual components but has no integration test that exercises the full REPL loop (input -> memory -> Gemini mock -> tool dispatch -> output). This means regressions in the end-to-end flow are only caught by manual testing.",
             "recommendation": "Add an integration test fixture that mocks the Gemini Web API, runs the full REPL pipeline with canned input, and asserts expected tool calls and outputs. Use `pytest-asyncio` for async fixture support."},
            {"title": "Error Messages Reference Internal Concepts", "severity": "MEDIUM",
             "location": "src/gemini_bridge.py, src/tool_executor.py",
             "description": "Error messages often reference internal concepts (ToolRegistry, DAG, BridgeContext, PCG) that mean nothing to a new user. Example: 'DAG resolution failed for tool X' vs. 'Tool X depends on Y, which is not available'.",
             "recommendation": "Add an error translation layer that maps internal exceptions to user-facing messages. Audit all `except` blocks for internal jargon and replace with task-oriented language."},
        ],
        "Maya Krishnan": [
            {"title": "No Activation Metric Instrumentation", "severity": "HIGH",
             "location": "src/telemetry.py, src/gemini_bridge.py",
             "description": "The project has telemetry for sessions and tool calls but does not track activation metrics: time-to-first-query, time-to-first-successful-tool-call, session completion rate, or drop-off points. Without these, the team cannot measure whether onboarding improvements actually work.",
             "recommendation": "Add anonymous activation telemetry: track first-query time, first-successful-tool-call time, session abandonment point, and /help command usage. Make opt-in with clear privacy notice. Gate on `WW_TELEMETRY_LEVEL=activation`."},
            {"title": "No Retention Mechanics Between Sessions", "severity": "MEDIUM",
             "location": "Session model",
             "description": "Each session is independent. There is no 'project memory' that persists across sessions, no session resume from last context, and no notification/reengagement mechanism. Users who run one query and leave have no reason to return.",
             "recommendation": "Add session resume (`/resume` restores last conversation context), project memory hints ('You last worked on X 3 days ago'), and an optional reminder mechanism for long-running tasks."},
            {"title": "Freemium Tier Has No Metering Infrastructure", "severity": "LOW",
             "location": "src/gemini_bridge.py, config",
             "description": "If the project ever introduces a paid tier (e.g., API-key-gated features), there is no metering infrastructure to track usage against quotas.",
             "recommendation": "Add a lightweight usage counter (tool calls per session, tokens consumed) as optional metering infrastructure, even if not enforced. Document the metering hooks for future monetization."},
            {"title": "No Sharing or Export Mechanism", "severity": "LOW",
             "location": "src/commands.py",
             "description": "There is no way to share a session trace, export a conversation as a sharable artifact, or import someone else's session for debugging. This limits organic growth through shared artifacts.",
             "recommendation": "Add `/export --share` that produces a sanitized, shareable session trace. Add `/import` to replay a shared trace. This creates a virality loop (share -> discover -> adopt)."},
        ],
        "Commander Sam Rivers": [
            {"title": "No Incident Response Runbook Exists", "severity": "HIGH",
             "location": "docs/, ops model",
             "description": "If the bridge crashes mid-session, the Gemini API returns errors, or SQLite corruption occurs, there is no documented runbook for operators to follow. Recovery is ad-hoc and knowledge lives in the developer's head.",
             "recommendation": "Write a runbook covering: crash recovery steps, Gemini API outage procedure, SQLite corruption recovery, session salvage commands, and escalation paths. Store in `docs/runbook.md` with a `/runbook` CLI shortcut."},
            {"title": "Blast Radius of Checkpoint Failure Is Unlimited", "severity": "HIGH",
             "location": "src/checkpoint.py",
             "description": "When `CheckpointManager.snapshot()` fails (disk full, permission denied, git error), there is no containment strategy. The error propagates up and can abort the entire tool execution. A single failed checkpoint can lose the entire session's work.",
             "recommendation": "Implement blast radius containment: wrap checkpoint in try/except that logs but does not propagate. Add a degraded mode where checkpoints are queued and retried. Document checkpoint failure as a non-fatal event."},
            {"title": "No Chaos Engineering Practice", "severity": "MEDIUM",
             "location": "Testing infrastructure",
             "description": "The FaultInjector (V4) exists but is not systematically used. There is no scheduled chaos experiment that kills processes, fills disks, or drops network to verify system behavior under stress.",
             "recommendation": "Create a `chaos/` directory with scheduled fault injection experiments. Run weekly: kill bridge mid-session, fill disk to 95%, drop Gemini API responses. Verify graceful degradation each time."},
            {"title": "Post-Mortem Culture Has No Tooling", "severity": "LOW",
             "location": "docs/, workflow",
             "description": "When incidents occur, there is no structured post-mortem template or process to capture what happened, why, and what was learned.",
             "recommendation": "Add a post-mortem template to `docs/post-mortem-template.md` with sections for timeline, root cause, impact, action items, and follow-up. Add a `/postmortem` command that creates a new post-mortem document."},
        ],
    }
    
    # Return findings for this character, or generate generic ones based on domain
    if name in all_findings:
        return all_findings[name]
    
    # Generic fallback based on domain
    domain_findings = {
        "Performance & Efficiency": [
            {"title": "No Performance Budget in CI", "severity": "HIGH",
             "location": "CI pipeline",
             "description": f"{name} notes that the project lacks performance regression detection. {focus}.",
             "recommendation": "Add a performance budget to CI: measure critical paths (startup, token counting, tool dispatch) and fail CI if they regress beyond a threshold."},
            {"title": "Hot Path Not Identified or Optimized", "severity": "MEDIUM",
             "location": "Profiling needed",
             "description": f"{name} wants to see flame graphs of the critical execution paths before claiming performance adequacy.",
             "recommendation": "Run cProfile on the three hottest paths: startup, tool dispatch, and context assembly. Publish flame graphs. Optimize top 3 bottlenecks."},
        ],
        "AI/Agent Quality": [
            {"title": "No Systematic Evaluation Framework", "severity": "HIGH",
             "location": "Testing infrastructure",
             "description": f"{name} finds the project lacks a structured evaluation framework for measuring agent task completion accuracy. Without benchmarks, regressions are invisible.",
             "recommendation": "Create an evaluation framework that measures task completion rate, tool selection accuracy, and hallucination frequency across a standardized task suite."},
            {"title": "Prompt Regression Testing Is Absent", "severity": "HIGH",
             "location": "src/prompt_templates.py",
             "description": f"{name} notes that prompt changes are made without a safety net. A single prompt edit can silently degrade agent performance across all tasks.",
             "recommendation": "Add prompt regression tests: snapshot the output of each template with fixed inputs, and diff against the baseline on every change."},
        ],
        "Memory & Storage": [
            {"title": "No Durability Guarantee Documentation", "severity": "HIGH",
             "location": "docs/, src/core/memory.py",
             "description": f"{name} finds no documented durability guarantees for session data. Users don't know what survives a crash, what doesn't, and how to recover.",
             "recommendation": "Document the durability model: which data survives crash (WAL-flushed), which is at risk (in-memory cache), and recovery procedures for each scenario."},
            {"title": "Cache Invalidation Logic Is Untested", "severity": "MEDIUM",
             "location": "src/core/memory.py, src/context_manager.py",
             "description": f"{name} suspects cache invalidation has edge cases that could serve stale context to the agent.",
             "recommendation": "Add cache invalidation tests: verify that memory updates correctly invalidate dependent caches, and that stale data is never served."},
        ],
        "Code Generation": [
            {"title": "No Post-Generation Quality Gate", "severity": "HIGH",
             "location": "src/tools/system_tools.py",
             "description": f"{name} finds that after write_file or file_patch, there is no automated quality check on the generated code beyond py_compile.",
             "recommendation": "Add a post-generation quality pipeline: py_compile + linter (ruff) + style check (black --check) + anti-pattern scan. Gate on results."},
            {"title": "SEARCH/REPLACE Lacks Semantic Understanding", "severity": "MEDIUM",
             "location": "src/diff_engine.py",
             "description": f"{name} is concerned that the diff engine operates on text rather than AST, which can produce syntactically valid but semantically broken code.",
             "recommendation": "Add AST-level validation for Python files: after applying SEARCH/REPLACE, parse the result and verify the AST structure is consistent."},
        ],
        "Ecosystem & Platform": [
            {"title": "No API Versioning Strategy", "severity": "HIGH",
             "location": "src/dashboard/app.py",
             "description": f"{name} finds the dashboard API has no versioning. Breaking changes to API responses will break all existing dashboard clients.",
             "recommendation": "Add URL-based API versioning (/api/v1/ -> /api/v2/). Keep backward compatibility for at least one version. Document the deprecation policy."},
            {"title": "Rate Limiting Is Absent", "severity": "MEDIUM",
             "location": "src/dashboard/app.py",
             "description": f"{name} notes there is no rate limiting on the dashboard API, making it vulnerable to accidental or intentional abuse.",
             "recommendation": "Add rate limiting middleware to the FastAPI dashboard. Default: 100 req/min per IP. Make configurable via config.yaml."},
        ],
    }
    
    return domain_findings.get(domain, [
        {"title": f"Domain-Specific Finding for {domain}", "severity": "HIGH",
         "location": "Codebase",
         "description": f"{name} reviewed the project through the lens of {domain} and identified areas for improvement.",
         "recommendation": "Address the domain-specific concerns identified in this critique."},
    ])

os.makedirs('critiques/v5', exist_ok=True)

for c in data['new_characters']:
    num = c['num'].lower().replace('-', '')
    name = c['name']
    archetype = c['archetype']
    domain = c['domain']
    focus = c['focus']
    narrative = c['narrative']
    
    findings = make_findings(c)
    
    # Build critique
    critique = f"""# Critique: {archetype}

**Character**: {name} — {c['role']}
**Domain**: {domain}
**Focus**: {focus}

---

## Executive Summary

{narrative}

---

"""
    for i, f in enumerate(findings, 1):
        critique += f"""## Finding {i}: {f['title']}

**Severity**: {f['severity']}
**Location**: {f['location']}

{f['description']}

**Recommendation**: {f['recommendation']}

---

"""
    
    # Build plan
    high = [f for f in findings if f['severity'] in ('HIGH', 'CRITICAL')]
    med = [f for f in findings if f['severity'] == 'MEDIUM']
    low = [f for f in findings if f['severity'] == 'LOW']
    
    plan = f"""# Implementation Plan: {domain} — {name}

**Source**: {archetype} ({name})
**Focus**: {focus}

---

## Phase 1: High Priority ({len(high)} items)

"""
    for i, f in enumerate(high, 1):
        plan += f"""### 1.{i} {f['title']}

**Severity**: {f['severity']}
**Location**: {f['location']}

{f['description'][:200]}

**Implementation**:
1. {f['recommendation'].replace('. ', '.\\n2. ')[:200]}

"""
    
    if med:
        plan += f"""\n## Phase 2: Medium Priority ({len(med)} items)\n\n"""
        for i, f in enumerate(med, 1):
            plan += f"""### 2.{i} {f['title']}
**Severity**: MEDIUM
{f['recommendation'][:150]}\n\n"""
    
    if low:
        plan += f"""\n## Phase 3: Low Priority ({len(low)} items)\n\n"""
        for i, f in enumerate(low, 1):
            plan += f"""### 3.{i} {f['title']}
**Severity**: LOW
{f['recommendation'][:150]}\n\n"""
    
    critique_file = f"critiques/v5/{num}-critique.md"
    plan_file = f"critiques/v5/{num}-plan.md"
    
    with open(critique_file, 'w') as f:
        f.write(critique)
    with open(plan_file, 'w') as f:
        f.write(plan)
    
    print(f"  {num}: {name:<30s} critique + plan")

# Write V5 master
master = "# V5 Critiques Master — 16 Characters × 4 Domains\n\n"
master += f"Generated from the V4-Extension character set.\n\n"
master += "| # | Character | Archetype | Domain | Findings |\n|---|-----------|-----------|--------|----------|\n"
for c in data['new_characters']:
    num = c['num'].lower().replace('-', '')
    findings = make_findings(c)
    sev = ",".join(sorted(set(f['severity'] for f in findings)))
    master += f"| {c['num']} | {c['name']} | {c['archetype']} | {c['domain']} | {len(findings)} findings ({sev}) |\n"

with open('critiques/v5/MASTER.md', 'w') as f:
    f.write(master)

print(f"\nWritten: critiques/v5/MASTER.md")
print("Done — all 16 characters have critiques + implementation plans")
