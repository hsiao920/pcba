# -*- coding: utf-8 -*-
"""Hand-transcribed pin/net data of the JL701N watch dev board PDF (pages 2 and 3).

Source: JL701N手表开发板原理图与PCB资料（共5页）.pdf
  page 2 = minimum system ("开发底板网络参考（非完整原理图）")  -> project 01_MinSystem
  page 3 = base board ("开发底板原理图")                       -> project 02_BaseBoard

Each part: (ref, value, kind, spec, note)
  kind 2-pin/3-pin small parts: R C D LED L XTAL BAT SW MIC ANT SJ NPN PMOS
        spec = {pin_name: net or None}
  kind "IC": spec = {"left": [(pinnum, pinname, net)], "right": [...]}
  kind "IC68": spec = {"names": {...}, "nets": {...}}
A net of None means the pin is drawn open / no-connect in the source.
"""


def pair(a, b):
    return {"1": a, "2": b}


# ------------------------------------------------------------------ page 2 : minimum system
U1_NAMES = {
    1: "PB9/SPI4CLKB/I2C1SCLB/ADC9", 2: "PGND", 3: "SW", 4: "VBAT", 5: "VPWR", 6: "IOVDD", 7: "IOVDD2", 8: "DCVDD",
    9: "PB8", 10: "PB7/ROSCI", 11: "PB6/ROSCO", 12: "PB5/I2C1SDAA/ADC8", 13: "PB4/SPI4DIA/I2C1SCLA",
    14: "PB3/SPI4DOA", 15: "PB2/SPI4CLKA/ADC7", 16: "PB1/ADC6/Long press reset", 17: "PB0",
    18: "BTRF", 19: "XOSCI", 20: "XOSCO", 21: "PC7", 22: "PC6", 23: "PC5/SFC1_D2/ADC5", 24: "PC4/SFC1_D1/ADC4",
    25: "PC3/SFC1_CS", 26: "PC2/SFC1_D0", 27: "PC1/SFC1_CLK", 28: "PC0/SFC1_D3", 29: "PC8",
    30: "USBDM/ADC11", 31: "USBDP/ADC10", 32: "PA15/LCD_D0", 33: "PA14/LCD_D1", 34: "PA13/LCD_D2",
    35: "LCD_D3/PA12", 36: "LCD_SPID3A(D4)/PA11", 37: "LCD_SPID2A(D5)/PA10", 38: "LCD_SPID1A(D6)/PA9",
    39: "ADC3/LCD_SPID0A(D7)/PA8", 40: "DVDD", 41: "LCD_SPICLKA(RGB_CLK)/PA7",
    42: "ADC2/WR/RD/RGB_SYNC2/SPI2DOA/PA6", 43: "ADC1/WR/RD/RGB_SYNC1/SPI2CLKA/PA5",
    44: "WR/RD/RGB_SYNC0/SPI2DIA/AIN_B1/PA4", 45: "SPIDOA/AIN_B0/PA3", 46: "SPI1CLKA/AIN_A1/PA2",
    47: "SPI1DIA/AIN_A0/PA1", 48: "ADC0/MICLDO/PA0", 49: "AVSS", 50: "ACM", 51: "VCM",
    52: "HPVSS", 53: "DACRN", 54: "DACRP", 55: "DACLN", 56: "DACLP", 57: "SDPG/PE6", 58: "AIN_C0/PG8",
    59: "ADC15/LCD_SPID3B/AIN_C1/PG7", 60: "LCD_SPID2B/AIN_D0/PG6", 61: "ADC14/LCD_SPID1B/AIN_D1/PG5",
    62: "LCD_SPID0B/PG4", 63: "LCD_SPICLKB/PG3", 64: "SD0CLKB/PG2", 65: "ADC13/SD0CMDB/PG1",
    66: "ADC12/SD0DATB/PG0", 67: "SPI4DIB/PB11", 68: "I2C1SDAB/SPI4DOB/PB10", 0: "VSS(PAD)"}

