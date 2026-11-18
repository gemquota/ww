"""Prompt-toolkit configuration for the interactive terminal."""

from prompt_toolkit import PromptSession


def create_terminal_session(**kwargs):
    """Create a terminal prompt that keeps pasted multi-line input together.

    In multiline mode, Enter inserts a newline and Escape+Enter submits the
    complete buffer as one message. This prevents pasted scripts from being
    split into separate chat turns.
    """
    return PromptSession(multiline=True, **kwargs)
