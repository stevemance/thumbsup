# Programming the weapon ESC from the Pico

The robot Pico can back up and reprogram the weapon ESC's flash over the
DShot signal wire (GP4), using the ESC's AM32 bootloader. This was validated
on the HITL rig on 2026-09-30 with a full backup and an identical-image
round-trip (see "Validation" below). No SWD or extra hardware is needed.

## The ESC

| Item | Value |
|---|---|
| ESC / target | FREELYRC_F421 (AT32F421, 32 KB flash, 1 KB pages, 4-byte program words) |
| Bootloader | `AM32_F421_PB4_BOOTLOADER_V4` (AlkaMotors lineage), byte-identical to the release |
| Firmware | AM32 2.20, byte-identical to `AM32_FREELYRC_F421_2.20.hex` from the AM32 v2.20 release |

Flash layout (offsets from 0x08000000, which is what the bootloader protocol uses):

| Range | Contents |
|---|---|
| 0x0000–0x0FFF | Bootloader. Never written: the service refuses it and so does the bootloader. |
| 0x1000–0x7BDF | Application (the 2.20 image ends at 0x65CB; the rest is erased) |
| 0x7BE0–0x7BFF | Target name `FREELYRC_F421` |
| 0x7C00–0x7FFF | EEPROM page: settings in bytes 0–191 (see `config/am32/`) |

**EEPROM byte 0 is the bootloader's "application valid" flag.** With it at
0x01 the bootloader jumps to the application whenever it sees the signal line
low for ~20 ms, which includes every Pico reset (RP2040 pads reset with a
pull-down). Any application write must therefore clear byte 0 first and set it
back only after the whole image has been verified.

## Tools

- `firmware/tests` target `am32_flasher_service`: service firmware for the
  robot Pico (USB CDC commands PING/ENTER/INFO/READCFG/READAT/FLASH/RUN).
  `FLASH` refuses anything outside 0x1000–0x7FFF or not word aligned, and reads
  every write back, replying `OK ... verified` only on an exact match (the
  bootloader acknowledges writes without checking them).
- `tools/am32_pico_flasher.py`:
  - `probe`: enter the bootloader, print INFO and the EEPROM header.
  - `read-flash --out X.bin`: back up 0x0000–0x8000, read twice, written only if both passes match.
  - `flash-hex --hex X.hex --no-run`: program whole 1 KB pages. The host also
    reads back every chunk unless `--no-verify` is given. It never writes below
    `--min-addr` (default 0x08001000).
    `--base-image backup.bin` supplies the bytes of partly covered pages from a
    backup rather than from the device.
  - `write-config --input cfg.bin`: validate a 192-byte config (codec rules),
    refuse a firmware/EEPROM-version mismatch, save the current EEPROM page,
    rewrite the whole page from memory (retrying the same image), and restore
    the saved page if it cannot complete. AM32 bootloaders do not implement a
    separate EEPROM command, so this is always a page rewrite.
- `tools/am32_config_codec.py`: YAML <-> 192-byte config. YAML files must be
  complete (decompile the ESC's config to start one); compile refuses byte 0
  != 0x01 and unknown layouts, and warns on suspicious values.

A write that starts on a 1 KB boundary erases the whole page, so always
program complete pages from a known image. Do not retry a failed page from a
fresh device read, which may already be half-erased.

## Procedure

Keep the HITL orchestrator away from the ESC while doing this: it re-provisions
on its own. The weapon motor must be free to spin later.

1. Power the ESC (`labctl psu set --channel 1 --voltage 12.6 --current 5.0 --on`)
   and flash `am32_flasher_service.uf2` to the robot Pico (check its serial first).
2. `python3 tools/am32_pico_flasher.py probe`. It must report
   `sig=471 flash=0x1F proto=1 name=FREELYRC_F421`. Stop on anything else.
3. **Back up**: `read-flash --out backup.bin`. Keep this file: it is the only way back.
4. Build the images from the backup (or the new firmware) with absolute addresses, e.g.
   `arm-none-eabi-objcopy -I binary -O ihex --change-addresses 0x08001000 app.bin app.hex`,
   and check each with `flash-hex --hex X.hex --dry-run`.
5. Write the EEPROM page with **byte 0 = 0x00** and verify it. Power-cycle
   the ESC and re-probe: it must stay in the bootloader. This is the recovery lever.
6. Write the application pages (0x1000–0x7BFF). On any error, power-cycle and
   re-run this step from the start; it is idempotent.
7. `read-flash` and compare everything except EEPROM byte 0 with the intended image.
8. Write the final EEPROM page (byte 0 = 0x01) and `read-flash` again: it must
   match the intended image exactly.
9. Flash the robot firmware back and run the HITL suites (`full_e2e`,
   `tools/telem_truth.py`).

For a firmware *update*, the EEPROM layout can change between AM32 versions
(`eeprom_version`), so check `tools/am32_config_codec.py` against the new
version before writing its settings.

## Validation (2026-09-30)

- Backup: 4 full reads over two sessions, identical (sha256 `eaad869f…`); plus
  one more with the fixed service. The bootloader and application matched their
  public releases byte for byte (only the 4 name-padding bytes 0x7BFC–0x7BFF
  are 0xFF on the ESC vs 0x00 in the release hex).
- The service refused writes at 0x0000, 0x0FFC, 0x7FFC, misaligned addresses
  and partial words without contacting the ESC.
- Pattern write and erase on the unused page 0x7400, verified.
- EEPROM byte 0 cleared; ESC power-cycled and Pico rebooted; ESC stayed in the bootloader.
- All 27 application pages rewritten from the backup (68 s), read back identical.
- EEPROM restored; the full 32 KB read back identical to the original backup.
- ESC then booted the application: HITL `full_e2e` passed (provisioning found the
  config already matching) and `tools/telem_truth.py` gave 100% valid frames and
  eRPM within 0.4% of the phase frequency, as before the round-trip.
