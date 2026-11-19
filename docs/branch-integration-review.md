# WW branch integration review

**Assessment date:** 2026-11-20  
**Baseline at review start:** main at 0043cb1516e2d4299e1804e4595e100917ad67d2  
**Repository inventory at review start:** 33 branches including main; no open pull requests. The integration/unified-runtime branch and PR #44 were created after that snapshot.

## Integration policy

The feature branches are not merge candidates merely because they contain useful work. Most have diverged from main by 40–80 commits. Direct merges would reintroduce older transport, dashboard, renderer, settings, or dependency implementations. The review therefore compares the feature intent with the current main implementation and ports only capabilities that are still missing.

The default terminal and dashboard now share ConversationRuntime, WWClient, tool schemas, policy checks, approval, and tool feedback. The separate legacy agent bridge is explicitly retired as an entry point; its optional agent/memory subsystems are not part of the supported runtime and are not an active migration target.

## Branch decisions

| Branch | Decision | Evidence / rationale |
|---|---|---|
| main | Keep as baseline | Current application and merged Phase 1/2 work. |
| integration/unified-runtime | Consolidated PR #44 | Shared terminal/browser runtime, Pages frontend, acceptance harness and repository cleanup. Core CI and code-quality both passed on head 3d46f1b; ready for squash merge, with device verification outstanding. |
| chore/lint-multimodal-canvas | Do not merge | Main already has a newer code-quality workflow, including project-context coverage. |
| dependabot/pip/google-genai-gte-2.9.0 | Close/archive | No commits ahead of main; dependency is not part of the current core transport. |
| dependabot/pip/prompt-toolkit-gte-3.0.52 | Close/archive | No commits ahead; main already requires prompt-toolkit 3.0.53 or newer. |
| dependabot/pip/pydantic-settings-gte-2.14.2 | Close/archive | No commits ahead; pydantic-settings is not a current core dependency. |
| dependabot/pip/rich-gte-15.0.0 | Do not merge | Main already requires rich 15.0.0 or newer; branch is an obsolete requirements-only change. |
| feat/gemini-multimodal-research | Do not merge | Artifact, Canvas, client and media functionality already exist in newer main modules. The branch versions are older and diverged. |
| feat/inline-terminal-and-clean-chat | Do not merge directly | Contains the earlier tool executor, protocol, permissions and dashboard implementation. Those capabilities are now connected through the shared runtime instead of copied from this old branch. |
| feat/pages-device-api | Do not merge directly | Pages workflow and device API already exist on main. Its browser page is superseded by the new streaming workspace frontend. |
| feature/cookies-txt-loader | Do not merge | Cookie loader and optional SECURE_1PSIDTS handling already exist on main. |
| feature/embedded-canvas-workspace | Do not merge | Canvas WebView module and tests already exist on main in a later form. |
| feature/markdown-elicitations | Do not merge | Markdown and elicitation renderer already exist on main with tests. |
| feature/project-context-and-performance | Do not merge | Project context exporter and attachment support already exist on main. |
| feature/quiet-polished-terminal | Selective port only | Its readline helper conflicts with the current prompt-toolkit input layer. Persistent history and command completion have been implemented using prompt-toolkit instead. |
| feature/startup-chat-picker | Do not merge | Startup chat selection and local settings already exist on main. |
| feature/terminal-polish-command-set | Selective port only | Substantially overlaps feature/quiet-polished-terminal. Do not merge both. Persistent history and command completion have been ported; remaining slash commands need separate value assessment. |
| fix/active-cli-multiline-input | Do not merge | Current terminal already uses prompt-toolkit multiline input with Escape+Enter submission. |
| fix/multiline-terminal-input | Do not merge directly | Overlaps feat/inline-terminal-and-clean-chat and is superseded by the current terminal input implementation. |
| fix/phase-1-api-security | Do not merge | API-key authentication, CORS and dashboard security tests are already in main. |
| fix/quiet-gemini-logs | Do not merge | Current terminal already configures Gemini logging. |
| fix/terminal-word-wrapping | Do not merge | Main already has the Markdown renderer and wrapping behaviour. |
| gh-pages | Replace artifact, not merge | It has no common ancestor with main and contained an obsolete progress dashboard. Its root index.html has been replaced with the current browser frontend. |
| phase-1-session-isolation | No action | No commits ahead of main. |
| phase-2-tool-approval-foundation | Already integrated | Approval policy, one-use grants and local approval are in main through the merged Phase 2 work. |
| phase-2b-diff-preview | Already integrated | Pre-approval file diff previews are in main. |
| phase-2c-adversarial-runtime-suite | Historical work only | Earlier diagnostics were evaluated; the probe script and tests have since been removed after the user ended the isolation workstream. |
| phase-2c-isolation-backend-evaluation | Do not merge | It is an isolation evaluation branch, and that objective has been abandoned. |
| phase-2c-runtime-capability-probe | Historical work only | The capability probe was used for the platform assessment, then removed from the active codebase when isolation work was abandoned. |
| phase-2d-audit-export | Already integrated | Audit export changes are in main. |
| phase-2d-audit-recovery | Already integrated | Audit failure recovery and subprocess cleanup work are in main. |
| phase-2d-audit-rotation | Already integrated | Audit rotation work is in main. |
| reboot/minimal-gemini-web-terminal | Do not merge | Earlier minimal-client baseline, substantially behind the current main implementation. |
| refactor/module-merging | Reject wholesale | Large destructive rewrite: dozens of removals/renames plus new 692-line context, 833-line observability and 489-line UI modules. It removes existing core, validation, API-key, memory, tool-schema and v7 modules. No evidence justifies replacing the current architecture wholesale. Mine isolated ideas only after parity tests. |

