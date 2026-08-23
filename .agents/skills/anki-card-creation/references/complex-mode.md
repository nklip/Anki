# Complex mode

Use complex mode for comprehensive explanations, mechanisms with multiple stages, or explicit step-by-step teaching.

## Outcome

Create a layered card that starts with the core mental model and then expands into the details a beginner needs.

Requirements:

- There is no character limit, but every section must contribute to understanding or prevent a material misconception.
- Include at least **two** local SVGs or images with different teaching purposes, such as structure plus behavior, or before-state plus after-state.
- If the Back teaches a step-by-step process, every numbered or named step must have its own local `.svg` diagram immediately under that step's heading. A general overview image does not replace step-specific SVGs.
- Begin the Back with the direct answer and a short roadmap of the explanation.
- Introduce terminology and the static model before describing state changes or edge cases.
- Prefer this teaching order when it fits: core idea → vocabulary → structure → process → example → limitations or misconceptions → concise summary.

For a process card, each step should state:

1. The state before the step.
2. The trigger.
3. What changes.
4. The state after the step.
5. Why the step matters.

Name process sections `### Step 1 — Clear action`, `### Step 2 — Clear action`, and so on. This lets the validator confirm that every step section contains its own `.svg` reference.

Keep closely related details together. Do not hide the main flow beneath tuning options, historical notes, or implementation trivia.

Before finishing, run:

```bash
python3 scripts/check_anki_card.py --mode complex path/to/card.md
```

The validator confirms the minimum visual count and checks SVG presence in `### Step …` sections. Manually confirm that every step diagram actually explains that step.
