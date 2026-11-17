# AnkiConnect operations

## Prerequisite and transport

Use the desktop Anki profile that owns the target collection, with [AnkiConnect](https://ankiweb.net/shared/info/2055492159) enabled. Its upstream project is [FooSoft AnkiConnect](https://git.sr.ht/~foosoft/anki-connect). If missing, explain that setup requires installing add-on code `2055492159` through Anki's add-on manager and restarting Anki; do not perform installation just because publication was requested. Read-only diagnosis and preparation can continue. Do not substitute direct database edits or `.apkg` import.

The helper uses API v6 and `http://127.0.0.1:8765`. `ANKI_CONNECT_URL` may select another **literal loopback IP and port**; it rejects remote hosts, proxy forwarding, redirects, and URLs containing credentials. Supply a configured API key through `ANKI_CONNECT_KEY`, never a committed file or logged command argument. `--timeout` is a global option, at most 60 seconds. No request is automatically retried.

Commands below run from the repository root. Create JSON parameter files as actual UTF-8 JSON using a serializer. Do not interpolate HTML or secrets into shell command text. Store run artifacts in the ignored local `.anki-publish/` directory (see identity reference).

```bash
python3 .agents/skills/anki-publish/scripts/anki_connect.py --help
python3 .agents/skills/anki-publish/scripts/anki_connect.py read version --params .anki-publish/empty.json
python3 .agents/skills/anki-publish/scripts/anki_connect.py read getActiveProfile --params .anki-publish/empty.json
python3 .agents/skills/anki-publish/scripts/anki_connect.py read deckNamesAndIds --params .anki-publish/empty.json
```

Here `empty.json` contains `{}`. Probe `apiReflect` when capability discovery is needed, for example with `{"scopes":["actions"],"actions":["notesInfo","cardsInfo","getReviewsOfCards","updateNoteFields"]}`. Verify required actions before media or note writes. If the installed API cannot expose the properties required by the updater, report the limitation rather than disabling verification.

`read` exposes a narrow allowlist: version/capability/profile discovery; deck names/IDs; model fields, templates and styling; note search/info; card info; review logs; media retrieval. For candidate lookup, `findNotes` takes `{"query":"..."}` and `notesInfo` takes `{"notes":[1234567890123]}`. Fetch models using their exact `modelName` from note info. Validate a found note's actual identity field rather than trusting search matching alone.

## Existing note: guarded content update

Keep Anki idle during the short snapshot/update/verification window: do not review cards, sync, edit the note, or switch profiles concurrently. The API does not provide an atomic compare-and-swap or lock. Do not automatically stop user activity; if activity is detected, leave the prepared update and obtain a fresh snapshot after it ends.

Before calling the updater, resolve identity, inspect all associated cards and templates, compare last-published hashes if available, and finish the HTML/media preparation. The helper is a guarded **field updater**, not a Markdown renderer or matching engine. It cannot decide which note belongs to a source.

```bash
python3 .agents/skills/anki-publish/scripts/anki_connect.py snapshot 1234567890123 --out .anki-publish/run/before.json
python3 .agents/skills/anki-publish/scripts/anki_connect.py update 1234567890123 --fields .anki-publish/run/fields.json --before .anki-publish/run/before.json
```

`fields.json` is a nonempty **partial** map of the exact fields being changed, for example:

```json
{"Front":"Text of the first level-one heading","Back":"<style>...</style><div class=\"anki-publish-example-back\">Rendered answer body, images and sources</div>"}
```

Use the prepared standard-text Front and rendered Back in place of the illustrative contents, following the rendering reference's title and spacing rules. Preserve the template's normal FrontSide, answer divider, and Anki margins; do not add field CSS that changes them by default. Omit unchanged or unmapped fields; never send empty placeholders. Keep SourceId immutable. The helper reads the expected state again, rejects stale snapshots and unsafe/unsupported templates, saves pre-write and after-write checkpoints, sends only `updateNoteFields`, and compares the result. An identical field map returns a no-op without a write.

Anki template behavior determines card generation. The guarded workflow handles existing ordinary unconditional front/back templates with all expected card ordinals present. It rejects cloze, conditional/filtered expressions, missing cards, formerly blank generation fields being populated, and blank replacements. Do not loosen those checks to update cloze or optional reverse notes. Assess such a note separately and explain the structural constraint; do not migrate it as a side effect of publication.

Success verifies the note identity, intended field values, untouched fields/tags, model fields/templates/style, card identity, every returned card property except rendered HTML/field copies/CSS and modification timestamp, and every returned review row. Required properties include due, queue, type, interval, factor, reps, lapses, remaining learning steps, ordinal, and deck name. Additional properties such as flags or original due/deck are compared if returned. Unexposed FSRS or database fields are not independently verified. The updater has no method to modify them.

If a transport error occurs, after-state is still captured when possible. Even when the desired fields are present, the command reports the uncertain request for reconciliation. Inspect the checkpoints and re-read; finalize an already successful update after verifying it, without sending the mutation again. Never automatically restore scheduling or replay a whole failed batch. Checkpoints are diagnostic content, not full collection backups.

Use the original `.prewrite.json` checkpoint named in the updater's result/error to verify an applied write without another Anki mutation:

```bash
python3 .agents/skills/anki-publish/scripts/anki_connect.py verify 1234567890123 --fields .anki-publish/run/fields.json --before .anki-publish/run/before.TIMESTAMP.prewrite.json
```

Substitute the actual checkpoint filename. This compares the intended content and preserved state with the original baseline. Do not replace that baseline with a fresh snapshot merely to get a no-op result; that can conceal a scheduling mismatch.

## New note: explicit creation

Search/reconcile before creating. Use one note per source. For a new dedicated model, a suitable `createModel` parameter file is:

```json
{
  "modelName": "Repository Markdown v1",
  "inOrderFields": ["SourceId", "Front", "Back"],
  "css": "",
  "isCloze": false,
  "cardTemplates": [{"Name":"Card 1","Front":"{{Front}}","Back":"{{Back}}"}]
}
```

These are suggested names: discover and inspect any existing model of that name first. Reuse it only if its fields and single-card template fit. If it is incompatible, choose a new dedicated name rather than overwriting it. SourceId is the first field to provide stable duplicate checking, but is absent from the visible templates. Separate front/back display avoids duplicating an article title and content via FrontSide.

After verifying media, prepare `addNote`:

```json
{
  "note": {
    "deckName": "Computer Science::Java",
    "modelName": "Repository Markdown v1",
    "fields": {
      "SourceId": "repository-uuid:source-uuid",
      "Front": "Text of the first level-one heading",
      "Back": "<style>...</style><div class=\"anki-publish-example-back\">Rendered answer without repeated question/title</div>"
    },
    "options": {"allowDuplicate": false, "duplicateScope": "collection"},
    "tags": []
  }
}
```

Use actual discovered names and generated UUIDs. With SourceId first, duplicate checking is useful, but it does not replace collection-wide matching of older unmanaged notes. Do not append arbitrary tags. The helper also supports an `anki-publish::source::<id>` identity tag for an established compatible scheme; prefer the SourceId field for new publisher-owned models.

```bash
python3 .agents/skills/anki-publish/scripts/anki_connect.py write createModel --params .anki-publish/run/new-model.json
python3 .agents/skills/anki-publish/scripts/anki_connect.py write addNote --params .anki-publish/run/new-note.json
```

Run the first command only if that model is absent. A new explicitly resolved deck can be created with `write createDeck` and `{"deck":"Exact::Deck"}`. The `write` command permits only `createModel`, `createDeck`, `addNote`, and `storeMediaFile`; it is not a generic escape hatch. Its creation commands are not transactional or automatically idempotent: use the pending-operation journal and reconciliation rules in the identity reference.

Read the new note and cards back, verify exact fields, identity, expected card count and actual destination, inspect Anki Preview, then commit its binding locally. New notes receive Anki's normal new-card state; do not assign a due date to imitate another note.

## Media transfer

Use `retrieveMediaFile` with `{"filename":"anki-publish-<sha256>.svg"}` to check an existing asset. It returns base64 or false for missing media. Compare decoded bytes with the prepared file. Upload a missing asset through `write storeMediaFile` using `{"filename":"anki-publish-<sha256>.svg","data":"<base64 bytes>"}`. Use the API's returned filename and retrieve it to verify the hash before inserting its reference. Prefer base64 over remote URL downloads to make the transferred bytes explicit. Do not call deleteMediaFile.

## Validation of this helper

The bundled tests use fake API responses and do not contact or modify Anki:

```bash
python3 -m unittest discover -s .agents/skills/anki-publish/scripts -p 'test_*.py'
```

These tests validate preservation guards and request behavior. They do not establish compatibility with every Anki/add-on version or prove rendering fidelity; perform the live readback and visual checks on each authorized publication.

## Primary references

- [AnkiConnect upstream](https://git.sr.ht/~foosoft/anki-connect) and [AnkiWeb add-on listing](https://ankiweb.net/shared/info/2055492159)
- [Historical upstream implementation: field updates, card info, reviews](https://github.com/FooSoft/anki-connect/blob/master/plugin/__init__.py) — useful API evidence, not a claim that this is the latest implementation; inspect installed capabilities.
- [Anki note fields and duplicate checking](https://docs.ankiweb.net/editing.html)
- [Anki HTML and shared styling](https://docs.ankiweb.net/templates/styling.html)
