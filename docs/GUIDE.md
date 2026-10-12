# DD2 Save Refresh: Research, Experience Fields, and Validation

This is the consolidated English guide. The executable implementation lives in `src/dd2_slot_refresh`; the repository README provides setup and CLI examples. Real saves and private identifiers are not distributed.

## Reusable Python interface

```python
from pathlib import Path
from dd2_slot_refresh.refresh import describe, read_tree, refresh

account_id = 123456789  # Synthetic example: use your Steam userdata folder number.
snapshot = Path("snapshots/run-01")

# Read and validate without modifying the frozen input.
source_summary = describe(read_tree(snapshot / "data000.bin", account_id))
print(source_summary["player_status"])  # Contains level and the raw experience field.

# Generate four candidate files; this does not install or upload anything.
# The output directory must not already exist or be inside the snapshot directory.
result = refresh(snapshot, Path("outputs/run-01"), account_id)
assert result["destination_after"]["player_status"] == result["source"]["player_status"]
```

The assertions above are a usage example only. Internal format and preservation checks use explicit `ValidationError` checks, so they remain active under `python -O`.

## Research notes: identity-preserving save refresh

## Purpose and evidence

The working objective was to copy newer gameplay state from an established first slot to a separately registered second slot. The second slot's independently created names and server identity needed to survive the copy.

The first migration was generated, decrypted again, installed, and then confirmed by the user to load and work online. A subsequent progress refresh was installed with matching hashes and semantic checks. The public implementation was also tested against local private snapshots; those files and reports are not part of the public project. These observations establish a working method for the observed PC format and account, not a guarantee across versions or all server rules.

## Why copying filenames is insufficient

The observed slot mapping is:

| Purpose | Source / slot 1 | Destination / slot 2 |
|---|---|---|
| Current source autosave | `data000.bin` | — |
| Recovery-file group | `data000.bin`, `data001Slot.bin`, `data004Slot.bin` | `data005Slot.bin`, `data006Slot.bin`, `data009Slot.bin` |
| Shared system save | `data00-1.bin` | Same file |

These names describe the observed mapping, not a promise about every release. Each destination file has its own file-detail `Slot` value. The shared system file carries linked slot metadata and display previews. Copying a source file and merely changing its filename can leave source identities or incorrect slot details behind.

## Network identity is a module, not a character name

`app.NetworkManager.GameSaveData_04` contains:

- `ServerUserId`: a 16-byte server-associated value; its exact semantics are not publicly established. In the tested account it differed between slots, so it must not be assumed to be one global Steam ID.
- `ServerSlotId`: a 16-byte server slot identifier.
- `ServerPawnId`: the main pawn's displayed search identifier.
- Reward, borrowing, checked-pawn, and inn-related network state.

These are in the save's network module. They are not embedded inside the Arisen's display name. No separate, definitively identified “Arisen server ID” was established by this analysis.

A new offline slot initially had a blank `ServerPawnId` and a zeroed `ServerSlotId`. After an online inn rest, the slot had a nonempty Pawn ID and a nonzero server slot value. The tool refuses a destination that has not completed that registration.

Preserving the **whole destination network module** avoids importing the source's network history along with its IDs. This was the tested strategy; it does not prove that every field in that module is independently necessary.

## Character selection without brittle record indexes

The game state includes `app.ContextDatabaseSaveDataRecord` objects whose `Contexts` array contains typed character contexts. Numeric record positions change as the world changes.

Select the Arisen's record by `app.PlayerPersonalDataContext`. Select the main pawn's record by `app.MainPawnDataContext`, then find its `app.PawnDataContext`, `app.PawnOwnerContext`, and `app.HumanStatusContext` within the same record. Do not assume a cached numeric record index still points to the player or main pawn.

Names and monikers have separate fields:

| Context | Fields |
|---|---|
| Arisen | `Name`, `NickName` |
| Main pawn | `_Name`, `_Nickname` |
| Main pawn owner display data | `_Name`, `_NickName` |

The owner display fields are made consistent with the retained destination Arisen fields. Appearance is copied from the source; preserving a name does not preserve the destination's appearance.

## Experience fields: what is known

`app.HumanStatusContext` contains `_Level`, `_Exp`, and `_IncreaseParams`. Job ranks, skills, equipment, and other gameplay state are held in additional contexts or modules.

