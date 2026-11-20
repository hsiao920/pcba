import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1])
mm = pcbnew.ToMM
for z in b.Zones():
    if z.GetNetname() != "GND": continue
    ly = z.GetLayer(); name = b.GetLayerName(ly)
    polys = z.GetFilledPolysList(ly)
    n = polys.OutlineCount()
    print(name, "fragments:", n)
    for i in range(n):
        o = polys.Outline(i)
        bb = o.BBox()
        area = abs(o.Area()) / 1e12
        print("   #%d bbox x[%.1f,%.1f] y[%.1f,%.1f] area %.2f mm2" % (i, mm(bb.GetLeft())-100, mm(bb.GetRight())-100, mm(bb.GetTop())-80, mm(bb.GetBottom())-80, area))
