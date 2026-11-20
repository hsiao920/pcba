import pymupdf, sys, re, collections
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from extract_cad import extract_page, REFDES

TB = {"Project:", "File:", "Date:", "Rockchip Electronics Co., Ltd", "Designed by:", "Rev:", "Sheet:", "of", "Reviewed by:",
      "<Checker>", "Yanhong.Li", "V1.1", "RV1126_RV1109_REF"}
pdf = sys.argv[1]
doc = pymupdf.open(pdf)
import os as _os, importlib as _il
if _os.environ.get("XT_ADAPTER"):
    doc = _il.import_module(_os.environ["XT_ADAPTER"]).open_pages()
pages = range(1, len(doc) + 1) if len(sys.argv) < 3 else [int(x) for x in sys.argv[2].split(",")]
for pno in pages:
    r = extract_page(doc[pno - 1], pno)
    W, H = r["size"]
    un = [t for t in r["unused"] if t["t"] not in TB and not (len(t["t"]) <= 2 and (t["bbox"][1] < 12 or t["bbox"][3] > H - 12 or t["bbox"][0] < 12 or t["bbox"][2] > W - 12))
          and not (t["bbox"][0] > W * 0.72 and t["bbox"][1] > H * 0.86) and t["size"] < 9]
    print(f"== p{pno}")
    for p in r["parts"]:
        pn = [r["pins"][k]["num"] for k in p["pins"]]
        dup = [x for x, c in collections.Counter(pn).items() if c > 1 and x]
        if not p["ref"] or dup or len(p["props"]) == 0:
            print("  PART", p["ref"], [x[0] for x in p["props"]], "pins", pn[:12], "dup", dup, [round(x) for x in p["box"]])
    if un: print("  UNUSED", [(t["t"], [round(x) for x in t["bbox"][:2]], hex(t["color"])) for t in un])
    for s in r["syms"]:
        if s["conn"] and s["kind"] == "gnd" and (s["box"][2] - s["box"][0]) < 3:
            print("  ODD-GND", [round(x) for x in s["box"]])

print("==== connectivity")
for pno in pages:
    r = extract_page(doc[pno - 1], pno)
    U = r["U"]; parts = {k: p for p in r["parts"] for k in p["pins"]}
    single = []
    for root, ks in r["nets"].items():
        if len(ks) == 1 and not r["netname"].get(root):
            k = ks[0]; p = parts.get(k)
            single.append(f'{p["ref"] if p else "?"}.{r["pins"][k]["num"]}')
    print(f"p{pno}: single-pin unnamed {len(single)}:", " ".join(single[:60]))
