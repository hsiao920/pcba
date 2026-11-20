import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
vias = [(t.GetPosition(), 'via') for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() == "GND": pads.append((p.GetPosition(), fp.GetReference() + "." + p.GetNumber(), p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD))
for z in b.Zones():
    if z.GetNetname() != "GND": continue
    ly = z.GetLayer(); polys = z.GetFilledPolysList(ly)
    for i in range(polys.OutlineCount()):
        o = polys.Outline(i)
        if abs(o.Area()) / 1e12 > 500: continue
        inv = [1 for (p, _) in vias if o.PointInside(p)]
        inp = [(n, th) for (p, n, th) in pads if o.PointInside(p)]
        bb = o.BBox()
        print(b.GetLayerName(ly), "frag %d (%.1f,%.1f) vias=%d pads=%s" % (i, mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 80, len(inv), inp))

print("--- via connectivity to the big B.Cu / F.Cu pours")
zs = {b.GetLayerName(z.GetLayer()): z for z in b.Zones() if z.GetNetname() == "GND"}
def frag_of(z, p):
    polys = z.GetFilledPolysList(z.GetLayer())
    for i in range(polys.OutlineCount()):
        if polys.Outline(i).PointInside(p): return i, abs(polys.Outline(i).Area()) / 1e12
    return None, 0
for (p, _) in vias:
    fF = frag_of(zs["F.Cu"], p); fB = frag_of(zs["B.Cu"], p)
    bigF = fF[1] > 500; bigB = fB[1] > 500
    if not (bigB):
        print("via (%.2f,%.2f): F frag %s  B frag %s  <-- B side NOT in main pour" % (mm(p.x) - 100, mm(p.y) - 80, fF[0], fB[0]))
