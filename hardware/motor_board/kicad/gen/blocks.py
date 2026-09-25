"""Circuit blocks per sheet (schematic grouping; the PCB floorplan places the same blocks)."""
import re


def rng(prefix, a, b):
    return [f"{prefix}{i}" for i in range(a, b + 1)]


BLOCKS = {
    "power": {
        "Power switch (LM74502 + back-to-back FETs)": ["U13", "Q7", "Q8", "JBAT1", "JBAT2", "D4", "D10", "R1", "R13", "R14", "R32",
                                                       "C12", "C13", "C14", "C18"],
        "Bus: shunt, TVS, bulk, bleeder": ["RS4", "C1", "D1", "R15"],
        "Pack monitor (INA239)": ["U7", "R2", "R3", "C2", "C3", "R12"],
        "Cell monitor (BQ76907)": ["U8", "J4", "D5"] + rng("R", 6, 11) + rng("C", 4, 9) + ["C11"],
        "Weapon nFAULT": ["R42", "C19", "TP9"],
    },
    "weapon": {
        "Gate driver (DRV8323RH)": ["U2", "R44", "R45", "R46", "C20", "C21", "C22", "C23", "C24"],
        "5 V buck (in U2)": ["L1", "D2", "C27", "C28", "C29", "C30", "R20", "R21", "R4", "R5", "C10"],
        "Weapon bridge": ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "RS1", "RS2", "RS3", "NT1", "NT2", "NT3", "C25", "C26", "C31",
                          "JW1", "JW2", "JW3", "TH1", "TP10"],
        "Phase dividers (top)": ["R22", "R24", "R26"],
        "Weapon interlock (AND)": ["U6", "C40", "R47", "R48", "R49"],
        "Dynamic ARM": ["C15", "D9", "C16", "R41", "R18", "U14", "C17", "R19", "TP6"],
    },
    "drive_left": {
        "Drive L (DRV8316C)": ["U3", "C303", "C304", "C305", "C306", "R301", "R300", "C307"],
        "VM filter": ["R302", "C300", "C301", "C302", "C308", "C309", "C310"],
        "Motor wires": ["JL1", "JL2", "JL3"],
    },
    "drive_right": {
        "Drive R (DRV8316C)": ["U4", "C403", "C404", "C405", "C406", "R401", "R400", "C407"],
        "VM filter": ["R402", "C400", "C401", "C402", "C408", "C409", "C410"],
        "Motor wires": ["JR1", "JR2", "JR3"],
        "DRV_OFF pull-up (shared)": ["R50", "TP8"],
    },
    "mcu": {
        "MCU (STM32G474)": ["U1", "C60", "C61", "C62", "C63", "C64", "C65", "C66", "C71", "R60", "C74", "C67", "R61"],
        "3.3 V LDO": ["U5", "C69", "C70"],
        "Header to compute board": ["J1", "R16", "R17", "R33", "R40"],
        "Test pads": ["TP1", "TP2", "TP3", "TP4", "TP5", "TP7", "TP11", "TP12"],
        "Weapon analog (phase, NTC, pack)": ["R23", "R25", "R27", "C41", "C42", "C43", "R43", "C44", "R63", "R64", "C68"],
        "Drive CSA filters": ["R70", "R71", "R72", "C80", "C81", "C82", "R80", "R81", "R82", "C90", "C91", "C92"],
        "Power LED, mounting holes": ["D3", "R62", "MH1", "MH2", "MH3", "MH4"],
    },
    "sensors": {
        "Sensor L (J2)": ["J2", "JP1", "U11", "C45", "C46", "U9", "C47", "R54", "R55", "R56", "R110", "R111", "R112",
                          "C110", "C111", "C112", "R52", "R113", "D7", "C72"],
        "Sensor R (J3)": ["J3", "JP2", "U12", "C48", "C49", "U10", "C50", "R57", "R58", "R59", "R114", "R115", "R116",
                          "C114", "C115", "C116", "R53", "R117", "D8", "C73"],
    },
}


def sheet_of():
    return {r: s for s, bl in BLOCKS.items() for refs in bl.values() for r in refs}


def order_key(ref):
    kind = {"U": 0, "Q": 1, "J": 2, "D": 3, "L": 4, "R": 6, "C": 7, "T": 8, "N": 9, "M": 10}.get(ref[0], 5)
    return (kind, re.sub(r"\d", "", ref), int(re.sub(r"\D", "", ref) or 0))
