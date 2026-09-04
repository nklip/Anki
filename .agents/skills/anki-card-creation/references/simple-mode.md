# Simple mode

Use simple mode unless the user selects complex mode.

## Outcome

Create one focused card that teaches a single core idea without assuming prior knowledge.

Requirements:

- The teaching content must contain **at most 3,000 Unicode characters**. The `## Front` and
  `## Sources` sections are excluded from that count: the Front is a prompt rather than teaching,
  and a card must never have to drop a citation to stay in budget. Everything else — the Back,
  its headings, tables, code, and image links — counts. Measure it with the bundled validator;
  do not treat bytes or words as characters.
- Include at least **one** local SVG or image. Prefer one purpose-built SVG that carries the central explanation.
- Ask one focused question on the Front.
- Begin the Back with a direct answer in one short paragraph. For a versioned feature, its first line must follow the shared bold feature-and-release rule and pass `--require-version-lead`.
- Include only the definitions, example, limitation, or warning needed to make that answer understandable.
- Keep the `## Sources` list compact while still meeting the shared verification rule.

Do not try to fill the character budget. If the topic is broad, teach its most important mental model and omit secondary detail. A short example is better than a catalog of features.

Before finishing, run:

```bash
python3 scripts/check_anki_card.py --mode simple path/to/card.md
```

Any result above 3,000 counted characters or without a valid local visual is a failure.
