"""
Interactive tutorial mode for onboarding.
Addresses NEW-V6-O4#1 (Jack Thompson).
"""
from typing import List, Dict, Optional


class TutorialStep:
    def __init__(self, title: str, description: str, command: str,
                 expected_output_contains: Optional[str] = None):
        self.title = title
        self.description = description
        self.command = command
        self.expected_output_contains = expected_output_contains
        self.completed = False


class TutorialSession:
    """Manages an interactive tutorial session."""

    STEPS = [
        TutorialStep(
            "Welcome", "Welcome to WW Bridge! Let's start with the basics.",
            "python gemini_bridge.py --help",
            "usage"
        ),
        TutorialStep(
            "Health Check", "Verify your credentials and API connectivity.",
            "python gemini_bridge.py --health",
            "All checks passed"
        ),
        TutorialStep(
            "Your First Query", "Ask the assistant a simple question.",
            "Say: 'What files are in this project?'",
            None
        ),
        TutorialStep(
            "Using Tools", "Try reading a file using the read_file tool.",
            "Say: 'Read the contents of src/gemini_bridge.py'",
            None
        ),
        TutorialStep(
            "Making Edits", "Create a new file with write_file.",
            "Say: 'Create a file called hello.py with a print statement'",
            None
        ),
        TutorialStep(
            "Undo", "Learn how to revert changes with /undo.",
            "Type: /undo",
            "Undone"
        ),
        TutorialStep(
            "Session Management", "Save and load sessions.",
            "Type: /save my_first_session",
            "saved"
        ),
    ]

    def __init__(self):
        self.current_step = 0
        self._completed_steps: List[int] = []

    def get_current(self) -> TutorialStep:
        return self.STEPS[self.current_step] if self.current_step < len(self.STEPS) else None

    def advance(self) -> bool:
        """Advance to next step. Returns False if tutorial is complete."""
        self._completed_steps.append(self.current_step)
        self.current_step += 1
        return self.current_step < len(self.STEPS)

    def get_progress(self) -> Dict:
        return {
            "current": self.current_step,
            "total": len(self.STEPS),
            "completed": len(self._completed_steps),
            "percentage": round(len(self._completed_steps) / len(self.STEPS) * 100, 1),
        }

    def is_complete(self) -> bool:
        return len(self._completed_steps) >= len(self.STEPS)

    def reset(self):
        self.current_step = 0
        self._completed_steps = []


class OnboardingTracker:
    """Tracks onboarding progress across sessions."""

    def __init__(self, telemetry):
        self.telemetry = telemetry

    def record_activity(self, activity: str):
        """Record onboarding activity for progress tracking."""
        if self.telemetry:
            funnel = getattr(self.telemetry, '_activation_funnel', None)
            if funnel:
                funnel.track(f"onboarding_{activity}")

    def get_milestone_status(self, tasks_completed: int) -> List[str]:
        """Get earned milestone badges."""
        badges = []
        if tasks_completed >= 1:
            badges.append("🏅 First Task")
        if tasks_completed >= 5:
            badges.append("⭐ Rising Star")
        if tasks_completed >= 10:
            badges.append("🏆 Power User")
        if tasks_completed >= 25:
            badges.append("👑 Master")
        return badges
