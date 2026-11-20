#!/usr/bin/env bash
# Rebuild all three KiCad projects from the PDFs and check them (ERC + netlist-vs-PDF).
cd "$(dirname "$0")/.."
export PYTHONPATH=tools
KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
build() {   # pdf outdir adapter aliasglobal
  local pdf="$1" out="$2"
  export XT_ADAPTER="$3"; export XT_ALIAS_GLOBAL="$4"
  [ -z "$3" ] && unset XT_ADAPTER
  [ -z "$4" ] && unset XT_ALIAS_GLOBAL
  python -X utf8 tools/gen_kicad.py "$pdf" "$out" "$out" || return 1
  "$KC" sch erc --severity-all --format json -o "$out/erc.json" "$out/$out.kicad_sch" >/dev/null 2>&1
  python -X utf8 -c "
import json,collections
d=json.load(open('$out/erc.json',encoding='utf-8'))
c=collections.Counter((v['severity'],v['type']) for s in d['sheets'] for v in s['violations'])
print('$out ERC', dict(c))"
  python -X utf8 tools/verify_net.py "$pdf" "$out/$out.kicad_sch" | head -3
  "$KC" sch export pdf -o "$out/${out}_rebuilt.pdf" "$out/$out.kicad_sch" >/dev/null 2>&1
  "$KC" sch export netlist --format kicadsexpr -o "$out/$out.net" "$out/$out.kicad_sch" >/dev/null 2>&1
  "$KC" sch export bom -o "$out/${out}_bom.csv" "$out/$out.kicad_sch" >/dev/null 2>&1
}
build KUNLUNV1.5.pdf KunLun_V1.5 "" ""
build SCH_KunLunV1.3.pdf KunLun_V1.3 v13_adapter ""
build "SCH_0.5青春版主板v1.0_2024-10-24.pdf" QingChun_0.5 jlc_adapter 1
