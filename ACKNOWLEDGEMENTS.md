# Acknowledgements and provenance

Format research was informed by:

- [kvasszn/ree-save-editor](https://github.com/kvasszn/ree-save-editor), especially its DD2 save profile, Mandarin format implementation, and typed-save reader/writer behavior. Reference revision examined during the work: `4125e497f1ae84cc746bb4a99da612c48bea161e`.
- [Save-transfer / online identity issue #42](https://github.com/kvasszn/ree-save-editor/issues/42), which documents account/slot/pawn identity failures and recovery reports. The reports do not establish every server validation rule.
- Direct inspection and validation of locally held, user-authorized DD2 PC snapshots.

The referenced editor repository did not declare a GitHub-recognized license when checked for publication. This project does not vendor its Rust source, assets, type dictionaries, executables, or user save files. The Python tooling and documentation here were authored for this workflow and express the observed format and preservation rules. The MIT license in this project does not grant rights to third-party code or game assets.

Dependencies are installed separately: [cryptography](https://cryptography.io/), [python-cityhash](https://github.com/escherba/python-cityhash), and [mmh3](https://github.com/hajimes/mmh3). Their respective licenses apply to those packages.

Dragon's Dogma 2, Capcom, Steam, and Valve names belong to their respective owners. This is an unofficial project without publisher endorsement.