U1_NETS = {
    1: "KEY4/UartTX", 2: "GND", 3: "SW", 4: "VBAT", 5: "VPWR", 6: "VDDIO33", 7: "VDDIO18", 8: "DCVDD",
    9: "Sensor_int1", 10: "32KI", 11: "32KO", 12: "IIC_SDA", 13: "IIC_SCL", 14: "G_INT", 15: "Sensor_int0",
    16: "KEY0", 17: "KEY1", 18: "BTRF", 19: "BT_OSCI", 20: "BT_OSCO", 21: "KEY2", 22: "KEY3",
    23: "SFC_D2", 24: "SFC_D1", 25: "SFC_CS", 26: "SFC_D0", 27: "SFC_CLK", 28: "SFC_D3", 29: "V_SFC",
    30: "USBDM", 31: "USBDP", 32: "D0", 33: "D1", 34: "D2", 35: "D3", 36: "SD3(D4)", 37: "SD2(D5)",
    38: "SD1(D6)", 39: "SD0(D7)", 40: "DVDD", 41: "LCD_CLK", 42: "LCD_CS", 43: "WR/SYNC1", 44: "RD/SYNC0",
    45: "LCD_TE", 46: "LCD_RST", 47: "MIC", 48: "MICLDO", 49: "AVSS", 50: "ACM", 51: "VCM", 52: "GND",
    53: "DACRN", 54: "DACRP", 55: "DACLN", 56: "DACLP", 57: "SD_PG", 58: "SD_EN", 59: "MUTE",
    60: "CTP_RST", 61: "CTP_INT", 62: "CTP_SDA", 63: "CTP_SCL", 64: "SD_CLK", 65: "SD_CMD", 66: "SD_DAT",
    67: "Motor_PWM", 68: "Backlight_PWM", 0: "GND"}


