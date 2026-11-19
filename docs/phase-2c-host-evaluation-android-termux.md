# Android / Termux host evaluation

**Collected:** 2026-11-19  
**Command:** `python -m scripts.probe_isolation`  
**Platform:** Android 7.0 / API 24, ARM64, Termux

## Recorded result

```json
{
  "indicators": {
    "bwrap_path_available": null,
    "cgroup_root_writable": false,
    "cgroup_v2_controllers": [],
    "namespace_handles_present": {
      "cgroup": false,
      "ipc": false,
      "mnt": false,
      "net": false,
      "pid": false,
      "user": false
    },
    "proot_indicators_present": false,
    "seccomp_mode": 2,
    "unprivileged_userns_setting": null,
    "user_namespace_max": null
  },
  "limitations": [
    "Namespace handles do not prove that namespace creation is permitted.",
    "Executable presence does not prove correct sandbox configuration.",
    "This inventory does not test network isolation, mount escape resistance, resource enforcement, process containment, or secret isolation.",
    "A separate adversarial runtime suite must verify host-side effects."
  ],
  "platform": {
    "android_api_level": 24,
    "machine": "aarch64",
    "sys_platform": "android",
    "system": "Android",
    "uid": 10404
  },
  "result": "diagnostic_only",
  "sandbox_accepted": false,
  "schema": 1
}
```

## Interpretation

- No Bubblewrap executable was found on PATH.
- No namespace handles were visible in the inspected `/proc/self/ns` entries.
- No cgroup v2 controllers were reported and the inspected cgroup root was not writable.
- Seccomp filtering was active (`Seccomp: 2`), but this alone does not establish a usable sandbox.
- The user-namespace sysctl indicators were unavailable, not confirmed disabled.
- PRoot markers were not detected. This is an environment-marker check, not proof that PRoot is absent from every possible launch path.

## Decision

This Termux host has **not demonstrated the capabilities required for a WW isolation backend**. It is therefore not accepted for privileged untrusted execution.

This is a negative capability evaluation, not proof that every possible Android device or kernel is incapable of isolation. Re-run the inventory and a complete adversarial suite on each target device/build before changing the decision.

The local WW approval and hard-deny controls remain in force. This result does not enable remote shell, writes, patches, network fetches or any other privileged execution path.
