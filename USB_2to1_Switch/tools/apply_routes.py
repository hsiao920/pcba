# -*- coding: utf-8 -*-
"""Run with KiCad python: adds tracks/vias from tools/tracks.json to USB_2to1_Switch_placed.kicad_pcb,
adds GND pours (F.Cu + B.Cu), silkscreen, writes USB_2to1_Switch.kicad_pcb and project design rules."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OFFX, OFFY = 100.0, 80.0
mm = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(mm(OFFX + x), mm(OFFY + y))


board = pcbnew.LoadBoard(os.path.join(ROOT, "USB_2to1_Switch_placed.kicad_pcb"))
data = json.load(open(os.path.join(HERE, "tracks.json")))
netmap = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}

for t in data["tracks"]:
    tr = pcbnew.PCB_TRACK(board)
    tr.SetStart(V(t["x1"], t["y1"])); tr.SetEnd(V(t["x2"], t["y2"]))
    tr.SetWidth(mm(t["w"]))
    tr.SetLayer(pcbnew.F_Cu if t["layer"] == "F" else pcbnew.B_Cu)
    tr.SetNet(netmap[t["net"]])
    board.Add(tr)
for v in data["vias"]:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(V(v["x"], v["y"]))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(mm(data["via_d"])); via.SetDrill(mm(data["via_drill"]))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(netmap[v["net"]])
    board.Add(via)

# GND pours
W, H = 70.0, 55.0
NOZONE = os.environ.get('NOZONE') == '1'
for layer in ([] if NOZONE else (pcbnew.F_Cu, pcbnew.B_Cu)):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(netmap["GND"])
    z.SetIsFilled(False)
    z.SetLocalClearance(mm(0.2))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.3))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)):
        ol.Append(mm(OFFX + x), mm(OFFY + y))
    board.Add(z)
if not NOZONE:
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

out = os.path.join(ROOT, "USB_2to1_Switch_nozone.kicad_pcb" if NOZONE else "USB_2to1_Switch.kicad_pcb")
board.Save(out)
print("saved", out, "tracks", len(data["tracks"]), "vias", len(data["vias"]))

# project rules (clearance 0.15, min track 0.15, via 0.6/0.3)
pro = os.path.join(ROOT, "USB_2to1_Switch.kicad_pro")
proj = json.load(open(pro, encoding="utf-8")) if os.path.exists(pro) else {}
proj.setdefault("meta", {"filename": "USB_2to1_Switch.kicad_pro", "version": 1})
bs = proj.setdefault("board", {}).setdefault("design_settings", {})
bs["rules"] = {"min_clearance": 0.12, "min_track_width": 0.15, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
               "min_via_annular_width": 0.1, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25,
               "min_hole_to_hole": 0.25, "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.08,
               "min_connection": 0.1, "solder_mask_to_copper_clearance": 0.0, "min_resolved_spokes": 2}
bs["defaults"] = {"track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3}
ns = proj.setdefault("net_settings", {"meta": {"version": 3}})
ns["classes"] = [{"name": "Default", "clearance": 0.12, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
                  "diff_pair_width": 0.25, "diff_pair_gap": 0.15, "diff_pair_via_gap": 0.25,
                  "microvia_diameter": 0.3, "microvia_drill": 0.1, "pcb_color": "rgba(0, 0, 0, 0.000)",
                  "priority": 2147483647, "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6, "bus_width": 12,
                  "line_style": 0}]
json.dump(proj, open(pro, "w", encoding="utf-8"), indent=2)