The tested refresh transferred, for example, a level-99 Arisen and level-98 main pawn. The associated raw `_Exp` values were preserved exactly from the source. Their actual values are not required as public fixtures.

Confirmed:

1. The selected player and main pawn records can be located by context type.
2. `_Level` and `_Exp` can be extracted without changing the save.
3. The complete source character state, including experience and attribute growth, survives refresh and serialization.
4. Output `_Level` and `_Exp` equal the source values.

Not confirmed:

- Whether `_Exp` is lifetime XP, current-level progress, or another accumulator in every release.
- Whether editing `_Exp` alone safely lowers a level, resets stats, or updates all related caches.
- Whether server validation accepts arbitrary changes to levels, jobs, or stats.

This project therefore performs a **complete state transfer**, not a standalone XP edit or level reset. Matching local fields does not imply server approval.

## Replacement rule and proof

Let `S` be the source gameplay tree and `D` the destination gameplay tree. Construct `C` from `S`, then substitute:

1. The complete network module from `D`.
2. The destination Arisen and main pawn names and monikers.
3. Consistent main pawn owner display names.
4. Each destination file's existing file-detail record.

To check the core gameplay mutation, restore those explicit exceptions in a copy of `C` back to their source values and compare the full tree to `S`. Equality must hold, including unknown structs and primitive arrays. Checking only a few visible values would miss accidental changes elsewhere.

The shared system file is similarly checked: only slot-2 entries in the observed metadata and preview arrays may differ. Slot-1 entries and unrelated roots must remain semantically identical.

## Reuse boundaries

Repeat with a fresh, frozen snapshot each time. Never reuse an old snapshot manifest as permission to overwrite newer live progress. The identities and names are derived from the current destination, not hardcoded in the tool.

The public tool supports the observed slot-1-to-slot-2 mapping. Other mappings, cross-account transfers, gameplay mods, or different layouts are outside the validated scope.


---

## Observed format and implementation details

This document describes the PC format encountered in the tested snapshots. It is not an official specification.

## Envelope

- Magic: `DSSS`.
- Version: `2`.
- Input flags: `0x10` for Mandarin encryption without deflate, or `0x18` for Mandarin plus deflate. Uncompressed system saves were encountered in the source snapshots.
- Output: version 2, flags `0x18`.
- First field-tree bytes logically begin at offset 16 of the decrypted stream.
- Trailer: a 128-byte RSA-associated value, an eight-byte decrypted payload length, and a four-byte Murmur3 checksum of the preceding file bytes.

The implementation uses DD2's observed format constants and the low 32 bits of an explicitly supplied account ID. Those constants are game format data, not a player's login credentials.

## Encryption and checks

The Mandarin layout splits the payload into pseudorandomly sized blocks in units of `0x4000` bytes. Each encrypted block has `0x210` bytes of masked metadata followed by AES-128-OFB ciphertext. Metadata contains four integer-pair encodings of the generated AES key and IV, a CityHash64 checksum, and eight additional bytes.

Validation is layered:

1. Validate header, supported flags, payload bounds, and the outer Murmur3 checksum.
2. Unmask each metadata block using the account-derived generator state.
3. Recover and compare the embedded AES key and IV values.
4. Decrypt each block and compare its meaningful plaintext bytes to CityHash64.
5. If compressed, validate raw-deflate completion and exact decompressed length.

Encryption writes compatible key/IV metadata, checksums, and the RSA-associated trailer. **The reader does not authenticate the RSA trailer itself independently.** Key/IV metadata authentication and checksums should not be described as a complete proof of every game-side integrity rule.

Input envelope and decompression sizes have explicit limits. The parser is intended for local game snapshots, not as an internet-facing untrusted-file service. Deep nesting and unknown field types can be rejected.

## Typed trees

Roots have a hash and a class. A class has a type hash and a list of hashed fields. Fields include:

- Primitive/enum values retained as raw bytes with their recorded size.
- Opaque structs retained as raw bytes; their meaning need not be known.
- UTF-16LE strings retained as byte sequences.
- Class values and arrays, including optional array class hashes.
- Primitive arrays whose complete values survive parsing and writing.

