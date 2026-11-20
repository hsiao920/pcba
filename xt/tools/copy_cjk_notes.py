# V1.3's Chinese notes cannot be read reliably from its PDF text layer; they are identical to V1.5's,
# so copy V1.5's recovered notes into the V1.3 sheets.
# usage: python copy_cjk_notes.py <v15 dir> <v13 dir> <page numbers like 11 15 16 18>
import re, sys

src, dst, pages = sys.argv[1], sys.argv[2], sys.argv[3:]
BAD = re.compile("[㄀-ㄯ㐀-鿿-]|\?")
HAN = re.compile(r"[㐀-鿿]")
PAT = re.compile(r'\(text "((?:[^"\\]|\\.)*)" \(exclude_from_sim no\) \(at [^)]*\) \(effects \(font \(size [0-9.]+ [0-9.]+\)\) \(justify left bottom\)\) \(uuid "[^"]*"\)\)')

for p in pages:
    a = open("%s/p%s.kicad_sch" % (src, p), encoding="utf-8").read()
    b = open("%s/p%s.kicad_sch" % (dst, p), encoding="utf-8").read()
    good = [m.group(0) for m in PAT.finditer(a) if HAN.search(m.group(1))]
    b2 = PAT.sub(lambda m: "" if BAD.search(m.group(1)) else m.group(0), b).rstrip()
    assert b2.endswith(")")
    b2 = b2[:-1] + "\n" + "\n".join(good) + "\n)\n"
    open("%s/p%s.kicad_sch" % (dst, p), "w", encoding="utf-8").write(b2)
    print(p, len(good), "notes copied")
