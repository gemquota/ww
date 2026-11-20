> **Historical only (2026-11-20):** Isolation work was explicitly abandoned. PRoot is the execution environment, not a security sandbox. Do not resume Bubblewrap, namespace, cgroup or capability-probe work unless the user explicitly requests it. See [the current architecture review](architecture-review.md).

# Phase 2C host capability inventory

Run the non-invasive inventory from the WW checkout:

```bash
python -m scripts.probe_isolation
```

The command reads procfs/sysfs indicators and checks whether `bwrap` is on
PATH. It does not invoke bwrap, create namespaces, change mounts, alter network
settings, or execute a test payload. Its result is deliberately fixed to
`diagnostic_only` with `sandbox_accepted: false`.

In particular, namespace handles in `/proc/self/ns` do not establish that
namespace creation is permitted. A visible cgroup controller does not prove
that WW can delegate or enforce limits. A bwrap executable does not prove
that its configuration blocks host access. Network isolation and adversarial
filesystem/process tests remain unverified by this inventory.

Capture the JSON output separately for each supported host. Do not attach
cookie files, environment dumps, process command lines, or other secrets.
The output intentionally excludes environment values and filesystem paths
other than the executable availability indicator.

This is a triage aid, not a sandbox acceptance test. Phase 2C remains open
until a candidate backend passes the full host-side adversarial suite described
in `phase-2c-isolation-evaluation.md` on the actual deployment host.
