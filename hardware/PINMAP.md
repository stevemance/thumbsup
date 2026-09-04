# ThumbsUp v1 pin map (rev v1.1)

## AM32 cell — firmware target `AT32DEV_F421`

Locked to AM32 `HARDWARE_GROUP_AT_B` + `HARDWARE_GROUP_AT_045` (verified against
`Inc/targets.h`, `Mcu/f421/Src/{peripherals,ADC,comparator,serial_telemetry}.c` on
2026-09-03).  Package pin numbers from the Artery DS_AT32F421 QFN-32 5×5 table; VSS is
the exposed pad only.

| Function | AT32F421 GPIO | QFN-32 pin | Notes |
|---|---|---|---|
| DShot / PWM input | **PB4** | 27 | TMR3 CH1. Bootloader `F421_PB4`. Pull-down R?01 is **DNP** (AM32 enables the AT32 pull-up; a 10 k pull-down breaks AM32 1-wire serial) |
| Phase A high / low | **PA10 / PB1** | 20 / 15 | → FD6288 HIN1 (22) / LIN1 (1) |
| Phase B high / low | **PA9 / PB0** | 19 / 14 | → HIN2 (23) / LIN2 (2) |
| Phase C high / low | **PA8 / PA7** | 18 / 13 | → HIN3 (24) / LIN3 (3) |
| BEMF A / B / C (CMP INM) | **PA0 / PA4 / PA5** | 6 / 10 / 11 | 10 k / 3.3 k from the phase |
| Virtual neutral (CMP INP) | **PA1** | 7 | star of 3 × 10 k from the BEMF taps |
| Current ADC | **PA3** | 9 | INA180A1 (20 V/V) on the 1 mΩ low-side shunt = 20 mV/A, 1 k / 10 nF; TP `ISENSE` |
| Voltage ADC | **PA6** | 12 | 100 k / 10 k from VBAT (`TARGET_VOLTAGE_DIVIDER 110`); TP `VSENSE` |
| Telemetry TX (USART1, KISS 115200) | **PB6** | 29 | TP `TLM` only |
| SWDIO / SWCLK | **PA13 / PA14** | 23 / 24 | 1×5 header: 3V3, SWDIO, SWCLK, NRST, GND |
| NRST | NRST | 4 | 100 nF; weapon cell also held low by Q49 (gate node) and Q50 (ARM_N) while disabled |
| BOOT0 | BOOT0 | 31 | 10 k to GND |
| VDD / VDD / VDDA | — | 1, 17, 5 | +3V3_MCU |
| VSS | EP | 33 | GND (only ground connection) |

FD6288Q / HX6288 QFN-24: LIN1/2/3 = 1/2/3, VCC = 4, COM = 6, LO3/2/1 = 9/10/11,
VS3/2/1 = 12/15/18, HO3/2/1 = 13/16/19, VB3/2/1 = 14/17/20, HIN1/2/3 = 22/23/24,
NC = 5, 7, 8, 21, **EP (25) = COM**.  VCC = +VDRV (drive cells) or W_VCC (weapon,
switched).  Bootstrap: 2.2 Ω + 1N5819WS + 100 nF from the cell's VCC.

HYG015N04LS1C2 PDFN 5×6 (footprint `PQFN-8-EP_6x5mm_P1.27mm_Generic`): leads 1–3 = S,
4 = G, tab 5 = D.  AP40P05 SOT-23: 1 = G, 2 = S, 3 = D.

Behaviour to remember (AM32 source): after 0.5 s (armed) / 2 s (unarmed) without frames the
ESC soft-resets; a line held **high** across that reset parks the ESC in the bootloader —
that is how am32.ca passthrough is entered on the L/R cells, and why the Pico must keep
streaming DShot or drive the line low when idle.

## Pico W

