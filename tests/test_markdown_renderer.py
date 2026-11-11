import io
import unittest

from rich.console import Console

from src.markdown_renderer import (
    Elicitation,
    parse_response,
    render_response,
    resolve_elicitation_selection,
)


class MarkdownRendererTests(unittest.TestCase):
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