def page2():
    P = []
    P.append(("U1", "JL701N(QFN68)", "IC68", {"names": U1_NAMES, "nets": U1_NETS}, ""))
    P += [
        ("R1", "0.5R(0603)", "R", pair("+5.0V", "VPWR"), ""),
        ("D1", "TVS(uni)", "D", {"A": "GND", "K": "+5.0V"}, "单向TVS保护"),
        ("D3", "ESD", "D", {"A": "GND", "K": "USBDM"}, ""),
        ("D4", "ESD", "D", {"A": "GND", "K": "USBDP"}, ""),
        ("BT1", "3.3V~4.2V", "BAT", {"+": "VBAT", "-": "GND"}, ""),
        ("C25", "106", "C", pair("VBAT", "GND"), ""),
        ("C2", "105", "C", pair("VBAT", "GND"), ""),
        ("C3", "105", "C", pair("VPWR", "GND"), ""),
        ("C10", "106", "C", pair("VDDIO33", "GND"), ""),
        ("C4", "105", "C", pair("VDDIO18", "GND"), ""),
        ("C5", "105", "C", pair("DCVDD", "GND"), ""),
        ("C1", "105", "C", pair("DCVDD", "GND"), ""),
        ("C9", "106", "C", pair("DCVDD", "GND"), ""),
        ("L1", "10uH", "L", pair("SW", "DCVDD"), ""),
        ("C8", "105", "C", pair("DVDD", "GND"), ""),
        ("C6", "105", "C", pair("VCM", "AVSS"), ""),
        ("C7", "105", "C", pair("ACM", "AVSS"), ""),
        ("BT_ANT1", "ANT", "ANT", {"1": "BT_ANT", "2": "GND"}, ""),
        ("L2", "10P", "L", pair("BT_ANT", "BTRF"), ""),
        ("C13", "NC", "C", pair("BT_ANT", "GND"), ""),
        ("C14", "NC", "C", pair("BTRF", "GND"), ""),
        ("Y1", "24M", "XTAL", pair("BT_OSCO", "BT_OSCI"), "freq +-10ppm, load 12pF"),
        ("C11", "NC", "C", pair("BT_OSCO", "GND"), ""),
        ("C12", "NC", "C", pair("BT_OSCI", "GND"), ""),
        ("Y2", "32.768K", "XTAL", pair("32KO", "32KI"), "+-20ppm, ESR<=70k"),
        ("C15", "15P", "C", pair("32KO", "GND"), ""),
        ("C16", "15P", "C", pair("32KI", "GND"), ""),
        ("U2", "25Q128", "IC",
         {"left": [("1", "CS", "SFC_CS"), ("2", "SO/IO1", "SFC_D1"), ("3", "WP/IO2", "SFC_D2"), ("4", "GND", "GND")],
          "right": [("8", "VCC", "V_SFC"), ("7", "IO3/HOLD", "SFC_D3"), ("6", "SCK", "SFC_CLK"), ("5", "IO0/SI", "SFC_D0")]},
         "外置UI flash"),
        ("R2", "NC/10K", "R", pair("SFC_CS", "V_SFC"), ""),
        ("C17", "104", "C", pair("V_SFC", "GND"), ""),
        ("U3", "GSensor", "IC",
         {"left": [("1", "SD0", None), ("2", "SDA/SDI/SDO", "IIC_SDA"), ("3", "VDD_IO", "VDDIO33"), ("4", "NC", "GND"),
                   ("5", "INT", "G_INT"), ("6", "INT2", "INT2_N")],
          "right": [("12", "SCL", "IIC_SCL"), ("11", "NC", "VDDIO33"), ("10", "CSB", None), ("9", "GND", "GND"),
                    ("8", "GND_IO", "GND"), ("7", "VDD", "VDDIO33")]},
         "pin4 NC drawn tied to GND, pin10 CSB open, pin11 NC tied VDDIO33 (as drawn)"),
        ("R7", "NC", "R", pair("INT2_N", "GND"), ""),
        ("C18", "104", "C", pair("VDDIO33", "GND"), ""),
        ("C19", "104", "C", pair("VDDIO33", "GND"), ""),
        ("J1", "CTP-1.54INCH", "IC",
         {"left": [("1", "VDD2.8", "VDDIO33"), ("2", "SCL", "CTP_SCL"), ("3", "SDA", "CTP_SDA"), ("4", "EINT", "CTP_INT"),
                   ("5", "RESET", "CTP_RST"), ("6", "GND", "GND"), ("7", "GND", "GND"), ("8", "NC", None),
                   ("9", "GND", "GND"), ("10", "GND", "GND")], "right": []}, "触摸屏"),
        ("C23", "105", "C", pair("VDDIO33", "GND"), ""),
        ("J2", "QSPI_AMOLED", "IC",
         {"left": [("1", "LEDK", "LEDK"), ("2", "GND", "GND"), ("3", "FMARK", "LCD_TE"), ("4", "SD0", "SD0(D7)"),
                   ("5", "SD1", "SD1(D6)"), ("6", "SD2", "SD2(D5)"), ("7", "SD3", "SD3(D4)"), ("8", "SCL", "LCD_CLK"),
                   ("9", "CS", "LCD_CS"), ("10", "RESET", "LCD_RST"), ("11", "VBAT", "VBAT"), ("12", "IOVCC", "VDDIO33"),
                   ("13", "VCC2.8", "VDDIO33"), ("14", "GND", "GND"), ("15", "GND", "GND"), ("16", "LEDA", "VDDIO33"),
                   ("17", "LEDA", "VDDIO33"), ("0", "shell", "GND")], "right": []},
         "原图脚号: SD1/SD2/SD3均印5, 此处顺延编号; SD0..SD3假设等于SD0(D7)..SD3(D4)"),
        ("C24", "105", "C", pair("VDDIO33", "GND"), ""),
        ("Q2", "9014", "NPN", {"B": "Q2B", "C": "Q2C", "E": "GND"}, ""),
        ("R10", "510R", "R", pair("Backlight_PWM", "Q2B"), ""),
        ("R6", "10K", "R", pair("Q2B", "GND"), ""),
        ("R3", "22R", "R", pair("Q2C", "LEDK"), ""),
        ("Q1", "9014", "NPN", {"B": "Q1B", "C": "MOT-", "E": "GND"}, ""),
        ("R4", "1K", "R", pair("Motor_PWM", "Q1B"), ""),
        ("R5", "10K", "R", pair("Q1B", "GND"), ""),
        ("D2", "5819", "D", {"A": "MOT-", "K": "VBAT"}, ""),
        ("C27", "NC", "C", pair("VBAT", "MOT-"), ""),
        ("C26", "105", "C", pair("VBAT", "GND"), ""),
        ("J3", "MOT", "IC", {"left": [("1", "1", "VBAT"), ("2", "2", "MOT-")], "right": []}, "震动马达"),
        ("S1", "KEY", "SW", pair("KEY0", "GND"), ""),
        ("S2", "KEY", "SW", pair("KEY1", "GND"), ""),
        ("S3", "KEY", "SW", pair("KEY2", "GND"), ""),
        ("S4", "KEY", "SW", pair("KEY3", "GND"), ""),
        ("M1", "MIC", "MIC", {"+": "MICN", "-": "GND"}, "麦地单独走线到AVSS"),
        ("R8", "2.2K", "R", pair("MICLDO", "MICN"), ""),
        ("C28", "NC", "C", pair("MICN", "GND"), ""),
        ("C20", "104", "C", pair("MICN", "MIC"), ""),
        ("Q3", "2301", "PMOS", {"G": "SD_EN", "D": "SDQ_D", "S": "VDDIO33"}, "SDnand供电mos"),
        ("R9", "100K", "R", pair("VDDIO33", "SD_EN"), ""),
        ("R14", "2.2R", "R", pair("SDQ_D", "SDQ_R"), ""),
        ("SJ1", "solder jct", "SJ", pair("SD_PG", "SD_VDD"), "原图无编号"),
        ("SJ2", "solder jct", "SJ", pair("SDQ_R", "SD_VDD"), "原图无编号"),
        ("C29", "105", "C", pair("SD_VDD", "GND"), ""),
        ("R16", "NC", "R", pair("SD_CD", "SD_VDD"), ""),
        ("TF1", "SD-TF", "IC",
         {"left": [("10", "CD", "SD_CD"), ("9", "WP", None), ("1", "D2", None), ("2", "D3/CS", None),
                   ("3", "CMD", "SD_CMD"), ("4", "VDD", "SD_VDD"), ("5", "CLK", "SD_CLK"), ("6", "VSS", "GND"),
                   ("7", "D0", "SD_DAT"), ("8", "D1", None), ("11", "Sheet", "GND")], "right": []}, ""),
        ("U4", "NS4150", "IC",
         {"left": [("1", "MUTE", "MUTE"), ("2", "Bypass", "BYPASS"), ("3", "IN+", "PA_INP"), ("4", "IN-", "PA_INN")],
          "right": [("8", "OUT+", "SPK+"), ("7", "GND", "GND"), ("6", "VDD", "VBAT"), ("5", "OUT-", "SPK-")]},
         "外置功放"),
        ("R13", "100K", "R", pair("MUTE", "GND"), ""),
        ("C30", "105", "C", pair("BYPASS", "GND"), ""),
        ("R11", "33K", "R", pair("DACLP", "R11C"), ""),
        ("C21", "104", "C", pair("R11C", "PA_INP"), ""),
        ("R12", "33K", "R", pair("DACLN", "R12C"), ""),
        ("C22", "104", "C", pair("R12C", "PA_INN"), ""),
        ("C31", "106", "C", pair("VBAT", "GND"), ""),
        ("J4", "SPK", "IC", {"left": [("1", "1", "SPK+"), ("2", "2", "SPK-")], "right": []}, ""),
    ]
    return P


