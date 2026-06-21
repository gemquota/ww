# Diagram Quality Evaluation — V6-D4#2

## Standards

### All Diagrams Must Have
- Title and legend
- Consistent notation
- Readable at 1024px width
- Color-blind safe palette

### Required Diagrams
| Diagram | Format | Location | Status |
|---|---|---|---|
| Agent hierarchy | SVG | docs/architecture/ | ⚠️ Needs update |
| Data flow | Mermaid | docs/architecture/ | ❌ Missing |
| Module dependencies | SVG | docs/architecture/ | ❌ Missing |
| Deployment topology | Mermaid | docs/ | ❌ Missing |

## Evaluation Criteria
1. **Clarity**: Can a new contributor understand it without explanation?
2. **Accuracy**: Does it match current code?
3. **Consistency**: Same notation used across all diagrams
4. **Maintainability**: Source files (Mermaid, draw.io) committed alongside rendered versions

## Color Palette
```json
{
  "primary": "#4A90D9",
  "secondary": "#50C878",
  "warning": "#F5A623",
  "error": "#D0021B",
  "background": "#F5F5F5",
  "text": "#333333"
}
```
