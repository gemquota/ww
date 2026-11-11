"""WW: a small terminal client for Gemini Web Chat.

The core entry point intentionally does not import the agent orchestrator,
tool executor, workspace scanner, plugins, memory system, or dashboard.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from src.cookie_loader import extract_gemini_cookies
from src.markdown_renderer import render_response, resolve_elicitation_selection
from src.ww_client import WWClient


BANNER = """WW | Gemini Web Chat
Send a prompt and press Enter. Commands: /new, /help, /exit"""


def configure_logging() -> None:
    """Keep normal terminal output focused on responses, not library chatter.

    Gemini Web API INFO/SUCCESS messages (quota refreshes, initialization
    details, etc.) are operational diagnostics rather than chat output.
    Warnings and errors remain visible so failures are still actionable.
    """
    logging.basicConfig(level=logging.WARNING)
    for name in ("gemini_webapi", "httpx", "httpcore", "websockets"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # gemini-webapi currently uses Loguru. Keep this optional so WW's CLI
    # remains importable even if the transport dependency changes its logger.
    try:
        from loguru import logger
    except ImportError:
        return
    logger.remove()
    logger.add(sys.stderr, level="WARNING")


async def run_terminal(
    client: WWClient, prompt: str | None = None, show_banner: bool = True
) -> int:
    try:
        await client.connect()
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports transport errors.
        print(f"Connection error: {exc}", file=sys.stderr)
        return 1

    if prompt is not None:
        try:
            render_response(await client.ask(prompt))
            return 0
        except Exception as exc:  # noqa: BLE001 - CLI boundary reports request errors.
            print(f"Request error: {exc}", file=sys.stderr)
            return 1
        finally:
            await client.close()

    if show_banner:
        print(BANNER)
    pending_options = ()
    try:
        while True:
            try:
                message = await asyncio.to_thread(input, "you> ")
            except (EOFError, KeyboardInterrupt):
                print("\\nGoodbye.")
                break
            message = message.strip()
            if not message:
                continue
            selection = resolve_elicitation_selection(message, pending_options)
            if selection is not None:
                message = selection.query
                print(f"Selected: {selection.label}")
            pending_options = ()
            command = message.lower()
            if command in {"/exit", "/quit"}:
                print("Goodbye.")
                break
            if command == "/help":
                print("Enter a prompt to chat. Reply with an option number to choose a Gemini suggestion. /new starts a fresh chat. /exit quits.")
                continue
            if command == "/new":
                try:
                    await client.new_conversation()
                    print("Started a new Gemini conversation.")
                except Exception as exc:  # noqa: BLE001 - CLI boundary reports errors.
                    print(f"Could not start a new conversation: {exc}")
                continue
            try:
                chunks = []
                async for chunk in client.ask_stream(message):
                    chunks.append(chunk)
                pending_options = render_response("".join(chunks))
            except Exception as exc:  # noqa: BLE001 - CLI boundary reports request errors.
                print(f"\\nRequest error: {exc}", file=sys.stderr)
    finally:
        await client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    configure_logging()
    parser = argparse.ArgumentParser(
        prog="ww", description="A simple terminal client for Gemini Web Chat."
    )
    parser.add_argument("-p", "--prompt", help="send one prompt and exit")
    parser.add_argument(
        "--cookies",
        default=os.getenv("WW_COOKIE_FILE", "cookies.txt"),
        help="Netscape-format cookie file (default: cookies.txt or WW_COOKIE_FILE)",
    )
    parser.add_argument("--no-banner", action="store_true", help="hide the startup banner")
    args = parser.parse_args(argv)

    try:
        for key, value in extract_gemini_cookies(args.cookies).items():
            os.environ.setdefault(key, value)
    except ValueError as exc:
        print(f"Cookie file error: {exc}", file=sys.stderr)
        return 2

    if not os.getenv("SECURE_1PSID"):
        print(
            "Missing Gemini Web Chat credentials. Put a Netscape-format "
            "cookies.txt beside gemini_bridge.py, pass --cookies PATH, or set "
            "SECURE_1PSID in your environment/.env file. SECURE_1PSIDTS is optional.",
            file=sys.stderr,
        )
        return 2
    try:
        return asyncio.run(
            run_terminal(WWClient(), prompt=args.prompt, show_banner=not args.no_banner)
        )
    except KeyboardInterrupt:
        print("\\nGoodbye.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
