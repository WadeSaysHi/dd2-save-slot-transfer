"""Public regression tests use generated data only; never load personal saves."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from dd2_slot_refresh.crypto import decrypt, encrypt
from dd2_slot_refresh.errors import ValidationError
from dd2_slot_refresh.refresh import describe, read_tree, refresh
from dd2_slot_refresh.tree import Codec, H, field

ACCOUNT = 123456789  # Synthetic test account, unrelated to any real snapshot.


def scalar(value, size=4):
    return {"size": size, "raw": value.to_bytes(size, "little", signed=True)}


def node(name, fields=()):
    return {"h": H(name), "fields": list(fields)}


def member(name, kind, value):
    return {"h": H(name), "t": kind, "v": value}


def string(name, value):
    return member(name, 15, value.encode("utf-16le"))


def object_array(values):
    return {"mt": 17, "ms": 0, "at": 1, "hashes": None, "vals": values}


def player(name):
    return node(
        "app.PlayerPersonalDataContext", [string("Name", name), string("NickName", "Alias")]
    )


def network(slot):
    return node(
        "app.NetworkManager.GameSaveData_04",
        [
            member("ServerUserId", 16, {"size": 16, "raw": bytes([slot + 10]) * 16}),
            member("ServerSlotId", 16, {"size": 16, "raw": bytes([slot]) * 16}),
            string("ServerPawnId", "SOURCE000001" if slot == 1 else "TARGET000002"),
            member("PrivateNetworkHistory", 8, scalar(100 + slot)),
        ],
    )


def game(slot, file_slot):
    name, pawn_name = ("Source", "SourcePawn") if slot == 1 else ("Dest Ω", "DestPawn")
    modules = [node(f"synthetic.Module{i}") for i in range(30)]
    modules[0] = node("app.GameSystem.GameSaveData", [member("SaveDataAppVersion", 8, scalar(7))])
    modules[15] = network(slot)
    status = lambda: node(
        "app.HumanStatusContext",
        [
            member("_Level", 7, scalar(99 if slot == 1 else 2)),
            member("_Exp", 7, scalar(141431 if slot == 1 else 182)),
            member("UnknownGrowthStruct", 16, {"size": 24, "raw": bytes(range(24))}),
        ],
    )
    arisen_record = node(
        "app.ContextDatabaseSaveDataRecord",
        [member("Contexts", -1, object_array([player(name), status()]))],
    )
    pawn_record = node(
        "app.ContextDatabaseSaveDataRecord",
        [
            member(
                "Contexts",
                -1,
                object_array(
                    [
                        node("app.MainPawnDataContext"),
                        node(
                            "app.PawnDataContext",
                            [string("_Name", pawn_name), string("_Nickname", "PawnAlias")],
                        ),
                        node(
                            "app.PawnOwnerContext",
                            [string("_Name", name), string("_NickName", "Alias")],
                        ),
                        status(),
                    ]
                ),
            )
        ],
    )
    modules[17] = node(
        "app.ContextDBMSSaveData",
        [member("Records", -1, object_array([arisen_record, pawn_record]))],
    )
    # A primitive array exercises preservation of values that the old JSON exporter omitted.
    modules[6] = node(
        "app.ItemManager.GameSaveData",
        [
            member(
                "SyntheticItems",
                -1,
                {
                    "mt": 8,
                    "ms": 4,
                    "at": 0,
                    "hashes": None,
                    "vals": [scalar(123), scalar(456), scalar(slot)],
                },
            )
        ],
    )
    return [
        {
            "h": H("GameRoot"),
            "c": node(
                "app.SaveDataManager.GameSaveData",
                [member("GameSaveDataList", -1, object_array(modules))],
            ),
        },
        {
            "h": H("DetailRoot"),
            "c": node(
                "via.storage.saveService.SaveFileDetail", [member("Slot", 7, scalar(file_slot))]
            ),
        },
    ]


def system():
    metas, previews = [], []
    for i in range(10):
        slot = 2 if i in (5, 6, 9) else 1
        metas.append(
            node(
                "SyntheticMeta",
                [
                    member("ServerSlotId", 16, {"size": 16, "raw": bytes([slot]) * 16}),
                    member("PlayTime", 7, scalar(1000 if slot == 1 else 50)),
                ],
            )
        )
        previews.append(
            node(
                "SyntheticPreview",
                [member("Player", 17, player("Source" if slot == 1 else "Dest Ω"))],
            )
        )
    info = {
        "h": 0x0488EA02,
        "fields": [
            {"h": 0x89B75AB3, "t": -1, "v": object_array(metas)},
            {"h": 0x559B544E, "t": -1, "v": object_array(previews)},
        ],
    }
    return [
        {
            "h": H("SystemRoot"),
            "c": node(
                "app.SaveDataManager.SystemSaveData",
                [member("SystemSaveDataList", -1, object_array([info]))],
            ),
        }
    ]


def write_snapshot(path):
    for name, slot, index in [
        ("data000.bin", 1, 0),
        ("data001Slot.bin", 1, 1),
        ("data004Slot.bin", 1, 4),
        ("data005Slot.bin", 2, 5),
        ("data006Slot.bin", 2, 6),
        ("data009Slot.bin", 2, 9),
    ]:
        (path / name).write_bytes(encrypt(Codec().write(game(slot, index)), ACCOUNT))
    (path / "data00-1.bin").write_bytes(encrypt(Codec().write(system()), ACCOUNT))


class WorkflowTests(unittest.TestCase):
    def test_crypto_tree_and_nonstandard_alignment_round_trip(self):
        original = game(1, 0)
        raw = Codec().write(original)
        encoded = encrypt(raw, ACCOUNT)
        plain, blocks = decrypt(encoded, ACCOUNT)
        self.assertEqual(plain, raw)
        self.assertGreater(blocks, 0)
        self.assertEqual(Codec(encoded[:16] + plain).parse(), original)

    def test_wrong_account_and_corruption_are_rejected(self):
        encoded = encrypt(Codec().write(game(1, 0)), ACCOUNT)
        with self.assertRaises(ValidationError):
            decrypt(encoded, ACCOUNT + 1)
        damaged = bytearray(encoded)
        damaged[100] ^= 1
        with self.assertRaises(ValidationError):
            decrypt(bytes(damaged), ACCOUNT)

    def test_full_refresh_preserves_identity_names_progress_and_slot_numbers(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot, output = Path(temp) / "snapshot", Path(temp) / "output"
            snapshot.mkdir()
            write_snapshot(snapshot)
            before = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir()
            }
            result = refresh(snapshot, output, ACCOUNT)
            self.assertEqual(result["destination_after"]["player"], "Dest Ω")
            self.assertEqual(result["destination_after"]["pawn"], "DestPawn")
            self.assertEqual(
                result["destination_after"]["player_status"], result["source"]["player_status"]
            )
            self.assertEqual(
                result["destination_after"]["identifiers"],
                result["destination_before"]["identifiers"],
            )
            for filename, slot in [
                ("data005Slot.bin", 5),
                ("data006Slot.bin", 6),
                ("data009Slot.bin", 9),
            ]:
                tree = read_tree(output / filename, ACCOUNT)
                self.assertEqual(
                    int.from_bytes(field(tree[-1]["c"], "Slot")["v"]["raw"], "little"), slot
                )
            self.assertEqual(
                before,
                {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir()},
            )
            self.assertEqual(len(json.loads((output / "validation.json").read_text())), 4)
            with self.assertRaises(ValidationError):
                refresh(snapshot, output, ACCOUNT)

    def test_unregistered_destination_never_creates_output(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot, output = Path(temp) / "snapshot", Path(temp) / "output"
            snapshot.mkdir()
            write_snapshot(snapshot)
            tree = game(2, 5)
            modules = field(tree[0]["c"], "GameSaveDataList")["v"]["vals"]
            field(modules[15], "ServerPawnId")["v"] = b""
            (snapshot / "data005Slot.bin").write_bytes(encrypt(Codec().write(tree), ACCOUNT))
            with self.assertRaises(ValidationError):
                refresh(snapshot, output, ACCOUNT)
            self.assertFalse(output.exists())

    def test_context_record_order_is_not_hardcoded(self):
        tree = game(2, 5)
        modules = field(tree[0]["c"], "GameSaveDataList")["v"]["vals"]
        field(modules[17], "Records")["v"]["vals"].reverse()
        self.assertEqual(describe(tree)["player"], "Dest Ω")
        self.assertEqual(describe(tree)["pawn"], "DestPawn")


if __name__ == "__main__":
    unittest.main()
