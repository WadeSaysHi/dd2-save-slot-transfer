# Transfer Slot 1 Progress to Slot 2 While Keeping Its Pawn Identity (PC)

## 1. What this transfer does

This guide is for players transferring their own existing PC progress from slot 1 to a separately created slot 2 on the same Steam account.

**Slot 2 receives:** the source world and quest state, character appearances, inventory, equipment, vocations, skills, levels, experience, and attribute growth.

**Slot 2 keeps:** its registered network module (including Pawn ID and server slot identity), Arisen and main pawn names and monikers, and consistent pawn-owner display names. Keeping a name does not keep the destination appearance: the source appearance is transferred.

The tool replaces all three destination recovery files with the current source autosave. Their previous recovery points remain only in your backup. It does not combine inventories or reset experience.

**Scope:** the observed DD2 Steam PC save layout and slot-1-to-slot-2 mapping. Cross-account transfers, consoles, modded layouts, other slot mappings, and future game versions are outside the validated scope.

The original transfer was reported to load and work online. Later transfers and the public implementation passed local file checks. This is not a guarantee of future server acceptance or protection from account restrictions. Use local backups and verify offline before considering any online use.

## 2. The principle: progress and identity are separate

A save is a structured state tree inside an encrypted, checksum-protected container. Renaming a file cannot update its embedded identity, internal slot number, or linked system metadata.

The observed source autosave is data000.bin. Slot 2 uses data005Slot.bin, data006Slot.bin, and data009Slot.bin. Both slots also refer to the shared system file data00-1.bin.

The transfer starts with the full source gameplay tree, then retains the destination's complete app.NetworkManager.GameSaveData_04 module. This includes ServerUserId, ServerSlotId, ServerPawnId, and network history. A display name is not a server identifier, and the exact meaning of ServerUserId has not been established.

Player and main pawn records are selected by their context types, rather than a fixed record index. Destination names, monikers, owner display fields, and each destination file's details are preserved. Only the destination's linked system metadata and previews are updated.

The output is serialized, encrypted, decrypted again, and checked against the expected complete tree. Removing the intentional exceptions must reconstruct the source gameplay tree exactly. Unrelated system entries must remain identical.

_Level, _Exp, and _IncreaseParams travel with the full character state. The tool does not assume that changing _Exp alone safely resets a character.

### Why a raw duplicate can collide with the original pawn

Copying a source save byte-for-byte into another slot also copies its embedded ServerPawnId and server-associated identifiers. Changing the filename or display name does not itself create a separately registered pawn. If both saves retain that identity, treating them as two independent online pawns risks competing updates or confusing upload/search results. Those server outcomes are a risk inference from the shared identity, not a reproduced result established here.

