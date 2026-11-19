# Repository guidance for agents

This repository contains Anki-ready Markdown study cards and their local teaching diagrams. Keep changes scoped to the requested topic and preserve unrelated cards, images, and worktree changes.

This file applies to the entire repository. More specific `AGENTS.md` files may add or override guidance for their own subdirectories if they are introduced later.

## Keep study content focused on the subject

Do not add authoring or process commentary to cards, articles, or learner-facing diagram text, including accessibility descriptions. Omit fact-checking announcements and dates, local Anki note/deck IDs and migration history, and narration about creating, redrawing, or adapting diagrams. Keep source links and required attribution, meaningful version scope and release dates, and qualifications needed to understand an example. Perform research and validation without appending a report of that work to the study material.

## Subagent model selection

- Use `gpt-5.6-luna` with `low` reasoning effort for straightforward read-only subtasks, such as reading files or URLs, and extracting facts.
- Give each subagent a focused task with only the context it needs. Batch related files or URLs together.
- Keep synthesis, decisions, and final verification with the main agent. Return ambiguous findings or work requiring deeper reasoning to the main agent.
- The main agent must still read applicable repository instructions and required skills directly.

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

- Default new cards to simple mode; use complex mode (also called article mode) when the user selects either name or clearly requests comprehensive treatment. When revising, follow the selected or established mode, using the lesson's scope when none is recorded.
- Both modes use title, navigation, teaching body, and final `# Sources`, without Front/Back boundary headings or HTML comments in Markdown prose. Simple mode allows up to 3,500 teaching-body characters and requires at least one local visual. Article mode requires at least two visuals and has a character limit only when requested.
- Verify factual claims using authoritative sources, or the fallback evidence rule defined by the skill.
- Use local teaching visuals from the card's sibling `images/` directory and link them with relative paths.
- Do not use this skill for exporting `.apkg` decks or other Anki package formats.

Validate from the repository root with an explicit mode. The shared document layout does not identify simple versus article mode, so the validator requires `--mode simple` or `--mode complex` and does not infer the mode from headings or length. Both modes count only the teaching body by default, excluding the opening title, back link, and final Sources section. For an article requested under 10k characters, pass `--under-chars 10k`.

```bash
python3 .agents/skills/anki-card-creation/scripts/check_anki_card.py --mode simple path/to/card.md
python3 .agents/skills/anki-card-creation/scripts/check_anki_card.py --mode complex path/to/card.md
```

For validator changes, run both the built-in self-test and regression suite:

```bash
python3 .agents/skills/anki-card-creation/scripts/check_anki_card.py --self-test
python3 -m unittest discover -s .agents/skills/anki-card-creation/scripts/tests
```

For cards about versioned features, follow the skill's version-lead rule and add `--require-version-lead` to validation.

### `anki-publish`

Entry point: [`.agents/skills/anki-publish/SKILL.md`](.agents/skills/anki-publish/SKILL.md)

Use this skill when the user asks to publish or update a repository card or article in the Anki desktop app. It resolves the related deck and existing note, preserves VS Code Markdown preview styling and local media, and updates content in place without changing review scheduling. Editing Markdown alone does not authorize publication.

- Preserve existing note/card identities, decks, tags, templates, due dates, and review state. Never delete and recreate a note to refresh its content.
- Use the guarded AnkiConnect helper and its before/after verification. Follow the skill's identity, rendering, and recovery references; do not infer deck names or note identity from a title alone.
- For content creation followed by publication, complete `anki-card-creation` and any required `svg-creation` work first, then use `anki-publish`.

Validate helper changes with:

```bash
python3 -m unittest discover -s .agents/skills/anki-publish/scripts -p 'test_*.py'
```

### `svg-creation`

Entry point: [`.agents/skills/svg-creation/SKILL.md`](.agents/skills/svg-creation/SKILL.md)  
Runtime requirements: [`.agents/skills/svg-creation/README.md`](.agents/skills/svg-creation/README.md)

Use this skill when creating, recreating, comparing, or repairing standalone SVG teaching diagrams and technical illustrations. It covers source-native SVG structure, layout, text clearance, connectors and arrowheads, accessibility metadata, PNG-etalon comparison, and visual review.

- Use the card's or article's own `images/` directory as the asset boundary, including when it is the current working directory; never nest an asset directory inside it, so no `images/images/`. Each new card or article gets its own `images/`; the repository no longer uses an `svg/` folder for new or revised visuals.
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
