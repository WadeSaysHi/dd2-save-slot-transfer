"""Generate an offline slot-1 to slot-2 transfer; never modify live saves."""

import copy
import hashlib
import json
from pathlib import Path

from . import tree as c
from .crypto import check_auth, decrypt, encrypt
from .errors import require

# These hashes identify unknown-name structures in the observed shared system save.
SYSTEM_SLOT_CLASS = 0x0488EA02
SLOT_METADATA_FIELD = 0x89B75AB3
SLOT_PREVIEW_FIELD = 0x559B544E


def read_tree(path, account_id):
    """Validate a frozen snapshot and verify semantic serialization round-trip."""
    enc = Path(path).read_bytes()
    data, _blocks = decrypt(enc, account_id)
    tree = c.Codec(enc[:16] + data).parse()
    require(c.Codec(enc[:16] + c.Codec().write(tree)).parse() == tree, "Semantic round-trip failed")
    return tree


def module(tree):
    return c.field(tree[0]["c"], "GameSaveDataList")["v"]["vals"]


def personal(tree):
    ns = [n for r in tree for n in c.walk(r["c"]) if n["h"] == c.H("app.PlayerPersonalDataContext")]
    require(len(ns) == 1, "Unsupported or inconsistent save structure")
    return ns[0]


def char_contexts(tree, marker):
    records = [
        n
        for r in tree
        for n in c.walk(r["c"])
        if n["h"] == c.H("app.ContextDatabaseSaveDataRecord")
    ]
    matches = []
    for r in records:
        cs = c.field(r, "Contexts")["v"]["vals"]
        if any(x["h"] == c.H(marker) for x in cs):
            matches.append(cs)
    require(len(matches) == 1, (marker, len(matches)))
    return matches[0]


def getctx(cs, name):
    return next(n for n in cs if n["h"] == c.H(name))


def text(f):
    return f["v"].decode("utf-16le").rstrip("\x00")


def describe(tree):
    net = module(tree)[15]
    ps = char_contexts(tree, "app.PlayerPersonalDataContext")
    ms = char_contexts(tree, "app.MainPawnDataContext")

    def status(cs):
        n = getctx(cs, "app.HumanStatusContext")
        return {
            "level": int.from_bytes(c.field(n, "_Level")["v"]["raw"], "little", signed=True),
            "exp_field": int.from_bytes(c.field(n, "_Exp")["v"]["raw"], "little", signed=True),
        }

    return {
        "player": text(c.field(personal(tree), "Name")),
        "pawn": text(c.field(getctx(ms, "app.PawnDataContext"), "_Name")),
        "player_status": status(ps),
        "pawn_status": status(ms),
        "identifiers": {
            k: text(c.field(net, k)) if k == "ServerPawnId" else c.field(net, k)["v"]["raw"].hex()
            for k in ["ServerUserId", "ServerSlotId", "ServerPawnId"]
        },
    }


