# Complex mode (also called article mode)

Use complex mode, also called article mode, for comprehensive explanations, mechanisms with multiple stages, or explicit step-by-step teaching. Both names select the same requirements. For revisions, follow the shared mode-selection rule: legacy `## Front`/`## Back` headings still indicate simple content requiring migration. Use `--mode complex` for explicit validation.

## Outcome

Create an article that starts with the core mental model and then expands into the details a beginner needs.

Requirements:

- Follow the shared order: title, one standalone upward navigation line without a list marker, then teaching content, separated by blank lines with no other intervening content. Omit `# Front` and `# Back`; end with `# Sources`. Do not generate HTML comments in article prose, including mode metadata comments. Fenced code examples and XML comments in separate SVG assets are unaffected.
- There is no character limit, but every section must contribute to understanding or prevent a material misconception.
- Include at least **two** local SVGs or images with different teaching purposes, such as structure plus behavior, or before-state plus after-state.
- If the article teaches a step-by-step process, every numbered or named step must have its own local `.svg` diagram immediately under that step's heading. A general overview image does not replace step-specific SVGs.
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

![topic-structure.svg](svg/topic-structure.svg)

## Behavior

Explain what changes and why it matters.

![topic-behavior.svg](svg/topic-behavior.svg)

# Sources

- [Descriptive source title](https://example.com/source)
```

For a process article, each step should state:

1. The state before the step.
2. The trigger.
3. What changes.
4. The state after the step.
5. Why the step matters.

Name process sections `## Step 1 — Clear action`, `## Step 2 — Clear action`, and so on. This lets the validator confirm that every step section contains its own `.svg` reference. Use `###` subsections for details within each step.

Keep closely related details together. Do not hide the main flow beneath tuning options, historical notes, or implementation trivia.

Before finishing, run:

```bash
python3 scripts/check_anki_card.py --mode complex path/to/card.md
```

The validator confirms the minimum visual count and checks SVG presence in `## Step …` sections. It also recognizes legacy `### Step …` through `###### Step …` headings, reports that they must migrate to `##`, and still requires each step's SVG during migration. A fenced image example or an image in a later step or peer section does not satisfy that requirement. Manually confirm that every step diagram actually explains that step and sits immediately under its heading.