# ------------------------------------------------------------------ page 3 : base board
def hdr(n, mapping, double=False):
    """Header symbol. Single row: all pins on the left. Double row: odd pins right, even pins left."""
    left, right = [], []
    for k in range(1, n + 1):
        item = (str(k), str(k), mapping.get(k))
        if double and k % 2 == 1:
            right.append(item)
        else:
            left.append(item)
    return {"left": left, "right": right}


def seq(names, start=1):
    return {i + start: n for i, n in enumerate(names)}


def page3():
    P = []
    j1 = seq(["GND"] * 4 + ["MCU_BAT"] * 2 + ["VPWR"] * 2 + ["VDDIO33"] * 2 + ["VDDIO18"] * 2 +
             ["PB11", "PB10", "PB9", "PB8", "PB7", "PB6", "PB5", "PB4", "PB3", "PB2", "PB1", "PB0"])
    j2 = seq(["PA2", "GND", "GND", "GND", "PA3", "PA4", "PA5", "PA6", "PA7", "PA8", "PA9", "PA10", "PA11", "PA12",
              "PA13", "PA14", "PA15", "USBDP", "USBDM", "PC8", "PC0", "PC5", "PC6", "PC7", "PC1", "PC2", "PC3", "PC4"])
    j3 = seq(["PG0", "PG1", "PG2", "PG3", "PG4", "PG5", "PG6", "PG7", "PG8", "PE6", "DACLP", "DACLN", "DACRP",
              "DACRN", "HPVSS", "HPVSS", "AVSS", "AVSS", "PA1", "PA0"])
    j10 = seq(["GND", "GND", "MCU_BAT", "VPWR", "VDDIO33", "VDDIO18", "PB11", "PB10", "PB9", "PB8", "PB7", "PB6",
               "PB5", "PB4", "PB3", "PB2", "PB1", "PB0"])
    j11 = seq(["PG0", "PG1", "PG2", "PG3", "PG4", "PG5", "PG6", "PG7", "PG8", "PE6", "DACLP", "DACLN", "DACRP",
               "DACRN", "HPVSS", "AVSS", "PA1", "PA0"])
    j12 = seq(["PA2", "PA3", "PA4", "PA5", "PA6", "PA7", "PA8", "PA9", "PA10", "PA11", "PA12", "PA13", "PA14", "PA15",
               "GND", "USBDP", "USBDM", "PC8", "PC0", "PC5", "PC6", "PC7", "PC1", "PC2", "PC3", "PC4"])
    left4 = ["LCD_BAT", "LCD_VCC", "Backlight_PWM", "LCD_RST", "LCD_TE", "RD/SYNC0", "WR/SYNC1", "LCD_CS", "LCD_CLK",
             "SD0(D7)", "SD1(D6)", "SD2(D5)", "SD3(D4)", "D3", "D2", "D1", "D0", "CTP_RST", "CTP_INT", "CTP_SDA",
             "CTP_SCL"]
    right4 = ["PVCC", "VDDIO33", "PB10", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7", "PA8", "PA9", "PA10", "PA11",
              "PA12", "PA13", "PA14", "PA15", "PG6", "PG5", "PG4", "PG3"]
    j4 = {}
    for i in range(21):
        j4[2 * (i + 1)] = left4[i]
        j4[2 * i + 1] = right4[i]
    j5 = {2: "VDDIO33", 4: "VDDIO18", 6: "PB5", 8: "PB4", 10: "PB3", 12: "PB2", 14: "PB8", 16: "GND",
          1: "VCC1", 3: "VCC2", 5: "IIC_SDA", 7: "IIC_SCL", 9: "G_INT", 11: "Sensor_int0", 13: "Sensor_int1", 15: "GND"}
    j6 = seq(["LCD_BAT", "LCD_VCC", "GND", "GND", "Backlight_PWM", "LCD_RST", "LCD_TE", "RD/SYNC0", "WR/SYNC1",
              "LCD_CS", "LCD_CLK", "SD0(D7)", "SD1(D6)", "SD2(D5)", "SD3(D4)", "D3", "D2", "D1", "D0", "GND",
              "CTP_RST", "CTP_INT", "CTP_SDA", "CTP_SCL"])
    j13 = {1: "PG8", 3: "PE6", 5: "PG0", 7: "PG1", 9: "PG2", 11: "GND",
           2: "SD_EN", 4: "SD_PG", 6: "SD_DAT", 8: "SD_CMD", 10: "SD_CLK", 12: "GND"}
    j14 = {1: "PB1", 3: "PB0", 5: "PC7", 7: "PC6", 9: "PB11",
           2: "KEY0", 4: "KEY1", 6: "KEY2", 8: "KEY3", 10: "Motor_PWM"}
    j15 = {1: "PG7", 3: "DACLP", 5: "DACRP", 7: "DACLN", 9: "DACRN",
           2: "MUTE", 4: "PA_IN+", 6: "PA_IN+", 8: "PA_IN-", 10: "PA_IN-"}
    j19 = seq(["VCC1", "VCC2", "IIC_SDA", "IIC_SCL", "G_INT", "GND", "Sensor_int0", "Sensor_int1", "GND", "GND"])
    allgnd4 = {i: "GND" for i in range(1, 5)}
    P += [
        ("J1", "CON24", "IC", hdr(24, j1), ""),
        ("J2", "CON28", "IC", hdr(28, j2), ""),
        ("J3", "CON20", "IC", hdr(20, j3), "最小系统接口"),
        ("J10", "CON18", "IC", hdr(18, j10), ""),
        ("J11", "CON18", "IC", hdr(18, j11), "port口排针"),
        ("J12", "CON26", "IC", hdr(26, j12), ""),
        ("J4", "DCON42", "IC", hdr(42, j4, True), "LCM跳线"),
        ("J5", "DCON16", "IC", hdr(16, j5, True), "Sensor跳线"),
        ("J6", "Port2.0mm", "IC", hdr(24, j6), "LCM模块接口"),
        ("J22", "GND", "IC", hdr(10, {i: "GND" for i in range(1, 11)}), ""),
        ("J19", "CON8", "IC", hdr(10, j19), "原图印CON8但画10脚"),
        ("J13", "DCON12", "IC", hdr(12, j13, True), "SD nand跳线"),
        ("J14", "DCON10", "IC", hdr(10, j14, True), ""),
        ("J15", "DCON10", "IC", hdr(10, j15, True), "音频功放输入跳线"),
        ("J8", "DCON4", "IC", hdr(4, {1: "VMIC", 3: "MIC_OUT", 2: "PA0", 4: "PA1"}, True), "麦克风跳线"),
        ("J7", "AVSS", "IC", hdr(4, {i: "AVSS" for i in range(1, 5)}), ""),
        ("J23", "HPVSS", "IC", hdr(4, {i: "HPVSS" for i in range(1, 5)}), ""),
        ("J9", "GND", "IC", hdr(4, allgnd4), ""),
        ("J16", "GND", "IC", hdr(4, allgnd4), ""),
        ("J21", "GND", "IC", hdr(4, allgnd4), ""),
        ("J17", "3V3", "IC", hdr(4, {1: "VDDIO33", 2: "VDDIO33", 3: "VDDIO33"}), "主控电源跳帽, 脚4原图疑似未接"),
        ("J18", "1V8", "IC", hdr(4, {1: "VDDIO18", 2: "VDDIO18", 3: "VDDIO18"}), "主控电源跳帽, 脚4原图疑似未接"),
        ("J26", "GND(value)", "IC", hdr(4, {i: "VDDIO33" for i in range(1, 5)}), "原图值GND但接VDDIO33, 待核对"),
        ("J24", "SPK", "IC", hdr(2, {1: "SPK+", 2: "SPK-"}), ""),
        ("J25", "MOT", "IC", hdr(2, {1: "PVCC", 2: "MOT-"}), "震动马达"),
        ("J20", "Earphone Jack", "IC",
         {"left": [("1", "1", None), ("2", "2", "JACK_T"), ("3", "3", "SPK-"), ("4", "4", None)], "right": []},
         "耳机座接线未能逐点转录: 仅2->R12->SPK+, 3->SPK-"),
        ("R12", "100R", "R", pair("JACK_T", "SPK+"), ""),
        ("USB1", "USBA", "IC",
         {"left": [("1", "+5V", "VUSB"), ("2", "DM", "USBDM"), ("3", "DP", "USBDP"), ("4", "ID", "GND"),
                   ("5", "GND", "GND"), ("6", "shell", "GND"), ("7", "shell", "GND"), ("8", "shell", "GND"),
                   ("9", "shell", "GND")], "right": []},
         "PC、升级; 原图4个外壳脚均印6, 此处顺延"),
        ("R5", "10K", "R", pair("VUSB", "LEDA_N"), ""),
        ("D1", "RED", "LED", {"A": "LEDA_N", "K": "GND"}, "充电输入指示灯"),
        ("JP1", "SJ", "SJ", pair("VUSB", "VPWR"), "主控电源跳冒(电流测试)"),
        ("JP2", "SJ", "SJ", pair("VBAT", "MCU_BAT"), "主控电源跳冒(电流测试)"),
        ("Q1", "2301", "PMOS", {"G": "Q1G", "D": "PVCC", "S": "VBAT"}, "功放电源切换"),
        ("D2", "5819", "D", {"A": "VBAT", "K": "PVCC"}, ""),
        ("D3", "5819", "D", {"A": "VUSB", "K": "PVCC"}, ""),
        ("R7", "1K", "R", pair("Q1G", "VUSB"), ""),
        ("R6", "100K", "R", pair("Q1G", "GND"), ""),
        ("BT1", "3.3V~4.2V", "BAT", {"+": "VBAT", "-": "GND"}, ""),
        ("C7", "106", "C", pair("VBAT", "GND"), ""),
        ("M1", "MIC", "MIC", {"+": "MICN", "-": "AVSS"}, ""),
        ("R4", "4.7K", "R", pair("VMIC", "MICN"), ""),
        ("C1", "NC", "C", pair("MICN", "AVSS"), ""),
        ("C2", "104", "C", pair("MICN", "MIC_OUT"), ""),
        ("U1", "NS4150", "IC",
         {"left": [("1", "MUTE", "MUTE"), ("2", "Bypass", "BYPASS"), ("3", "IN+", "PA_INP"), ("4", "IN-", "PA_INN")],
          "right": [("8", "OUT+", "SPK+"), ("7", "GND", "GND"), ("6", "VDD", "PVCC"), ("5", "OUT-", "SPK-")]},
         "外置功放"),
        ("R3", "100K", "R", pair("MUTE", "GND"), ""),
        ("C5", "105", "C", pair("BYPASS", "GND"), ""),
        ("R1", "33K", "R", pair("PA_IN+", "R1C"), ""),
        ("C3", "104", "C", pair("R1C", "PA_INP"), ""),
        ("R2", "33K", "R", pair("PA_IN-", "R2C"), ""),
        ("C4", "104", "C", pair("R2C", "PA_INN"), ""),
        ("C6", "106", "C", pair("PVCC", "GND"), ""),
        ("Q2", "2301", "PMOS", {"G": "SD_EN", "D": "SDQ_D", "S": "VDDIO33"}, "SDnand供电mos"),
        ("R8", "100K", "R", pair("VDDIO33", "SD_EN"), ""),
        ("R9", "2.2R", "R", pair("SDQ_D", "SD_VDD"), ""),
        ("SJ_PG", "SD_PG tie", "SJ", pair("SD_PG", "SD_VDD"), "原图为直连线, 以0欧姆跳线表示"),
        ("C8", "105", "C", pair("SD_VDD", "GND"), ""),
        ("R11", "NC", "R", pair("SD_CD", "SD_VDD"), ""),
        ("TF1", "SD-TF", "IC",
         {"left": [("10", "CD", "SD_CD"), ("9", "WP", None), ("1", "D2", None), ("2", "D3/CS", None),
                   ("3", "CMD", "SD_CMD"), ("4", "VDD", "SD_VDD"), ("5", "CLK", "SD_CLK"), ("6", "VSS", "GND"),
                   ("7", "D0", "SD_DAT"), ("8", "D1", None), ("11", "Sheet", "GND")], "right": []}, ""),
        ("S1", "KEY", "SW", pair("KEY0", "GND"), ""),
        ("S2", "KEY", "SW", pair("KEY1", "GND"), ""),
        ("S3", "KEY", "SW", pair("KEY2", "GND"), ""),
        ("S4", "KEY", "SW", pair("KEY3", "GND"), ""),
        ("Q3", "9014", "NPN", {"B": "Q3B", "C": "MOT-", "E": "GND"}, ""),
        ("R13", "220R", "R", pair("Motor_PWM", "Q3B"), ""),
        ("R14", "10K", "R", pair("Q3B", "GND"), ""),
        ("D4", "5819", "D", {"A": "MOT-", "K": "PVCC"}, ""),
        ("C10", "NC", "C", pair("PVCC", "MOT-"), ""),
        ("C9", "105", "C", pair("PVCC", "GND"), ""),
    ]
    return P
