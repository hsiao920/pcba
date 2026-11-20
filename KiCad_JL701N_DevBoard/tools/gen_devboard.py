# -*- coding: utf-8 -*-
"""Generate the two KiCad projects (01_MinSystem, 02_BaseBoard) from devboard_data.py.

Style follows the earlier A01 control-board reconstruction: every part is one editable symbol card,
each connected pin has a short wire stub ending in a GLOBAL label (same label = same net),
open pins get a no-connect flag, all pins are electrical type passive, no footprints.

usage:  python gen_devboard.py            (writes projects next to this tools/ folder)
        python gen_devboard.py --verify   (also runs kicad-cli netlist export and compares every pin)
"""
import csv
import json
import math
import os
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import devboard_data as D  # noqa: E402

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
LIB = "DevBoard_Source"
CHAR = 110          # text width per character in 0.01 mm (font 0.9-1.0)
GRID = 254          # 2.54 mm in 0.01 mm units
PAPERS = [("A4", 29700, 21000), ("A3", 42000, 29700), ("A2", 59400, 42000), ("A1", 84100, 59400), ("A0", 118900, 84100)]

SMALL = {"R", "C", "D", "LED", "L", "XTAL", "BAT", "SW", "MIC", "ANT", "SJ", "NPN", "PMOS"}
PREFIX = {"R": "R", "C": "C", "D": "D", "LED": "D", "L": "L", "XTAL": "Y", "BAT": "BT", "SW": "S", "MIC": "M",
          "ANT": "ANT", "SJ": "SJ", "NPN": "Q", "PMOS": "Q"}


def f(v):
    return "%.2f" % (v / 100.0)


def uid():
    return str(uuid.uuid4())


