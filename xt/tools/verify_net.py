# Compare KiCad-exported netlist with the connectivity computed directly from the PDF geometry.
# Usage: python verify_net.py <pdf> <kicad_sch> [decoder]
import sys, os, subprocess, collections, re, importlib, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymupdf
from extract_cad import extract_page

pdf, sch = sys.argv[1], sys.argv[2]
dec = importlib.import_module(sys.argv[3]).decode if len(sys.argv) > 3 else None
KC = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
xmlp = os.path.splitext(sch)[0] + "_net.xml"
subprocess.run([KC, "sch", "export", "netlist", "--format", "kicadxml", "-o", xmlp, sch], capture_output=True)
root = ET.parse(xmlp).getroot()
kn = []
for n in root.iter("net"):
    pins = frozenset((x.get("ref"), x.get("pin")) for x in n.iter("node") if not x.get("ref").startswith("#"))
    if pins: kn.append((n.get("name"), pins))
kmap = {}
for name, ps in kn:
    for p in ps: kmap[p] = (name, ps)


def split_ref(ref):
    m = re.match(r"^(.*\d)([A-Z])$", ref)
    if m and not re.match(r"^[A-Z]{2,5}_", ref): return m.group(1)
    return ref


doc = pymupdf.open(pdf)
import os as _os, importlib as _il
if _os.environ.get("XT_ADAPTER"):
    doc = _il.import_module(_os.environ["XT_ADAPTER"]).open_pages()
UF = {}
def f(a):
    UF.setdefault(a, a)
    while UF[a] != a: UF[a] = UF[UF[a]]; a = UF[a]
    return a
def u(a, b): UF[f(a)] = f(b)

pages = [extract_page(doc[i], i + 1, decode=dec) for i in range(len(doc))]
gnames = {s["name"] for r in pages for s in r["syms"] if s["conn"]}
if os.environ.get("XT_ALIAS_GLOBAL"):
    gnames |= {a["name"] for r in pages for a in r["aliases"]}
for r in pages:
    # replicate pin numbering of the generator
    for part in r["parts"]:
        pins = [r["pins"][k] for k in part["pins"]]
        if all(p["num"] is None for p in pins):
            order = sorted(range(len(pins)), key=lambda i: (pins[i]["outer"][0], pins[i]["outer"][1]))
            for n, i in enumerate(order): pins[i]["num"] = str(n + 1)
        else:
            used = {p["num"] for p in pins if p["num"]}; n = 1
            for p in pins:
                if not p["num"]:
                    while str(n) in used: n += 1
                    p["num"] = str(n); used.add(p["num"])
    owner = {k: part for part in r["parts"] for k in part["pins"]}
    roots = set(r["nets"]) | set(r["netname"])
    for root_ in roots:
        ks = r["nets"].get(root_, [])
        node = ("pg", r["page"], root_)
        f(node)
        for k in ks:
            part = owner.get(k)
            if part and part["ref"]:
                u(("pin", split_ref(part["ref"]), r["pins"][k]["num"]), node)
        for kind, nm in r["netname"].get(root_, ()):
            if kind == "alias" and nm not in gnames:
                u(("lname", r["page"], nm), node)
            else:
                u(("gname", nm), node)
nets = collections.defaultdict(set)
for k in list(UF):
    if k[0] == "pin": nets[f(k)].add((k[1], k[2]))
mine = [frozenset(v) for v in nets.values()]
ok = bad = 0
diffs = []
for ps in mine:
    any_p = next(iter(ps))
    kk = kmap.get(any_p)
    if kk and kk[1] == ps: ok += 1
    else:
        bad += 1
        diffs.append((sorted(ps)[:6], kk and sorted(kk[1])[:6], kk and kk[0]))
print("nets from PDF:", len(mine), "KiCad nets:", len(kn), "identical:", ok, "different:", bad)
for d in diffs[:20]: print("  PDF", d[0], "\n  KiCad", d[2], d[1])
allpins = sum(len(x) for x in mine)
print("pins:", allpins, "KiCad pins:", sum(len(p) for _, p in kn))
