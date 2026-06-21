# Recursive Refinement Protocol (RRP)

The RRP is an iterative, structured inquiry framework designed to extract maximum clarity from complex, ambiguous, or highly experimental requests. It avoids premature implementation by progressively narrowing the solution space through cascading rounds of dialogue.

## 1. The Core Lifecycle

### Step 1: Open Inquiry (The "Wide Net")
The protocol begins with a set of **X open-ended questions**. These questions target the "Blind Spots" of the request—architectural decisions, user experience nuances, and edge-case handling.
- *Goal*: Discover unknown unknowns.

### Step 2: Follow-up Analysis (The "Funnel")
For each answer provided in Step 1, the agent generates **Y multiple-choice questions**. These are derived directly from the previous signal to force a decision between concrete technical or conceptual paths.
- *Goal*: Converge on a specific strategy.

### Step 3: Round Iteration (The "Drill-Down")
Steps 1 and 2 are repeated for **Z rounds**. Each round increases in granularity, moving from "What are we building?" to "How exactly does this line of code behave?"
- *Goal*: Total architectural alignment.

### Step 4: Final Synthesis (The "Intent")
Once Z rounds are complete, the agent generates an `intent.md` report. This file serves as the definitive specification for the implementation phase.
- *Report Structure*:
    - **Overview**: A high-level narrative of the goal.
    - **Key Requirements**: A detailed list of decomposed tasks (bullets).
    - **Technical Blueprint**: Tables or diagrams mapping data flows and logic.
    - **Decision Log**: A comprehensive list of every answer and choice made during the RRP.

## 2. Dynamic Variables
The intensity of the RRP is governed by three variables:
- **X**: Number of open-ended questions per round.
- **Y**: Number of follow-up options per question.
- **Z**: Number of total refinement rounds.

Example: `RRP(5, 3, 3)` = 5 Questions, 3 Options each, 3 Rounds.

## 3. Deployment Mandate
Whenever the Recursive Refinement Protocol is invoked, the agent MUST NOT write source code until the final `intent.md` is approved.
