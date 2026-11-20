# Compare two rebuilt KiCad projects (BOM + connectivity) and write a markdown report.
import sys, os, subprocess, collections, xml.etree.ElementTree as ET
KC = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"


def load(sch):
    x = os.path.splitext(sch)[0] + "_net.xml"
    subprocess.run([KC, "sch", "export", "netlist", "--format", "kicadxml", "-o", x, sch], capture_output=True)
    r = ET.parse(x).getroot()
    comps = {}
    for c in r.iter("comp"):
        ref = c.get("ref")
        if ref.startswith("#"): continue
        comps[ref] = (c.findtext("value") or "", next((f.text for f in c.iter("field") if f.get("name") == "Package"), "") or "")
    pin2net = {}; nets = {}
    for n in r.iter("net"):
        pins = frozenset((x.get("ref"), x.get("pin")) for x in n.iter("node") if not x.get("ref").startswith("#"))
        for p in pins: pin2net[p] = (n.get("name"), pins)
    return comps, pin2net


a, b, out = sys.argv[1], sys.argv[2], sys.argv[3]
ca, pa = load(a); cb, pb = load(b)
L = []
L.append("# %s vs %s\n" % (os.path.basename(a), os.path.basename(b)))
onlya = sorted(set(ca) - set(cb)); onlyb = sorted(set(cb) - set(ca))
L.append("## Parts only in A (%d)\n" % len(onlya))
L += ["- %s  %s  %s" % (r, *ca[r]) for r in onlya]
L.append("\n## Parts only in B (%d)\n" % len(onlyb))
L += ["- %s  %s  %s" % (r, *cb[r]) for r in onlyb]
chg = [r for r in sorted(set(ca) & set(cb)) if ca[r][0] != cb[r][0]]
L.append("\n## Value changes (%d)\n" % len(chg))
L += ["- %s: %s -> %s" % (r, ca[r][0], cb[r][0]) for r in chg]
# connectivity: for each common pin, compare the set of common pins on its net
common = set(r for r in ca if r in cb)
diffs = []
seen = set()
for p, (na, sa) in pa.items():
    if p[0] not in common or p in seen: continue
    if p not in pb: continue
    nb, sb = pb[p]
    sa_c = {q for q in sa if q[0] in common}; sb_c = {q for q in sb if q[0] in common}
    seen |= sa_c
    if sa_c != sb_c:
        diffs.append((na, nb, sorted(sa_c - sb_c), sorted(sb_c - sa_c)))
L.append("\n## Connectivity differences among common parts (%d nets)\n" % len(diffs))
for na, nb, ma, mb in diffs[:300]:
    L.append("- A net `%s` / B net `%s`: only-in-A %s ; only-in-B %s" % (na, nb, ["%s.%s" % q for q in ma][:8], ["%s.%s" % q for q in mb][:8]))
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("A parts", len(ca), "B parts", len(cb), "onlyA", len(onlya), "onlyB", len(onlyb), "value changes", len(chg), "net diffs", len(diffs))
