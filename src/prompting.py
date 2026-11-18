"""Prompt-toolkit configuration for the interactive terminal."""


def create_terminal_session(**kwargs):
    """Create a prompt that keeps pasted multi-line input in one message.

    In multiline mode, Enter inserts a newline and Escape+Enter submits the
    complete buffer. Import prompt_toolkit lazily so core-only installations
    can import the rest of WW without the optional interactive UI dependency.
    """
    from prompt_toolkit import PromptSession

    return PromptSession(multiline=True, **kwargs)
