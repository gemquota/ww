"""The minimal WW terminal: prompt in, Gemini Web Chat response out."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable

from dotenv import load_dotenv

from src.core_chat import GeminiWebChat


BANNER = """WW | Gemini Web Chat
Send a prompt and press Enter. Commands: /new, /help, /exit
"""


async def run_terminal(
    client: GeminiWebChat | None = None,
    prompt: str | None = None,
    show_banner: bool = True,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], object] = print,
) -> int:
    """Run interactive chat or send one prompt in non-interactive mode."""
    chat = client or GeminiWebChat()

    try:
        await chat.connect()
    except Exception as exc:
        output_fn(f"Connection error: {exc}")
        return 1

    if prompt is not None:
        try:
            output_fn(await chat.send(prompt))
            return 0
        except Exception as exc:
            output_fn(f"Request error: {exc}")
            return 1

    if show_banner:
        output_fn(BANNER.rstrip())

    try:
        while True:
            try:
                message = await asyncio.to_thread(input_fn, "you> ")
            except (EOFError, KeyboardInterrupt):
                output_fn("\nGoodbye.")
                break

            message = message.strip()
            if not message:
                continue
            command = message.lower()

            if command in {"/exit", "/quit"}:
                output_fn("Goodbye.")
                break
            if command == "/help":
                output_fn("Enter a prompt to chat. /new starts a fresh chat. /exit quits.")
                continue
            if command == "/new":
                try:
                    await chat.new_conversation()
                    output_fn("Started a new Gemini conversation.")
                except Exception as exc:
                    output_fn(f"Could not start a new conversation: {exc}")
                continue

            try:
                answer = await chat.send(message)
                output_fn(f"gemini> {answer}")
            except Exception as exc:
                output_fn(f"Request error: {exc}")
    finally:
        await chat.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="ww",
        description="A simple terminal client for Gemini Web Chat.",
    )
    parser.add_argument(
        "-p", "--prompt", help="send one prompt and exit instead of opening the terminal"
    )
    parser.add_argument("--no-banner", action="store_true", help="hide the startup banner")
    args = parser.parse_args(argv)

    if not os.getenv("SECURE_1PSID") or not os.getenv("SECURE_1PSIDTS"):
        print(
            "Missing Gemini Web Chat credentials. Add SECURE_1PSID and "
            "SECURE_1PSIDTS to .env or your environment.",
            file=sys.stderr,
        )
        return 2

    try:
        return asyncio.run(
            run_terminal(prompt=args.prompt, show_banner=not args.no_banner)
        )
    except KeyboardInterrupt:
        print("\nGoodbye.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
