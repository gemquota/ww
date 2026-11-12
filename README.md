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

Set `WW_COOKIE_FILE` to choose a different default path. Explicit `SECURE_1PSID` / `SECURE_1PSIDTS` environment variables, or values in a local `.env`, take precedence over values extracted from the cookie file.

**Security:** `cookies.txt` and `.env` are gitignored. Do not commit or share browser session cookies. They can grant access to your signed-in Google account. Rotate the session if the file is exposed.

## Interactive chat

On startup, WW loads up to 20 recent Gemini conversations and displays them in pages. The default page size is 15.

- Dates appear in a fixed-width column on the **left**, formatted as `DD/MM HH:MM` with leading zeroes and no year.
- Press **Enter** to resume the most recent conversation.
- Enter a visible number to resume that conversation.
- Enter `>` or `<` to move between pages.
- Enter `n` to start a new conversation, or `q` to cancel the picker.

Prompts are entered at `you>`. Gemini responses are rendered as Markdown. Interactive `<ElicitationsGroup>` / `<Elicitation>` suggestions appear as numbered choices; enter a number to send that option's exact `query` as the next prompt.

### Commands

| Command | Action |
|---|---|
| `/new` | Start a fresh Gemini conversation |
| `/chats` | Browse and switch conversations |
| `/chats FOLDER` | Browse only conversations assigned to a local folder |
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
| `/artifacts` | List locally saved reports, images, videos, and audio |
| `/open N` | Open a saved artifact with the Android or desktop handler |
| `/help` | Show help |
| `/exit` or `/quit` | Exit WW |

Folders are local labels associated with Gemini conversation IDs. They do not create, move, or delete anything in Google's cloud history. A selected Gem and model are defaults for **new** conversations; resuming an existing chat preserves that conversation's own settings.

### One-shot prompt

```bash
python gemini_bridge.py --prompt "Explain TCP versus UDP"
```

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


### Gemini Canvas in an Android WebView

On Android, `/canvas` launches Gemini in a separate native WebView Activity through [Termux:GUI](https://github.com/termux/termux-gui). The Android WebView is the actual browser engine: it parses and renders HTML/CSS and executes JavaScript, rather than WW trying to imitate browser layout in the terminal.

Setup is optional:

1. Install the **Termux:GUI** Android add-on from [F-Droid](https://f-droid.org/packages/com.termux.gui/) or its official releases.
2. In regular Termux (outside the Debian proot), install the Python bindings:

   ```bash
   pkg install python
   python -m pip install termuxgui
   ```

3. Start WW in Debian and run `/canvas`.

The first launch asks for permission to enable JavaScript. WW keeps WebView navigation restricted to HTTPS Google-owned hosts used by Gemini and sign-in; other HTTP(S) links are handed to Android's external browser. Sign in inside this WebView if prompted: its cookie store is separate from Chrome's.

If WW cannot find the Termux host interpreter, set `WW_TERMUX_PYTHON` to its path, normally `/data/data/com.termux/files/usr/bin/python`. If your Termux home is mounted somewhere other than the default shared-home path, set `WW_TERMUX_HOME` as well.

This is a browser-backed Canvas route, not a direct Gemini Canvas API. It depends on the installed Android WebView, Termux:GUI, Google's current Gemini web UI, and Canvas being enabled for the account. If Google blocks embedded sign-in on a particular device/account, open Gemini in the regular Android browser instead.

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

The core runtime uses the terminal entry point, a small cookie loader, the conversation transport, local JSON preferences, and the Gemini Web client library. It does not require an API key, agent hierarchy, tools, repository access, or a local database.

## Notes

WW uses the unofficial `gemini-webapi` integration. Google can change its web interface or invalidate session cookies, so the integration may need maintenance. This is a web-session client, not an official Google API.

## Development

```bash
python -m pip install -r requirements.txt
python -m py_compile gemini_bridge.py src/cookie_loader.py src/ww_client.py src/ww_settings.py src/markdown_renderer.py src/artifacts.py
python -m unittest discover -s tests -v
```
