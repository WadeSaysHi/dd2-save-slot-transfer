# DD2 Save Slot Transfer

An offline Python toolkit for transferring **Dragon's Dogma 2 PC progress from slot 1 to slot 2**, while preserving slot 2's registered network identity and character names.

The procedure was used for an initial migration and a later progress transfer. The original migration was confirmed by the user to load and work online. The later transfer passed file-level checks; that is a separate claim from an in-game or server acceptance test.

## What gets copied and preserved

| Data | Rule |
|---|---|
| Progress, world state, appearance, inventory, equipment, jobs, skills, levels, experience, attribute growth | Copy the complete source autosave |
| Destination `ServerUserId`, `ServerSlotId`, `ServerPawnId`, rewards, and borrowing history | Preserve the **entire destination network module** |
| Arisen name and moniker | Preserve destination fields |
| Main pawn name and moniker | Preserve destination fields |
| Main pawn's owner display name and moniker | Match the destination Arisen |
| Destination file-detail slot numbers | Preserve each destination file's record |
| Slot 2 metadata and UI previews | Update progress previews, retain destination names and server slot identity |
| Slot 1 and unrelated system entries | Leave unchanged |

**All three slot-2 recovery files receive the same current source autosave.** Their old recovery points survive only in your backup. This is not a merge of two playthroughs or an experience-reset tool.

## Install

Project: [dd2-save-slot-transfer](https://github.com/WadeSaysHi/dd2-save-slot-transfer). Version 0.2 uses the `dd2-save-slot-transfer transfer` command and the `dd2_save_slot_transfer.transfer` Python interface. Reinstall if you used the original package; old command names are no longer documented.

Python 3.11 or later:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install .
```

## Prepare a frozen snapshot

1. Exit DD2 and prevent Steam Cloud from restoring or changing files during the operation.
2. Copy the complete `win64_save` directory to a separate local snapshot directory. A typical Steam location is `Steam/userdata/<account-folder>/2054970/remote/win64_save`.
3. Slot 2 must already have its own Arisen and main pawn. Connect in-game and rest at an inn or owned home until its Pawn ID and server slot identity are populated. A new offline pawn with an empty ID is not a suitable destination.
4. Keep all real saves and generated reports private. `comparison.json` contains character names and server IDs.

Use the number of your Steam `userdata` account folder as `--account-id`. A SteamID64 also works because this observed DD2 PC envelope uses its low 32 bits. This parameter is an account identifier, not a password.

## Inspect and generate

The following PowerShell examples use your actual account folder number, not a bundled sample account:

```powershell
$accountId = 123456789  # Replace this synthetic example with your own account folder number.
dd2-save-slot-transfer inspect .\snapshots\run-01\data000.bin --account-id $accountId
dd2-save-slot-transfer transfer --snapshot .\snapshots\run-01 --output .\outputs\run-01 --account-id $accountId
```

`transfer` writes candidates to a **new** directory. It never connects to Steam, a server, or another PC and never installs or alters live saves. Review:

- `comparison.json`: source, previous destination, proposed destination, levels, experience fields, and identities.
- `validation.json`: candidate SHA-256 hashes, sizes, and authenticated block counts.
- `snapshot-manifest.json`: hashes of all snapshot `.bin` files, used as installation preconditions.

The layout supported here is DSSS v2 with input flags `0x10` or `0x18` (output uses `0x18`), 30 game modules, and the observed slot-1/slot-2 indexing. Structural/version/identity mismatches stop the operation. New game versions, mods, cross-account transfers, other platforms, or other slot mappings require separate research.

## Optional Windows installation

Copy the candidate directory to Windows, then run:

```powershell
.\scripts\Install-Transfer.ps1 `
  -SaveDirectory 'D:\Steam\userdata\123456789\2054970\remote\win64_save' `
  -CandidateDirectory 'D:\DD2-Work\candidate' `
  -BackupDirectory 'D:\DD2-Backups\unique-run-name' `
  -WhatIf
```

Replace those example paths. Remove `-WhatIf` only after reviewing the comparison and confirming the game is closed. The helper checks the snapshot's current live-file hashes, makes a new complete backup, installs only the four allowlisted files, verifies hashes, and attempts rollback on installation failure. It cannot survive every interruption, such as a power loss in the middle of copying; retain the backup.

The generic PowerShell wrapper is based on the previously exercised backup/hash/install/rollback sequence. The exact published wrapper has been syntax-checked with Windows PowerShell, but has not been run against live saves as part of publication.

First check the destination offline: names, appearances, equipment, location, and levels. Then test online uploading and searching by the retained Pawn ID. Local checks cannot prove server acceptance, and restoring local files cannot guarantee reversal of an uploaded server state.

## Guides and validation

- [Player guide for Steam](docs/STEAM_GUIDE.md)
- [Transfer guide with reusable Python example](docs/GUIDE.md)
- [Research notes and experience-field analysis](docs/RESEARCH.md)
- [Format, serialization, and encryption checks](docs/FORMAT.md)
- [Validation procedure and evidence boundaries](docs/VALIDATION.md)
- [Acknowledgements and format references](ACKNOWLEDGEMENTS.md)

```bash
python -m unittest discover -s tests -v
```

Tests use **synthetic** trees and accounts. No real saves, private identifiers, cloud tokens, machine paths, or type dictionaries are included in this repository.

## License

The Python tooling, documentation, and scripts authored for this project are available under [MIT](LICENSE). This is an unofficial research tool, not affiliated with or endorsed by Capcom or Valve. No upstream editor source, game files, or upstream type dictionary is redistributed.
