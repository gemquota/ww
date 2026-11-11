#!/usr/bin/env python3
"""WW: a small terminal client for Gemini Web Chat.

The core entry point intentionally does not import the agent orchestrator,
tool executor, workspace scanner, plugins, memory system, or dashboard.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from src.ww_client import WWClient


BANNER = """WW | Gemini Web Chat
Send a prompt and press Enter. Commands: /new, /help, /exit"""


async def run_terminal(client: WWClient, prompt: str | None = None,
                       show_banner: bool = True) -> int:
    try:
        await client.connect()
    except Exception as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 1

    if prompt is not None:
        try:
            print(await client.ask(prompt))
            return 0
        except Exception as exc:
            print(f"Request error: {exc}", file=sys.stderr)
            return 1
        finally:
            await client.close()

    if show_banner:
        print(BANNER)
    try:
        while True:
            try:
                message = await asyncio.to_thread(input, "you> ")
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break
            message = message.strip()
            if not message:
                continue
            command = message.lower()
            if command in {"/exit", "/quit"}:
                print("Goodbye.")
                break
            if command == "/help":
                print("Enter a prompt to chat. /new starts a fresh chat. /exit quits.")
                continue
            if command == "/new":
                try:
                    await client.new_conversation()
                    print("Started a new Gemini conversation.")
                except Exception as exc:
                    print(f"Could not start a new conversation: {exc}")
                continue
            try:
                print(f"gemini> {await client.ask(message)}")
            except Exception as exc:
                print(f"Request error: {exc}", file=sys.stderr)
    finally:
        await client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="ww", description="A simple terminal client for Gemini Web Chat."
    )
    parser.add_argument("-p", "--prompt", help="send one prompt and exit")
    parser.add_argument("--no-banner", action="store_true", help="hide the startup banner")
    args = parser.parse_args(argv)

    if not os.getenv("SECURE_1PSID") or not os.getenv("SECURE_1PSIDTS"):
        print(
            "Missing Gemini Web Chat credentials. Set SECURE_1PSID and "
            "SECURE_1PSIDTS in your environment or local .env file.",
            file=sys.stderr,
        )
        return 2
    try:
        return asyncio.run(
            run_terminal(WWClient(), prompt=args.prompt, show_banner=not args.no_banner)
        )
    except KeyboardInterrupt:
        print("\nGoodbye.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
