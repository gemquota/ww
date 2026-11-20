> **Historical only (2026-11-20):** Isolation work was explicitly abandoned. PRoot is the execution environment, not a security sandbox. Do not resume Bubblewrap, namespace, cgroup or capability-probe work unless the user explicitly requests it. See [the current architecture review](architecture-review.md).

# Phase 2C Bubblewrap host smoke suite

The initial Linux host-side adversarial smoke suite is:

```bash
python -m scripts.test_bwrap_isolation
```

Run it only on a disposable Linux host where Bubblewrap is installed and user namespaces are permitted. It creates a temporary host sentinel, a host loopback listener and a short-lived host process. It does not modify system configuration. The host process and temporary files are cleaned up by the harness.

The harness creates a minimal root with read-only `/usr`, a private `/tmp`, a new `/proc` mount and Bubblewrap's `--unshare-all` namespaces. It checks that a host-only filesystem sentinel is hidden, host loopback is unreachable, a host process is absent from the sandbox PID namespace, and a parent environment sentinel is not inherited. Assertions include host-side checks where possible.

## Important limitations

This is an initial smoke suite, **not the full Phase 2C acceptance suite**. It does not yet prove cgroup resource enforcement, descendant cleanup under crash/cancellation, descriptor and raw-syscall escape resistance, complete IPv4/IPv6/UDP/DNS/Unix-socket isolation, secret-FD isolation, or audit durability. The report always contains `sandbox_accepted: false`, even when all smoke tests pass.

A `not_run` result means prerequisites or Bubblewrap namespace setup were unavailable. It must not be interpreted as a pass. Do not weaken the test to make a restricted host report success.

Do not run untrusted user payloads through this harness. It is a controlled capability test using fixed, locally generated probes.
