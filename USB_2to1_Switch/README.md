# USB 2进1出 软件可控切换板 (CH552G + TS3USB221A + 2×TPS22916)

| 文件 | 内容 |
|---|---|
| `USB_2to1_Switch.kicad_pro` | KiCad 项目(用 KiCad 10 打开) |
| `USB_2to1_Switch.kicad_sch` / `_sch.pdf` | 原理图(卡片式,同名全局标签=同网络) |
| `USB_2to1_Switch.kicad_pcb` | PCB(70×55mm,2 层,上下层 GND 铺铜) |
| `USB_2to1_Switch_layout_top.pdf` / `_bottom.pdf` | 上/下层 layout |
| `USB_2to1_Switch_top.png` / `_bottom.png` | 3D 渲染 |
| `fab/` | Gerber、钻孔、位置文件、BOM (**未确认前不要打样**) |
| `REVIEW.md` | 与规格书不符的修正与待确认事项 (**先读这份**) |
| `connectivity.csv` | 每个元件脚位与网络对照 |
| `tools/` | 产生器: `design.py`(唯一的数据来源)、`gen_sch.py`、`build_pcb.py`、`route.py`、`apply_routes.py`、`placement.py` |

重新产生:
1. 改 `tools/design.py`(零件/网络)或 `tools/placement.py`(摆位)
2. `python tools/gen_sch.py`
3. `"C:\Program Files\KiCad\10.0\bin\python.exe" tools/build_pcb.py`
4. `python tools/route.py`(约 1 分钟)
5. `"C:\Program Files\KiCad\10.0\bin\python.exe" tools/apply_routes.py`

`USB_2to1_Switch_placed.*`、`USB_2to1_Switch_nozone.*`、`nz_*.pdf`、`routed.pdf`、`placed_top.pdf`、`drc_placed.json` 是中间产物,可删除。
