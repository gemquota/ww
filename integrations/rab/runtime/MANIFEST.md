# RAB capability manifest

- Version: 0.1.0
- Platform: Android-17-aarch64-64bit
- Generated: 2026-11-21T22:24:46+10:00

| Capability | State | Adapter | Dependencies |
|---|---|---|---|
| runtime.python | **executable** | local_process | none |
| runtime.node | **executable** | local_process | none |
| storage.sqlite | **executable** | local_process | none |
| shell.ssh | **executable** | local_process | none |
| dev.git | **executable** | local_process | none |
| net.curl | **executable** | local_process | none |
| android.notification | **unavailable** | none | android.termux_api_app |
| android.toast | **unavailable** | none | android.termux_api_app |
| android.camera_info | **unavailable** | none | android.termux_api_app |
| android.screenshot | **unavailable** | none | none |
| android.adb | **executable** | local_process | none |
| android.activity_manager | **executable** | local_process | none |
| android.input | **unavailable** | none | none |
| android.termux_api_app | **unavailable** | none | none |
| android.google_play_services | **verified** | android_package | none |
| android.macrodroid_app | **verified** | android_package | none |
| transport.termalin | **verified** | external_connector | none |
| automation.macrodroid_builder | **executable** | chat_tool | android.macrodroid_app |
| android.remote_desktop | **unavailable** | none | none |
| automation.rab_android_bridge | **awaiting_setup** | local_http | android.macrodroid_app |

## RAB Local Android Bridge

Status: awaiting_setup.

One MacroDroid macro exposes seven localhost-only endpoints:
- rab/notify
- rab/screenshot
- rab/tap
- rab/drag
- rab/type
- rab/launch_app
- rab/ping

Import link: https://macrodroidlink.com/m/honBMSONferS

The link expires 2026-11-28. Import and enable the macro once. MacroDroid uses its configured HTTP server port; RAB currently defaults to 8080. The macro whitelist accepts requests only from 127.0.0.1. Screenshot and UI interaction also require MacroDroid accessibility service.

The bridge is not executable until the local ping endpoint responds with RAB_PING_OK.
