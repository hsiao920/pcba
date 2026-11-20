# list suspicious texts (unresolved '?' or stray non-ASCII) in a rebuilt KiCad project
import re, glob, sys

QUOTED = r'"((?:[^"\\]|\\.)*)"'
PAT = re.compile(r'\((?:text|label|global_label) ' + QUOTED + r'|\(property "(?:Value|Reference)" ' + QUOTED)
for f in sorted(glob.glob(sys.argv[1] + "/p*.kicad_sch")):
    s = open(f, encoding="utf-8").read()
    bad = set()
    for m in PAT.finditer(s):
        t = m.group(1) or m.group(2) or ""
        if "?" in t:
            bad.add(t)
        elif re.search(r"[^\x00-\x7f]", t) and not re.search(r"[一-鿿]", t) and not re.fullmatch(r"[^\x00-\x7f°±Ω%µ ]*", ""):
            if not re.fullmatch(r"[\x00-\x7f°±Ω µ]*", t):
                bad.add(t)
    if bad:
        print(f[-9:], sorted(bad)[:12])
