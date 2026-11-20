import pymupdf, sys, json
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from extract_cad import extract_page

pdf, pno, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
doc = pymupdf.open(pdf)
page = doc[pno - 1]
r = extract_page(page, pno)
sh = page.new_shape()
for p in r["parts"]:
    b = p["box"]
    sh.draw_rect(pymupdf.Rect(*b)); sh.finish(color=(0, 0.7, 0) if p["ref"] else (1, 0.5, 0), width=1.2)
for pn in r["pins"]:
    sh.draw_line(pymupdf.Point(*pn["inner"]), pymupdf.Point(*pn["outer"]))
    sh.finish(color=(0, 0.8, 0.8) if pn["num"] else (1, 0.6, 0), width=2)
for s in r["syms"]:
    if not s["conn"]: continue
    sh.draw_rect(pymupdf.Rect(*s["box"])); sh.finish(color=(0.6, 0, 0.9), width=0.8)
for t in r["unused"]:
    sh.draw_rect(pymupdf.Rect(*t["bbox"])); sh.finish(color=(1, 0.8, 0), width=0.5)
sh.commit()
page.get_pixmap(dpi=int(sys.argv[4]) if len(sys.argv) > 4 else 130).save(out)
for p in r["parts"]:
    if not p["ref"]:
        print("NOREF box", [round(x) for x in p["box"]], "pins", [r["pins"][k]["num"] for k in p["pins"]])
for k, pn in enumerate(r["pins"]):
    if not pn["num"]:
        print("NONUM pin", [round(x, 1) for x in pn["inner"]], [round(x, 1) for x in pn["outer"]])
print("UNUSED", [t["t"] for t in r["unused"]][:200])
