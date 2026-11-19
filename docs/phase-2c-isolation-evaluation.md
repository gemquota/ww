# Phase 2C: isolation backend evaluation

Status: evaluation and acceptance plan only. No backend is currently trusted or enabled.

## Decision

Do not enable privileged remote execution until one backend passes the complete host-side verification suite. A working directory restriction, subprocess timeout, PRoot guest, or human approval prompt is not an OS sandbox.

The backend must demonstrate all of the following on the actual deployment host:

- **Filesystem:** deny-by-default virtual root; only explicit workspace and scratch binds; read-only runtime/toolchain binds; symlink, hard-link, /proc, descriptor and raw-syscall escape tests.
- **Network:** no outbound TCP, UDP, DNS or Unix-socket route to host services by default; explicit allowlisted egress only. A userspace LD_PRELOAD wrapper is not sufficient evidence of network isolation.
- **Process:** child process tree is contained, host processes are not enumerable or signalable, and cancellation/timeout reaps every descendant.
- **Resources:** enforced CPU, memory, process-count, file-size, open-FD and wall-clock limits applied to the child.
- **Secrets and capabilities:** clean environment; no inherited credentials, browser cookies, SSH keys, host control sockets or unexpected file descriptors.
- **Audit:** redacted start/decision/exit records, bounded output, and reliable cleanup after crashes or cancellation.

A backend is accepted only after runtime probes prove each capability. Executable presence or a successful version check does not count.

## Platform findings

### Linux with kernel namespaces

Bubblewrap is the leading candidate where user and mount namespaces work. Its security model depends on kernel namespace support; network isolation must be explicitly enabled and verified. The runtime probe must also confirm that the selected host can enforce resource limits, preferably through delegated cgroups v2. Having bwrap installed is not enough.

References:
- [Bubblewrap project](https://github.com/containers/bubblewrap)
- [Bubblewrap user namespace requirements](https://github.com/flatpak/flatpak/wiki/User-namespace-requirements)

### Android / Termux

Termux executes native processes under the Android kernel and app UID. The environment is not automatically a container. Namespace and mount capabilities vary by device, Android build and whether execution is inside PRoot.

PRoot is useful for filesystem/path translation and distribution compatibility, but it does not provide PID, network or IPC namespaces, cgroups or seccomp isolation. It must not be accepted as a security boundary.

[abwrap](https://github.com/dukmu/abwrap-android) is a promising Termux-oriented userspace filesystem mediator. Its own security document explicitly excludes network filtering, PID/resource namespaces and cgroups. It may be evaluated as one filesystem-control component, but it does not satisfy the complete WW sandbox contract on its own and has not been independently audited for this integration.

TermWrap is another early Termux-oriented prototype. Its documented network kill switch relies on userspace interception and its threat model excludes actively malicious native code. It is not accepted as a network-isolation backend.

References:
- [Termux execution environment](https://github.com/termux/termux-packages/wiki/Termux-execution-environment)
- [PRoot-Distro limitations](https://github.com/termux/proot-distro#limitations)
- [abwrap security model and limitations](https://github.com/dukmu/abwrap-android/blob/main/docs/SECURITY.md)
- [TermWrap](https://github.com/open-todo/TermWrap)

### Current WW deployment policy

Until a Termux backend passes the full suite:

- Local terminal operations remain subject to explicit human approval and existing hard-deny checks.
- The browser API remains read-only (read_file, list_dir only).
- Remote shell, Git mutation, file writes, patches and network-fetch tools remain unavailable.
- No PRoot, abwrap, TermWrap or bwrap wrapper is silently selected as a fallback.
- If a required capability is absent or a probe is inconclusive, privileged remote execution stays disabled.

A future deployment may use a separate Linux worker with verified Bubblewrap/cgroups isolation for privileged remote operations while Termux remains the local bridge and approval authority.

## Required adversarial verification

A candidate backend must run a disposable test fixture and prove:

1. Read the allowed workspace and scratch mounts.
2. Fail to read a host sentinel placed outside every allowed mount.
3. Fail to write to read-only runtime mounts.
4. Fail to escape through relative/absolute symlinks, hard links, parent traversal, /proc/self/fd, openat directory FDs and raw syscalls.
5. Fail to connect to loopback, private IPv4/IPv6, public IPs and DNS when network is disabled.
6. Fail to inspect or signal a host process outside the sandbox.
7. Hit each configured resource limit without destabilizing the WW server.
8. Lose all descendants after timeout, cancellation, parent crash and output overflow.
9. Receive no host secrets through environment variables or inherited descriptors.
10. Leave the host sentinel and WW workspace unchanged after denied operations.

Each test must assert host-side state, not merely trust the sandboxed process's reported error. The test suite must run on the actual Android device for a Termux backend and on each supported Linux image for a Bubblewrap backend.

## Exit criteria

Phase 2C is complete only when at least one backend passes every required capability and adversarial test on its target platform. Until then, the safe result is an explicit unavailable state, not a degraded sandbox presented as secure.