Names are matched by Murmur3 with seed `0xffffffff`. A **hash is not a fixed byte offset**. For example, `ServerPawnId`'s field hash is `0x4fdc3a98`; its file position changes as earlier content grows or shrinks.

The field format's size-based alignment uses:

```python
aligned = (position + size - 1) & ~(size - 1)
```

Do not replace it with modulo alignment. The observed behavior also applies to sizes such as 24, even though they are not powers of two.

Rewriting strings of a different length can move later fields. The serializer recomputes alignment rather than overwriting bytes at stale offsets. Padding bytes are normalized to zero. Therefore **semantic tree equality**, not identical encrypted bytes, is the round-trip check.

## System slot indexing

The observed system class hash is `0x0488ea02`. Its metadata array field hash is `0x89b75ab3`; the preview array field hash is `0x559b544e`. These names were not resolved, so the tool preserves the hashes explicitly.

The supported source-to-destination index mapping is `(0 → 5), (1 → 6), (4 → 9)`. Each metadata entry must already have the expected source or destination server slot identity. The tool copies source preview content, preserves target server slot IDs, and retains destination Arisen display names.

No large SDK type dictionary is required or bundled: only the known field/type hashes needed to select the supported structures are used.


---

## Validation protocol and evidence boundaries

## Before generating candidates

- Close the game and take a complete frozen snapshot.
- Confirm the destination has a registered nonempty Pawn ID and nonzero server slot identity.
- Validate file checksums, encryption metadata, decompression, and full tree parsing.
- Serialize and parse the input again; require full semantic equality.
- Require matching source/destination module schema and stored app-version value.

## Candidate invariants

The public implementation derives all names and IDs from the provided snapshot.

1. The complete destination network module is retained.
2. The Arisen and main pawn names and monikers are retained.
3. The main pawn's owner display names match the retained Arisen names.
4. All other gameplay values, including unknown structs and primitive arrays, match the source.
5. Player/main pawn `_Level` and `_Exp` equal source values.
6. All three destination recovery files retain their individual file-detail records.
7. System metadata remains linked to the destination server slot identity.
8. System modifications are limited to destination metadata/preview indexes 5, 6, and 9.
9. Unrelated system roots, entries, and source previews remain semantically identical.

The gameplay proof restores every allowed exception back to the source value and requires the entire tree to equal the source. The system proof restores the allowed destination entries and requires equality to the original system tree.

Each generated candidate is encrypted, its key/IV metadata checked, decrypted, checksum-checked, decompressed, and parsed again. Both payload bytes and the expected full field tree must match. SHA-256 manifests link generated bytes to installation checks.

## Before and after installation

- Preserve a complete backup in a new directory.
- Require the current live files and backup files to match the frozen snapshot hashes.
- Refuse a running game.
- Install only the four known destination/system files.
- Verify candidate hashes after copying and source/unrelated file hashes remain unchanged.
- Restore modified files from the fresh backup on installation failure.

The optional PowerShell wrapper supports `-WhatIf`. Its generic published form is not a substitute for checking the target paths and reviewing candidate reports.

## What has been verified

| Evidence | Scope |
|---|---|
| Original migration and name correction | User reported successful in-game behavior and online validation |
| Later progress refresh | File parsing, complete semantic checks, encryption/checksums, and installed hashes passed |
| Public Python implementation | Generated candidates from private snapshots; output hashes matched the previously installed validated refresh |
| Public automated tests | Synthetic encryption/tree round trips, corruption and wrong-account rejection, identity/name preservation, slot-detail preservation, rejection of unregistered pawns, and record-order independence |
| Published generic PowerShell installer | Reviewed from the exercised manual installation sequence and syntax-checked by Windows PowerShell; not run against live saves during publication |

Private test data is deliberately absent from the repository. Synthetic tests let anyone verify the core invariants without access to personal saves. The real-snapshot statement describes local evidence; it is not independently reproducible from public fixtures.

## Not guaranteed

- Server acceptance after every migration or later title update.
- Server-side rollback after a local backup restore.
- The exact meaning of `_Exp` in every version, or safety of editing it independently.
- Cross-platform, cross-account, modded, or arbitrary slot migration.
- Compatibility with files whose structure happens to pass some checks but differs in unrecognized semantics.

Do not equate a matching checksum with gameplay or server validity. Complete an offline load check and a separate online test after each installed refresh.
