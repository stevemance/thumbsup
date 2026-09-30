#!/usr/bin/env python3
import argparse
import dataclasses
import sys
import time
from pathlib import Path

import serial


class ServiceError(RuntimeError):
    pass


@dataclasses.dataclass
class ServiceReply:
    kind: str
    line: str


@dataclasses.dataclass
class FlashGeometry:
    page_size: int
    write_align: int
    source: str


class PicoAm32Service:
    def __init__(self, port: str, baud: int = 115200, verbose: bool = False):
        self.port = port
        self.baud = baud
        self.verbose = verbose
        self.ser = serial.Serial(port, baudrate=baud, timeout=0.2, write_timeout=2.0)
        self._synced = False

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _read_reply(self, timeout_s: float) -> ServiceReply:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            self._log(f"<< {line}")
            if line.startswith("OK "):
                return ServiceReply("OK", line)
            if line.startswith("ERR "):
                return ServiceReply("ERR", line)
            if line.startswith("DATA "):
                return ServiceReply("DATA", line)
            # Ignore verbose bootloader logs.
        raise TimeoutError(f"Timed out waiting for service reply ({timeout_s}s)")

    def sync(self, attempts: int = 8) -> None:
        if self._synced:
            return

        # Opening USB CDC can reset Pico. Drain startup noise first.
        drain_deadline = time.monotonic() + 2.5
        while time.monotonic() < drain_deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                self._log(f"<< {line}")
        self.ser.reset_input_buffer()

        for _ in range(attempts):
            try:
                reply = self.cmd("PING", timeout_s=1.2)
                if reply.line.startswith("OK PONG"):
                    self._synced = True
                    return
            except (TimeoutError, ServiceError):
                pass
            time.sleep(0.2)

        raise TimeoutError("Timed out waiting for flasher service PING response")

    def cmd(self, command: str, timeout_s: float = 15.0) -> ServiceReply:
        self._log(f">> {command}")
        self.ser.write((command + "\n").encode("utf-8"))
        self.ser.flush()
        reply = self._read_reply(timeout_s)
        if reply.kind == "ERR":
            raise ServiceError(reply.line)
        return reply

    def enter(self) -> None:
        # Bootloader entry can take a while with high-idle retries.
        self.cmd("ENTER", timeout_s=90.0)

    def info(self) -> tuple[dict[str, str], str]:
        reply = self.cmd("INFO", timeout_s=5.0)
        if not reply.line.startswith("OK INFO "):
            raise ServiceError(f"Unexpected INFO response: {reply.line}")

        fields: dict[str, str] = {}
        for tok in reply.line.split()[2:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                fields[k] = v
        return fields, reply.line

    def read_cfg(self) -> bytes:
        reply = self.cmd("READCFG", timeout_s=10.0)
        if not reply.line.startswith("DATA CFG "):
            raise ServiceError(f"Unexpected READCFG response: {reply.line}")
        hex_data = reply.line.split(" ", 2)[2]
        return bytes.fromhex(hex_data)

    def read_at(self, addr: int, length: int) -> bytes:
        if length < 1 or length > 256:
            raise ValueError("length must be 1..256")
        reply = self.cmd(f"READAT {addr:04X} {length}", timeout_s=10.0)
        if not reply.line.startswith("DATA READAT "):
            raise ServiceError(f"Unexpected READAT response: {reply.line}")
        parts = reply.line.split(" ")
        if len(parts) < 5:
            raise ServiceError(f"Malformed READAT response: {reply.line}")
        return bytes.fromhex(parts[4])

    def read_span(self, addr: int, length: int) -> bytes:
        out = bytearray()
        remaining = length
        cursor = addr
        while remaining > 0:
            n = min(256, remaining)
            out.extend(self.read_at(cursor, n))
            cursor += n
            remaining -= n
        return bytes(out)

    def flash_chunk(self, addr: int, payload: bytes) -> None:
        if not payload or len(payload) > 256:
            raise ValueError("payload must be 1..256 bytes")
        self.cmd(f"FLASH {addr:04X} {payload.hex().upper()}", timeout_s=10.0)


def parse_intel_hex(path: Path) -> list[tuple[int, bytes]]:
    memory: dict[int, int] = {}
    upper = 0

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if not line.startswith(":"):
            raise ValueError(f"{path}:{lineno}: not an Intel HEX record")
        try:
            raw = bytes.fromhex(line[1:])
        except ValueError as exc:
            raise ValueError(f"{path}:{lineno}: invalid hex payload") from exc
        if len(raw) < 5:
            raise ValueError(f"{path}:{lineno}: record too short")
        reclen = raw[0]
        if len(raw) != reclen + 5:
            raise ValueError(f"{path}:{lineno}: record length mismatch")
        if (sum(raw) & 0xFF) != 0:
            raise ValueError(f"{path}:{lineno}: checksum mismatch")
        addr = (raw[1] << 8) | raw[2]
        rectype = raw[3]
        data = raw[4:4 + reclen]

        if rectype == 0x00:
            base = (upper << 16) | addr
            for i, b in enumerate(data):
                memory[base + i] = b
        elif rectype == 0x01:
            break
        elif rectype == 0x04:
            if reclen != 2:
                raise ValueError(f"{path}:{lineno}: invalid extended-linear record")
            upper = (data[0] << 8) | data[1]
        else:
            # Ignore unsupported record types.
            continue

    if not memory:
        return []

    segs: list[tuple[int, bytes]] = []
    addrs = sorted(memory.keys())
    start = addrs[0]
    prev = addrs[0]
    chunk = bytearray([memory[start]])
    for a in addrs[1:]:
        if a == prev + 1:
            chunk.append(memory[a])
        else:
            segs.append((start, bytes(chunk)))
            start = a
            chunk = bytearray([memory[a]])
        prev = a
    segs.append((start, bytes(chunk)))
    return segs


def iter_chunks(segments: list[tuple[int, bytes]], chunk_size: int) -> list[tuple[int, bytes]]:
    out: list[tuple[int, bytes]] = []
    for start, data in segments:
        off = 0
        while off < len(data):
            c = data[off:off + chunk_size]
            out.append((start + off, c))
            off += len(c)
    return out


def build_memory_map(segments: list[tuple[int, bytes]], min_addr: int) -> dict[int, int]:
    out: dict[int, int] = {}
    for start, data in segments:
        for i, b in enumerate(data):
            addr = start + i
            if addr >= min_addr:
                out[addr] = b
    return out


def infer_flash_geometry(name: str, page_size_override: int | None, align_override: int | None) -> FlashGeometry:
    upper = name.upper()

    if page_size_override is not None and page_size_override <= 0:
        raise ValueError("--page-size must be > 0")
    if align_override is not None and align_override <= 0:
        raise ValueError("--write-align must be > 0")

    if "V203" in upper or "CH32V203" in upper:
        page_size = page_size_override or 256
        write_align = align_override or 4
        return FlashGeometry(page_size=page_size, write_align=write_align, source="name:v203")

    if "G071" in upper or "G431" in upper or "L431" in upper:
        page_size = page_size_override or 2048
        write_align = align_override or 8
        return FlashGeometry(page_size=page_size, write_align=write_align, source="name:2k-page")

    if "F421" in upper or "F415" in upper or "F051" in upper or "F031" in upper or "E230" in upper:
        page_size = page_size_override or 1024
        write_align = align_override or 4
        return FlashGeometry(page_size=page_size, write_align=write_align, source="name:1k-page")

    if page_size_override is None:
        raise ValueError(
            "Unable to infer flash geometry from ESC name; pass --page-size and --write-align"
        )

    return FlashGeometry(
        page_size=page_size_override,
        write_align=align_override or 4,
        source="manual",
    )


def make_page_updates(memory: dict[int, int], page_size: int) -> dict[int, list[tuple[int, int]]]:
    page_updates: dict[int, list[tuple[int, int]]] = {}
    for addr, val in memory.items():
        page_num = addr // page_size
        page_base = page_num * page_size
        page_updates.setdefault(page_num, []).append((addr - page_base, val))
    return page_updates


def program_pages(
    svc: PicoAm32Service,
    page_updates: dict[int, list[tuple[int, int]]],
    geometry: FlashGeometry,
    flash_base: int,
    chunk_size: int,
    verify: bool,
) -> None:
    if chunk_size < 1 or chunk_size > 256:
        raise ValueError("chunk_size must be 1..256")
    if (chunk_size % geometry.write_align) != 0:
        raise ValueError(f"chunk_size ({chunk_size}) must be a multiple of write-align ({geometry.write_align})")
    if (geometry.page_size % chunk_size) != 0:
        raise ValueError(
            f"page_size ({geometry.page_size}) must be divisible by chunk_size ({chunk_size})"
        )

    pages = sorted(page_updates.keys())
    total_chunks = len(pages) * (geometry.page_size // chunk_size)
    done = 0

    for pidx, page_num in enumerate(pages, start=1):
        page_base_abs = page_num * geometry.page_size
        rel_base = page_base_abs - flash_base
        rel_last = rel_base + geometry.page_size - 1
        if rel_base < 0 or rel_last > 0xFFFF:
            raise ValueError(
                f"Page 0x{page_base_abs:08X} exceeds 16-bit bootloader address range"
            )

        page_data = bytearray(svc.read_span(rel_base, geometry.page_size))
        updates = page_updates[page_num]
        for off, val in updates:
            page_data[off] = val

        for off in range(0, geometry.page_size, chunk_size):
            payload = bytes(page_data[off:off + chunk_size])
            addr = rel_base + off
            svc.flash_chunk(addr, payload)
            if verify:
                got = svc.read_at(addr, len(payload))
                if got != payload:
                    raise ServiceError(f"Verify mismatch at 0x{page_base_abs + off:08X}")
            done += 1
            if (done % 16) == 0 or done == total_chunks:
                print(f"Flashed {done}/{total_chunks} chunks ({pidx}/{len(pages)} pages)")


def cmd_probe(args: argparse.Namespace) -> int:
    svc = PicoAm32Service(args.port, args.baud, args.verbose)
    try:
        svc.sync()
        svc.enter()
        _, info_line = svc.info()
        print(info_line)
        sample = svc.read_at(0x7C00, 32)
        print(f"DATA EEPROM_7C00 {sample.hex().upper()}")
        return 0
    finally:
        svc.close()


def cmd_read_config(args: argparse.Namespace) -> int:
    svc = PicoAm32Service(args.port, args.baud, args.verbose)
    try:
        svc.sync()
        svc.enter()
        cfg = svc.read_cfg()
        if len(cfg) != 192:
            raise ServiceError(f"Expected 192 bytes, got {len(cfg)}")
        Path(args.out).write_bytes(cfg)
        print(f"Wrote {len(cfg)} bytes to {args.out}")
        return 0
    finally:
        svc.close()


def cmd_write_config(args: argparse.Namespace) -> int:
    cfg = Path(args.input).read_bytes()
    if len(cfg) != 192:
        raise ValueError(f"{args.input}: expected 192 bytes, got {len(cfg)}")

    svc = PicoAm32Service(args.port, args.baud, args.verbose)
    try:
        svc.sync()
        svc.enter()
        info_fields, _ = svc.info()

        try:
            svc.cmd(f"WRITECFG {cfg.hex().upper()}", timeout_s=15.0)
            print("Config write OK")
            return 0
        except ServiceError:
            # Bootloader variant fallback: preserve full page contents and rewrite page.
            name = info_fields.get("name", "")
            geometry = infer_flash_geometry(name, page_size_override=None, align_override=None)
            if "F421" not in name.upper():
                raise ServiceError(
                    "WRITECFG failed and fallback eeprom base is only implemented for F421 targets"
                )

            eeprom_base_abs = 0x08007C00
            updates = {eeprom_base_abs + i: cfg[i] for i in range(len(cfg))}
            page_updates = make_page_updates(updates, geometry.page_size)
            program_pages(
                svc,
                page_updates=page_updates,
                geometry=geometry,
                flash_base=0x08000000,
                chunk_size=256,
                verify=True,
            )
            verify_cfg = svc.read_cfg()
            if verify_cfg != cfg:
                raise ServiceError("WRITECFG fallback verify mismatch")
            print("Config write OK (flash fallback)")
            return 0
    finally:
        svc.close()


def cmd_flash_hex(args: argparse.Namespace) -> int:
    segments = parse_intel_hex(Path(args.hex))
    memory = build_memory_map(segments, args.min_addr)
    if not memory:
        print("No flashable data after filtering")
        return 0

    first = min(memory.keys())
    last = max(memory.keys())
    print(f"Parsed {len(segments)} segments")
    print(f"Address range: 0x{first:08X}..0x{last:08X}")

    if args.dry_run:
        filtered_segments: list[tuple[int, bytes]] = []
        for start, data in segments:
            seg_end = start + len(data)
            if seg_end <= args.min_addr:
                continue
            if start < args.min_addr:
                data = data[args.min_addr - start:]
                start = args.min_addr
            filtered_segments.append((start, data))

        chunks = iter_chunks(filtered_segments, args.chunk_size)
        for i, (addr, data) in enumerate(chunks[:10], start=1):
            print(f"  chunk {i:03d}: addr=0x{addr:08X} len={len(data)}")
        if len(chunks) > 10:
            print(f"  ... {len(chunks)-10} more chunks")
        return 0

    svc = PicoAm32Service(args.port, args.baud, args.verbose)
    try:
        svc.sync()
        svc.enter()
        info_fields, info_line = svc.info()
        if args.verbose:
            print(info_line)

        geometry = infer_flash_geometry(
            info_fields.get("name", ""),
            page_size_override=args.page_size,
            align_override=args.write_align,
        )

        print(
            f"Geometry: page={geometry.page_size} align={geometry.write_align} ({geometry.source})"
        )
        page_updates = make_page_updates(memory, geometry.page_size)
        print(f"Touched pages: {len(page_updates)}")

        program_pages(
            svc,
            page_updates=page_updates,
            geometry=geometry,
            flash_base=args.flash_base,
            chunk_size=args.chunk_size,
            verify=args.verify,
        )

        if not args.no_run:
            svc.cmd("RUN", timeout_s=5.0)
            print("Issued RUN")

        print("Flash complete")
        return 0
    finally:
        svc.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AM32 flasher/config orchestration through Pico service firmware"
    )
    p.add_argument("--port", default="/dev/ttyHITL_ROBOT", help="Pico USB CDC port (default: /dev/ttyHITL_ROBOT)")
    p.add_argument("--baud", type=int, default=115200, help="USB serial baud")
    p.add_argument("--verbose", action="store_true", help="Print raw service traffic")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("probe", help="Enter bootloader and print info")
    sp.set_defaults(func=cmd_probe)

    sr = sub.add_parser("read-config", help="Read 192-byte EEPROM config")
    sr.add_argument("--out", required=True, help="Output .bin path")
    sr.set_defaults(func=cmd_read_config)

    sw = sub.add_parser("write-config", help="Write 192-byte EEPROM config")
    sw.add_argument("--input", required=True, help="Input .bin path (192 bytes)")
    sw.set_defaults(func=cmd_write_config)

    sf = sub.add_parser("flash-hex", help="Flash Intel HEX firmware using page-safe writes")
    sf.add_argument("--hex", required=True, help="Intel HEX file")
    sf.add_argument("--chunk-size", type=int, default=256, help="Program chunk size (1..256, default: 256)")
    sf.add_argument("--flash-base", type=lambda s: int(s, 0), default=0x08000000, help="MCU flash base (default: 0x08000000)")
    sf.add_argument("--min-addr", type=lambda s: int(s, 0), default=0x08001000, help="Minimum absolute address to flash (default: 0x08001000)")
    sf.add_argument("--page-size", type=lambda s: int(s, 0), default=None, help="Override flash page size in bytes")
    sf.add_argument("--write-align", type=lambda s: int(s, 0), default=None, help="Override write alignment in bytes")
    sf.add_argument("--verify", action="store_true", help="Read back each programmed chunk")
    sf.add_argument("--dry-run", action="store_true", help="Parse and plan only")
    sf.add_argument("--no-run", action="store_true", help="Do not issue RUN after flashing")
    sf.set_defaults(func=cmd_flash_hex)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ServiceError, ValueError, TimeoutError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
