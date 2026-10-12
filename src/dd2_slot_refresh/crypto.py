"""DD2 PC DSSS encryption envelope, compression, and integrity checks.

Game format constants are not personal account credentials. Every account-derived
value is calculated from an explicit command-line parameter; no account is embedded.
See docs/FORMAT.md and ACKNOWLEDGEMENTS.md for format references.
"""

import struct
import zlib

import cityhash
import mmh3
from cryptography.hazmat.decrepit.ciphers import modes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from .errors import ValidationError, require

MAX_PAYLOAD = 32 * 1024 * 1024
MAX_DECOMPRESSED = 256 * 1024 * 1024


def inflate(data, expected_size):
    """Bound decompression before parsing a local, potentially malformed snapshot."""
    require(0 < expected_size <= MAX_DECOMPRESSED, "Decompressed size exceeds limit")
    decoder = zlib.decompressobj(-15)
    raw = decoder.decompress(data, expected_size + 1)
    require(len(raw) == expected_size and decoder.eof, "Invalid compressed payload length")
    require(
        not decoder.unused_data and (not decoder.unconsumed_tail),
        "Unexpected compressed trailing data",
    )
    return raw


def validate_envelope(data, account_id):
    """Reject unsupported formats before loops, allocations, or authentication."""
    require(0 < account_id <= (1 << 64) - 1, "Account ID must be a positive uint64")
    require(160 <= len(data) <= MAX_PAYLOAD * 2, "Unexpected encrypted file size")
    require(data[:4] == b"DSSS", "Missing DSSS header")
    version, flags = struct.unpack_from("<II", data, 4)
    require(
        version == 2 and flags in (16, 24),
        "Only DD2 PC DSSS v2, Mandarin (0x10) or Mandarin + Deflate (0x18), is supported",
    )
    size = struct.unpack_from("<Q", data, len(data) - 12)[0]
    require(24 <= size <= MAX_PAYLOAD, "Unexpected encrypted payload length")
    require(
        mmh3.hash(data[:-4], 4294967295, signed=False)
        == struct.unpack_from("<I", data, len(data) - 4)[0],
        "File checksum mismatch",
    )


def decrypt(data, account_id):
    """Validate the envelope and key/IV metadata, then decrypt and decompress."""
    validate_envelope(data, account_id)
    try:
        check_auth(data, account_id)
        return _decrypt_payload(data, account_id)
    except (OverflowError, ZeroDivisionError, struct.error, IndexError, zlib.error) as exc:
        raise ValidationError("Malformed envelope or incorrect account ID") from exc


MASK = (1 << 64) - 1


def rng(s):
    """Return the mixed state used as the next state by this envelope variant."""
    z = s + 11400714819323198485 & MASK
    z = (z ^ z >> 30) * 13787848793156543929 & MASK
    z = (z ^ z >> 27) * 10723151780598845931 & MASK
    return z ^ z >> 31


