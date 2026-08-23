---
name: anki-card-creation
description: Create or revise Anki-ready Markdown cards in this repository with verified beginner-friendly explanations, correctly highlighted code, local teaching visuals, and end-of-card sources. Use for simple or complex card creation; not for exporting Anki decks or packages.
---

# Anki Card Creation

Create a self-contained Markdown card that teaches someone who does not already know the topic. Put the answer's most important information first, then build understanding with definitions, a visual model, examples, and qualifications.

## Select a mode

- Use **simple mode** by default. Read [references/simple-mode.md](references/simple-mode.md).
- Use **complex mode** when the user requests it or explicitly asks for comprehensive, multi-stage, or step-by-step treatment. Read [references/complex-mode.md](references/complex-mode.md).

Do not silently relax simple mode's 3,000-character limit. Narrow the card to its core lesson or use complex mode only when the user's request selects it.

## Research before drafting

Verify every factual claim about the topic using one of these evidence paths:

1. Official or primary documentation that directly supports the claim; or
2. At least two independent, reputable sources when adequate official documentation is unavailable.

Open and read the sources rather than relying on remembered facts or search snippets. Prefer specifications, official manuals, standards, release notes, and project source code over secondary summaries. For Java topics, prefer the JLS, JVMS, JDK API documentation, OpenJDK JEPs, official HotSpot documentation, and version-matched OpenJDK source. Distinguish specified behavior from implementation details and identify the relevant version when behavior can change.

Put all citations in the final `## Sources` section. Do not scatter citations through the teaching content.

## Output location and files

- Write the `.md` file in the topic directory selected by the user. If none is specified, infer the best existing topic directory from the current repository and nearby cards.
- Store local visuals in the sibling `svg/` directory when the output is an SVG; use lowercase hyphenated filenames.
- Link visuals with a relative path and meaningful alt text, for example: `![How bucket selection works](svg/hashmap-bucket-selection.svg)`.
- Do not modify unrelated cards or diagrams. Preserve an existing card's filename unless the user asks to rename it.

## Required card structure

Use this order:

```markdown
# Clear topic title

## Front

A focused question that tells the learner what they should be able to explain.

## Back

The direct answer and most important fact first.

![Meaningful description](svg/descriptive-name.svg)

Beginner-friendly explanation, examples, and important limits.

## Sources

- [Descriptive source title](https://example.com/source)
```

The `## Sources` section must be the final second-level section. Keep the Front concise; put teaching content on the Back.

## Writing and formatting

- Define a term before using it to explain another term. Expand abbreviations on first use.
- Prefer short sentences, concrete examples, and explicit cause-and-effect language.
- Explain both **what happens** and **why it matters**. State common misconceptions only when they help prevent a likely error.
- Use headings to expose the learning path. Use lists for sequences or sets, and tables only when rows genuinely make comparison easier.
- Use inline code for identifiers, options, values, and short expressions.
- Give every fenced block an appropriate language tag. Java source must use lowercase `java`; shell commands should use `bash`; plain output or conceptual pseudocode should use `text`.
- Compile or run Java examples when practical with a JDK version appropriate to the topic. If code is intentionally incomplete or conceptual, label it clearly instead of presenting it as compilable Java.
- Keep examples minimal and make names convey their purpose. Avoid clever code that creates a second lesson.

## Visual requirement and SVG skill handoff

Every card must contain the mode's required number of local teaching visuals. A visual must explain structure, state, flow, comparison, or cause and effect; decorative imagery does not count.

Before creating or adapting card visuals, check whether the `svg-creation` skill is available. If it is available, invoke it and use it to create or edit the required SVG files. Follow its render-and-review workflow, including text clearance, arrowhead checks, beginner comprehensibility, useful XML comments, and avoidance of dominant meaningless empty space. Do not bypass an available `svg-creation` skill by hand-writing unchecked SVG.

If `svg-creation` is unavailable, create or reuse a suitable local image, verify that it renders, and inspect legibility at normal and zoomed sizes. Never use an image whose licensing or provenance is unclear.

Place each visual immediately after the paragraph or heading that introduces what it teaches. The surrounding text must explain how to read it.

## Final validation

Run the validator from this skill directory:

```bash
python3 scripts/check_anki_card.py --mode simple path/to/card.md
python3 scripts/check_anki_card.py --mode complex path/to/card.md
```

Also verify:

- The opening Back paragraph answers the Front directly.
- Every factual statement is supported by the chosen evidence path.
- Every visual is referenced, rendered, inspected, and easy for a novice to interpret.
- Each Java code fence uses `java`, and practical snippets compile or run as claimed.
- No text or image link is broken.
- Citations are last and no unrelated files changed.
