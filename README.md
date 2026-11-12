# WW

**A lightweight terminal client for Gemini Web Chat.**

WW keeps the core job simple: authenticate to Gemini Web Chat, send prompts, and render responses. Interactive mode can resume previous conversations, organise them into local folders, and use Gemini Gems and account-available models.

The Overseer, specialist agents, orchestration, tool execution, workspace scanning, plugins, persistent agent memory and dashboard remain optional extensions. None is required by the basic terminal.

## Requirements

- Python 3.11+
- An authenticated Google Gemini Web session
- A Netscape-format browser export named `cookies.txt`, containing `__Secure-1PSID`; `__Secure-1PSIDTS` is optional

## Install

```bash
git clone https://github.com/gemquota/ww.git
cd ww
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Authentication

Export your Google cookies from your browser in **Netscape cookies.txt format** and place the file in the WW project root:

```text
ww/
├── cookies.txt
├── gemini_bridge.py
└── ...
```

WW extracts `__Secure-1PSID` and `__Secure-1PSIDTS` from Google-domain entries. It ignores cookies for other domains and never prints cookie values.

Start with the default file:

```bash
python gemini_bridge.py
```

Or specify another file:

```bash
python gemini_bridge.py --cookies /path/to/cookies.txt
```

Set `WW_COOKIE_FILE` to choose a different default path. Explicit `SECURE_1PSID` / `SECURE_1PSIDTS` environment variables, or values in a local `.env`, take precedence over values extracted from the cookie file. Third-party transport logs, connection chatter, polling messages, and direct library prints are hidden by default. WW shows concise, actionable errors instead. Use `python gemini_bridge.py --debug` or set `WW_DEBUG=1` (including in `.env`) to expose transport diagnostics.

**Security:** `cookies.txt` and `.env` are gitignored. Do not commit or share browser session cookies. They can grant access to your signed-in Google account. Rotate the session if the file is exposed.

## Interactive chat

On startup, WW loads recent Gemini conversations and displays them in a compact, formatted table inside a clean terminal panel. The default page size is 15.

- Dates appear in a fixed-width column on the **left**, formatted as `DD/MM HH:MM` with leading zeroes and no year.
- Press **Enter** to resume the most recent conversation.
- Enter a visible number to resume that conversation.
- Enter `>` or `<` to move between pages.
- Enter `n` to start a new conversation, or `q` to cancel the picker.

Prompts are entered at a compact `›` input marker, then echoed as a labelled `You:` block with an indented body. Gemini output appears under `Gemini:` with the same line-break and indentation treatment. Transcript-style `gemini>` and `you>` prefixes are parsed into separate speaker blocks (prefix-like text inside fenced code is left untouched). Markdown and interactive `<ElicitationsGroup>` / `<Elicitation>` suggestions remain supported; enter a number to send that option's exact `query` as the next prompt.

Tab completion and arrow-key history are enabled when Python's `readline` module is available. WW stores up to 5,000 local input lines under `$XDG_STATE_HOME/ww/history` (normally `~/.local/state/ww/history`) with owner-only file permissions. Live streaming is opt-in because the upstream streaming interface returns text chunks rather than the full structured multimodal response; leave it off when you need generated media and artifact downloads.

### Commands

| Command | Action |
|---|---|
| `/new` | Start a fresh Gemini conversation |
| `/context [path]` | Inventory a project, embed text files, sample large files, and attach the JSON snapshot to the active chat |
| `/context refresh` | Rebuild and attach the previously selected project snapshot |
| `/context status` | Show the last export summary |
| `/context exclude DIR` / `/context include DIR` | Add or remove a directory-name exclusion for future exports |
| `/status` | Show the active chat, model, and context settings |
| `/models` | List models available to the signed-in Gemini account |
| `/model NAME` / `/model default` | Set or reset the default model used for new chats |
| `/last` | Resend the previous prompt in the active conversation |
| `/copy` | Copy the last Gemini text response using the available system clipboard helper |
| `/clear` | Clear the terminal display without closing the conversation |
| `/history` | Show recent local input history |
| `/search TEXT` | Search saved local input history |
| `/repeat N` | Resend a numbered prompt from `/history` |
| `/stream on` / `/stream off` | Enable live text streaming or restore structured response rendering |
| `/doctor` | Check local WW runtime capabilities without making network requests |
| `/chats` | Browse and switch conversations |
| `/chats FOLDER` | Browse only conversations assigned to a local folder |
| `/chats search TEXT` | Find conversations by title or conversation ID |
| `/folders` | List folders currently in use |
| `/folder NAME` | Assign the active conversation to a folder (creates it if needed) |
| `/folder clear` | Remove the active conversation's folder assignment |
| `/gems` | List, create, edit, delete, or select Gemini Gems |
| `/customize` | Set conversations per page and the default model for new chats |
| `/research [topic]` | Review a Deep Research plan, approve it, and retrieve the finished report |
| `/research --latest` | Recover the latest completed research report from this conversation |
| `/image [prompt]` | Generate an image and save the returned image artifact |
| `/video [prompt]` | Generate a video and save the returned video artifact |
| `/music [prompt]` | Generate original music/audio and save the returned audio |
| `/canvas [Google URL]` | Open Gemini in the optional Android WebView through Termux:GUI |
| `/artifacts` | List locally saved reports, images, videos, and audio |
| `/open N` | Open a saved artifact with the Android or desktop handler |
| `/help` | Show help |
| `/exit` or `/quit` | Exit WW |

Folders are local labels associated with Gemini conversation IDs. They do not create, move, or delete anything in Google's cloud history. A selected Gem and model are defaults for **new** conversations; resuming an existing chat preserves that conversation's own settings.

### One-shot prompt

```bash
python gemini_bridge.py --prompt "Explain TCP versus UDP"
```

### Project context export and attachment

Run `/context` from inside a project to detect its Git/project root, recursively inventory its directories and files, and attach a structured JSON snapshot to the active Gemini conversation. You can also pass an explicit path:

```text
/context ~/projects/mocean
/context refresh
/context status
/context exclude assets
/context include assets
```

Small text files are embedded in full. Large text files are sampled from their beginning and end, while binary files are inventoried without embedding their bytes. Common generated directories are skipped. Sensitive files such as `.env`, browser cookies, and private keys remain in the inventory but their contents are omitted. The export is written to `.ww/project-context.json`, which is gitignored, and the default embedded-content budget is 12 MiB. WW refuses to attach an export larger than 20 MiB. Additional directory-name exclusions and explicit inclusions are saved in local WW settings. Explicit inclusions can restore normally skipped generated directories; version-control metadata directories remain excluded.

You can also run the exporter without starting WW: `python -m src.project_context --root /path/to/project --output /tmp/project-context.json`. Its defaults are a 256 KiB full-text threshold, 32 KiB samples from each end of larger files, an 8 MiB per-file hashing ceiling, and a 12 MiB total embedded-content budget.

This sends the JSON file through `gemini-webapi`'s file attachment support in the existing conversation. It does not upload the project to a WW server. Review the export before sharing it: filenames, source code, and other non-sensitive text are still sent to Gemini.

## Deep Research and generated media

WW keeps Gemini's structured response instead of flattening everything into a text string. This is important because Deep Research reports, generated images, videos, and music/audio are attached as separate objects by `gemini-webapi`.

### Deep Research

Start a research task in the current conversation:

```text
/research Compare current open-source local browser engines for Android
```

WW displays the proposed plan and its steps before asking for confirmation. Once approved, it waits for the finished report and renders the Markdown document, including its source list. Gemini does not currently expose a reliable percentage or detailed progress state through the underlying web client, so WW shows an activity spinner rather than inventing a progress bar.

Research reports can take several minutes. The wait timeout is 30 minutes. If the terminal session is interrupted or the report is still running, resume the same Gemini conversation and use:

```text
/research --latest
```

This searches the active conversation history for a completed report.

### Image, video, and music generation

Use explicit commands so WW can phrase the request for the appropriate Gemini generation capability:

```text
/image A detailed cutaway illustration of a deep-sea hydrothermal vent
/video A short cinematic underwater shot of a manta ray
/music Original ambient electronic music with warm analogue textures
```

You can omit the prompt after a command and paste a multi-line prompt, ending with a line containing only `.`. Gemini account eligibility, regional availability, usage limits, and subscription requirements still apply. WW cannot grant features that Google has not enabled for the account.

Generated images, videos, and audio are downloaded using the media objects' own save methods. Images are previewed inline when `chafa` or `viu` is installed; otherwise WW prints their saved paths. On Android, `/open N` hands a file to `termux-open` when available. Desktop environments can use `xdg-open`.


### Embedded Gemini Canvas workspace on Android

On Android, `/canvas` opens a **WW-owned native Activity with Gemini rendered inside an embedded Android WebView**. This is no longer just a bare browser launch: the workspace includes native Back, Forward, Reload, Gemini-home, and Done controls, a status line, and a full-height WebView. Your WW terminal session remains available in the background, so you can switch back to the conversation without closing the Canvas workspace.

The WebView is the actual Android browser engine. Gemini Canvas remains Google's own interactive web application; WW does not attempt to parse or imitate its editor.

Setup is optional:

1. Install the **Termux:GUI** Android add-on from [F-Droid](https://f-droid.org/packages/com.termux.gui/) or its [official releases](https://github.com/termux/termux-gui/releases).
2. In regular Termux (outside the Debian proot), install the Python bindings:

   ```bash
   pkg install python
   python -m pip install termuxgui
   ```

3. Start WW in Debian and run `/canvas`.

The first launch asks for permission to enable JavaScript. Navigation inside the WebView is restricted to HTTPS Google-owned hosts used by Gemini and sign-in. Other ordinary HTTP(S) links are handed to Android's external browser, keeping unrelated sites out of the JavaScript-enabled Google session. Sign in inside this WebView if prompted: its cookie store is separate from Chrome's.

If WW cannot find the Termux host interpreter, set `WW_TERMUX_PYTHON` to its path, normally `/data/data/com.termux/files/usr/bin/python`. If your Termux home is mounted somewhere other than the default shared-home path, set `WW_TERMUX_HOME` as well.

This depends on Termux:GUI, the installed Android System WebView, Google's current Gemini web UI, and Canvas being enabled for the account. It has not been device-tested as part of the repository CI. If Google blocks embedded sign-in on a particular device/account, use the regular Android browser instead.

### Artifact storage

Artifacts are stored locally, grouped by Gemini conversation ID:

```text
~/.local/share/ww/artifacts/
└── CONVERSATION_ID/
    ├── research/
    ├── images/
    ├── videos/
    └── audio/
```

Set `XDG_DATA_HOME` to move the storage root. Use `/artifacts` to list saved files and `/open N` to open one. WW does not upload these local files anywhere.


## Local settings

WW stores preferences and folder assignments in:

- `~/.config/ww/settings.json`, or
- `$XDG_CONFIG_HOME/ww/settings.json` when `XDG_CONFIG_HOME` is set.

The settings file contains the chat page size, default model, default Gem ID, and local chat-folder assignments. It contains no authentication cookies.

## Core architecture

```text
Terminal -> cookie loader -> WWClient -> Gemini Web Chat
                         \-> local preferences and folder metadata
```

The core runtime uses the terminal entry point, a small cookie loader, the conversation transport, local JSON preferences, the project-context exporter, and the Gemini Web client library. It does not require an API key, agent hierarchy, tools, repository access, or a local database.

## Notes

WW uses the unofficial `gemini-webapi` integration. Google can change its web interface or invalidate session cookies, so the integration may need maintenance. This is a web-session client, not an official Google API.

## Development

```bash
python -m pip install -r requirements.txt
python -m py_compile gemini_bridge.py src/*.py
python -m unittest discover -s tests -v
```
