"""Lossless field/array values with canonical serialization of DSSS trees.

Values remain bytes, including unknown structs. UTF-16 strings are not decoded
and re-encoded implicitly. Padding may be normalized; tree equality, rather than
ciphertext equality, is the round-trip invariant.
"""

import struct

import mmh3

from .errors import require


def H(name):
    """Hash a type or field name, rather than treating the hash as an offset."""
    return mmh3.hash(name, 0xFFFFFFFF, signed=False)


FM = {
    2: "?",
    3: "b",
    4: "B",
    5: "h",
    6: "H",
    7: "i",
    8: "I",
    9: "q",
    10: "Q",
    11: "f",
    12: "d",
    13: "B",
    14: "H",
}


class Codec:
    """Parse or write one complete field tree; use a fresh instance per operation."""

    def __init__(self, d=b""):
        self.d = d
        self.p = 16
        self.b = bytearray(b"DSSS" + struct.pack("<III", 2, 24, 0))
        self.classes = []

    def align(self, n):
        # Match the observed size-mask rule, including non-power-of-two structs.
        require(n > 0, "Invalid alignment size")
        self.p = self.p + n - 1 & ~(n - 1)

    def rd(self, fmt):
        """Read a bounded little-endian scalar or tuple."""
        require(self.p + struct.calcsize("<" + fmt) <= len(self.d), "Truncated primitive")
        v = struct.unpack_from("<" + fmt, self.d, self.p)
        self.p += struct.calcsize("<" + fmt)
        return v[0] if len(v) == 1 else v

    def cls(self):
        """Read the field count and type hash before recursively reading fields."""
        n, h = self.rd("II")
        require(n < 100000, "Unsupported or inconsistent save structure")
        c = {"h": h, "fields": []}
        self.classes.append(c)
        for _ in range(n):
            fh, t = self.rd("Ii")
            c["fields"].append({"h": fh, "t": t, "v": self.val(t)})
            self.align(4)
        return c

    def val(self, t, size=None):
        """Retain all primitive and struct bytes, including unknown field content."""
        if t == 17:
            return self.cls()
        if t == -1:
            self.align(4)
            mt, ms, n, at = self.rd("iIIi")
            require(n < 1000000, "Unsupported or inconsistent save structure")
            require(at in (0, 1), "Unsupported array representation")
            hashes = None
            if at == 1:
                marker = self.rd("I")
                if marker == 0xFFEEFFEE:
                    hashes = [self.rd("I") for _ in range(n)]
                else:
                    self.p -= 4
            vals = [
                self.val(17 if at == 1 else mt, None if at == 1 or mt == 15 else ms)
                for _ in range(n)
            ]
            self.align(4)
            return {"mt": mt, "ms": ms, "at": at, "hashes": hashes, "vals": vals}
        if t == 15:
            self.align(4)
            n = self.rd("I")
            require(n <= 1000000 and self.p + 2 * n <= len(self.d), "Invalid UTF-16 length")
            b = self.d[self.p : self.p + 2 * n]
            self.p += 2 * n
            return b
        if size is None:
            self.align(4)
            size = self.rd("I")
        require(0 <= size < 10000000, "Unsupported or inconsistent save structure")
        if size > 1:
            self.align(size)
        require(t in [1, 16] or t in FM, "Unknown field type")
        count = size if t in [1, 16] else struct.calcsize(FM[t])
        require(self.p + count <= len(self.d), "Truncated field bytes")
        b = self.d[self.p : self.p + count]
        self.p += count
        return {"size": size, "raw": b}

    def parse(self):
        roots = []
        while self.p < len(self.d) - 7:
            roots.append({"h": self.rd("I"), "c": self.cls()})
        require(self.p == len(self.d), (self.p, len(self.d)))
        return roots

    def pad(self, n):
        self.b.extend(b"\x00" * ((len(self.b) + n - 1 & ~(n - 1)) - len(self.b)))

    def wr(self, fmt, *v):
        self.b.extend(struct.pack("<" + fmt, *v))

    def wc(self, c):
        self.wr("II", len(c["fields"]), c["h"])
        for f in c["fields"]:
            self.wr("Ii", f["h"], f["t"])
            self.wv(f["t"], f["v"])
            self.pad(4)

    def wv(self, t, v, sized=False):
        if t == 17:
            self.wc(v)
            return
        if t == -1:
            self.pad(4)
            self.wr("iIIi", v["mt"], v["ms"], len(v["vals"]), v["at"])
            if v["hashes"] is not None:
                self.wr("I", 0xFFEEFFEE)
                # Some arrays carry one class hash per element before the values.
                for h in v["hashes"]:
                    self.wr("I", h)
            for x in v["vals"]:
                self.wv(17 if v["at"] == 1 else v["mt"], x, v["at"] == 0 and v["mt"] != 15)
            self.pad(4)
            return
        if t == 15:
            self.pad(4)
            self.wr("I", len(v) // 2)
            self.b.extend(v)
            return
        if not sized:
            self.pad(4)
            self.wr("I", v["size"])
        if v["size"] > 1:
            self.pad(v["size"])
        self.b.extend(v["raw"])

    def write(self, roots):
        """Return payload only; the virtual 16-byte header preserves alignment."""
        for r in roots:
            self.wr("I", r["h"])
            self.wc(r["c"])
        return bytes(self.b[16:])


def field(c, name):
    return next(f for f in c["fields"] if f["h"] == H(name))


def walk(c):
    yield c
    for f in c["fields"]:
        if f["t"] == 17:
            yield from walk(f["v"])
        elif f["t"] == -1 and f["v"]["at"] == 1:
            for x in f["v"]["vals"]:
                yield from walk(x)
