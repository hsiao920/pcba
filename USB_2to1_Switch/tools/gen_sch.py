# -*- coding: utf-8 -*-
"""Generate KiCad schematic (card layout with global labels) + symbol library + project files from design.py."""
import os, sys, uuid, csv
sys.path.insert(0, os.path.dirname(__file__))
import design

OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
PROJ = "USB_2to1_Switch"
LIB = "USB2to1"
PITCH = 254  # 0.01 mm units


def u():
    return str(uuid.uuid4())


def f(v):  # 0.01mm int -> string
    return "%.2f" % (v / 100.0)


def sym_geometry(p):
    left, right = p["sym"]
    n = max(len(left), len(right), 1)
    names = [nm for _, nm in left + right] or ["1"]
    hw = max(int(max(len(x) for x in names) * 1.15 + 3), 4) * 100
    hw = ((hw + PITCH - 1) // PITCH) * PITCH
    return left, right, n, hw


def sym_text(p, prefix=""):
    left, right, n, hw = sym_geometry(p)
    ref = p["ref"]
    hh = n * PITCH // 2
    s = ['(symbol "%s%s" (pin_names (offset .508)) (in_bom yes) (on_board yes)' % (prefix, ref)]
    s.append('(property "Reference" "%s" (at 0.00 %s 0) (effects (font (size 1.0 1.0))))' % (ref, f(hh + 508)))
    s.append('(property "Value" "%s" (at 0.00 %s 0) (effects (font (size 1.0 1.0))))' % (p["value"], f(hh + 254)))
    s.append('(property "Footprint" "%s:%s" (at 0.00 0.00 0) (effects (font (size 1.0 1.0)) (hide yes)))' % p["fp"])
    s.append('(symbol "%s_0_1" (rectangle (start %s %s) (end %s %s) (stroke (width .254) (type default)) (fill (type background))))'
             % (ref, f(-hw), f(hh), f(hw), f(-hh)))
    s.append('(symbol "%s_1_1"' % ref)
    for side, lst in ((0, left), (1, right)):
        for k, (num, nm) in enumerate(lst):
            y = n * PITCH // 2 - PITCH // 2 - k * PITCH
            x = -(hw + 508) if side == 0 else (hw + 508)
            ang = 0 if side == 0 else 180
            s.append('(pin passive line (at %s %s %d) (length 5.08) (name "%s" (effects (font (size 0.85 0.85)))) '
                     '(number "%s" (effects (font (size 0.85 0.85)))))' % (f(x), f(y), ang, nm, num))
    s.append("))")
    return "".join(s)


def main():
    parts = [q for q in design.build() if not q["ref"].startswith("H")]   # mounting holes: footprint only
    # ---------- layout: columns
    MAXH = 52070
    x0, y0 = 3048, 4572
    colx, cury, colw = x0, y0, 0
    placed = []
    for p in parts:
        left, right, n, hw = sym_geometry(p)
        h = n * PITCH + 1778
        w = 2 * (hw + 508) + 2 * 3302
        if cury + h > MAXH + y0:
            colx += colw + 762
            cury, colw = y0, 0
        cx = colx + 3302 + hw + 508
        cy = cury + 889 + n * PITCH // 2
        placed.append((p, cx, cy))
        cury += h
        colw = max(colw, w)
    total_w = colx + colw + 2000

    paper = "A1" if total_w < 84100 else "A0"
    body = []
    libs = []
    nets_seen = {}
    conn = []
    for p, cx, cy in placed:
        left, right, n, hw = sym_geometry(p)
        libs.append(sym_text(p, LIB + ":"))
        ref = p["ref"]
        body.append('(symbol (lib_id "%s:%s") (at %s %s 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "%s")'
                    % (LIB, ref, f(cx), f(cy), u()))
        body.append('(property "Reference" "%s" (at %s %s 0) (effects (font (size 1.0 1.0))))' % (ref, f(cx), f(cy - n * PITCH // 2 - 508)))
        body.append('(property "Value" "%s" (at %s %s 0) (effects (font (size 1.0 1.0))))' % (p["value"], f(cx), f(cy - n * PITCH // 2 - 254)))
        body.append('(property "Footprint" "%s:%s" (at %s %s 0) (effects (font (size 1.0 1.0)) (hide yes)))' % (p["fp"][0], p["fp"][1], f(cx), f(cy)))
        for _, (num, _) in enumerate(left + right):
            body.append('(pin "%s" (uuid "%s"))' % (num, u()))
        body.append('(instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))' % (PROJ, ROOT_UUID, ref))
        for side, lst in ((0, left), (1, right)):
            for k, (num, nm) in enumerate(lst):
                y = cy - (n * PITCH // 2 - PITCH // 2 - k * PITCH)
                px = cx - (hw + 508) if side == 0 else cx + (hw + 508)
                net = p["pins"].get(num)
                conn.append((ref, num, nm, net or ""))
                if net is None:
                    body.append('(no_connect (at %s %s) (uuid "%s"))' % (f(px), f(y), u()))
                    continue
                lx = px - 508 if side == 0 else px + 508
                body.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))' % (f(px), f(y), f(lx), f(y), u()))
                body.append('(global_label "%s" (shape bidirectional) (at %s %s %d) (effects (font (size 1.0 1.0)) (justify %s)) (uuid "%s"))'
                            % (net, f(lx), f(y), 180 if side == 0 else 0, "right" if side == 0 else "left", u()))
                nets_seen.setdefault(net, 0)
                nets_seen[net] += 1
    notes = [
        "USB 2-in-1-out software-controlled switch board  (CH552G + TS3USB221A + 2x TPS22916)",
        "Design source: USB_2to1_Switch_TypeC_原理图文字版.md - corrected, see REVIEW.md. Same global label = same net.",
        "All GPIO control lines: P1.5->S (divider), P1.1->ON1, P1.6->ON2, P1.4->CMD LED. GND is common, never switched.",
    ]
    txt = []
    for i, t in enumerate(notes):
        txt.append('(text "%s" (at %s %s 0) (effects (font (size 1.8 1.8)) (justify left bottom)) (uuid "%s"))' % (t, f(2000), f(1600 + i * 900), u()))

    sch = ('(kicad_sch (version 20250114) (generator "eeschema") (uuid "%s") (paper "%s") '
           '(title_block (title "USB 2-in-1-out switch") (rev "A") (comment 1 "generated from design.py")) '
           '(lib_symbols %s)%s%s)' % (ROOT_UUID, paper, "".join(libs), "".join(txt), "".join(body)))
    with open(os.path.join(OUT, PROJ + ".kicad_sch"), "w", encoding="utf-8") as fh:
        fh.write(sch)
    with open(os.path.join(OUT, LIB + ".kicad_sym"), "w", encoding="utf-8") as fh:
        fh.write('(kicad_symbol_lib (version 20241209) (generator "usb2to1_gen")%s)' % "".join(sym_text(p) for p, _, _ in placed))
    with open(os.path.join(OUT, "sym-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(sym_lib_table (version 7) (lib (name "%s") (type "KiCad") (uri "${KIPRJMOD}/%s.kicad_sym") (options "") (descr "generated")))\n' % (LIB, LIB))
    pro = os.path.join(OUT, PROJ + ".kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w", encoding="utf-8") as fh:
            fh.write('{\n  "meta": {\n    "filename": "%s.kicad_pro",\n    "version": 1\n  }\n}\n' % PROJ)
    with open(os.path.join(OUT, "connectivity.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ref", "pin", "pin_name", "net"])
        w.writerows(conn)
    print("parts", len(placed), "nets", len(nets_seen), "paper", paper, "width", total_w / 100)


ROOT_UUID = "b5c0a1e2-7a31-4c2e-9d11-5a6f0c0d2e01"
if __name__ == "__main__":
    main()
