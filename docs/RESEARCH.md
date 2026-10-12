# Identity-preserving save transfer

## Purpose and evidence

The working objective was to copy newer gameplay state from an established first slot to a separately registered second slot. The second slot's independently created names and server identity needed to survive the copy.

The first migration was generated, decrypted again, installed, and then confirmed by the user to load and work online. A subsequent progress transfer was installed with matching hashes and semantic checks. The public implementation was also tested against local private snapshots; those files and reports are not part of the public project. These observations establish a working method for the observed PC format and account, not a guarantee across versions or all server rules.

## Why copying filenames is insufficient

The observed slot mapping is:

| Purpose | Source / slot 1 | Destination / slot 2 |
|---|---|---|
| Current source autosave | `data000.bin` | — |
| Recovery-file group | `data000.bin`, `data001Slot.bin`, `data004Slot.bin` | `data005Slot.bin`, `data006Slot.bin`, `data009Slot.bin` |
| Shared system save | `data00-1.bin` | Same file |

These names describe the observed mapping, not a promise about every release. Each destination file has its own file-detail `Slot` value. The shared system file carries linked slot metadata and display previews. Copying a source file and merely changing its filename can leave source identities or incorrect slot details behind.

### Why a raw duplicate can collide with the original pawn

Copying a source save byte-for-byte into another slot also copies its embedded ServerPawnId and server-associated identifiers. Changing the filename or display name does not itself create a separately registered pawn. If both saves retain that identity, treating them as two independent online pawns risks competing updates or confusing upload/search results. Those server outcomes are a risk inference from the shared identity, not a reproduced result established here.

[A community file-renaming tutorial](https://www.reddit.com/r/DragonsDogma/comments/1w9bs6n/tutorial_merging_your_old_dd2_multisaves_into_the/) describes moving previously separate playthroughs; that differs from cloning one playthrough into multiple slots. [A direct discussion of cloning a save to hire its pawn](https://www.reddit.com/r/DragonsDogma2/comments/1x3gw8t/is_it_possible_to_duplicate_save_slot_1_main_to/) also questions whether duplication creates distinct Pawn IDs. These discussions are community evidence, not a controlled server test. They do not establish inevitable corruption or a specific ban duration.

This project requires source and destination Pawn IDs and server slot IDs to be distinct, then retains the already registered destination network module. It refuses colliding input identities; it does not repair an already duplicated identity or guarantee server acceptance. Keep names, file details, and shared system metadata consistent too.

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

The tested transfer transferred, for example, a level-99 Arisen and level-98 main pawn. The associated raw `_Exp` values were preserved exactly from the source. Their actual values are not required as public fixtures.

Confirmed:

1. The selected player and main pawn records can be located by context type.
2. `_Level` and `_Exp` can be extracted without changing the save.
3. The complete source character state, including experience and attribute growth, survives transfer and serialization.
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
