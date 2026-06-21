# Doc Search Strategy — V6-D1#4

## Search Methods

### 1. GitHub Repository Search
Use GitHub's built-in search with these patterns:
- `repo:user/ww-bridge <query>`
- Search in `docs/` directory: `path:docs/ <query>`
- Search in issues: `is:issue <query>`

### 2. Local grep
```bash
# Full-text search in docs
rg -i "<query>" docs/ --type md

# Search code comments
rg -i "<query>" src/ --type py
```

### 3. MkDocs Search
When running `mkdocs serve`, use the built-in search bar
which indexes all markdown content in `docs/`.

### 4. Doc Search Tool
The built-in `doc_search` tool searches documentation:
```
tool:doc_search query="<search terms>"
```

## Index
- docs/ — User and developer documentation
- meta/ — Audit reports, plans, analysis
- agents/ — Agent hierarchy definitions
- ADRs in docs/adr/ — Decision records
