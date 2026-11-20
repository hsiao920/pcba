# JL701N 手表开发板 KiCad 原理图重建（待核对版）

来源：`D:\Users\jacky\jieli\doc\jieli doc\硬件资料\JL701N手表开发板原理图与PCB资料（共5页）.pdf`
第 2 页 = 最小系统（`01_MinSystem`），第 3 页 = 开发底板（`02_BaseBoard`）。第 1 页是 IO 分配表，第 4、5 页是 PCB 图，未转换。

## 怎么开
- 开 `01_MinSystem\JL701N_MinSystem.kicad_pro` 或 `02_BaseBoard\JL701N_BaseBoard.kicad_pro`。
- 两页分成两个独立专案：两页的位号会重复（例如 R1、C1 在两页是不同零件），且同名网络不应合并。
- 每个零件一张卡片；每个已连接脚位接一小段线加全域标签，**同名全域标签 = 同一网络**。开放脚位画无连接叉。
- `connectivity.csv`：位号／脚位／网络对照表。`*_preview.pdf`：KiCad 匯出的图。

## 验证结果（`kicad-cli` 10.0.7）
| 专案 | 零件 | 脚位 | 已连接 | 与手抄数据逐脚比对 | ERC |
|---|---|---|---|---|---|
| 01_MinSystem | 75 | 275 | 268 | 差异 0 | 11 个警告（只出现一次的网络，见 REVIEW） |
| 02_BaseBoard | 68 | 421 | 413 | 差异 0 | 无 |

「差异 0」只证明**生成的原理图与我手抄的表一致**，不证明手抄本身与 PDF 一致。抄录时已逐块对照 PDF 放大图，但仍是人工转录。

## 限制
- 人工转录，不是原厂 EDA 档转换。
- 所有脚位类型为 passive，ERC 无法验证供电和输出冲突。
- 元件符号都是矩形加脚名，没有指定封装，没有 PCB。
- 不得直接当作可生产设计。

## 重新生成
`tools\devboard_data.py` 是手抄数据；`python tools\gen_devboard.py --verify` 重建两个专案并用 kicad-cli 比对。
修数据后重跑即可。

## 与我们控制板比较电源架构（这份重建的主要用途）
- 开发板：电池（BT1）→ 经 JP2 → MCU 的 **VBAT 脚直接吃电池**；内部 Buck 产生 DCVDD，内部 LDO 产生 IOVDD（VDDIO33）。VPWR 只接 USB 5V 充电输入（R1 0.5Ω + TVS）。
- 我们的控制板：电池 → SY7011 升压到 5V（常开）→ ME6231 LDO → VDD_3V3 → MCU 的 VBAT。
- 开发板的 Flash 供电 `V_SFC` 来自 PC8（可软件关断）；我们控制板的 Flash 接 VDD_3V3 常开。
- 开发板的 SD NAND 供电有 MOS 开关（Q3，由 SD_EN 控制）。
