# References used for the motor board

| Document | Used for |
|---|---|
| TI DRV8316 datasheet SLVSF16B (Apr 2022) | Table 6-1 pinout (DRV8316R), 7.1 abs max (VM 40 V, 4 V/µs), 7.3 ROC, 8.3.2.2 3x PWM, 8.3.4 buck (unused: 22 Ω + 22 µF, BUCK_DIS), CSA gain |
| TI DRV8323 datasheet SLVSDJ3D (Mar 2022) | Table 6-4 pinout (48-pin DRV8323RS), 7.1/7.3 limits (SHx, SPx, VREF 3–5.5 V), 8.3.1.1.2 3x PWM, charge pump capacity, buck = LMR16006X |
| TI LMR16006 datasheet SNVSA24 | buck inductor/capacitor/diode sizing, VFB 0.765 V |
| `STM32G474RxTx_pins.xml` | ST STM32_open_pin_data (BSD-3, `STM32_open_pin_data_LICENSE`): every pin/alternate function in `design/mcu_pinmap.md` is checked against it by `design/motor_board.py` |
| HUAYI HYG015N04LS1C2 datasheet (`hardware/datasheets/pdf/`) | weapon FET RDS(on), capacitances, gate charge for `spice/sim_weapon_bridge.py` |

Datasheets were read on 2026-09-23 from ti.com; ST's own site blocks scripted downloads, so the
MCU pin data comes from ST's GitHub pin database instead of the PDF.