[A community file-renaming tutorial](https://www.reddit.com/r/DragonsDogma/comments/1w9bs6n/tutorial_merging_your_old_dd2_multisaves_into_the/) describes moving previously separate playthroughs; that differs from cloning one playthrough into multiple slots. [A direct discussion of cloning a save to hire its pawn](https://www.reddit.com/r/DragonsDogma2/comments/1x3gw8t/is_it_possible_to_duplicate_save_slot_1_main_to/) also questions whether duplication creates distinct Pawn IDs. These discussions are community evidence, not a controlled server test. They do not establish inevitable corruption or a specific ban duration.

This project requires source and destination Pawn IDs and server slot IDs to be distinct, then retains the already registered destination network module. It refuses colliding input identities; it does not repair an already duplicated identity or guarantee server acceptance. Keep names, file details, and shared system metadata consistent too.

## 3. Prepare your destination and a frozen backup

1. Create slot 2 with its own Arisen and main pawn. If needed, connect in-game and rest at an inn or owned home so its Pawn ID and server slot identity are populated. A blank, unregistered pawn is rejected.
2. Record the destination names and Pawn ID privately. Never post your saves or these identifiers in comments or bug reports.
3. After destination registration, turn Network Features off in DD2 under System > Options > Network, then exit the game. Separately pause Steam Cloud in the game's Steam Properties. Cloud sync and the game's pawn-network features are different systems. Check any other backup/sync software that watches the save folder.
4. Find the active save directory. A typical location is Steam/userdata/<account-folder>/2054970/remote/win64_save. Your Steam installation may be on another drive.
5. Copy the entire win64_save folder to a new, separate snapshot directory. Keep an additional untouched backup. Do not play or let any client write to the live saves while generating and installing candidates.

The --account-id value is the numeric Steam userdata folder for the active account. A SteamID64 also works in this observed format through its low 32 bits. It is not your login name or password.

All paths and account numbers in this guide are examples. Replace them with your own local values. The snapshot must contain the source, destination, and shared system files together.

## 4. Use the open-source project to generate candidates

The implementation and detailed format checks are available in [dd2-save-slot-transfer on GitHub](https://github.com/WadeSaysHi/dd2-save-slot-transfer). I maintain this free MIT-licensed project. It does not request a Steam password or send save data to a server.

On GitHub, use Code > Download ZIP and extract it, or clone the repository. Install Python 3.11 or later from its official source. Open PowerShell in the extracted project directory. Run py -3 --version and confirm it reports Python 3.11 or later. Stop if any command reports an error; do not continue to installation after a failed generation.

The examples use the virtual environment directly, so activating a PowerShell environment is unnecessary. Forward slashes in these quoted Windows paths are intentional:

```powershell
py -3 -m venv env
$python = (Resolve-Path "env/Scripts/python.exe").Path
& $python -m pip install .
$accountId = 123456789
$work = "D:/DD2-Work"
$snapshot = "$work/snapshots/run-01"
$output = "$work/outputs/run-01"
$cli = "dd2_save_slot_transfer.cli"
& $python -m $cli inspect "$snapshot/data000.bin" `
  --account-id $accountId
& $python -m $cli transfer --snapshot $snapshot `
  --output $output --account-id $accountId
```

123456789 is synthetic: replace it with your account folder number. Set $work to your own work directory and place the complete frozen win64_save contents directly inside snapshots/run-01. Choose a new output directory each time.

Generation does not install anything. Review these local reports:

- comparison.json: source, previous destination, proposed destination, names, identities, levels, and raw experience fields.
- validation.json: hashes and validation results for the four candidate files.
- snapshot-manifest.json: hashes of the original snapshot, used to reject stale installations.

These reports contain private save information. Do not upload them. If validation fails, stop and investigate the account, registration, game version, and file layout. Do not disable checks to force a transfer.

## 5. Review and install the four files

Check comparison.json before writing any live file: destination identifiers and names must equal destination_before; player and pawn level/experience fields must equal the source. The generator also checks the complete gameplay and system trees.

The optional Windows helper backs up the full snapshot file set, requires live files to match the snapshot hashes, refuses a running DD2 process, installs only the four allowlisted candidates, and verifies installed hashes. It attempts rollback if installation fails.

From the project directory, preview the operation:

```powershell
$live = 'D:/Steam/userdata/123456789/2054970/remote/win64_save'
$candidate = 'D:/DD2-Work/outputs/run-01'
$backup = 'D:/DD2-Backups/transfer-run-01'
./scripts/Install-Transfer.ps1 -SaveDirectory $live `
  -CandidateDirectory $candidate -BackupDirectory $backup -WhatIf
```

Replace every path and the synthetic account number. The backup directory must not already exist. Remove -WhatIf only after checking the target paths and reports, keeping DD2 closed and sync paused. If PowerShell blocks the script, stop and review your system's policy; this guide does not require disabling security protections.

The four files are data005Slot.bin, data006Slot.bin, data009Slot.bin, and data00-1.bin. Do not copy comparison.json or the manifests into the live save folder.

The published helper has been reviewed and syntax-checked; its exact generic form has not been exercised against live saves as part of publication. Keep the complete backup even after a successful copy. An interruption such as power loss can still leave a partial installation.

## 6. Verify, recover, and repeat

**Offline check first:** confirm DD2 Network Features remains off before loading slot 2; pausing Steam Cloud alone does not disable pawn uploading. The setting is under System > Options > Network, as described in the [Capcom Steam FAQ](https://www.capcom-support.com/hc/en-us/articles/13470419567260-Dragon-s-Dogma-2-Frequently-Asked-Questions-Steam). Check the retained names, transferred appearances, location, quest progress, equipment, inventory, and levels. Check that slot 1 still loads with its original state.

If anything is wrong, exit the game and Steam, preserve the failed state separately, and restore the complete matching backup folder. Keep sync paused until you have loaded and checked the restored state. A local restore cannot guarantee rollback of data already uploaded to the game server.

Only consider reconnecting after the offline check. Local checks cannot certify server acceptance or enforcement behavior. If you choose to test online, compare the destination's retained Pawn ID and actual uploaded pawn state; a successful load alone does not prove a successful upload.

Before re-enabling Steam Cloud, retain both your original backup and the working local state. If Steam presents a conflict, inspect which copy you intend to keep rather than accepting an unfamiliar cloud version.

For the next transfer, take a fresh frozen snapshot and use new output and backup directories. The tool derives names and identities from that current destination. Never reuse an old manifest to overwrite progress made since the snapshot.

This is an unofficial community project, with no Capcom or Valve endorsement. Relevant resources: [Steam Community rules](https://help.steampowered.com/en/faqs/view/6862-8119-C23E-EA7B) and [Steam's external-link filtering explanation](https://help.steampowered.com/en/faqs/view/628C-E332-BD8C-4D36). A source-code link is not platform approval.

## 7. Manual alternative: Windows-only backup and restore

### A separate method without project code or third-party tools

This section uses only Windows File Explorer, Steam, and the game. It can back up and restore an existing complete save state. It cannot selectively transplant slot-1 progress while preserving slot-2 identity.

**Make a backup**

1. Exit DD2 and pause Steam Cloud for the game. Exit Steam before copying.
2. Open the active account's Steam/userdata/<account-folder>/2054970/remote directory in File Explorer.
3. Copy the entire win64_save folder to a separate folder with a unique date/run label. Do not move the original or combine files from different backups.
4. Keep a note of which playthrough and slots the backup contains. Store this note and backup privately.

**Restore a backup**

1. With DD2 and Steam closed and sync still paused, copy the current entire win64_save folder somewhere else so the current state is recoverable.
2. Move the current win64_save folder out of the remote directory, then copy the chosen complete backup into remote under the exact name win64_save. This avoids mixing old and new files.
3. Start Steam with sync paused and network uploading prevented, then load the game and verify the expected slots and progress.
4. Keep both backups. Restore your saved previous folder if the result is wrong. Resolve any Cloud conflict deliberately before resuming sync.

Restoring the complete folder restores all contained slots to that snapshot; it is not a selective slot-2 replacement. Do not rename data000.bin to a slot-2 filename: internal identity, file-detail records, and shared system metadata would not be repaired.

The selective transfer described earlier requires parsing, editing, and re-encrypting the protected save structure. No equivalent Windows-only file-copy procedure has been verified. This manual alternative is useful for recovery, and does not change the rules that apply to save modification.
