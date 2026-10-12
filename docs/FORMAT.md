# Observed format and implementation details

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