def transfer(snapshot, output, account_id):
    """Preserve destination identity and names while replacing its game progress.

    All three destination recovery points use the latest source autosave.
    The output directory must be new. Identity values in the generated local
    reports are private and should not be published.
    """
    srcdir, out = (Path(snapshot).resolve(), Path(output).resolve())
    require(not out.is_relative_to(srcdir), "Output must be outside the snapshot directory")
    require(not out.exists(), "Output exists; choose a new directory")
    require(srcdir.is_dir(), "Snapshot directory is missing")

    # Hash the frozen snapshot before reading any save to detect a mixed-time input.
    manifest = [
        {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(srcdir.glob("*.bin"))
    ]
    require(
        {
            "data000.bin",
            "data001Slot.bin",
            "data004Slot.bin",
            "data005Slot.bin",
            "data006Slot.bin",
            "data009Slot.bin",
            "data00-1.bin",
        }.issubset({entry["file"] for entry in manifest}),
        "Incomplete frozen snapshot",
    )

    def read(filename):
        return read_tree(srcdir / filename, account_id)

    source, target, system = (read("data000.bin"), read("data005Slot.bin"), read("data00-1.bin"))
    sm, tm = (module(source), module(target))
    require(len(sm) == len(tm) == 30, "Unsupported module layout")
    require(
        [x["h"] for x in sm] == [x["h"] for x in tm], "Source/destination module schemas differ"
    )
    require(
        [i for i, x in enumerate(sm) if x["h"] == c.H("app.NetworkManager.GameSaveData_04")]
        == [15],
        "Unexpected network module position",
    )
    require(
        c.field(sm[0], "SaveDataAppVersion")["v"] == c.field(tm[0], "SaveDataAppVersion")["v"],
        "Source/destination game versions differ",
    )
    a, b = (describe(source), describe(target))
    require(bool(b["player"]) and bool(b["pawn"]), "Destination names are missing")
    require(len(b["identifiers"]["ServerPawnId"]) == 12, "Destination pawn is not registered")
    require(
        a["identifiers"]["ServerPawnId"] != b["identifiers"]["ServerPawnId"],
        "Unsupported or inconsistent save structure",
    )
    require(
        a["identifiers"]["ServerSlotId"] != b["identifiers"]["ServerSlotId"],
        "Unsupported or inconsistent save structure",
    )
    require(
        b["identifiers"]["ServerSlotId"] != "00" * 16, "Unsupported or inconsistent save structure"
    )
    # Keep the whole destination network module, including its reward/borrow history.
    new = copy.deepcopy(source)
    module(new)[15] = copy.deepcopy(tm[15])
    pn = personal(new)
    pt = personal(target)
    for k in ["Name", "NickName"]:
        c.field(pn, k)["v"] = copy.deepcopy(c.field(pt, k)["v"])
    ms = char_contexts(new, "app.MainPawnDataContext")
    mt = char_contexts(target, "app.MainPawnDataContext")
    pawn = getctx(ms, "app.PawnDataContext")
    tpawn = getctx(mt, "app.PawnDataContext")
    for k in ["_Name", "_Nickname"]:
        c.field(pawn, k)["v"] = copy.deepcopy(c.field(tpawn, k)["v"])
    # Update the main pawn's owner display cache together with the Arisen name.
    owner = getctx(ms, "app.PawnOwnerContext")
    c.field(owner, "_Name")["v"] = copy.deepcopy(c.field(pt, "Name")["v"])
    c.field(owner, "_NickName")["v"] = copy.deepcopy(c.field(pt, "NickName")["v"])
    # Undo only allowed exceptions; the entire remaining tree must equal the source.
    proof = copy.deepcopy(new)
    module(proof)[15] = copy.deepcopy(sm[15])
    pp = personal(proof)
    ps = personal(source)
    for k in ["Name", "NickName"]:
        c.field(pp, k)["v"] = copy.deepcopy(c.field(ps, k)["v"])
    mp = char_contexts(proof, "app.MainPawnDataContext")
    sp = char_contexts(source, "app.MainPawnDataContext")
    for cls, fields in [
        ("app.PawnDataContext", ["_Name", "_Nickname"]),
        ("app.PawnOwnerContext", ["_Name", "_NickName"]),
    ]:
        for k in fields:
            c.field(getctx(mp, cls), k)["v"] = copy.deepcopy(c.field(getctx(sp, cls), k)["v"])
    require(proof == source, "Unsupported or inconsistent save structure")
    require(
        describe(new)["player_status"] == a["player_status"],
        "Unsupported or inconsistent save structure",
    )
    require(
        describe(new)["pawn_status"] == a["pawn_status"],
        "Unsupported or inconsistent save structure",
    )
    require(
        describe(new)["identifiers"] == b["identifiers"],
        "Unsupported or inconsistent save structure",
    )
    outputs = {}
    for fn in ["data005Slot.bin", "data006Slot.bin", "data009Slot.bin"]:
        dest = read(fn)
        require(
            describe(dest)["identifiers"] == b["identifiers"],
            "Unsupported or inconsistent save structure",
        )
        candidate = copy.deepcopy(new)
        require(
            dest[-1]["c"]["h"] == c.H("via.storage.saveService.SaveFileDetail"),
            "Destination file detail is missing",
        )
        expected_slot = {"data005Slot.bin": 5, "data006Slot.bin": 6, "data009Slot.bin": 9}[fn]
        require(
            int.from_bytes(c.field(dest[-1]["c"], "Slot")["v"]["raw"], "little") == expected_slot,
            "Destination file-detail slot number is incorrect",
        )
        candidate[-1] = copy.deepcopy(dest[-1])
        outputs[fn] = candidate
    # Unknown system structures use observed hashes, never guessed byte offsets.
    sysnew = copy.deepcopy(system)
    info = next(n for n in c.walk(sysnew[0]["c"]) if n["h"] == SYSTEM_SLOT_CLASS)
    meta = next(f["v"]["vals"] for f in info["fields"] if f["h"] == SLOT_METADATA_FIELD)
    previews = next(f["v"]["vals"] for f in info["fields"] if f["h"] == SLOT_PREVIEW_FIELD)
    for si, di in [(0, 5), (1, 6), (4, 9)]:
        old = meta[di]
        require(
            c.field(old, "ServerSlotId")["v"]["raw"].hex() == b["identifiers"]["ServerSlotId"],
            "Destination metadata identity mismatch",
        )
        require(
            c.field(meta[si], "ServerSlotId")["v"]["raw"].hex() == a["identifiers"]["ServerSlotId"],
            "Source metadata identity mismatch",
        )
        fresh = copy.deepcopy(meta[si])
        c.field(fresh, "ServerSlotId")["v"] = copy.deepcopy(c.field(old, "ServerSlotId")["v"])
        meta[di] = fresh
        preview = copy.deepcopy(previews[si])
        p = next(n for n in c.walk(preview) if n["h"] == c.H("app.PlayerPersonalDataContext"))
        for k in ["Name", "NickName"]:
            c.field(p, k)["v"] = copy.deepcopy(c.field(pt, k)["v"])
        previews[di] = preview
    outputs["data00-1.bin"] = sysnew
    info_before = next(n for n in c.walk(system[0]["c"]) if n["h"] == SYSTEM_SLOT_CLASS)
    for f in info["fields"]:
        old = next(x for x in info_before["fields"] if x["h"] == f["h"])
        if f["h"] in [SLOT_METADATA_FIELD, SLOT_PREVIEW_FIELD]:
            for i, (v, w) in enumerate(zip(f["v"]["vals"], old["v"]["vals"])):
                if i not in [5, 6, 9]:
                    require(v == w, "Unsupported or inconsistent save structure")
        else:
            require(f == old, "Unsupported or inconsistent save structure")
    sysproof = copy.deepcopy(sysnew)
    proof_info = next(n for n in c.walk(sysproof[0]["c"]) if n["h"] == SYSTEM_SLOT_CLASS)
    for f in proof_info["fields"]:
        if f["h"] in [SLOT_METADATA_FIELD, SLOT_PREVIEW_FIELD]:
            old = next(x for x in info_before["fields"] if x["h"] == f["h"])
            for i in [5, 6, 9]:
                f["v"]["vals"][i] = copy.deepcopy(old["v"]["vals"][i])
    require(sysproof == system, "Unsupported or inconsistent save structure")
    require(
        manifest
        == [
            {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(srcdir.glob("*.bin"))
        ],
        "Snapshot changed during generation",
    )
    out.mkdir(parents=True)
    validation = []
    for fn, tree in outputs.items():
        raw = c.Codec().write(tree)
        enc = encrypt(raw, account_id)
        check_auth(enc, account_id)
        plain, blocks = decrypt(enc, account_id)
        require(plain == raw, "Unsupported or inconsistent save structure")
        parsed = c.Codec(enc[:16] + plain).parse()
        require(parsed == tree, "Unsupported or inconsistent save structure")
        if fn != "data00-1.bin":
            require(describe(parsed) == describe(new), "Unsupported or inconsistent save structure")
        (out / fn).write_bytes(enc)
        validation.append(
            {
                "file": fn,
                "sha256": hashlib.sha256(enc).hexdigest(),
                "blocks": blocks,
                "bytes": len(enc),
            }
        )
    (out / "snapshot-manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "validation.json").write_text(json.dumps(validation, indent=2))
    (out / "comparison.json").write_text(
        json.dumps(
            {
                "source": a,
                "destination_before": b,
                "destination_after": describe(new),
                "checks": [
                    "semantic roundtrip",
                    "source gameplay data equality except named exceptions",
                    "destination network module preserved exactly",
                    "first-slot system previews unchanged",
                    "encryption authentication",
                    "block and file checksums",
                    "decompression size and payload equality",
                ],
            },
            indent=2,
        )
    )
    return {"source": a, "destination_before": b, "destination_after": describe(new)}
