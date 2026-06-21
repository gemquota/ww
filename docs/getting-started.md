# Getting Started Guide

**Last updated**: 2026-06-20  
**Version**: 1.0.0  

Addresses NEW-V6-D3#1 (Sofia Reyes), NEW-V6-O1#1 (Dr. Rachel Kim),
NEW-V6-O3#1 (Dr. Sunita Gupta).

## Prerequisites

- Python 3.10+
- A Gemini API key OR Gemini Web cookies
- Git (optional, for checkpoint support)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd ww

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your credentials
```

## Verify Installation

```bash
python gemini_bridge.py --health
```

## Your First Session

```bash
python gemini_bridge.py
```

Type a query like: "What files are in this project?"

## Learning Path

### Beginner (15 min)
1. ✅ Setup and health check
2. ✅ First query
3. ✅ Read a file using `read_file`
4. ✅ Create a file using `write_file`
5. ✅ Undo changes with `/undo`

### Intermediate (1 hour)
1. Session management: `/save`, `/load`
2. Script mode: `--script "query"`
3. Theme customization: `--theme high_contrast`
4. Verbose mode: `--verbose`
5. Plugin basics

### Advanced (2+ hours)
1. Multi-agent workflows
2. Custom tool development
3. Plugin authoring
4. Benchmark suite
5. Chaos engineering experiments

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| "No credentials found" | Run `--auth` for setup instructions |
| "Rate limit exceeded" | Wait 60 seconds and retry |
| "Tool execution failed" | Check `--verbose` for details |
| Session corrupted | Run `/salvage` or restore from backup |

## Next Steps

- Read the [tutorial](src/tutorial.py) for an interactive walkthrough
- Explore advanced features with progressive discovery
- Join the community for support
