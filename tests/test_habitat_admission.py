# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate_habitat_admission import HabitatAdmissionError, validate


ROOT = Path(__file__).resolve().parents[1]


class HabitatAdmissionTests(unittest.TestCase):
    def copy_fixture(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / ".janus").mkdir(parents=True)
        shutil.copy2(ROOT / ".janus" / "HABITAT_LINK.json", tmp / ".janus" / "HABITAT_LINK.json")
        shutil.copy2(ROOT / ".janus" / "HABITAT_ADMISSION.json", tmp / ".janus" / "HABITAT_ADMISSION.json")
        shutil.copy2(ROOT / "PROJECT_STATUS.json", tmp / "PROJECT_STATUS.json")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        return tmp

    @staticmethod
    def rewrite(path: Path, mutate) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_current_repository_admission_passes(self) -> None:
        receipt = validate(ROOT)
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["role"], "LEGACY_EXPERIMENTAL_SANDBOX_REFERENCE")
        self.assertFalse(receipt["runtime_activation"])
        self.assertFalse(receipt["write_back"])
        self.assertEqual(receipt["authority_delta"], 0)

    def test_write_back_widening_fails_closed(self) -> None:
        root = self.copy_fixture()
        self.rewrite(
            root / ".janus" / "HABITAT_LINK.json",
            lambda data: data.__setitem__("write_back_default", "ALLOW"),
        )
        with self.assertRaises(HabitatAdmissionError):
            validate(root)

    def test_habitat_command_authority_widening_fails_closed(self) -> None:
        root = self.copy_fixture()
        self.rewrite(
            root / ".janus" / "HABITAT_LINK.json",
            lambda data: data.__setitem__("habitat_command_authority_granted", True),
        )
        with self.assertRaises(HabitatAdmissionError):
            validate(root)

    def test_runtime_activation_through_admission_fails_closed(self) -> None:
        root = self.copy_fixture()
        self.rewrite(
            root / ".janus" / "HABITAT_ADMISSION.json",
            lambda data: data["habitat_role"].__setitem__("runtime_activation_implied", True),
        )
        with self.assertRaises(HabitatAdmissionError):
            validate(root)

    def test_direct_memory_write_admission_fails_closed(self) -> None:
        root = self.copy_fixture()
        self.rewrite(
            root / ".janus" / "HABITAT_ADMISSION.json",
            lambda data: data["memory_power_boundary"].__setitem__(
                "direct_write_to_cortex_store", True
            ),
        )
        with self.assertRaises(HabitatAdmissionError):
            validate(root)

    def test_direct_power_executor_registration_fails_closed(self) -> None:
        root = self.copy_fixture()
        self.rewrite(
            root / ".janus" / "HABITAT_ADMISSION.json",
            lambda data: data["memory_power_boundary"].__setitem__(
                "direct_power_executor_registration", True
            ),
        )
        with self.assertRaises(HabitatAdmissionError):
            validate(root)

    def test_legacy_project_cannot_be_silently_promoted_to_flagship(self) -> None:
        root = self.copy_fixture()
        self.rewrite(
            root / "PROJECT_STATUS.json",
            lambda data: data.__setitem__("flagship_research", True),
        )
        with self.assertRaises(HabitatAdmissionError):
            validate(root)

    def test_science_nonclaim_cannot_be_silently_removed(self) -> None:
        root = self.copy_fixture()

        def mutate(data):
            data["not_established"].remove("validated scientific result")

        self.rewrite(root / "PROJECT_STATUS.json", mutate)
        with self.assertRaises(HabitatAdmissionError):
            validate(root)

    def test_existing_habitat_link_blob_pin_is_part_of_admission(self) -> None:
        root = self.copy_fixture()
        self.rewrite(
            root / ".janus" / "HABITAT_ADMISSION.json",
            lambda data: data["existing_link"].__setitem__("blob_sha", "0" * 40),
        )
        with self.assertRaises(HabitatAdmissionError):
            validate(root)


if __name__ == "__main__":
    unittest.main()
