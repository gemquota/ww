import io
import unittest
from os import terminal_size
from unittest.mock import patch

from rich.console import Console

from src.markdown_renderer import (
    Elicitation,
    parse_response,
    parse_speaker_blocks,
    render_chat_response,
    render_response,
    resolve_elicitation_selection,
)


class MarkdownRendererTests(unittest.TestCase):
    def test_parses_speaker_prefixes_into_distinct_blocks(self):
        source = "you> Please inspect this.\ngemini> I will inspect it.\nMore detail."
        blocks = parse_speaker_blocks(source)
        self.assertEqual(blocks, (
            ("you", "Please inspect this."),
            ("gemini", "I will inspect it.\nMore detail."),
        ))

    def test_speaker_prefixes_inside_code_fences_are_not_parsed(self):
        source = 'gemini> Example:\n\n```text\nyou> this is literal\n```'
        blocks = parse_speaker_blocks(source)
        self.assertEqual(len(blocks), 1)
        self.assertIn("you> this is literal", blocks[0][1])

    def test_chat_renderer_labels_and_indents_speakers(self):
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=80)
        render_chat_response("gemini> A response.", console=console)
        rendered = output.getvalue()
        self.assertIn("Gemini:", rendered)
        self.assertIn("A response.", rendered)

    def test_extracts_group_and_preserves_markdown(self):
        source = """## Result

A **formatted** answer.

<ElicitationsGroup message="To continue:">
<Elicitation label="Compare the options" query="Compare option A with option B." />
<Elicitation label="Make a checklist" query="Create a checklist for this task." />
</ElicitationsGroup>
"""
        parsed = parse_response(source)
        self.assertIn("## Result", parsed.markdown)
        self.assertIn("**formatted**", parsed.markdown)
        self.assertEqual(len(parsed.groups), 1)
        self.assertEqual(parsed.groups[0].message, "To continue:")
        self.assertEqual(parsed.options[0].label, "Compare the options")
        self.assertEqual(parsed.options[0].query, "Compare option A with option B.")

    def test_does_not_parse_component_examples_inside_fenced_code(self):
        source = '''Example:

```xml
<ElicitationsGroup message="not interactive">
<Elicitation label="Fake" query="Do not send" />
</ElicitationsGroup>
```
'''
        parsed = parse_response(source)
        self.assertEqual(parsed.groups, ())
        self.assertIn("<ElicitationsGroup", parsed.markdown)

    def test_invalid_group_is_preserved(self):
        source = '<ElicitationsGroup message="empty">no options</ElicitationsGroup>'
        parsed = parse_response(source)
        self.assertEqual(parsed.groups, ())
        self.assertEqual(parsed.markdown, source)

    def test_selection_returns_exact_query(self):
        options = (
            Elicitation("First option", "Run the first action exactly."),
            Elicitation("Second option", "Run the second action exactly."),
        )
        self.assertEqual(
            resolve_elicitation_selection("2", options),
            options[1],
        )
        self.assertEqual(
            resolve_elicitation_selection("/choose 1", options),
            options[0],
        )
        self.assertIsNone(resolve_elicitation_selection("3", options))
        self.assertIsNone(resolve_elicitation_selection("not a number", options))

    def test_default_renderer_wraps_at_detected_terminal_width(self):
        output = io.StringIO()
        source = (
            "This is a longer sentence where every word must remain whole "
            "when the terminal reaches its right edge."
        )
        with patch("src.markdown_renderer.shutil.get_terminal_size",
                   return_value=terminal_size((20, 24))):
            render_response(source, file=output)

        rendered = output.getvalue()
        self.assertEqual(rendered.split(), source.split())
        self.assertTrue(
            all(len(line) <= 20 for line in rendered.splitlines() if line),
            rendered,
        )

    def test_renderer_displays_markdown_and_choices(self):
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=100)
        options = render_response(
            "# Hello\n\n**Bold** response.\n\n"
            '<ElicitationsGroup message="Next:">'
            '<Elicitation label="Do the next thing" query="Do it." />'
            "</ElicitationsGroup>",
            console=console,
        )
        rendered = output.getvalue()
        self.assertIn("Hello", rendered)
        self.assertIn("Bold", rendered)
        self.assertIn("Next:", rendered)
        self.assertIn("Do the next thing", rendered)
        self.assertEqual(options, (Elicitation("Do the next thing", "Do it."),))


if __name__ == "__main__":
    unittest.main()
