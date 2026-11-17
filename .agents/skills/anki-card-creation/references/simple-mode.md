# Simple mode

Use simple mode for new cards unless the user selects complex mode (also called article mode). For revisions, follow the shared mode-selection rule.

## Outcome

Create one focused card that teaches a single core idea without assuming prior knowledge.

Requirements:

- Use the same layout as an article: title, one standalone upward navigation line without a list marker, teaching body, then final `# Sources`. Separate these with blank lines. Do not add Front/Back boundary headings or a separate question section. Do not generate HTML comments in Markdown prose, including mode metadata; fenced code examples are unaffected.
- The teaching body must contain **at most 3,500 Unicode characters**. Exclude the opening title, navigation line, and final `# Sources` section. Count the body Markdown, including prose, headings, tables, code, and image links; trim only outer whitespace and normalize CRLF line endings to LF. Measure it with the bundled validator, not bytes or words. A card must never have to drop a citation to stay in budget.
- Include at least **one** local SVG or image from the sibling `images/` directory. Prefer one purpose-built SVG that carries the central explanation.
- Make the title identify one focused topic or question.
- Begin the body immediately after the navigation line with a direct answer in one short paragraph. For a versioned feature, its first line must follow the shared bold feature-and-release rule and pass `--require-version-lead`.
- Include only the definitions, example, limitation, or warning needed to make that answer understandable.
- Keep the `# Sources` list compact while still meeting the shared verification rule.

Do not try to fill the character budget. If the topic is broad, teach its most important mental model and omit secondary detail. A short example is better than a catalog of features.

Before finishing, run:

```bash
python3 scripts/check_anki_card.py --mode simple path/to/card.md
```

Any result above 3,500 counted characters or without a valid local visual is a failure.
