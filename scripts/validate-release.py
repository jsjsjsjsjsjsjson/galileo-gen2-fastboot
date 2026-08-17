#!/usr/bin/env python3
"""Validate the Galileo Gen 2 raw image, capsule and embedded GRUB."""

from __future__ import annotations

import hashlib
import re
import struct
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
ARTIFACTS = PROJECT / "artifacts"
CAPSULE = ARTIFACTS / "galileo-gen2-grub-2.14-fastboot-plain.cap"
RAW = ARTIFACTS / "galileo-gen2-grub-2.14-fastboot-missing-pdat.bin"
GRUB = ARTIFACTS / "grub-2.14-galileo-gen2.efi"
COMPONENTS = ARTIFACTS / "CapsuleComponents.ini"

EXPECTED_COMPONENTS = {
    0xFFF08000: PROJECT / "flash/mfh.bin",
    0xFFFE0000: PROJECT / "firmware/FV/FlashModules/EDKII_BOOTROM_OVERRIDE.Fv",
    0xFFF90000: PROJECT / "firmware/FV/FlashModules/EDKII_RECOVERY_IMAGE1.Fv.signed",
    0xFFF30000: PROJECT / "firmware/FV/FlashModules/EDKII_NVRAM.bin",
    0xFFF00000: PROJECT / "firmware/FV/FlashModules/RMU.bin",
    0xFFEC0000: PROJECT / "firmware/FV/FlashModules/EDKII_BOOT_STAGE1_IMAGE1.Fv.signed",
    0xFFE80000: PROJECT / "firmware/FV/FlashModules/EDKII_BOOT_STAGE1_IMAGE2.Fv.signed",
    0xFFD00000: PROJECT / "firmware/FV/FlashModules/EDKII_BOOT_STAGE2_COMPACT.Fv.signed",
    0xFFCFF000: PROJECT / "flash/layout.conf",
    0xFF800000: PROJECT / "firmware/grub-2.14-galileo-gen2.efi.fv.signed",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_grub() -> None:
    data = GRUB.read_bytes()
    assert data[:2] == b"MZ", "GRUB is not a PE/COFF image"
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe_offset : pe_offset + 4] == b"PE\0\0"
    machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
    assert machine == 0x014C, f"GRUB PE machine is not IA32: {machine:#x}"
    assert b"GRUB_2.14_Galileo_Gen2" in data
    assert b"/tmp/quark-port-audit" not in data
    assert b"No grub.cfg found - rescan removable media" not in data
    assert b"help" in data


def check_capsule() -> None:
    data = CAPSULE.read_bytes()
    css = struct.unpack_from("<13I", data, 0)
    assert css[0] == 0x5F435348, "missing Intel CSS signing header"
    assert css[2] == len(data), "CSS module size does not match file size"
    body = css[8]
    assert body == 0x400, f"unexpected signed body offset: {body:#x}"

    header_size, flags, image_size = struct.unpack_from("<III", data, body + 16)
    assert header_size == 0x50
    assert flags == 0x10000
    assert image_size == len(data) - body

    targets = set()
    hint_base = body + header_size
    for index in range(20):
        target, size, source, reserved = struct.unpack_from(
            "<IIII", data, hint_base + index * 16
        )
        if target in (0, 0xFFFFFFFF):
            break
        assert size and size % 0x1000 == 0
        assert reserved == 0xFFFFFFFF
        assert body + source + size <= len(data)
        component = EXPECTED_COMPONENTS[target].read_bytes()
        assert data[body + source : body + source + len(component)] == component
        targets.add(target)
    assert targets == set(EXPECTED_COMPONENTS), (
        f"capsule target mismatch: got {sorted(targets)}, "
        f"expected {sorted(EXPECTED_COMPONENTS)}"
    )


def check_layout() -> None:
    raw = RAW.read_bytes()
    assert len(raw) == 8 * 1024 * 1024
    for target, path in EXPECTED_COMPONENTS.items():
        component = path.read_bytes()
        offset = target - 0xFF800000
        assert raw[offset : offset + len(component)] == component
    text = COMPONENTS.read_text(encoding="utf-8")
    for removed in ("Kernel", "Ramdisk", "grub.conf"):
        assert re.search(rf"^\[{re.escape(removed)}\]$", text, re.MULTILINE) is None


def main() -> None:
    check_grub()
    check_capsule()
    check_layout()
    for path in (CAPSULE, RAW, GRUB):
        print(f"{digest(path)}  {path.relative_to(PROJECT)}")
    print("validation: OK")


if __name__ == "__main__":
    main()
