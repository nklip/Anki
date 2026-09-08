---
name: anki-card-creation
description: Create or revise Anki-ready Markdown cards in this repository with verified beginner-friendly explanations, correctly highlighted code, local teaching visuals, and end-of-card sources. Use for simple or complex (also called article mode) card creation; not for exporting Anki decks or packages.
---

# Anki Card Creation

Create a self-contained Markdown card that teaches someone who does not already know the topic. Put the answer's most important information first, then build understanding with definitions, a visual model, examples, and qualifications.

## Select a mode

- Default new cards to **simple mode**. Read [references/simple-mode.md](references/simple-mode.md).
- Use **complex mode**, also called **article mode**, when the user requests either name or explicitly asks for comprehensive, multi-stage, or step-by-step treatment. Read [references/complex-mode.md](references/complex-mode.md). Both names select the same mode; use `--mode complex` for explicit validation.
- When revising, follow the user's selected mode or infer it from the existing structure: any exact `Front` or `Back` heading at level one or legacy level two, outside fenced code and HTML comments, indicates simple mode; none indicates complex/article mode. A single heading or a mixed-level pair is still simple content requiring repair. Promote legacy `## Front`/`## Back` to `# Front`/`# Back` and add any missing boundary; mode comments do not select the mode.

Do not silently relax simple mode's 3,000-character limit, which counts the Back only — `# Front` and `# Sources` are excluded. Narrow a simple-mode card to its core lesson instead of changing its mode merely to exceed the limit.

## Research before drafting

Verify every factual claim about the topic using one of these evidence paths:

1. Official or primary documentation that directly supports the claim; or
2. At least two independent, reputable sources when adequate official documentation is unavailable.

Open and read the sources rather than relying on remembered facts or search snippets. Prefer specifications, official manuals, standards, release notes, and project source code over secondary summaries. For Java topics, prefer the JLS, JVMS, JDK API documentation, OpenJDK JEPs, official HotSpot documentation, and version-matched OpenJDK source. Distinguish specified behavior from implementation details and identify the relevant version when behavior can change.

Put all citations in the final `# Sources` section. Do not scatter citations through the teaching content.

## Lead sentence for versioned features

When the card is about a feature that was added, previewed, finalized, or made generally available in a particular release, make the first nonblank line of the teaching content a standalone bold sentence. This is under `# Back` in simple mode and immediately after the navigation line in complex/article mode. The sentence states:

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
- Store local visuals in the sibling `svg/` directory when the output is an SVG; use lowercase hyphenated filenames.
- Link visuals with a relative path. The Markdown image alt text must contain the linked file's exact filename, including its extension, without requiring the directory path. Prefer the filename alone, for example: `![jpa-sequence-allocation.svg](images/jpa-sequence-allocation.svg)`. Put the teaching description in the surrounding prose; additional descriptive alt text is allowed when it also includes the filename.
- Do not modify unrelated cards or diagrams. Preserve an existing card's filename unless the user asks to rename it.

## Required card structure

Immediately after the level-one title, add exactly one standalone upward navigation line containing a `Back to …` link wrapped in `<sub>`, without a leading list marker, as shown in the template below. Link to the subject's root/index README, such as `system design/Readme.md`, using the real subject name in the label, the target's actual filename case, and a path relative to the card's directory. Include `#content` only when the target has a `Content` anchor; otherwise use the correct existing anchor or omit the fragment. If the subject has no index README, link to the repository's `README.md` with the label `Back to Anki Flashcards`.

Separate the title, navigation line, and following content with blank lines; allow no other content between the title and navigation line. In simple mode, `# Front` follows the navigation line with no intervening content. In complex/article mode, the teaching content follows the navigation line directly, without `# Front` or `# Back`.

Add or update the navigation link whenever creating or revising a card. Neither mode may contain HTML comments in Markdown prose, including mode metadata; remove legacy comments when revising. Fenced code examples and XML comments in separate SVG assets are unaffected. The navigation line does not count toward the simple-mode character limit.

Use this simple-mode order, adapting the navigation label and target to the card's location. This example is for a card one directory below `system design/Readme.md`; the article template is in [references/complex-mode.md](references/complex-mode.md):

```markdown
# Clear topic title

<sub>[Back to System Design](../Readme.md#content)</sub>

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

Use level-one headings for simple mode's `# Front` and `# Back`, and for both modes' final `# Sources` section. Keep the simple-mode Front concise and put its teaching content on the Back.

## Writing and formatting

- Define a term before using it to explain another term. Expand abbreviations on first use.
- Prefer short sentences, concrete examples, and explicit cause-and-effect language.
- Explain both **what happens** and **why it matters**. State common misconceptions only when they help prevent a likely error.
- Use level-two headings (`##`) for teaching sections within the Back or article body, including process steps, and level-three headings (`###`) for subsections. When updating the previous hierarchy, shift `###` to `##` and `####` to `###`. Keep bold text for emphasis and the required version lead. Use lists for sequences or sets, and tables only when rows genuinely make comparison easier.
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

Run the validator from this skill directory. Its default `--mode auto` follows the shared mode-selection rule, including legacy level-two boundaries; use `--mode simple` or `--mode complex` to check a selected format explicitly. Heading recognition accepts LF and CRLF line endings. HTML comments outside fenced code are invalid in both modes, including mode metadata. Fenced code examples do not count as headings, navigation, comments, sources, or teaching visuals; their text still counts toward a simple-mode Back's character budget. Local navigation checks verify the exact case of each path component and the existence of the README fragment, including heading anchors and explicit HTML anchors:

```bash
python3 scripts/check_anki_card.py path/to/card.md
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

- The title and exactly one standalone navigation line without a list marker appear first, separated by blank lines. The navigation line is followed by simple mode's `# Front` or the article body, with a blank line and no intervening metadata.
- The navigation label names the actual subject or repository, and the destination is the intended subject index or repository README.
- Simple mode uses `# Front` and `# Back`; complex/article mode omits both. Both modes have final `# Sources`, `##` teaching sections, and `###` subsections.
- Neither mode contains HTML comments outside fenced code, including mode metadata.
- The opening teaching paragraph states the core answer; in simple mode it answers the Front directly.
- A versioned feature card starts with the required bold feature-and-release sentence and passes `--require-version-lead`.
- Every factual statement is supported by the chosen evidence path.
- Every visual is referenced, rendered, inspected, and easy for a novice to interpret.
- Each Java code fence uses `java`, and practical snippets compile or run as claimed.
- Every Markdown image alt text contains the linked image's exact filename, including its extension.
- No text or image link is broken.
- Citations are last and no unrelated files changed.
