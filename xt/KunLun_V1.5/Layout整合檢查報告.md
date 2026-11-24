# KunLun V1.5：線路圖 + Layout 整合與檢查報告（2026-11-24）

來源
- Layout：`mirror\kunlunv1.5.2-H`（PADS 二進位 `.pcb` → PADS ASCII → KiCad 10 匯入的 `kunlunv1.5.2-H_1\kunlunv1.5.2-H.kicad_pcb`）
- 線路圖：本資料夾 `KunLun_V1.5.kicad_sch`（由 KUNLUNV1.5.pdf 重建）

## 本資料夾新增／更新的檔案
| 檔案 | 說明 |
|---|---|
| `KunLun_V1.5.kicad_pcb` | 整合後的 PCB（與專案同名，開專案即可進 PCB 編輯器） |
| `KunLun.pretty\` | 從 PCB 取出的 34 種封裝，線路圖與 PCB 共用 |
| `fp-lib-table` | 封裝庫設定（`KunLun` → `KunLun.pretty`） |
| `KunLun_V1.5.kicad_dru`、`.kicad_pro` | 帶入匯入專案的自訂規則與板子設定 |
| `drc.json`、`drc_parity.json`、`erc.json` | 最後一次 DRC / 線路圖一致性 / ERC 結果 |

## 做了什麼
1. 線路圖 383 顆零件的 `Footprint` 欄位全部改成 `KunLun:<封裝名>`（含原本缺的 66 顆）。
2. 修了線路圖 4 處錯誤（對照 PCB 與原 PDF 後確認，見下）。
3. PCB 的 4 顆 BGA（U1000 SoC、U4000 eMMC、U3200/U3201 DDR）匯入後腳位是流水號 1..N 且沒有網路：依走線接觸位置反推球名，改回 A1、Y5 這類球名，並補上網路（比對符合率 U1000 299/303、DDR 91/94、eMMC 30/34）。
4. PCB 元件的 Value 改成線路圖的值、12 顆 DNP 依線路圖同步。

## 線路圖修正（原重建有誤）
| 位置 | 原本 | 改成 | 依據 |
|---|---|---|---|
| p11 U2500 第 5 腳、C10003/4/5、C2525 第 2 腳 | VCC_BAT | GND | PCB + 原 PDF（GND 符號被誤判成 VCC_BAT） |
| p11 R2550 第 2 腳、TP4017 | 懸空 | VCC_BAT | PCB + 原 PDF |
| p11 D2511 / SW1 | D2511 誤帶 4 腳、SW1 只有 1、3 腳 | D2511 為 2 腳；SW1 補 2、4 腳 | PCB 腳位、原 PDF |
| p10 C2300 | 腳號「10V」 | 腳號 2 | 規格文字誤當腳號 |
| p16 FPC2 第 14/20 腳 | CLKP 接在第 20 腳、第 14 腳空 | 第 14 腳 = MIPI_DSI_TX0_CLKP；第 20 腳 = VCC_3V3 | PCB + 原 PDF |

## 檢查結果
- 網路比對（線路圖 vs PCB，以腳位群組比對，不看網路名稱）：249 條多腳網路全部一致，僅剩下面「已知差異」。
- ERC：0 錯誤（警告 331，皆為重建時的懸空線頭／標籤類，不影響連線）。
- 線路圖一致性（DRC parity）：不一致 404 筆，內容為網路命名不同（PCB 為 PADS 自動名 N2xxxxxx，線路圖為 Net-(...)，屬命名差異）、PCB 元件缺 `Package` 欄位（兩項皆為顯示數量上限 199，實際可能更多）、PCB 多 6 顆。
- DRC：以此板原設定仍有大量違規（clearance、線寬、孔徑、絲印等，報告每類顯示上限 199）；151～153 個未連接項目，多數為 GND / VCC_DDR 銅皮與過孔連通性（匯入後銅皮邊界／填充與原軟體不同所致）。**匯入板只能當參考，不能直接拿去出 Gerber**，要先在 KiCad 內逐項確認。

## 已知差異（需人工確認）
1. PCB 比線路圖多 6 顆：C10007（GND–UV_RESET）、C10008（GND–RGB_RESET）、C10009/C10010（GND–MIPI_CSI_CLK0/1，EMI 電容）、R10002/R10003（MIPI_CSI_CLK1/0 串聯電阻）。線路圖 V1.5 沒有，應是 Layout 版本 1.5.2-H 的修改。
2. 因上一項，SoC 的 MIPI_CSI_CLK0/1（U1000 V21、W21）在 PCB 上經電阻才到 FPC1，與線路圖直連不同。
3. 線路圖 LED4（UV_LED）只有 1、3 腳，PCB 第 2 腳接 GND（散熱焊盤）。
4. U4000（eMMC）線路圖只畫出 32 個有連線的球，其餘球在 PCB 上是無網路狀態。
