# Footprint to-do list: every part without a footprint, grouped for review.
# usage: python footprint_list.py <project dir> <project name> <out csv>
import sys, csv, re, collections
import xml.etree.ElementTree as ET

proj, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
root = ET.parse("%s/%s_net.xml" % (proj, name)).getroot()

SUGGEST = {
    "SOT_23_5": "Package_TO_SOT_SMD:SOT-23-5",
    "SOT_23": "Package_TO_SOT_SMD:SOT-23",
    "SOD_323": "Diode_SMD:D_SOD-323",
    "IND_252010": "Inductor_SMD:L_1008_2520Metric (電感 2.5x2.0 mm，依實際型號確認高度/焊盤)",
    "IND_201610": "Inductor_SMD:L_0806_2016Metric (電感 2.0x1.6 mm，依實際型號確認)",
    "FBGA96_14R00X11R00X1R20": "需自建: DDR4 x16 FBGA96 (14.0x11.0 mm)，依 DRAM 資料手冊",
    "BGA409_14R00X14R00X0R90": "需自建: RV1126/RV1109 BGA409 14x14 mm，依 Rockchip 封裝圖",
    "BGA153_13RX11R5X0R9_2L": "Package_BGA 的 eMMC BGA-153 11.5x13 mm 系列，依 KLM8G1GETF 資料手冊確認",
    "SMD_1606-4": "需自建: 雙色 LED 1.6x0.6 mm 4 腳，依 A-SP1922BS1GHC 資料手冊",
    "TYPE_C": "Connector_USB:USB_C_Receptacle_* (依實際連接器型號，腳位需對 24 腳 + 屏蔽腳)",
    "0.3mm_fpc_39p": "需自建: FPC 0.3 mm 間距 39 腳，依連接器型號",
    "0.3mm_fpc_21p": "需自建: FPC 0.3 mm 間距 21 腳，依連接器型號",
    "0.5mm_FPC_8P": "Connector_FFC-FPC:* 0.5 mm 8 腳，依連接器型號",
}
BY_REF = [
    (r"^TP\d", "TestPoint:TestPoint_Pad_D1.0mm (測試點)"),
    (r"^(ESD|D)\d", "依型號確認 (ESD/二極體: SOD-323 / SOT-23 / DFN0603 等)"),
    (r"^Y\d", "Crystal:Crystal_SMD_* (依 24MHz/32.768kHz 晶振型號)"),
    (r"^(SW|KEY)\d", "Button_Switch_SMD:* (依開關型號)"),
    (r"^FPC\d", "Connector_FFC-FPC:* (依連接器型號)"),
    (r"^LED\d", "LED_SMD:* (依 LED 型號)"),
    (r"^U\d", "依 IC 型號確認封裝"),
    (r"^Q\d", "依型號確認 (SOT-23 / SOT-23-3)"),
    (r"^[RCL]\d", "阻容電感: 尺寸 (0402/0603/0805…) 原圖沒標，需確認"),
]


def suggest(pkg, ref):
    if pkg in SUGGEST: return SUGGEST[pkg]
    for pat, s in BY_REF:
        if re.match(pat, ref): return s
    return ""


groups = collections.defaultdict(list)
total = 0
for c in root.iter("comp"):
    ref = c.get("ref")
    if ref.startswith("#"): continue
    if c.findtext("footprint"): continue
    pkg = next((f.text for f in c.iter("field") if f.get("name") == "Package"), "") or ""
    spec = next((f.text for f in c.iter("field") if f.get("name") == "Spec"), "") or ""
    value = c.findtext("value") or ""
    prefix = re.match(r"^[A-Za-z_]+", ref).group(0)
    groups[(prefix, pkg, value)].append(ref)
    total += 1


def refkey(r):
    m = re.match(r"^([A-Za-z_]+)(\d+)", r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


rows = []
for (prefix, pkg, value), refs in groups.items():
    refs = sorted(refs, key=refkey)
    rows.append([prefix, value, pkg or "(原圖沒有封裝資訊)", len(refs), " ".join(refs), suggest(pkg, refs[0]), ""])
rows.sort(key=lambda r: (r[0], r[1]))
with open(out, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["類別", "值/型號", "原圖封裝字串", "數量", "位號", "建議 KiCad 封裝 (待你確認)", "你指定的封裝"])
    w.writerows(rows)
print(name, "parts without footprint:", total, "groups:", len(rows))