def _decrypt_payload(d, account_id):
    # Meaningful last-block bytes alone contribute to the block checksum.
    require(d[:4] == b"DSSS", "Unsupported or inconsistent save structure")
    require(
        mmh3.hash(d[:-4], 4294967295, signed=False) == struct.unpack("<I", d[-4:])[0],
        "Unsupported or inconsistent save structure",
    )
    n = struct.unpack("<Q", d[-12:-4])[0]
    s = 0x5EC646997D69AE1B
    sizes = []
    for _ in range((n + 16383) // 16384):
        sizes.append(((s & 7) + 1) * 16384)
        s = rng(s)
    s = s + (~(account_id & 4294967295) & MASK) & MASK
    pos = 16
    out = bytearray()
    checks = []
    for size in sizes:
        k = bytearray()
        iv = bytearray()
        for _ in range(16):
            s = rng(s)
            k.append(s & 255)
            iv.append(s >> 8 & 255)
        meta = bytearray(d[pos : pos + 528])
        for j in range(528):
            s = rng(s)
            meta[j] ^= s & 255
        dec = (
            Cipher(algorithms.AES(bytes(k)), modes.OFB(bytes(iv)))
            .decryptor()
            .update(d[pos + 528 : pos + 528 + size])
        )
        dec = dec[: min(size, n - len(out))]
        check = struct.unpack("<Q", meta[512:520])[0]
        require(cityhash.CityHash64(dec) == check, "block checksum failed")
        checks.append(True)
        out.extend(dec)
        pos += size + 528
        if len(out) == n:
            break
    require(len(out) == n, "Unsupported or inconsistent save structure")
    if struct.unpack("<I", d[8:12])[0] & 8:
        _, _, cs, ds = struct.unpack("<QIIQ", out[:24])
        out = bytearray(inflate(bytes(out[24 : 24 + cs]), ds))
        require(len(out) == ds, "Unsupported or inconsistent save structure")
    return (bytes(out), len(checks))


P = int.from_bytes(
    bytes.fromhex("f33b6fb972a0b72515e45c391829e182ad8a9bdc0a64d3444d79c810ab863717"), "little"
)
R = int.from_bytes(
    bytes.fromhex("e66f544afcce68c5ef07b9a07b277585344a1db61376e831f73b9fbd5f44f715"), "little"
)
X0 = pow(R, 20, P)
N = int.from_bytes(
    bytes.fromhex(
        "4fa448364f5b3507e945075cc21994bdedef96962c74d53159d50a5c62ed50864885ddfe79705dfad0b638220ca2299fccae152164590cc89d33698452a8f6416107a6952f126bb21ee3e332d2285db728c09bfa8cbd4c3b13b358b9838dea7cf39dc12e37066a09cf7809a0d0ea06c3bbaa14776400f403f863ed83b5bdd3c2"
    ),
    "little",
)


def encrypt(raw, account_id):
    """Encode a payload as DD2 PC Mandarin + raw-deflate, using an explicit account."""
    require(0 < account_id <= MASK, "Account ID must be a positive uint64")
    require(0 < len(raw) <= MAX_DECOMPRESSED, "Raw payload exceeds limit")
    INV = ~(account_id & 4294967295) & MASK
    # Fixed public game constants; the account contributes only its low 32 bits.
    X1 = pow(pow(R, INV, P), 20, P)
    co = zlib.compressobj(5, zlib.DEFLATED, -15)
    comp = co.compress(raw) + co.flush()
    payload = struct.pack("<QIIQ", len(comp) + 16, 1, len(comp), len(raw)) + comp
    s = 0x5EC646997D69AE1B
    sizes = []
    for _ in range((len(payload) + 16383) // 16384):
        sizes.append(((s & 7) + 1) * 16384)
        s = rng(s)
    s = s + INV & MASK
    out = bytearray(b"DSSS" + struct.pack("<III", 2, 24, 0))
    pos = 0
    for size in sizes:
        k = bytearray()
        iv = bytearray()
        for _ in range(16):
            s = rng(s)
            k.append(s & 255)
            iv.append(s >> 8 & 255)
        pairs = bytearray()
        for i in range(4):
            plain = int.from_bytes((k + iv)[i * 8 : i * 8 + 8], "little")
            pairs.extend(X0.to_bytes(64, "little"))
            pairs.extend((X1 * plain).to_bytes(64, "little"))
        chunk = payload[pos : pos + size]
        pairs.extend(struct.pack("<QQ", cityhash.CityHash64(chunk), 0))
        for j in range(528):
            s = rng(s)
            pairs[j] ^= s & 255
        encrypted = (
            Cipher(algorithms.AES(bytes(k)), modes.OFB(bytes(iv)))
            .encryptor()
            .update(chunk + b"\x00" * (size - len(chunk)))
        )
        out.extend(pairs)
        out.extend(encrypted)
        pos += len(chunk)
        if pos == len(payload):
            break
    # This trailer generator advances additively; it is distinct from block RNG state.
    rsa_state = 0x90EDB79172FDBE51
    rands = bytearray()
    for _ in range(32):
        rsa_state = rsa_state + 11400714819323198485 & MASK
        rands.append(rsa_state & 255)
    rands[:8] = INV.to_bytes(8, "little")
    out.extend(pow(int.from_bytes(rands, "little"), 65537, N).to_bytes(128, "little"))
    out.extend(struct.pack("<Q", len(payload)))
    out.extend(b"\x00" * (-len(out) % 4))
    out.extend(struct.pack("<I", mmh3.hash(bytes(out), 4294967295, signed=False)))
    return bytes(out)


def check_auth(enc, account_id):
    """Recover each block's metadata key/IV and compare to generated values."""
    INV = ~(account_id & 4294967295) & MASK
    n = struct.unpack("<Q", enc[-12:-4])[0]
    s = 0x5EC646997D69AE1B
    sizes = []
    for _ in range((n + 16383) // 16384):
        sizes.append(((s & 7) + 1) * 16384)
        s = rng(s)
    s = s + INV & MASK
    pos = 16
    left = n
    for size in sizes:
        k = bytearray()
        iv = bytearray()
        for _ in range(16):
            s = rng(s)
            k.append(s & 255)
            iv.append(s >> 8 & 255)
        meta = bytearray(enc[pos : pos + 528])
        for j in range(528):
            s = rng(s)
            meta[j] ^= s & 255
        recovered = bytearray()
        for i in range(4):
            x = int.from_bytes(meta[i * 128 : i * 128 + 64], "little")
            ct = int.from_bytes(meta[i * 128 + 64 : (i + 1) * 128], "little")
            recovered.extend((ct // pow(x, INV, P)).to_bytes(8, "little"))
        require(recovered == k + iv, "auth failed")
        left -= min(size, left)
        pos += size + 528
        if not left:
            break
