# Cognitive Load Redesign — V6-O1#1

## Problem
New users face high cognitive load when first using the bridge:
- Understanding 3-tier agent hierarchy
- Learning tool syntax (tool:xxx)
- Managing API credentials
- Understanding context window management

## Redesign Principles

### 1. Progressive Disclosure
- **First run**: Interactive setup wizard
- **First query**: Guided template with tool suggestions
- **After 5 queries**: Introduce advanced features
- **After 25 queries**: Full power user interface

### 2. Defaults Over Configuration
- Sensible defaults for all settings
- Configuration is always optional
- "It just works" for 80% of use cases

### 3. Consistent Mental Model
- Agent hierarchy → Corporate hierarchy metaphor
- Tools → Specialized workers
- Context → Workspace/desk metaphor
- Memory → Filing cabinet metaphor

## Implementation
- Add `--guided` flag for first-run experience
- Progressive tooltips in TUI
- Context-sensitive help (`/help <topic>`)
- Onboarding wizard on first launch