| Pico | Function |
|---|---|
| GPIO0 / GPIO1 / GPIO4 | DShot DRIVE_L / DRIVE_R / WEAPON through 100 Ω (R24–R26) |
| GPIO2 / GPIO3 | LSM6DS3TR-C INT1 / ADXL375 INT1 |
| GPIO6 / GPIO7 | I2C1 SDA / SCL, 2.2 k pull-ups to +3V3_A (400 kHz max: LSM6/ADXL) |
| GPIO8 | ARM_N — arm link sense, active low, 10 k pull-up to the **Pico's own 3V3** |
| GPIO9 | WEAPON_EN — active high, 100 k pull-down on the board; TP40 |
| GPIO10 / GPIO11 | spare GPIO on the expansion header |
| GPIO12 / GPIO13 | UART0 TX / RX on the expansion header |
| GPIO16 / 17 / 18 / 19 | SPI0 MISO / CS / SCK / MOSI → W25Q128 |
| GPIO22 | SK6812 data (via 74AHCT1G125) |
| GPIO26 / ADC0 | pack voltage, 100 k / 22 k + 100 nF (12.6 V → 2.27 V; divider 5.545) |
| GPIO27 / ADC1 | +3V3_A monitor, 10 k / 10 k (also "is the board powered?") |
| GPIO28 / ADC2 | board NTC (10 k NTC / 3.3 k from +3V3_A; ratiometric — compute against 3V3_MON) |
| ADC3 (internal) | VSYS / 3 — read only with the CYW43 SPI idle (pico-sdk `read_vsys` pattern) |
| RUN | reset button SW1 (100 nF) and expansion header |
| VSYS | +5V through D3 (1N5819WS) |
| 3V3 (out) | ARM_N pull-up only |
| VBUS, 3V3_EN, ADC_VREF | not connected |

Expansion header J3 (2×6): 1 +5V, 2 GND, 3 +3V3_A (≤ 100 mA), 4 GND, 5 SDA, 6 SCL,
7 UART0_TX, 8 UART0_RX, 9 GP10, 10 GP11, 11 RUN, 12 GND.  I2C addresses in use:
0x40 0x41 0x44 0x45 0x53 0x6A.

## Firmware migration (`firmware/include/config.h` and `src/`)

| Define / code | Old (hand-wired robot) | Board v1 |
|---|---|---|
| `PIN_STATUS_LEDS` | 28 | **22** (28 is now the NTC ADC) |
| `BATTERY_DIVIDER` | 4.0 | **5.545** (100 k + 22 k) / 22 k; calibrate against INA226 VBUS |
| `PIN_SAFETY_BUTTON` → `PIN_ARM_N` | 8 | 8, active low, `gpio_disable_pulls(8)` |
| `PIN_WEAPON_EN` | — | 9; init low; raise ≥ 1.5 s before weapon throttle; never restore "armed" from RAM/flash |
| `PIN_LSM_INT1` / `PIN_ADXL_INT1` | — | 2 / 3 |
| I2C1 / SPI0 / UART0 | — | GP6/7, GP16–19, GP12/13 |
| Drive motors | 50 Hz servo PWM on GP0/GP1 | DShot300 bidirectional (`dshot.c`) on GP0/GP1 |
| `am32_config.c` UART1 GP4/GP5, `am32_bootloader.c` `AM32_PIN 4` | — | per-channel pin (0/1/4); PIO budget: bootloader/pio_uart programs on **pio1** |
| Bench guard | — | skip SPI0/I2C1/LED/DShot init while 3V3_MON < 3.0 V (USB-only power) |
| Weapon telemetry | — | invalid while disabled (AT32 in reset) |
| `FAILSAFE_TIMEOUT` | 1500 ms | consider 500–1000 ms |

## I2C addresses (7-bit)

| Device | Address | Straps |
|---|---|---|
| INA226 pack | 0x40 | A1 = GND, A0 = GND |
| INA226 drive L | 0x41 | A1 = GND, A0 = VS |
| INA226 drive R | 0x44 | A1 = VS, A0 = GND |
| INA226 weapon | 0x45 | A1 = VS, A0 = VS |
| LSM6DS3TR-C | 0x6A | SA0 = GND, CS = VDDIO, SDx/SCx = GND |
| ADXL375 | 0x53 | SDO = GND, CS = VDDIO; 800 Hz ODR max on 400 kHz I2C |
