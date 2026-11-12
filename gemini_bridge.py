"""WW: a small terminal client for Gemini Web Chat.

The core entry point intentionally does not import the agent orchestrator,
tool executor, workspace scanner, plugins, memory system, or dashboard.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import logging
import os
import sys

from dotenv import load_dotenv

from src.cookie_loader import extract_gemini_cookies
from src.markdown_renderer import render_response, resolve_elicitation_selection
from src.ww_client import WWClient
from src.ww_settings import (assign_chat_folder, chats_in_folder, folder_names, load_settings, save_settings)


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


def format_chat_date(timestamp: object) -> str:
    """Format a chat timestamp as a fixed-width, year-free local date."""
    if not timestamp:
        return " " * 11
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime("%d/%m %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return " " * 11


def choose_startup_chat(
    chats: list[object],
    page_size: int = 15,
    folder_map: dict[str, str] | None = None,
) -> int | None:
    """Display paginated recent chats and let the user resume one or start fresh."""
    if not chats:
        print("No previous Gemini conversations found. Starting a new chat.")
        return None
    page_size = max(1, min(int(page_size), 50))
    folder_map = folder_map or {}
    page = 0
    page_count = (len(chats) + page_size - 1) // page_size
    while True:
        first = page * page_size
        visible = chats[first:first + page_size]
        print(f"\nRecent Gemini conversations  (page {page + 1}/{page_count})")
        print("  DATE        #  CONVERSATION")
        print("  " + "-" * 66)
        for offset, chat in enumerate(visible):
            title = getattr(chat, "title", None) or "(untitled conversation)"
            date_label = format_chat_date(getattr(chat, "timestamp", None))
            folder = folder_map.get(getattr(chat, "cid", ""), "")
            folder_label = f"  [{folder}]" if folder else ""
            print(f"  {date_label}  {offset + 1:>2}. {title}{folder_label}")
        print("\nEnter = most recent | number = open | > = next page | < = previous page")
        print("n = new chat | q = cancel")
        try:
            choice = input("Continue [1]? ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            raise
        if not choice:
            return first
        if choice in {"n", "new"}:
            return None
        if choice in {"q", "quit", "cancel"}:
            return -1
        if choice in {">", "next"} and page + 1 < page_count:
            page += 1
            continue
        if choice in {"<", "prev", "previous"} and page > 0:
            page -= 1
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(visible):
            return first + int(choice) - 1
        print("Choose a visible number, >, <, n, or q.")


def customize_menu(client: WWClient, settings: dict[str, object]) -> None:
    """Edit local display preferences and the default model for new chats."""
    while True:
        current_size = int(settings.get("chat_page_size", 15))
        current_model = settings.get("default_model") or "Gemini account default"
        print("\nWW customization")
        print(f"  1. Conversations per page: {current_size}")
        print(f"  2. Default model: {current_model}")
        print("  0. Back")
        choice = input("Customize> ").strip().lower()
        if choice in {"0", "q", "back"}:
            save_settings(settings)
            return
        if choice == "1":
            raw = input("Conversations per page (5-50) [15]: ").strip()
            if not raw:
                settings["chat_page_size"] = 15
            elif raw.isdigit() and 5 <= int(raw) <= 50:
                settings["chat_page_size"] = int(raw)
            else:
                print("Enter a whole number from 5 to 50.")
        elif choice == "2":
            models = client.list_models()
            available = [model for model in models if getattr(model, "is_available", True)]
            print("  0. Gemini account default")
            for index, model in enumerate(available, 1):
                label = getattr(model, "display_name", None) or getattr(model, "model_name", "Unknown")
                print(f"  {index}. {label}")
            selected = input("Default model [0]: ").strip()
            if selected in {"", "0"}:
                settings["default_model"] = None
            elif selected.isdigit() and 1 <= int(selected) <= len(available):
                settings["default_model"] = getattr(available[int(selected) - 1], "model_name", None)
            else:
                print("Invalid model selection.")
        else:
            print("Choose 1, 2, or 0.")


async def manage_gems(client: WWClient, settings: dict[str, object]) -> None:
    """List, select, create, edit, and delete account Gems."""
    while True:
        try:
            gems = await client.list_gems()
        except Exception as exc:
            print(f"Could not load Gemini Gems: {exc}")
            return
        print("\nGemini Gems")
        if not gems:
            print("  No visible Gems found.")
        for index, gem in enumerate(gems, 1):
            name = getattr(gem, "name", None) or "(unnamed Gem)"
            kind = "built-in" if getattr(gem, "predefined", False) else "custom"
            active = "  [default]" if getattr(gem, "id", None) == settings.get("default_gem") else ""
            print(f"  {index}. {name} ({kind}){active}")
        print("  s N = use Gem for new chats | c = create | e N = edit | d N = delete")
        print("  0 = no default Gem | q = back")
        command = input("Gems> ").strip()
        if command.lower() in {"q", "quit", "back"}:
            save_settings(settings)
            return
        if command == "0":
            settings["default_gem"] = None
            save_settings(settings)
            continue
        parts = command.split(maxsplit=1)
        action = parts[0].lower() if parts else ""
        if action == "c":
            name = input("Gem name: ").strip()
            prompt = input("System instructions: ").strip()
            description = input("Description (optional): ").strip()
            if name and prompt:
                try:
                    await client.create_gem(name, prompt, description)
                    print(f"Created Gem: {name}")
                except Exception as exc:
                    print(f"Could not create Gem: {exc}")
            else:
                print("A Gem needs both a name and system instructions.")
            continue
        if action in {"s", "e", "d"} and len(parts) == 2 and parts[1].isdigit():
            index = int(parts[1]) - 1
            if not 0 <= index < len(gems):
                print("No Gem at that number.")
                continue
            gem = gems[index]
            gem_id = str(getattr(gem, "id", ""))
            if action == "s":
                settings["default_gem"] = gem_id
                save_settings(settings)
                print(f"Default Gem set to {getattr(gem, 'name', gem_id)} for new chats.")
            elif getattr(gem, "predefined", False):
                print("Built-in Gems cannot be edited or deleted.")
            elif action == "e":
                name = input(f"Name [{getattr(gem, 'name', '')}]: ").strip() or getattr(gem, "name", "")
                prompt = input("System instructions (enter to keep current): ").strip()
                description = input(f"Description [{getattr(gem, 'description', '')}]: ").strip() or getattr(gem, "description", "")
                prompt = prompt or getattr(gem, "prompt", "")
                if prompt:
                    try:
                        await client.update_gem(gem_id, name, prompt, description)
                        print("Gem updated.")
                    except Exception as exc:
                        print(f"Could not update Gem: {exc}")
            else:
                confirm = input(f"Delete '{getattr(gem, 'name', gem_id)}' from Google? [y/N] ")
                if confirm.lower() == "y":
                    try:
                        await client.delete_gem(gem_id)
                        if settings.get("default_gem") == gem_id:
                            settings["default_gem"] = None
                        save_settings(settings)
                        print("Gem deleted.")
                    except Exception as exc:
                        print(f"Could not delete Gem: {exc}")
            continue
        print("Invalid command.")


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

    settings = load_settings()
    if show_banner:
        print(BANNER)
    try:
        chats = client.list_chats()
        selected = choose_startup_chat(
            chats,
            int(settings.get("chat_page_size", 15)),
            settings.get("chat_folders", {}),
        )
        if selected == -1:
            await client.close()
            return 0
        if selected is not None:
            chosen = chats[selected]
            await client.resume_conversation(chosen.cid)
            print(f"\nResumed: {chosen.title or '(untitled conversation)'}")
        else:
            await client.new_conversation(
                model=settings.get("default_model"),
                gem=settings.get("default_gem"),
            )
            print("\nStarted a new Gemini conversation.")
    except (EOFError, KeyboardInterrupt):
        await client.close()
        return 130
    except Exception as exc:
        print(f"Could not load chat history: {exc}", file=sys.stderr)
        print("Starting a new conversation instead.")
        await client.new_conversation(
            model=settings.get("default_model"),
            gem=settings.get("default_gem"),
        )

    pending_options = ()
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
                print(
                    "Commands: /new, /chats [folder], /folders, /folder NAME, "
                    "/folder clear, /gems, /customize, /help, /exit. "
                    "Reply with an option number to choose a Gemini suggestion."
                )
                continue
            if command == "/customize":
                try:
                    customize_menu(client, settings)
                except Exception as exc:
                    print(f"Could not open customization: {exc}")
                continue
            if command == "/gems":
                await manage_gems(client, settings)
                continue
            if command == "/folders":
                names = folder_names(settings)
                if names:
                    print("Chat folders: " + ", ".join(names))
                else:
                    print("No folders yet. Use /folder NAME while a chat is active.")
                continue
            if command.startswith("/folder"):
                argument = message[len("/folder"):].strip()
                if not argument:
                    names = folder_names(settings)
                    print("Folders: " + (", ".join(names) if names else "(none)"))
                elif argument.lower() in {"clear", "remove", "none"}:
                    chat_id = getattr(client._chat, "cid", None)
                    if chat_id:
                        assign_chat_folder(settings, chat_id, None)
                        save_settings(settings)
                        print("Removed the active chat from its folder.")
                    else:
                        print("No active chat to move.")
                else:
                    chat_id = getattr(client._chat, "cid", None)
                    if chat_id:
                        assign_chat_folder(settings, chat_id, argument)
                        save_settings(settings)
                        print(f"Moved the active chat into '{argument}'.")
                    else:
                        print("No active chat to organise.")
                continue
            if command.startswith("/chats"):
                try:
                    chats = client.list_chats()
                    argument = message[len("/chats"):].strip()
                    if argument:
                        chats = chats_in_folder(chats, settings, argument)
                        if not chats:
                            print(f"No conversations in folder '{argument}'.")
                            continue
                    selected = choose_startup_chat(
                        chats,
                        int(settings.get("chat_page_size", 15)),
                        settings.get("chat_folders", {}),
                    )
                    if selected == -1:
                        continue
                    if selected is not None:
                        chosen = chats[selected]
                        await client.resume_conversation(chosen.cid)
                        print(f"\nResumed: {chosen.title or '(untitled conversation)'}")
                except Exception as exc:
                    print(f"Could not switch conversation: {exc}")
                continue
            if command == "/new":
                try:
                    await client.new_conversation(
                        model=settings.get("default_model"),
                        gem=settings.get("default_gem"),
                    )
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
                print(f"\nRequest error: {exc}", file=sys.stderr)
    finally:
        save_settings(settings)
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
        settings = load_settings()
        page_size = max(20, int(settings.get("chat_page_size", 15)))
        return asyncio.run(
            run_terminal(
                WWClient(recent_chats=page_size),
                prompt=args.prompt,
                show_banner=not args.no_banner,
            )
        )
    except KeyboardInterrupt:
        print("\\nGoodbye.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
