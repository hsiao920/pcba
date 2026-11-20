# -*- coding: utf-8 -*-
"""USB 2-in-1-out switch board: single source of truth (parts, pins, nets, footprints).

Derived from  D:\\Users\\jacky\\jieli\\藍牙測試 dut\\USB_2to1_Switch_TypeC_原理图文字版.md
with the corrections listed in REVIEW.md (CH552G pin numbers, active-high RST, TS3 OE polarity,
GPIO reset state, LED_CMD supply, ...).

Part = dict(ref, value, fp=(lib, name), sym=(left, right), pins={pad: net|None}, note)
  sym  : two lists of (pin number, pin name); pin numbers equal the footprint pad numbers.
  pins : pad number -> net name (None = intentionally unconnected, drawn with a no-connect flag).
"""

FP_LIBS = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"

R_FP = ("Resistor_SMD", "R_0603_1608Metric")
C_FP = ("Capacitor_SMD", "C_0603_1608Metric")
C8_FP = ("Capacitor_SMD", "C_0805_2012Metric")
LED_FP = ("LED_SMD", "LED_0603_1608Metric")
SOT23 = ("Package_TO_SOT_SMD", "SOT-23")
SOT236 = ("Package_TO_SOT_SMD", "SOT-23-6")


TP_NETS = ["GND", "+5V", "+3V3", "V33", "RST", "CMD", "ON1", "ON2", "S", "GND", "OUT_VBUS", "VSW", "GND", "VBUS1", "VBUS2"]


def two(a, b, na="1", nb="2"):
    return ([(na, na)], [(nb, nb)])


def rc(ref, value, a, b, fp=R_FP, note=""):
    return dict(ref=ref, value=value, fp=fp, sym=([("1", "1")], [("2", "2")]), pins={"1": a, "2": b}, note=note)


