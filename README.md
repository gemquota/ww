# WW

**A lightweight terminal client for Gemini Web Chat.**

WW's core job is deliberately simple: send prompts to Gemini Web Chat and display the responses. One remote conversation stays active during the terminal process, so follow-up prompts retain context.

The Overseer, specialist agents, orchestration, tool execution, workspace scanning, plugins, persistent agent memory and dashboard are optional extensions. None is imported, initialized, or required by the basic terminal.

## Requirements

- Python 3.11+
- An authenticated Google Gemini Web session
- A Netscape-format browser export named \`cookies.txt\`, containing \`__Secure-1PSID\`; \`__Secure-1PSIDTS\` is optional

## Install

\`\`\`bash
git clone https://github.com/gemquota/ww.git
cd ww
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
\`\`\`

## Authentication

Export your Google cookies from your browser in **Netscape cookies.txt format** and place the file in the WW project root:

\`\`\`text
ww/
├── cookies.txt
├── gemini_bridge.py
└── ...
\`\`\`

WW automatically extracts \`__Secure-1PSID\` and \`__Secure-1PSIDTS\` from Google-domain entries in that file. It ignores cookies for other domains and never prints cookie values.

Start with the default file:

\`\`\`bash
python gemini_bridge.py
\`\`\`

Or specify another file:

\`\`\`bash
python gemini_bridge.py --cookies /path/to/cookies.txt
\`\`\`

You can also set \`WW_COOKIE_FILE\` to choose a different default path. Explicit \`SECURE_1PSID\` / \`SECURE_1PSIDTS\` environment variables, or values in a local \`.env\`, take precedence over values extracted from the cookie file. Manual \`.env\` configuration remains available as a fallback:

\`\`\`dotenv
SECURE_1PSID=your_cookie_value
SECURE_1PSIDTS=your_cookie_timestamp_value
\`\`\`

**Security:** \`cookies.txt\` and \`.env\` are gitignored. Do not commit or share browser session cookies. They can grant access to your signed-in Google account. Rotate the session if the file is exposed.

## Start chatting

\`\`\`bash
python gemini_bridge.py
\`\`\`

Enter prompts at \`you>\`; Gemini responses appear at \`gemini>\` as they stream in. The same chat is retained for the process lifetime. Gemini responses are rendered as Markdown (headings, lists, tables, links, and fenced code blocks). Interactive `<ElicitationsGroup>` / `<Elicitation>` suggestions are shown as numbered choices; enter the number to send that option's exact `query` as your next prompt.

### Commands

| Command | Action |
|---|---|
| \`/new\` | Start a fresh Gemini conversation |
| \`/help\` | Show help |
| \`/exit\` or \`/quit\` | Exit WW |

### One-shot prompt

\`\`\`bash
python gemini_bridge.py --prompt "Explain TCP versus UDP"
\`\`\`

## Core architecture

\`\`\`text
Terminal -> cookie loader -> WWClient -> Gemini Web Chat
\`\`\`

The core runtime is limited to the terminal entry point, a small cookie loader, a conversation transport, and the Gemini Web client library. It does not require an API key, agent hierarchy, tools, repository access, or a local database.

The existing advanced modules are retained as optional/legacy code while the basic terminal is made reliable. They must not become core imports or installation requirements.

## Notes

WW uses the unofficial \`gemini-webapi\` integration. Google can change its web interface or invalidate session cookies, so the integration may need maintenance. This is a web-session client, not an official Google API.

## Development

\`\`\`bash
python -m pip install -r requirements.txt
python -m py_compile gemini_bridge.py src/cookie_loader.py src/ww_client.py src/markdown_renderer.py
\`\`\`
