# -*- coding: utf-8 -*-
"""Run with KiCad's python:  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" build_pcb.py
Creates USB_2to1_Switch_placed.kicad_pcb (footprints placed, nets assigned, outline, labels) and pads.json (for router)."""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import design, placement
import importlib
importlib.reload(placement)

ROOT = os.path.normpath(os.path.join(HERE, ".."))
OFFX, OFFY = 100.0, 80.0          # board origin on the sheet (mm)
mm = pcbnew.FromMM
tomm = pcbnew.ToMM


def V(x, y):
    return pcbnew.VECTOR2I(mm(OFFX + x), mm(OFFY + y))


board = pcbnew.BOARD()
nets = {}


def net(name):
    if name not in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    return nets[name]


parts = design.build()
placed = {}
for p in parts:
    lib, name = p["fp"]
    path = os.path.join(ROOT, "USB2to1.pretty") if lib == "USB2to1" else os.path.join(design.FP_LIBS, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit("footprint not found: %s:%s" % (lib, name))
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(p["ref"])
    fp.SetValue(p["value"])
    x, y, rot = placement.PLACE[p["ref"]]
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(V(x, y))
    board.Add(fp)
    for pad in fp.Pads():
        num = pad.GetNumber()
        if num in p["pins"] and p["pins"][num]:
            pad.SetNet(net(p["pins"][num]))
    # reference text: small, silk
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    fp.Reference().SetTextThickness(mm(0.12))
    fp.Value().SetVisible(False)
    placed[p["ref"]] = fp

# ---- outline 70 x 55, 1 mm corner radius
W, H, R = design.BOARD_W, design.BOARD_H, 1.0


def seg(x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
    s.SetWidth(mm(0.1))
    board.Add(s)


def arc(cx, cy, sx, sy, ex, ey):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetCenter(V(cx, cy)); s.SetStart(V(sx, sy)); s.SetEnd(V(ex, ey))
    s.SetWidth(mm(0.1))
    board.Add(s)


seg(R, 0, W - R, 0); seg(W, R, W, H - R); seg(W - R, H, R, H); seg(0, H - R, 0, R)
arc(R, R, 0, R, R, 0); arc(W - R, R, W - R, 0, W, R); arc(W - R, H - R, W, H - R, W - R, H); arc(R, H - R, R, H, 0, H - R)


def text(s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetPosition(V(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(0.15 if size >= 1 else 0.12))
    t.SetTextAngleDegrees(rot)
    board.Add(t)


for (s, x, y, size, rot) in getattr(placement, "LABELS", []):
    text(s, x, y, size, rot=rot)

# ---- net classes / design rules go to the project file (see apply step)
out = os.path.join(ROOT, "USB_2to1_Switch_placed.kicad_pcb")
board.Save(out)

# ---- pads dump for the router
dump = {"W": W, "H": H, "pads": [], "holes": []}
for ref, fp in placed.items():
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize(pcbnew.F_Cu)
        ang = pad.GetOrientationDegrees()
        attr = pad.GetAttribute()
        thru = attr in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        layers = []
        if pad.IsOnLayer(pcbnew.F_Cu): layers.append("F")
        if pad.IsOnLayer(pcbnew.B_Cu): layers.append("B")
        shp = pad.GetShape()
        shape = {pcbnew.PAD_SHAPE_CIRCLE: "circle", pcbnew.PAD_SHAPE_RECT: "rect", pcbnew.PAD_SHAPE_OVAL: "oval",
                 pcbnew.PAD_SHAPE_ROUNDRECT: "rect"}.get(shp, "rect")
        drill = pad.GetDrillSize()
        d = dict(ref=ref, num=pad.GetNumber(), net=pad.GetNetname(), x=tomm(pos.x) - OFFX, y=tomm(pos.y) - OFFY,
                 w=tomm(sz.x), h=tomm(sz.y), ang=ang, shape=shape, layers=layers, thru=thru,
                 npth=(attr == pcbnew.PAD_ATTRIB_NPTH), drill=max(tomm(drill.x), tomm(drill.y)))
        dump["pads"].append(d)
with open(os.path.join(HERE, "pads.json"), "w", encoding="utf-8") as fh:
    json.dump(dump, fh, indent=1)
print("placed", len(placed), "footprints; nets", len(nets), "->", out)