def build():
    P = []
    # ------------------------------------------------------------------ ICs
    P.append(dict(
        ref="U1", value="CH552G", fp=("Package_SO", "SOIC-16_3.9x9.9mm_P1.27mm"),
        sym=([("1", "P3.2/INT0"), ("2", "P1.4/SCS"), ("3", "P1.5/MOSI"), ("4", "P1.6/MISO"), ("5", "P1.7/SCK"),
              ("6", "RST"), ("7", "P3.0/RXD"), ("8", "P3.1/TXD")],
             [("16", "V33"), ("15", "VCC"), ("14", "GND"), ("13", "P3.7/UDM"), ("12", "P3.6/UDP"),
              ("11", "P3.4"), ("10", "P3.3/INT1"), ("9", "P1.1")]),
        pins={"1": None, "2": "CMD", "3": "S_DRV", "4": "ON2", "5": None, "6": "RST", "7": None, "8": None,
              "9": "ON1", "10": None, "11": None, "12": "D4P", "13": "D4N", "14": "GND", "15": "+5V", "16": "V33"},
        note="CH552G SOP16 pinout per WCH CH552 datasheet (md pin table was wrong)"))
    P.append(dict(
        ref="U2", value="TS3USB221A", fp=("Package_DFN_QFN", "Texas_UQFN-10_1.5x2mm_P0.5mm"),
        sym=([("1", "1D+"), ("2", "1D-"), ("3", "2D+"), ("4", "2D-"), ("5", "GND")],
             [("10", "VCC"), ("9", "S"), ("8", "D+"), ("7", "D-"), ("6", "OE")]),
        pins={"1": "D1P", "2": "D1N", "3": "D2P", "4": "D2N", "5": "GND", "6": "GND", "7": "D3N", "8": "D3P",
              "9": "S", "10": "+3V3"},
        note="OE is active-LOW: tied to GND (md said 3.3V which disables the switch)"))
    for ref, vin, on, note in (("U3", "VBUS1", "ON1", "CH1 load switch"), ("U4", "VBUS2", "ON2", "CH2 load switch")):
        P.append(dict(
            ref=ref, value="TPS22916BYFP", fp=("USB2to1", "TPS22916_YFP_DSBGA-4_0.4mm"),
            sym=([("A2", "VIN"), ("B2", "ON")], [("A1", "VOUT"), ("B1", "GND")]),
            pins={"A2": vin, "B2": on, "A1": "VSW", "B1": "GND"}, note=note + " (0.4mm pitch WCSP)"))
    P.append(dict(
        ref="U5", value="AMS1117-3.3", fp=("Package_TO_SOT_SMD", "SOT-223-3_TabPin2"),
        sym=([("3", "VIN"), ("1", "GND")], [("2", "VOUT")]),
        pins={"1": "GND", "2": "+3V3", "3": "+5V"}, note="restored to the original spec; AMS1117 wants a tantalum/ESR output cap, ceramic-only may oscillate"))

    # ------------------------------------------------------------------ connectors
    def typec(ref, vb, dp, dn, cc1, cc2, note):
        left = [("A4", "VBUS"), ("B9", "VBUS"), ("A9", "VBUS"), ("B4", "VBUS"), ("A6", "D+"), ("B6", "D+"),
                ("A7", "D-"), ("B7", "D-"), ("A5", "CC1"), ("B5", "CC2"), ("A8", "SBU1"), ("B8", "SBU2")]
        right = [("A1", "GND"), ("B12", "GND"), ("A12", "GND"), ("B1", "GND"), ("SH", "SHIELD")]
        pins = {"A4": vb, "B9": vb, "A9": vb, "B4": vb, "A6": dp, "B6": dp, "A7": dn, "B7": dn,
                "A5": cc1, "B5": cc2, "A8": None, "B8": None,
                "A1": "GND", "B12": "GND", "A12": "GND", "B1": "GND", "SH": "GND"}
        return dict(ref=ref, value="Type-C receptacle (UFP)", fp=("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12"),
                    sym=(left, right), pins=pins, note=note)
    P.append(typec("J1", "VBUS1", "D1P", "D1N", "J1_CC1", "J1_CC2", "IN1 / CMW"))
    P.append(typec("J2", "VBUS2", "D2P", "D2N", "J2_CC1", "J2_CC2", "IN2 / PC"))
    P.append(dict(ref="J3", value="USB-A receptacle", fp=("Connector_USB", "USB_A_Molex_67643_Horizontal"),
                  sym=([("1", "VBUS"), ("2", "D-"), ("3", "D+"), ("4", "GND")], [("SH", "SHIELD")]),
                  pins={"1": "OUT_VBUS", "2": "D3N", "3": "D3P", "4": "GND", "SH": "GND"}, note="OUT / DUT"))
    P.append(dict(ref="J4", value="Mini-USB-B receptacle", fp=("Connector_USB", "USB_Mini-B_Lumberg_2486_01_Horizontal"),
                  sym=([("1", "VBUS"), ("2", "D-"), ("3", "D+"), ("4", "ID"), ("5", "GND")], [("SH", "SHIELD")]),
                  pins={"1": "+5V", "2": "D4N", "3": "D4P", "4": None, "5": "GND", "SH": "GND"}, note="CTRL / CDC"))
    P.append(dict(ref="J5", value="ISP 1x6", fp=("Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical"),
                  sym=([("1", "5V"), ("2", "GND"), ("3", "D+"), ("4", "D-"), ("5", "RST"), ("6", "BOOT")], []),
                  pins={"1": "+5V", "2": "GND", "3": "D4P", "4": "D4N", "5": "RST_J5", "6": "BOOT"}, note=""))

    # ------------------------------------------------------------------ ESD / TVS
    for ref, dp, dn, vb in (("ESD1", "D1P", "D1N", "VBUS1"), ("ESD2", "D2P", "D2N", "VBUS2"),
                            ("ESD3", "D3P", "D3N", "OUT_VBUS"), ("ESD4", "D4P", "D4N", "+5V")):
        P.append(dict(ref=ref, value="USBLC6-2SC6", fp=SOT236,
                      sym=([("1", "I/O1"), ("2", "GND"), ("3", "I/O2")], [("6", "I/O1"), ("5", "VBUS"), ("4", "I/O2")]),
                      pins={"1": dp, "6": dp, "3": dn, "4": dn, "2": "GND", "5": vb}, note=""))
    for ref, vb in (("TVS1", "VBUS1"), ("TVS2", "VBUS2"), ("TVS3", "OUT_VBUS"), ("TVS4", "+5V")):
        P.append(dict(ref=ref, value="SMAJ5.0A", fp=("Diode_SMD", "D_SMA"),
                      sym=([("1", "K")], [("2", "A")]), pins={"1": vb, "2": "GND"}, note=""))

    # ------------------------------------------------------------------ Type-C Rd
    P += [rc("R1", "5.1k", "J1_CC1", "GND"), rc("R2", "5.1k", "J1_CC2", "GND"),
          rc("R3", "5.1k", "J2_CC1", "GND"), rc("R4", "5.1k", "J2_CC2", "GND")]
    # ------------------------------------------------------------------ GPIO conditioning
    P += [rc("R5", "1.5k", "ON1", "GND", note="strong pull-down: CH552 GPIO reset state is a weak pull-up (~70k)"),
          rc("R6", "1.5k", "ON2", "GND", note="strong pull-down: CH552 GPIO reset state is a weak pull-up (~70k)"),
          rc("R7", "5.1k", "S_DRV", "S", note="S input divider: CH552 swings 5V, TS3 S max recommended = VCC"),
          rc("R8", "10k", "S", "GND"),
          rc("R9", "10k", "CMD", "GND")]
    # ------------------------------------------------------------------ reset / boot (CH552 RST is active HIGH)
    P += [rc("R14", "1k", "RSTSW", "RST"), rc("R15", "10k", "RST", "GND"), rc("R16", "100", "RST", "RST_J5"),
          rc("R17", "10k", "BOOT", "D4P", note="BOOT: UDP pulled to V33 at power-up (verify with WCH reference design)")]
    for ref, a, b, note in (("SW_RST", "+5V", "RSTSW", "RST"), ("SW_BOOT", "V33", "BOOT", "BOOT")):
        P.append(dict(ref=ref, value=note, fp=("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A"),
                      sym=([("1", "1")], [("2", "2")]), pins={"1": a, "2": b}, note=""))
    # ------------------------------------------------------------------ LEDs
    P += [rc("R10", "1k", "OUT_VBUS", "LED1_A"), rc("R11", "1k", "OUT_VBUS", "LED2_A"),
          rc("R12", "1k", "+5V", "LEDP_A"), rc("R13", "1k", "+5V", "LEDC_A", note="from +5V: blue LED Vf ~3V cannot run from 3.3V")]
    for ref, val, a, k, note in (("LED1", "green", "LED1_A", "LED1_K", "IN1 / CMW"), ("LED2", "yellow", "LED2_A", "LED2_K", "IN2 / PC"),
                                 ("LED_PWR", "red", "LEDP_A", "GND", "PWR"), ("LED_CMD", "blue", "LEDC_A", "LEDC_K", "CMD")):
        P.append(dict(ref=ref, value=val, fp=LED_FP, sym=([("2", "A")], [("1", "K")]), pins={"2": a, "1": k}, note=note))
    for ref, g, d in (("Q1", "ON1", "LED1_K"), ("Q2", "ON2", "LED2_K"), ("Q3", "CMD", "LEDC_K")):
        P.append(dict(ref=ref, value="2N7002", fp=SOT23, sym=([("1", "G")], [("3", "D"), ("2", "S")]),
                      pins={"1": g, "3": d, "2": "GND"}, note=""))
    # ------------------------------------------------------------------ capacitors
    caps = [("C1", "0.1u", "+5V", "GND", C_FP), ("C2", "0.1u", "V33", "GND", C_FP), ("C3", "0.1u", "RST", "GND", C_FP),
            ("C4", "10u", "+5V", "GND", C8_FP), ("C6", "10u", "+5V", "GND", C8_FP), ("C5", "22u", "+3V3", "GND", C8_FP),
            ("C7", "0.1u", "+3V3", "GND", C_FP),
            ("C9", "10u", "VBUS1", "GND", C8_FP), ("C10", "0.1u", "VBUS1", "GND", C_FP),
            ("C11", "10u", "VSW", "GND", C8_FP), ("C12", "0.1u", "VSW", "GND", C_FP),
            ("C13", "10u", "VBUS2", "GND", C8_FP), ("C14", "0.1u", "VBUS2", "GND", C_FP),
            ("C15", "10u", "VSW", "GND", C8_FP), ("C16", "0.1u", "VSW", "GND", C_FP),
            ("C17", "10u", "OUT_VBUS", "GND", C8_FP), ("C18", "0.1u", "OUT_VBUS", "GND", C_FP)]
    for ref, v, a, b, fp in caps:
        P.append(rc(ref, v, a, b, fp=fp))
    # ------------------------------------------------------------------ output current limit (resettable fuse)
    P.append(dict(ref="F1", value="PTC 2.5A hold / 5A trip (MF-MSMF250)", fp=("Fuse", "Fuse_1812_4532Metric"),
                  sym=([("1", "1")], [("2", "2")]), pins={"1": "VSW", "2": "OUT_VBUS"},
                  note="J3 output short-circuit protection; VSW = load-switch side, OUT_VBUS = connector side"))
    # ------------------------------------------------------------------ test points
    for i, net in enumerate(TP_NETS, 1):
        P.append(dict(ref="TP%d" % i, value="TP_" + net, fp=("TestPoint", "TestPoint_Pad_D1.5mm"),
                      sym=([("1", "1")], []), pins={"1": net}, note=""))
    # ------------------------------------------------------------------ mounting holes
    for i in range(1, 5):
        P.append(dict(ref="H%d" % i, value="M3", fp=("MountingHole", "MountingHole_3.2mm_M3"),
                      sym=([("1", "1")], []), pins={"1": "GND"}, note=""))
    return P


# net classes: name -> (track width mm, clearance mm)
NET_CLASS = {
    "VBUS1": (1.0, 0.2), "VBUS2": (1.0, 0.2), "OUT_VBUS": (1.2, 0.2), "VSW": (1.2, 0.2),
    "+5V": (0.6, 0.2), "+3V3": (0.4, 0.2),
}
DEFAULT_CLASS = (0.25, 0.15)

BOARD_W, BOARD_H = 70.0, 55.0

# placement: ref -> (x, y, rotation_deg)  (board coordinates, mm, y downwards, rotation CCW as shown in KiCad)
PLACE = {}
