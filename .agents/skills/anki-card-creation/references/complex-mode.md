# Complex mode (also called article mode)

Use complex mode, also called article mode, for comprehensive explanations, mechanisms with multiple stages, or explicit step-by-step teaching. Both names select the same requirements. For revisions, follow the shared mode-selection rule. Use `--mode complex` for explicit validation.

## Outcome

Create an article that starts with the core mental model and then expands into the details a beginner needs.

Requirements:

- Follow the shared order: title, one standalone upward navigation line without a list marker, then teaching content, separated by blank lines with no other intervening content. Omit `# Front` and `# Back`; end with `# Sources`. Do not generate HTML comments in article prose, including mode metadata comments. Fenced code examples and XML comments in separate SVG assets are unaffected.
- There is no character limit, but every section must contribute to understanding or prevent a material misconception.
- Include at least **two** local SVGs or images with different teaching purposes, such as structure plus behavior, or before-state plus after-state.
- If the article teaches a step-by-step process, every numbered or named step must have its own local `.svg` diagram in the sibling `images/` directory, linked immediately under that step's heading. A general overview image does not replace step-specific SVGs.
- Begin the teaching content immediately after the navigation line with the direct answer and a short roadmap of the explanation. For a versioned feature, the first nonblank line after navigation must follow the shared bold feature-and-release rule and pass `--require-version-lead`.
- Introduce terminology and the static model before describing state changes or edge cases.
- Prefer this teaching order when it fits: core idea → vocabulary → structure → process → example → limitations or misconceptions → concise summary.

Use this structure, adapting the navigation link to the article's location:

```markdown
# Clear topic title

<sub>[Back to System Design](../Readme.md#content)</sub>

**For a versioned feature: official feature name + lifecycle event + release/version.**

The core answer and a short roadmap of the explanation.

## Structure

Explain the model and how to read the visual.

![topic-structure.svg](images/topic-structure.svg)

## Behavior

Explain what changes and why it matters.

![topic-behavior.svg](images/topic-behavior.svg)

# Sources

- [Descriptive source title](https://example.com/source)
```

For a process article, each step should state:

1. The state before the step.
2. The trigger.
3. What changes.
4. The state after the step.
5. Why the step matters.

Choose step-heading levels from the article's hierarchy. Use `## Step 1 — Clear action`, `## Step 2 — Clear action`, and so on when the steps form the main sections. When a process belongs inside a broader `##` section, use `### Step 1 — Clear action`, `### Step 2 — Clear action`, and so on beneath it. Keep steps in the same sequence at the same level, including steps with bold labels. Do not flatten meaningful groups just because their subsections are numbered steps.

Both forms require each step's own `.svg` reference. Main-section steps may have `###` detail subsections; named sub-items within any `###` subsection, including a nested step, may use `#### **Named sub-item**`, following the shared heading rule. A `Use case:` prefix is optional.

Keep closely related details together. Do not hide the main flow beneath tuning options, historical notes, or implementation trivia.

## Review questions

When an article includes review questions, make `## Check your understanding` its last teaching section before `# Sources`. In a numbered article, give it the next section number and use the same title and updated anchor in the contents list. When revising an existing `Self-check` section, rename it and keep each answer with its question.

Follow the [WAL article’s example](../../../../distributed%20systems/Write-ahead%20log%20%28WAL%29/Readme.md#7-check-your-understanding). Start a numbered list at 1. Leave each question visible and nest one closed `<details>` block beneath it with the exact label `<summary>Answer</summary>`. Indent the whole block to the start of the question text. Keep the blank lines shown below so Markdown inside the answer renders correctly. Favor questions that ask the reader to apply the lesson, with a short answer explaining why.

```markdown
## Check your understanding

1. A changed page is ready to be written to its data file. What must PostgreSQL save first?

   <details>
   <summary>Answer</summary>

   PostgreSQL must make the WAL records for that page’s changes durable. Recovery can then use them if the page write is interrupted.

   </details>

2. How can two transactions share one WAL synchronization?

   <details>
   <summary>Answer</summary>

   Synchronizing through the later commit record also covers the earlier one because both records are in the same ordered log.

   </details>
```

Before finishing, run:

```bash
python3 scripts/check_anki_card.py --mode complex path/to/card.md
```

The validator confirms the minimum visual count and checks SVG presence in both `## Step …` sections and `### Step …` subsections within a `##` section. It reports orphaned level-three steps and step headings at deeper levels, including when their labels are wrapped in `**` or `__`. A fenced image example or an image in a later step, peer section, or parent section does not satisfy a step's diagram requirement. Manually confirm that every step diagram actually explains that step and sits immediately under its heading.