## Pull-request history checked

- PR #21: terminal polish line, closed without merge. Its prompt/history ideas were reviewed; the readline-specific implementation was not copied.
- PR #30: earlier terminal/tool integration, merged. The code existed, but the default root entry point was not using the executor.
- PR #33: Pages/device API work, merged.
- PRs #34–35: API security and dashboard/session infrastructure, merged.
- PR #36: approval policy and local approval, merged.
- PR #37: isolation architecture documentation, merged; no longer an active objective.
- PR #38–40: audit, subprocess cleanup, rotation and export, merged.
- PR #41: pre-approval diff preview, merged.
- PR #42–43: capability probe and Termux host evaluation, merged.

## Changes made on the integration branch

- Added one ConversationRuntime for terminal and browser chat.
- Connected the root terminal CLI to that runtime.
- Replaced the dashboard's separate WebGeminiClient path with WWClient and the same runtime.
- Added streamed browser chat and tool lifecycle events.
- Replaced the Pages chat prototype with a responsive browser workspace.
- Replaced the obsolete gh-pages root index with the same frontend.
- Added persistent prompt-toolkit history and command completion instead of the old readline helper.
- Added tool schema validation before approval, synchronous tool offloading, atomic workspace writes, and corrected Python syntax validation.
- Disabled URL fetching in the supported runtime until DNS pinning and redirect validation can be implemented safely.
- Added a consolidated Termux/PRoot acceptance harness, local API smoke test, frontend JavaScript syntax check, and browser Local Network Access support.
- Bounded and debounced browser transcript persistence.
- Removed conflicting Pages deployment, obsolete progress dashboard, abandoned isolation probe/tests, inert nested CI, broken Terraform deployment and stale dependency constraints.
- Corrected optional Docker configuration and added a secret-safe build context; Docker remains unverified.
- Updated AGENTS.md, CONTRIBUTING.md, pytest.ini, mypy.ini, ADRs, API/tool docs and historical-document notices.
- Removed the duplicate unit-test workflow and expanded the main CI job.

## Remaining migration work

The older src/gemini_bridge.py and src/tool_executor.py remain in the repository as retired migration source and contain unresolved references. They are not used by the supported terminal or browser app. Advanced specialist-agent, memory-tier and orchestration features have not been ported; they remain explicitly outside the supported runtime unless separately requested.

No feature branch should be merged wholesale after this review. Remaining useful changes should be ported as isolated, tested commits against the shared runtime. PR #44 is the consolidated integration branch; it must pass the final CI and code-quality checks before squash merge.
