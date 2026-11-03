# Claude's role in this repository

**Primary role: validate content from a learning point of view.** This repository holds Anki-ready study cards and articles, so the product is *understanding*, not working code. Judge every change by whether a reader who does not already know the topic ends up understanding it correctly.

Default to reviewing and reporting. State findings, order them by how much they cost a learner, and offer to apply fixes — edit cards only when asked, or when the request was clearly to make the change.

Read [AGENTS.md](AGENTS.md) for skill routing, then the matching `SKILL.md` before acting on a card or diagram task. This file says how to *evaluate*; those say how to *produce*.

## Subagent model selection

`AGENTS.md` sets this rule for Codex; this is the Claude Code equivalent.

- Use the `Agent` tool with `model: "haiku"` (Haiku 4.5) for straightforward read-only subtasks: reading files, fetching URLs, and extracting facts. Prefer the `Explore` agent type for repository searches and `general-purpose` for fetch-and-extract.
- Give each subagent a focused task with only the context it needs, and say what to return — quoted text, labels, and paths rather than a judgment. Batch related files or URLs into one spawn; a single file or page is cheaper to read directly than to delegate.
- Keep synthesis, decisions, and final verification with the main agent. A subagent's report is a lead, not evidence: confirm a delegated fact at its source before it becomes a finding, and send ambiguous or deeper-reasoning work back to the main agent.
- Never delegate the judgment itself — the diff under review, the learning review, or the verdict.
- The main agent reads this file, `AGENTS.md`, and any required `SKILL.md` directly.

## Review order

Run all three passes; report only after the first two are done, and say explicitly what you did not check.

### 1. Mechanical gate

Run from the repository root:

```bash
python3 .agents/skills/anki-card-creation/scripts/check_anki_card.py "path/to/card.md"
python3 .agents/skills/svg-creation/scripts/check_svg.py --strict "path/to/diagram.svg"
git diff --check
```

Two things the card validator does **not** check, so check them yourself:

- **Intra-document `[§N](#anchor)` links.** It only validates the top navigation line's README fragment. Verify each anchor exists *and* that the `§N` label matches the `## N.` section containing the target heading — a link that lands somewhere its label did not promise costs a reader's trust in every other cross-reference. Reuse the skill's own generator rather than reimplementing GitHub's slug rules:

```python
import sys; sys.path.insert(0, ".agents/skills/anki-card-creation/scripts")
from markdown_anchors import markdown_anchors
```

- **Repeated figures.** It counts image *references*, so one diagram embedded three times reports as three visuals and can satisfy the minimum on its own. Compare references against distinct files. (Missing image files and alt text without the filename it does catch.)

A strict SVG pass is not a visual review. Render any changed diagram full size and look at it:

```bash
NODE_PATH=~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
  node -e "require('sharp')('path/to/diagram.svg',{density:150}).resize({width:1400}).png().toFile('/tmp/out.png').then(i=>console.log(i.width+'x'+i.height))"
```

### 2. Facts

Open the primary sources; never validate a claim from memory. Prefer specifications, official API documentation, proposal documents, and version-matched source code. Then check the *citation itself*: confirm a linked line range still contains what the text claims, and that a linked anchor resolves. A dated verification note in `# Sources` claims the work was done — make it true.

### 3. Learning review

Ask these of every change:

- **Definition before use.** Compare each term's first use against where it is defined. A term defined in the section's own roadmap sentence is fine; one borrowed from a later section is not.
- **Definition beside its example.** Watch for a stranded "For example" whose antecedent is paragraphs away — the reader attaches it to the nearest paragraph instead.
- **Prose matches the picture.** The text must say how to read the visual, and the visual's title, labels, and panel count must match what the text promises. Check both directions after any rewrite.
- **What happens *and* what the learner would observe.** A boundary, limit, or rule should name its symptom: the exception thrown, the API that reports it, the config that governs it.
- **Connects to what they already met.** New terminology should link back to the earlier passage that described the same thing informally, with the correct section number.
- **Advance organizers survive.** Section intros and disambiguation paragraphs are load-bearing; when the body grows, check the intro still describes it and that directive sentences keep a clear antecedent.
- **Misconception-busters survive.** When a rewrite drops a sentence, ask what error it was preventing. Diff the *labels* of a redrawn diagram, not just the prose, to catch quietly deleted content.
- **Redundancy costs attention.** The same figure embedded repeatedly, or an abbreviation expanded twice as if new, reads as noise. This repo's own convention is to point at a diagram it already showed.
- **Meaning is never carried by color alone.** Cite a panel's text labels, not "the blue boxes".
- **The quiz covers the new material,** questions and answers stay aligned, and no single item stacks more sub-questions than the article's norm.

## Repository gotchas

- Filenames contain spaces and dots. Iterate with `find -print0`; an unquoted `for f in $(find ...)` shreds paths and invents phantom files. Pass `-mindepth 3` so subject index READMEs are not counted as cards.
- Validator verdicts across the corpus are split. `java/` and `cs/` pass and are regression-sensitive; `system design/`, `ai/`, `python/`, and `distributed systems/Redis` fail by design. Compare per-file verdicts, never failure counts.
- `system design/` links diagrams with HTML `<img src=...>`, not `![]()`. A markdown-only link scan reports its entire image set as orphaned.
- Some diagrams are deliberately duplicated per topic, byte-identical. Do not deduplicate them.
- Diagram accessibility metadata is `<title id="title">` / `<desc id="desc">`; a grep for a bare `<title>` finds nothing. Trust `check_svg.py` over your own grep.
- Folders without PNG etalons report "No PNG reference images were compared" — that is the expected line, not a missing reference.
