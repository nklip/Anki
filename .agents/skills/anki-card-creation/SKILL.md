---
name: anki-card-creation
description: Create or revise Anki-ready Markdown cards in this repository with verified beginner-friendly explanations, correctly highlighted code, local teaching visuals, and end-of-card sources. Use for simple or complex (also called article mode) card creation; not for exporting Anki decks or packages.
---

# Anki Card Creation

Create a self-contained Markdown card that teaches someone who does not already know the topic. Put the answer's most important information first, then build understanding with definitions, a visual model, examples, and qualifications.

## Select a mode

- Default new cards to **simple mode**. Read [references/simple-mode.md](references/simple-mode.md).
- Use **complex mode**, also called **article mode**, when the user requests either name or explicitly asks for comprehensive, multi-stage, or step-by-step treatment. Read [references/complex-mode.md](references/complex-mode.md). Both names select the same mode.
- In article mode, link the numbered `##` sections from an ordered contents list. End the teaching body with [Check your understanding](references/complex-mode.md#review-questions), with at least one question about each preceding `##` section.
- When revising, follow the user's selected mode or the established mode in the subject index or task context. If none is recorded, choose from the lesson's scope: one focused idea is simple; comprehensive treatment is complex. Both modes use the same Markdown structure, so the absence of Front/Back headings does not identify a mode. Do not add mode metadata to the document.
- Pass the selected mode explicitly to the validator: `--mode simple` or `--mode complex`. When revising a legacy card with Front/Back sections, convert the requested file to the shared structure while preserving its teaching content.

In both modes, character limits count the teaching body by default. Exclude the opening title, the back link, and the entire final `# Sources` section. Use a whole-file count only when the user explicitly asks for one.

Simple cards allow up to 3,500 teaching-body characters. Narrow a simple card to its core lesson if needed. Articles have no default cap. When the user asks for an article “under 10k chars,” pass `--under-chars 10k` during final validation and use the reported teaching-body count. Substitute the requested limit for other sizes.

## Research before drafting

Verify every factual claim about the topic using one of these evidence paths:

1. Official or primary documentation that directly supports the claim; or
2. At least two independent, reputable sources when adequate official documentation is unavailable.

Open and read the sources rather than relying on remembered facts or search snippets. Prefer specifications, official manuals, standards, release notes, and project source code over secondary summaries. For Java topics, prefer the JLS, JVMS, JDK API documentation, OpenJDK JEPs, official HotSpot documentation, and version-matched OpenJDK source. Distinguish specified behavior from implementation details and identify the relevant version when behavior can change.

Put all citations in the final `# Sources` section. Do not scatter citations through the teaching content.

Keep research and production history out of the finished study material. Do not add verification announcements or dates, local Anki note/deck IDs, migration or rewriting history, or commentary about creating, redrawing, or adapting diagrams. This applies throughout the card, including `# Sources`, captions, and image descriptions. Keep concise source links and required attribution, useful version scope and release dates, and qualifications that explain an example's assumptions. Verification remains required; its work log does not belong in the lesson.

## Lead sentence for versioned features

When the card is about a feature that was added, previewed, finalized, or made generally available in a particular release, make the first nonblank line of the teaching content a standalone bold sentence immediately after the navigation line in either mode. The sentence states:

1. The feature's official name.
2. The exact lifecycle event, using wording such as **introduced**, **first previewed**, **became final**, or **became generally available**.
3. The release or version in which that event occurred.
4. The authoritative proposal identifier, such as a JEP, when one exists and materially identifies the feature.

For example:

```markdown
**Compact source files and instance `main` methods became final in JDK 25 with JEP 512.**
```

Use the lifecycle wording from the authoritative source. Do not describe a preview release as final or present a later refinement as the feature's first introduction. If the topic is not a versioned feature, do not invent a release history; start the teaching content with the ordinary direct answer instead.

## Output location and files

- Write the `.md` file in the topic directory selected by the user. If none is specified, infer the best existing topic directory from the current repository and nearby cards.
- Store local visuals in the card's own sibling `images/` directory, for both simple cards and articles; use lowercase hyphenated filenames. Every card and article has exactly one `images/` folder with its diagrams directly inside it: no nested `images/images/`, and no `svg/` directory.
- Link visuals with a relative path. The Markdown image alt text must contain the linked file's exact filename, including its extension, without requiring the directory path. Prefer the filename alone, for example: `![jpa-sequence-allocation.svg](images/jpa-sequence-allocation.svg)`. Put the teaching description in the surrounding prose; additional descriptive alt text is allowed when it also includes the filename.
- Do not modify unrelated cards or diagrams. Preserve an existing card's filename unless the user asks to rename it.

## Required card structure

Immediately after the level-one title, add exactly one standalone upward navigation line containing a `Back to …` link wrapped in `<sub>`, without a leading list marker, as shown in the template below. Link to the subject's root/index README, such as `system design/Readme.md`, using the real subject name in the label, the target's actual filename case, and a path relative to the card's directory. Include `#content` only when the target has a `Content` anchor; otherwise use the correct existing anchor or omit the fragment. If the subject has no index README, link to the repository's `README.md` with the label `Back to Anki Flashcards`.

Separate the title, navigation line, and following content with blank lines; allow no other content between the title and navigation line. In both modes, the teaching content follows the navigation line directly. Do not add `# Front`, `# Back`, or equivalent boundary sections. A simple card is a short explanation in the same layout as an article, without a separate question-and-answer wrapper.

Add or update the navigation link whenever creating or revising a card. Neither mode may contain HTML comments in Markdown prose, including mode metadata. Fenced code examples and XML comments in separate SVG assets are unaffected.

Use this shared order, adapting the navigation label and target to the card's location. This simple-mode example is for a card one directory below `system design/Readme.md`. For the numbered article template, see [complex mode](references/complex-mode.md).

```markdown
# Clear topic title

<sub>[Back to System Design](../Readme.md#content)</sub>

**For a versioned feature: official feature name + lifecycle event + release/version.**

For other topics: the direct answer and most important fact first.

## How it works

Beginner-friendly explanation that introduces the visual model.

![descriptive-name.svg](images/descriptive-name.svg)

### Important limit

An example or qualification needed to understand the core answer.

# Sources

- [Descriptive source title](https://example.com/source)
```

Use level-one headings for the opening title and final `# Sources` section in both modes. In simple mode, make the title identify the focused topic or question and begin the body with the direct answer.

## Writing and formatting

- Write in natural, simple language in both simple cards and complex/article mode. Use familiar words and direct, conversational phrasing, as if explaining the topic to a beginner. Avoid stiff or inflated wording and unnecessary jargon. Simplify the wording without losing technical accuracy or important qualifications.
- Define a term before using it to explain another term. Expand abbreviations on first use.
- Prefer short sentences, concrete examples, and explicit cause-and-effect language.
- Explain both **what happens** and **why it matters**. State common misconceptions only when they help prevent a likely error.
- Use level-two headings (`##`) for teaching sections and level-three headings (`###`) for subsections. Put process steps at the level where they belong. In articles, apply the [article section numbering](references/complex-mode.md) to main-section steps too. Within a `###` subsection, optionally use level-four headings for named sub-items, such as use cases, components, patterns, or failure scenarios. Enclose the entire heading text in one bold span, for example `#### **Retrying a failed update**`; a `Use case:` prefix is optional. Inline code may appear inside the bold span. Do not use levels five or six.
- Use bold text for emphasis and the required version lead. Use lists for sequences or sets, and tables only when rows genuinely make comparison easier.
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

Run the validator from this skill directory with the selected `--mode simple` or `--mode complex`. Mode selection is explicit. Heading recognition accepts LF and CRLF line endings. HTML comments outside fenced code are invalid in both modes, including mode metadata. Fenced code examples do not count as headings, navigation, comments, sources, or teaching visuals. Their text counts toward the teaching-body budget in both modes. Local navigation checks verify the exact case of each path component and the existence of the README fragment, including heading anchors and explicit HTML anchors:

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

- The title and exactly one standalone navigation line without a list marker appear first, separated by blank lines. The teaching body follows the navigation line, with a blank line and no intervening metadata.
- The navigation label names the actual subject or repository, and the destination is the intended subject index or repository README.
- Both modes omit Front/Back boundary headings and have final `# Sources`, `##` teaching sections, and `###` subsections, with optional bold `####` named sub-items nested within subsections. The validator checks level-four bold formatting and nesting; manually confirm that each sub-item belongs within its parent subsection.
- Neither mode contains HTML comments outside fenced code, including mode metadata.
- The opening teaching paragraph states the core answer to the title's topic or question.
- The prose sounds natural, uses simple language, and explains necessary technical terms without sacrificing accuracy.
- A versioned feature card starts with the required bold feature-and-release sentence and passes `--require-version-lead`.
- Every factual statement is supported by the chosen evidence path.
- No authoring or process commentary remains. The validator catches common verification, local-note history, and diagram-production phrases; review other wording manually.
- Every visual is referenced, rendered, inspected, and easy for a novice to interpret.
- Each Java code fence uses `java`, and practical snippets compile or run as claimed.
- Every Markdown image alt text contains the linked image's exact filename, including its extension.
- No text or image link is broken.
- Citations are last and no unrelated files changed.