def up254(v):
    return int(math.ceil(v / float(GRID))) * GRID


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def safe(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def sides(part):
    ref, value, kind, spec, note = part
    if kind == "IC":
        return list(spec["left"]), list(spec["right"])
    if kind == "IC68":
        names, nets = spec["names"], spec["nets"]
        left = [(str(i), names[i], nets[i]) for i in range(1, 35)] + [("0", names[0], nets[0])]
        right = [(str(i), names[i], nets[i]) for i in range(35, 69)]
        return left, right
    items = [(str(i + 1), name, net) for i, (name, net) in enumerate(spec.items())]
    if kind in ("NPN", "PMOS"):
        return items[:1], items[1:]
    return items[:1], items[1:]


def symname(part):
    ref, value, kind, spec, note = part
    return kind if kind in SMALL else "IC_" + safe(ref)


class Sym:
    """geometry of one symbol; all numbers in 0.01 mm, symbol space is y-up"""

    def __init__(self, part):
        self.part = part
        self.name = symname(part)
        self.left, self.right = sides(part)
        n = max(len(self.left), len(self.right), 1)
        self.n = n
        self.hh = n * GRID // 2
        ml = max([len(p[1]) for p in self.left] + [0])
        mr = max([len(p[1]) for p in self.right] + [0])
        if self.right:
            hw = up254((ml + mr) * CHAR + 400)
        else:
            hw = up254(ml * CHAR + 400)
        self.hw = max(hw, GRID)
        self.pinlen = GRID

    def row_y(self, k):  # symbol-space y of row k
        return self.n * GRID // 2 - GRID // 2 - k * GRID

    def pins(self):
        """yield (side, num, name, net, px, py) in symbol space; px,py = connection point"""
        out = []
        for k, (num, name, net) in enumerate(self.left):
            out.append(("L", num, name, net, -(self.hw + self.pinlen), self.row_y(k)))
        for k, (num, name, net) in enumerate(self.right):
            out.append(("R", num, name, net, self.hw + self.pinlen, self.row_y(k)))
        return out

    def lib_text(self, prefixed):
        name = self.name
        libname = (LIB + ":" + name) if prefixed else name
        pre = PREFIX.get(self.part[2], "U")
        s = '(symbol "%s" (pin_names (offset .508)) (in_bom yes) (on_board yes)' % libname
        s += '(property "Reference" "%s" (at 0 %s 0) (effects (font (size 1.0 1.0))))' % (pre, f(self.hh + 762))
        s += '(property "Value" "%s" (at 0 %s 0) (effects (font (size 1.0 1.0))))' % (name, f(self.hh + 254))
        s += '(property "Footprint" "" (at 0 0 0) (effects (font (size 1.0 1.0)) (hide yes)))'
        s += '(symbol "%s_0_1" (rectangle (start %s %s) (end %s %s) (stroke (width .254) (type default)) (fill (type background))))' % (
            name, f(-self.hw), f(self.hh), f(self.hw), f(-self.hh))
        s += '(symbol "%s_1_1"' % name
        for side, num, pname, net, px, py in self.pins():
            ang = 0 if side == "L" else 180
            s += ('(pin passive line (at %s %s %d) (length %s) (name "%s" (effects (font (size 0.9 0.9)))) '
                  '(number "%s" (effects (font (size 0.9 0.9)))))') % (f(px), f(py), ang, f(self.pinlen), esc(pname), esc(num))
        s += "))"
        return s


def build_sheet(proj, parts, title, srcpage):
    root_uuid = uid()
    syms = [Sym(p) for p in parts]
    # check shared small symbols have identical pin names
    seen = {}
    for sy in syms:
        key = sy.name
        sig = [(p[1], p[0]) for p in sy.left + sy.right]
        if key in seen:
            assert seen[key].left and [(p[1]) for p in seen[key].left + seen[key].right] == [p[1] for p in sy.left + sy.right], key
        else:
            seen[key] = sy
    # symbols with identical name must have identical geometry: widen small ones to the max
    by_name = {}
    for sy in syms:
        by_name.setdefault(sy.name, []).append(sy)
    for name, lst in by_name.items():
        if len(lst) > 1:
            hw = max(s.hw for s in lst)
            for s in lst:
                s.hw = hw

    # card sizes
    def card_size(sy):
        ref, value, kind, spec, note = sy.part
        ll = max([len(p[2]) for p in sy.left if p[2]] + [0])
        lr = max([len(p[2]) for p in sy.right if p[2]] + [0])
        w = 2 * (sy.hw + sy.pinlen + 2 * GRID) + (ll + lr) * CHAR + 1200
        h = 2 * sy.hh + 2300 + (700 if note else 0)
        return w, h

    order = sorted(syms, key=lambda s: (0 if s.part[2] in ("IC", "IC68") else 1, -s.hh))
    chosen = None
    for pname, pw, ph in PAPERS:
        usable_h = ph - 4000
        cols, x, y, colw = [], 2000, 4000, 0
        placed = []
        cur = []
        for sy in order:
            w, h = card_size(sy)
            if y + h > usable_h and cur:
                x += colw
                y, colw = 4000, 0
            cur_x = x
            placed.append((sy, cur_x, y, w, h))
            y += h
            colw = max(colw, w)
            cur = [1]
        total_w = x + colw + 2000
        if total_w <= pw or pname == "A0":
            chosen = (pname, pw, ph, placed, total_w)
            break
    pname, pw, ph, placed, total_w = chosen

    out = []
    out.append('(kicad_sch (version 20250114) (generator "eeschema") (uuid "%s") (paper "%s")' % (root_uuid, pname))
    out.append('(title_block (title "%s") (rev "REVIEW") (comment 1 "hand transcription of %s; footprints not assigned"))' % (esc(title), esc(srcpage)))
    out.append("(lib_symbols")
    done = set()
    for sy in syms:
        if sy.name not in done:
            done.add(sy.name)
            out.append(sy.lib_text(True))
    out.append(")")
    out.append('(text "%s" (at 2000 2000 0) (effects (font (size 2 2)) (justify left bottom)) (uuid "%s"))' % (esc(title), uid()))
    out.append('(text "Source: %s. Same GLOBAL label = same net. No footprints, no PCB, all pins passive." (at 2000 3200 0) (effects (font (size 1.3 1.3)) (justify left bottom)) (uuid "%s"))' % (esc(srcpage), uid()))

    expected = []  # (ref, pin, net)
    rows = []
    for sy, cx, cy, w, h in placed:
        ref, value, kind, spec, note = sy.part
        X = cx + (w // 2)
        X = (X // GRID) * GRID
        Y = cy + 1500 + sy.hh
        Y = (Y // GRID) * GRID
        ll = max([len(p[2]) for p in sy.left if p[2]] + [0])
        out.append('(symbol (lib_id "%s:%s") (at %s %s 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "%s")'
                   % (LIB, sy.name, f(X), f(Y), uid()))
        out.append('(property "Reference" "%s" (at %s %s 0) (effects (font (size 1.0 1.0))))' % (esc(ref), f(X), f(Y - sy.hh - 762)))
        out.append('(property "Value" "%s" (at %s %s 0) (effects (font (size 1.0 1.0))))' % (esc(value), f(X), f(Y - sy.hh - 254)))
        out.append('(property "Footprint" "" (at %s %s 0) (effects (font (size 1.0 1.0)) (hide yes)))' % (f(X), f(Y)))
        out.append('(property "SourcePage" "%s" (at %s %s 0) (effects (font (size 1.0 1.0)) (hide yes)))' % (srcpage[-6:].replace("/", "_"), f(X), f(Y)))
        if note:
            out.append('(property "Review" "%s" (at %s %s 0) (effects (font (size 1.0 1.0)) (hide yes)))' % (esc(note), f(X), f(Y)))
        for side, num, pname, net, px, py in sy.pins():
            out.append('(pin "%s" (uuid "%s"))' % (esc(num), uid()))
        out.append('(instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))' % (proj, root_uuid, esc(ref)))
        for side, num, pin_label, net, px, py in sy.pins():
            sx, sy_ = X + px, Y - py
            if net is None:
                out.append('(no_connect (at %s %s) (uuid "%s"))' % (f(sx), f(sy_), uid()))
                rows.append((ref, value, num, pin_label, ""))
                continue
            ex = sx - 2 * GRID if side == "L" else sx + 2 * GRID
            ang = 180 if side == "L" else 0
            out.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))' % (f(sx), f(sy_), f(ex), f(sy_), uid()))
            out.append('(global_label "%s" (shape bidirectional) (at %s %s %d) (effects (font (size 1.0 1.0)) (justify %s)) (uuid "%s"))'
                       % (esc(net), f(ex), f(sy_), ang, "right" if side == "L" else "left", uid()))
            expected.append((ref, num, net))
            rows.append((ref, value, num, pin_label, net))
        if note:
            out.append('(text "%s: %s" (at %s %s 0) (effects (font (size 0.9 0.9)) (justify left top)) (uuid "%s"))'
                       % (esc(ref), esc(note), f(X - sy.hw - sy.pinlen - 2 * GRID), f(Y + sy.hh + 500), uid()))
    out.append(")")
    return "".join(out), syms, expected, rows, pname


def write_project(sub, proj, parts, title, srcpage):
    d = os.path.join(ROOT, sub)
    os.makedirs(d, exist_ok=True)
    sch, syms, expected, rows, paper = build_sheet(proj, parts, title, srcpage)
    with open(os.path.join(d, proj + ".kicad_sch"), "w", encoding="utf-8") as fh:
        fh.write(sch)
    with open(os.path.join(d, proj + ".kicad_pro"), "w", encoding="utf-8") as fh:
        json.dump({"meta": {"filename": proj + ".kicad_pro", "version": 1}}, fh, indent=2)
    lib = ['(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") (generator_version "9.0")']
    done = set()
    for sy in syms:
        if sy.name not in done:
            done.add(sy.name)
            lib.append(sy.lib_text(False))
    lib.append(")")
    with open(os.path.join(d, LIB + ".kicad_sym"), "w", encoding="utf-8") as fh:
        fh.write("".join(lib))
    with open(os.path.join(d, "sym-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(sym_lib_table (version 7) (lib (name "%s") (type "KiCad") (uri "${KIPRJMOD}/%s.kicad_sym") (options "") (descr "PDF reconstruction - review required")))\n' % (LIB, LIB))
    with open(os.path.join(d, "connectivity.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ref", "value", "pin", "pin_name", "net (blank = open/NC)"])
        w.writerows(rows)
    print(sub, proj, "paper", paper, "parts", len(parts), "pins", len(rows), "connected", len(expected))
    return d, expected


def verify(d, proj, expected):
    xml = os.path.join(d, "validation_netlist.xml")
    erc = os.path.join(d, "validation_erc.json")
    sch = os.path.join(d, proj + ".kicad_sch")
    subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", xml, sch], check=True, capture_output=True)
    subprocess.run([KICAD_CLI, "sch", "erc", "--format", "json", "--severity-all", "-o", erc, sch], capture_output=True)
    tree = ET.parse(xml)
    got = {}
    for net in tree.getroot().iter("net"):
        name = net.get("name")
        for node in net.iter("node"):
            got[(node.get("ref"), node.get("pin"))] = name
    diffs = []
    for ref, pin, net in expected:
        g = got.get((ref, pin))
        g_norm = g[1:] if g and g.startswith("/") else g
        if g_norm != net:
            diffs.append((ref, pin, net, g))
    print(proj, "netlist compare: expected", len(expected), "differences", len(diffs))
    for x in diffs[:20]:
        print("   DIFF", x)
    try:
        e = json.load(open(erc, encoding="utf-8"))
        cnt = {}
        for sh in e.get("sheets", []):
            for v in sh.get("violations", []):
                key = (v.get("severity"), v.get("type"))
                cnt[key] = cnt.get(key, 0) + 1
        print(proj, "ERC:", cnt if cnt else "no violations")
    except Exception as ex:  # noqa
        print("ERC json read failed", ex)
    return diffs


if __name__ == "__main__":
    jobs = [
        ("01_MinSystem", "JL701N_MinSystem", D.page2(), "JL701N dev board - minimum system (PDF page 2)", "JL701N手表开发板原理图 page 2"),
        ("02_BaseBoard", "JL701N_BaseBoard", D.page3(), "JL701N dev board - base board (PDF page 3)", "JL701N手表开发板原理图 page 3"),
    ]
    res = []
    for sub, proj, parts, title, src in jobs:
        res.append((write_project(sub, proj, parts, title, src), proj))
    if "--verify" in sys.argv:
        for (d, expected), proj in res:
            verify(d, proj, expected)
