# Run with KiCad python: makes sure every GND fill fragment is tied to the main pours on BOTH layers,
# adding stitching vias where a fragment (together with the vias inside it) is isolated.
import pcbnew, sys
path = sys.argv[1]
b = pcbnew.LoadBoard(path)
mm = pcbnew.FromMM; tomm = pcbnew.ToMM
gnd = [n for n in b.GetNetInfo().NetsByNetcode().values() if n.GetNetname() == "GND"][0]
zs = {b.GetLayerName(z.GetLayer()): z for z in b.Zones() if z.GetNetname() == "GND"}
MAIN = 500.0


def frags(layer):
    z = zs[layer]; polys = z.GetFilledPolysList(z.GetLayer())
    return [(polys.Outline(i), abs(polys.Outline(i).Area()) / 1e12) for i in range(polys.OutlineCount())]


def gnd_vias():
    return [t.GetPosition() for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]


def find_frag(fr, p):
    for k, (o, a) in enumerate(fr):
        if o.PointInside(p): return k
    return None


added = 0
for it in range(6):
    F, B = frags("F.Cu"), frags("B.Cu")
    vias = gnd_vias()
    bad = []
    for lname, fr, other in (("F.Cu", F, B), ("B.Cu", B, F)):
        for k, (o, a) in enumerate(fr):
            if a > MAIN: continue
            ok = False
            for p in vias:
                if o.PointInside(p):
                    j = find_frag(other, p)
                    if j is not None and other[j][1] > MAIN: ok = True; break
            if not ok:
                # fragments that only hold a THT GND pad are tied through the barrel
                has_tht = False
                for fp in b.GetFootprints():
                    for pd in fp.Pads():
                        if pd.GetNetname() == "GND" and pd.GetAttribute() != pcbnew.PAD_ATTRIB_SMD and o.PointInside(pd.GetPosition()):
                            has_tht = True
                if not has_tht: bad.append((lname, k, o, other))
    if not bad: break
    for (lname, k, o, other) in bad:
        mainother = max(other, key=lambda t: t[1])[0]
        bb = o.BBox(); step = mm(0.2); best = None
        x = bb.GetLeft() + mm(0.3)
        while x < bb.GetRight() - mm(0.3) and not best:
            y = bb.GetTop() + mm(0.3)
            while y < bb.GetBottom() - mm(0.3):
                p = pcbnew.VECTOR2I(int(x), int(y))
                if (o.PointInside(p) and o.SquaredDistance(p) >= mm(0.5) ** 2 and
                        mainother.PointInside(p) and mainother.SquaredDistance(p) >= mm(0.5) ** 2):
                    best = p; break
                y += step
            x += step
        if best is None:
            print("  NO ROOM to tie", lname, "fragment", k, "x[%.1f,%.1f] y[%.1f,%.1f]" % (tomm(bb.GetLeft()) - 100, tomm(bb.GetRight()) - 100, tomm(bb.GetTop()) - 80, tomm(bb.GetBottom()) - 80))
            continue
        v = pcbnew.PCB_VIA(b); v.SetPosition(best); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
        b.Add(v); added += 1
        print("  stitch via (%.2f, %.2f) ties %s fragment %d" % (tomm(best.x) - 100, tomm(best.y) - 80, lname, k))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(path)
print("added", added)
