# Repository guidance for agents

This repository contains Anki-ready Markdown study cards and their local teaching diagrams. Keep changes scoped to the requested topic and preserve unrelated cards, images, and worktree changes.

This file applies to the entire repository. More specific `AGENTS.md` files may add or override guidance for their own subdirectories if they are introduced later.

## Repository skills

Repository-scoped skills live in `.agents/skills/`. Codex discovers these skills automatically when it runs inside this repository. A skill may be invoked explicitly by name or selected implicitly when its description matches the task.

When a task names or clearly matches a skill:

1. Read that skill's complete `SKILL.md` before taking task actions.
2. Follow links to references only when the skill routes the current task to them.
3. Prefer the skill's scripts for deterministic validation instead of recreating their checks manually.
4. Treat this file as routing and repository context; the selected `SKILL.md` remains the authoritative workflow.

Official background: [custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md) and [building and using Codex skills](https://developers.openai.com/codex/skills).

### `anki-card-creation`

Entry point: [`.agents/skills/anki-card-creation/SKILL.md`](.agents/skills/anki-card-creation/SKILL.md)

Use this skill when creating or revising Anki-ready Markdown cards in this repository. It covers research quality, beginner-friendly teaching structure, simple and complex modes, source placement, code examples, local visuals, and final card validation.

- Use simple mode by default; use complex mode only when the user selects or clearly requests comprehensive treatment.
- Keep the required `Front`, `Back`, and final `Sources` structure.
- Verify factual claims using authoritative sources, or the fallback evidence rule defined by the skill.
- Use local teaching visuals and link them with relative paths.
- Do not use this skill for exporting `.apkg` decks or other Anki package formats.

Validate from the repository root with the appropriate mode:

```bash
python3 .agents/skills/anki-card-creation/scripts/check_anki_card.py --mode simple path/to/card.md
python3 .agents/skills/anki-card-creation/scripts/check_anki_card.py --mode complex path/to/card.md
```

For cards about versioned features, follow the skill's version-lead rule and add `--require-version-lead` to validation.

### `svg-creation`

Entry point: [`.agents/skills/svg-creation/SKILL.md`](.agents/skills/svg-creation/SKILL.md)  
Runtime requirements: [`.agents/skills/svg-creation/README.md`](.agents/skills/svg-creation/README.md)

Use this skill when creating, recreating, comparing, or repairing standalone SVG teaching diagrams and technical illustrations. It covers source-native SVG structure, layout, text clearance, connectors and arrowheads, accessibility metadata, PNG-etalon comparison, and visual review.

- Use an existing `svg/` or `images/` directory as the asset boundary, including when it is the current working directory; never create another `svg/` or `images/` directory inside it.
- Keep diagrams editable and source-native; never embed the PNG etalon with `<image>`.
- Preserve the etalon's canvas, content, colors, labels, connector routing, and arrowheads when recreating a PNG.
- A same-stem PNG beside an SVG is discovered automatically by the checker.
- Treat strict comparison warnings as actionable. Generate difference images when a mismatch is not immediately obvious.
- Automated checks do not replace full-size side-by-side visual inspection, especially around text and connector endpoints.
- Do not use this skill for raster artwork or an established code-generated icon system.

Validate from the repository root:

```bash
python3 .agents/skills/svg-creation/scripts/check_svg.py --strict path/to/diagram.svg
```

For explicit references and difference artifacts, follow [`.agents/skills/svg-creation/references/reference-validation.md`](.agents/skills/svg-creation/references/reference-validation.md).

## Combining the skills

When a card task needs a new or revised diagram, use both skills in this order:

1. Use `anki-card-creation` to determine the card mode, lesson, required visual, file location, and surrounding explanation.
2. Use `svg-creation` to create or repair the visual and complete its strict render-and-review workflow.
3. Return to `anki-card-creation` to verify the relative image link and validate the completed card.

For an SVG-only request, use `svg-creation` without loading the card workflow. For a prose-only card edit that does not add or alter a visual, use `anki-card-creation` alone.

## Maintaining repository skills

Do not alter a skill's instructions, references, or scripts unless the user asks for a skill change or the task explicitly includes maintaining the workflow. When updating a skill:

- keep `SKILL.md` focused and route conditional detail into `references/`;
- use scripts only for repeated deterministic checks;
- update related documentation and regression tests together;
- run the changed script, its tests, and `git diff --check` before delivery;
- preserve compatibility with the repository paths and examples described above.
