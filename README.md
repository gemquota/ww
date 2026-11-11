# WW

**A lightweight terminal client for Gemini Web Chat.**

WW's core job is deliberately simple: send prompts to Gemini Web Chat and display the responses. One remote conversation stays active during the terminal process, so follow-up prompts retain context.

The Overseer, specialist agents, orchestration, tool execution, workspace scanning, plugins, persistent agent memory and dashboard are optional extensions. None is imported, initialized, or required by the basic terminal.

## Requirements

- Python 3.10+
- An authenticated Google Gemini Web session
- The session cookies `SECURE_1PSID` and `SECURE_1PSIDTS`

## Install

```bash
git clone https://github.com/gemquota/ww.git
cd ww
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set the two cookie values in your shell environment or in a local `.env` file:

```dotenv
SECURE_1PSID=your_cookie_value
SECURE_1PSIDTS=your_cookie_timestamp_value
```

Never commit real session cookies. They grant access to your signed-in Google session.

## Start chatting

```bash
python gemini_bridge.py
```

Enter prompts at `you>`; Gemini responses appear at `gemini>`. The same chat is retained for the process lifetime.

### Commands

| Command | Action |
|---|---|
| `/new` | Start a fresh Gemini conversation |
| `/help` | Show help |
| `/exit` or `/quit` | Exit WW |

### One-shot prompt

```bash
python gemini_bridge.py --prompt "Explain TCP versus UDP"
```

## Core architecture

```text
Terminal -> WWClient -> Gemini Web Chat
```

The core runtime is limited to the terminal entry point, a small conversation transport, and the Gemini Web client library. It does not require an API key, agent hierarchy, tools, repository access, or a local database.

The existing advanced modules are retained as optional/legacy code while the basic terminal is made reliable. They must not become core imports or installation requirements.

## Notes

WW uses the unofficial `gemini-webapi` integration. Google can change its web interface or invalidate session cookies, so the integration may need maintenance. This is a web-session client, not an official Google API.

## Development

```bash
python -m pip install -r requirements.txt
python -m py_compile gemini_bridge.py src/ww_client.py
```
