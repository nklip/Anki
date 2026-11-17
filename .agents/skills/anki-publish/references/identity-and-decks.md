# Identity and deck resolution

## Profile and deck

Use AnkiConnect `getActiveProfile` and `deckNamesAndIds`. Do not switch profiles automatically. If the intended profile is unknown and there is no established binding, use the active profile only after checking that its decks and candidate notes match the requested subject. If that evidence is inconclusive, ask for the intended profile.

Resolve a new note's deck in this order:

1. The user's explicit deck or an established mapping for this source.
2. A previously verified subject-to-deck mapping for the same profile.
3. A uniquely matching existing deck supported by subject and neighboring notes.

Repository subjects include `ai`, `aws`, `cs`, `distributed systems`, `java`, `k8s`, `python`, and `system design`. Discover their real deck names, capitalization, and `::` hierarchy. Do not manufacture a new hierarchy or fall back to Default. Ask when several destinations are equally plausible. Create a new deck only when the requested destination or lack of a suitable deck has been resolved.

Decks belong to cards. Notes with several cards can span decks, and filtered decks can temporarily change apparent placement. Existing-note publication preserves all current placement; a folder move does not authorize moving cards. Identify a note collection-wide, even if its current deck differs from a folder-derived destination.

## Durable source identity

Use a local binding file at `<repo>/.anki-publish/state.json`. Keep it machine-local with a narrow `.git/info/exclude` entry when permitted; never commit profile names, note IDs, snapshots, or personal collection content by accident. Use restrictive file permissions and atomic replacement. Do not store API keys there. If the local file cannot be written, retain a task artifact and report that persistence is pending.

Suggested schema (values are illustrative, not defaults):

```json
{
  "schema": 1,
  "repositoryId": "a-generated-uuid",
  "sources": {
    "another-generated-uuid": {
      "path": "java/Syntax. Record classes/Readme.md",
      "profile": "User 1",
      "noteId": 1234567890123,
      "modelName": "Repository Markdown v1",
      "deck": "Computer Science::Java",
      "fields": {"front": "Front", "back": "Back"},
      "lastPublishedFieldHashes": {"Front": "sha256:...", "Back": "sha256:..."},
      "sourceHash": "sha256:...",
      "renderFingerprint": "sha256:..."
    }
  }
}
```

Allocate an immutable UUID per source. Do not derive identity only from a title, filename, absolute checkout path, or content hash. New notes get `SourceId = <repositoryId>:<sourceUUID>` in a dedicated field; the field is not displayed. Do not add metadata to Markdown prose. An adopted existing note can be tracked entirely in the binding file so that only its intended content fields change.

On each run:

- Confirm profile and note ID against fresh `notesInfo`; an ID alone is not enough across profiles. Validate model, field mapping, source identity when present, and prior published field hashes.
- Search the `SourceId` collection-wide and compare its returned field value **exactly**. Search syntax is a candidate filter, not proof of identity. Escape search literals. Two exact identity matches are a conflict.
- For a rename/move, reuse the binding and UUID using Git rename evidence or a confirmed source mapping. A byte-identical copy may be a new note; do not merge it automatically. If the manifest is lost, search SourceId and legacy candidates before creating.
- Compare current mapped fields to their last-published hashes. If they differ and the user has not already authorized overwriting those edits, show the source-versus-Anki conflict and ask which version to keep. A fresh pre-write snapshot also detects edits made during this publication.

## Adopt an existing note

For an unbound source, search for its title, distinctive front text, and neighboring subject notes, including outside the inferred deck. Inspect `notesInfo`, `cardsInfo`, model fields/templates, and full content. Title equality alone is insufficient.

Adopt a unique, convincing match or a note explicitly identified by the user. Save its ID and mapping locally; do not change its tags or add fields to its shared model. If several candidates match, show their note IDs, decks, and front excerpts and ask which one to update. If the source has changed too much to prove correspondence, ask rather than inventing a duplicate. Create a new note only after the search establishes that no corresponding note exists.

On first adoption there is no prior published hash. Compare the existing rendered fields with the proposed fields before replacement. Ordinary outdated lesson text can be refreshed under the publishing request, but identifiable Anki-only annotations, personal examples, or unrelated content are a conflict: preserve them in an existing unmapped field where appropriate, or ask how to incorporate/replace them unless the user already specified this. Prepare the diff and rendered output first. Do not silently discard personal annotations or add fields to the shared model to avoid the question.

## Journal and retry

Before creating, record the generated SourceId, intended fields, destination, and a pending operation locally. If `addNote` times out, search that exact SourceId and inspect the result before another attempt. Zero results after one read is not proof of failure while Anki is still handling the request: wait for completion/connectivity and reconcile again. If the outcome remains unknown, stop and report it.

For an update timeout, read the note and compare it with both the old snapshot and the intended fields. If the intended content is already present, use the helper's `verify` command against the **original pre-write checkpoint**, then finish the binding. A fresh no-op is not evidence that the original scheduling survived. If only the old content is present, confirm its review state still matches the original and obtain a new snapshot before a retry. Any third state is a conflict. Never replay a whole batch of mixed successes.
