"""Regression tests for Gemini's textual WW tool protocol."""

import unittest

from src.tool_protocol import extract_tool_blocks


class ToolFenceParserTests(unittest.TestCase):
    def test_extracts_the_shell_block_from_geminis_explanatory_response(self):
        response = """Understanding: You want to concatenate the project files.
Planned Steps:
 * Confirm the approach.
 * Provide the requested shell snippet.

Safer and yes

```tool:shell
cat << 'EOF' > combine.py
import os

output_file = "combined_source.txt"
exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}
exclude_files = {output_file, 'combine.py'}

with open(output_file, 'w', encoding='utf-8', errors='ignore') as outfile:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file in exclude_files:
                continue
            path = os.path.join(root, file)
            outfile.write(f"\\n\\n--- FILE: {path} ---\\n\\n")
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f"[Error: {e}]")
print(f"Done. Output written to {output_file}")
EOF
python3 combine.py
```
"""
        blocks = extract_tool_blocks(response)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], "shell")
        self.assertIn("cat << 'EOF' > combine.py", blocks[0][1])
        self.assertIn("python3 combine.py", blocks[0][1])
        self.assertTrue(blocks[0][1].endswith("python3 combine.py"))

    def test_ignores_tool_fence_nested_inside_an_ordinary_code_example(self):
        response = """Example only:
```markdown
```tool:shell
rm -rf important
```
```
"""
        self.assertEqual(extract_tool_blocks(response), [])

    def test_extracts_multiple_explicit_blocks_and_accepts_fence_metadata(self):
        response = """```tool:read id=first
README.md
```

````tool:shell id=second
python -m pytest -q
````
"""
        self.assertEqual(
            extract_tool_blocks(response),
            [("read", "README.md"), ("shell", "python -m pytest -q")],
        )

    def test_ignores_unclosed_tool_fence(self):
        response = "Here is a command:\n\n```tool:shell\necho unsafe"
        self.assertEqual(extract_tool_blocks(response), [])

    def test_ignores_normal_markdown_code_fences(self):
        response = """```bash
echo "this is documentation, not an instruction"
```
"""
        self.assertEqual(extract_tool_blocks(response), [])


if __name__ == "__main__":
    unittest.main()
