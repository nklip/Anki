---
name: anki-card-creation
description: Create or revise Anki-ready Markdown cards in this repository with verified beginner-friendly explanations, correctly highlighted code, local teaching visuals, and end-of-card sources. Use for simple or complex (also called article mode) card creation; not for exporting Anki decks or packages.
---

# Anki Card Creation

Create a self-contained Markdown card that teaches someone who does not already know the topic. Put the answer's most important information first, then build understanding with definitions, a visual model, examples, and qualifications.

## Select a mode

- Use **simple mode** by default. Read [references/simple-mode.md](references/simple-mode.md).
- Use **complex mode**, also called **article mode**, when the user requests either name or explicitly asks for comprehensive, multi-stage, or step-by-step treatment. Read [references/complex-mode.md](references/complex-mode.md). Both names select the same mode; use `complex` in card metadata and `--mode complex` for validation.

Do not silently relax simple mode's 3,000-character limit, which counts the Back only — `# Front` and `# Sources` are excluded. Narrow the card to its core lesson or use complex mode only when the user's request selects it.

## Research before drafting

Verify every factual claim about the topic using one of these evidence paths:

1. Official or primary documentation that directly supports the claim; or
2. At least two independent, reputable sources when adequate official documentation is unavailable.

Open and read the sources rather than relying on remembered facts or search snippets. Prefer specifications, official manuals, standards, release notes, and project source code over secondary summaries. For Java topics, prefer the JLS, JVMS, JDK API documentation, OpenJDK JEPs, official HotSpot documentation, and version-matched OpenJDK source. Distinguish specified behavior from implementation details and identify the relevant version when behavior can change.

Put all citations in the final `# Sources` section. Do not scatter citations through the teaching content.

## Lead sentence for versioned features

When the card is about a feature that was added, previewed, finalized, or made generally available in a particular release, make the first nonblank line under `# Back` a standalone bold sentence that states:

1. The feature's official name.
2. The exact lifecycle event, using wording such as **introduced**, **first previewed**, **became final**, or **became generally available**.
3. The release or version in which that event occurred.
4. The authoritative proposal identifier, such as a JEP, when one exists and materially identifies the feature.

For example:

```markdown
**Compact source files and instance `main` methods became final in JDK 25 with JEP 512.**
```

Use the lifecycle wording from the authoritative source. Do not describe a preview release as final or present a later refinement as the feature's first introduction. If the topic is not a versioned feature, do not invent a release history; start the Back with the ordinary direct answer instead.

## Output location and files

- Write the `.md` file in the topic directory selected by the user. If none is specified, infer the best existing topic directory from the current repository and nearby cards.
- Store local visuals in the sibling `svg/` directory when the output is an SVG; use lowercase hyphenated filenames.
- Link visuals with a relative path. The Markdown image alt text must contain the linked file's exact filename, including its extension, without requiring the directory path. Prefer the filename alone, for example: `![jpa-sequence-allocation.svg](images/jpa-sequence-allocation.svg)`. Put the teaching description in the surrounding prose; additional descriptive alt text is allowed when it also includes the filename.
- Do not modify unrelated cards or diagrams. Preserve an existing card's filename unless the user asks to rename it.

## Required card structure

Immediately after the level-one title, add exactly one standalone upward navigation line containing a `Back to …` link wrapped in `<sub>`, without a leading list marker, as shown in the template below. Link to the subject's root/index README, such as `system design/Readme.md`, using the real subject name in the label, the target's actual filename case, and a path relative to the card's directory. Include `#content` only when the target has a `Content` anchor; otherwise use the correct existing anchor or omit the fragment. If the subject has no index README, link to the repository's `README.md` with the label `Back to Anki Flashcards`.

After the navigation line, add one HTML comment recording the selected mode and matching validation flag, followed by `# Front`. Separate the title, navigation line, comment, and `# Front` with blank lines; allow no other intervening content. Use exactly one of these comment forms:

```markdown
<!-- Card mode: simple. Validate with --mode simple. -->
<!-- Card mode: complex. Validate with --mode complex. -->
```

Add or update the navigation link and mode comment whenever creating or revising a card. Both are metadata and do not count toward the simple-mode character limit.

Use this order, adapting the navigation label and target to the card's location. This example is for a card one directory below `system design/Readme.md`:

```markdown
# Clear topic title

<sub>[Back to System Design](../Readme.md#content)</sub>

<!-- Card mode: simple. Validate with --mode simple. -->

# Front

A focused question that tells the learner what they should be able to explain.

# Back

**For a versioned feature: official feature name + lifecycle event + release/version.**

For other topics: the direct answer and most important fact first.

## How it works

Beginner-friendly explanation that introduces the visual model.

![descriptive-name.svg](svg/descriptive-name.svg)

### Important limit

An example or qualification needed to understand the core answer.

# Sources

- [Descriptive source title](https://example.com/source)
```

Use level-one headings for `# Front`, `# Back`, and `# Sources`. The `# Sources` section must be the final section. Keep the Front concise; put teaching content on the Back.

## Writing and formatting

- Define a term before using it to explain another term. Expand abbreviations on first use.
- Prefer short sentences, concrete examples, and explicit cause-and-effect language.
- Explain both **what happens** and **why it matters**. State common misconceptions only when they help prevent a likely error.
- Use level-two headings (`##`) for teaching sections within the Back, including process steps, and level-three headings (`###`) for subsections. When updating the previous hierarchy, shift `###` to `##` and `####` to `###`. Keep bold text for emphasis and the required version lead. Use lists for sequences or sets, and tables only when rows genuinely make comparison easier.
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

Run the validator from this skill directory with the `--mode` recorded in the card comment. The validator requires the comment and checks that its declared mode and flag match the selected validation mode. Fenced code examples do not count as headings, navigation, mode metadata, sources, or teaching visuals; their text still counts toward the Back's character budget. Local navigation checks verify the exact case of each path component and the existence of the README fragment, including heading anchors and explicit HTML anchors:

```bash
python3 scripts/check_anki_card.py --mode simple path/to/card.md
python3 scripts/check_anki_card.py --mode complex path/to/card.md
python3 scripts/check_anki_card.py --mode simple --require-version-lead path/to/versioned-feature-card.md
```

When changing the validator, also run its built-in self-test and regression suite from this skill directory:

```bash
python3 scripts/check_anki_card.py --self-test
python3 -m unittest discover -s scripts/tests
```

The README fragment checker supports standalone ATX (`## Heading`) and Setext headings, common inline formatting, duplicate heading suffixes, and explicit HTML `id`/`name` anchors. For a target generated by an extension or a heading inside a list, blockquote, or raw HTML block, use an explicit HTML anchor and confirm the link in GitHub's rendered README.

Also verify:

- The title, exactly one standalone navigation line without a list marker, mode comment, and `# Front` appear in that order, separated by blank lines with no other intervening content. The comment matches the mode used to create or revise the card.
- The navigation label names the actual subject or repository, and the destination is the intended subject index or repository README.
- The card uses `# Front`, `# Back`, and final `# Sources`, with `##` teaching sections and `###` subsections.
- The opening Back paragraph answers the Front directly.
- A versioned feature card starts with the required bold feature-and-release sentence and passes `--require-version-lead`.
- Every factual statement is supported by the chosen evidence path.
- Every visual is referenced, rendered, inspected, and easy for a novice to interpret.
- Each Java code fence uses `java`, and practical snippets compile or run as claimed.
- Every Markdown image alt text contains the linked image's exact filename, including its extension.
- No text or image link is broken.
- Citations are last and no unrelated files changed.
