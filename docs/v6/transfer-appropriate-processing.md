# Transfer-Appropriate Processing — V6-O1#4

## Concept
Transfer-appropriate processing (TAP) is a cognitive psychology principle stating that knowledge transfer is maximized when the cognitive processes engaged during learning match those required during application.

## Application to WW Bridge Onboarding

### Principle 1: Match Learning Context to Use Context
- **Problem**: Users learn about agent hierarchy in a static document, then struggle to apply it in the CLI.
- **Solution**: Tutorial steps should be performed in the actual CLI environment, using real commands.
- **Implementation**: `src/tutorial.py` runs inside the WW Bridge CLI, not as a separate document.

### Principle 2: Vary Practice Conditions
- **Problem**: Users practice one tool at a time and can't combine them.
- **Solution**: Design exercises that require chaining multiple tools.
- **Implementation**: Tutorial steps progressively combine tools (read → edit → validate).

### Principle 3: Encourage Generative Processing
- **Problem**: Users follow steps without understanding why.
- **Solution**: Each tutorial step includes a "why this matters" explanation.
- **Implementation**: Every `TutorialStep` includes a `description` field explaining purpose.

### How This Is Measured
- Transfer success rate: percentage of users who complete a task after tutorial
- Time from tutorial completion to first autonomous task
- Error rate reduction between first and fifth autonomous task

## References
- Morris, Bransford & Franks (1977) — Levels of processing versus transfer appropriate processing
- Barnett & Ceci (2002) — When and where do we apply what we learn?
