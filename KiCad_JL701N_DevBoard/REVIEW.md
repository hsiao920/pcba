# 原图疑点与重建限制（逐项请对照 PDF 核对）

## 01_MinSystem（PDF 第 2 页）
1. U1 为 68 脚（含 0 号焊盘 VSS(PAD)）；PDF 上下左右四边的脚在 KiCad 里统一排成左 1~34+0、右 35~68，脚号和脚名照原图抄。
2. J2（QSPI_AMOLED）原图脚号 SD1/SD2/SD3 三个都印成 5；本版顺延编号 1~17，外壳脚 0。
3. J2 的 SD0..SD3 与 MCU 的 `SD0(D7)..SD3(D4)` 名称不同；本版**假设为同一网络**（原图名称不一致）。
4. U3（GSensor，12 脚）：原图 pin 4 `NC` 画成接地、pin 10 `CSB` 悬空、pin 11 `NC` 接 VDDIO33，按图抄录，未改。INT2 经 R7（NC）到地。
5. SD 供电：原图用两个**无编号的焊接跳点**（本版 SJ1、SJ2）分别接 `SD_PG` 和 Q3 + R14 路径到 `SD_VDD`。
6. U1 pin 49 `AVSS` 与 `GND` 分开；C6、C7 接 AVSS。M1 的地「单独走线到芯片 AVSS」，本版接 GND（原图符号为普通地），请确认。
7. U1 的 VBAT、VPWR、IOVDD(VDDIO33)、IOVDD2(VDDIO18)、DCVDD 各自有去耦电容；VPWR 经 R1(0.5Ω) 接 `+5.0V`（并联 TVS D1）。
8. ERC 的 11 个 `isolated_pin_label` 警告：`KEY4/UartTX`、`Sensor_int0/1`、`D0~D3`、`WR/SYNC1`、`RD/SYNC0`、`DACRN`、`DACRP` 在本页只出现一次，原图中它们是留给底板的网络标签，不是错误。

## 02_BaseBoard（PDF 第 3 页）
1. `J19` 原图值印 `CON8`，实际画了 10 脚；按 10 脚抄。
2. `J17`（3V3）、`J18`（1V8）：脚 1~3 接 VDDIO33 / VDDIO18，**脚 4 原图疑似未接**（竖线停在第 3 脚），本版画成开放。
3. `J26`：原图值印 GND，但上方标签是 VDDIO33 且竖线延伸到脚 4；本版**四脚全接 VDDIO33**，请对照实物。
4. `J20` 耳机座：内部接点符号太密，只转录 `2 → R12(100R) → SPK+`、`3 → SPK-`，脚 1、4 留空，**不完整**。
5. `USB1`：原图 4 个外壳脚均印 6；本版顺延编号 6~9，全接 GND；ID(4) 与 GND(5) 接同一点。
6. `J15`：脚 4 与 6 同为 `PA_IN+`，脚 8 与 10 同为 `PA_IN-`（原图两点相连）。
7. `J4`（DCON42）：奇数脚在右、偶数脚在左，按原图；脚 1 = PVCC、脚 3 = VDDIO33。
8. SD 供电：`SD_PG` 在原图是**直接接到 SD_VDD 节点**，本版用一个 0Ω 跳线 `SJ_PG` 表示该连线；R11（NC）接在 SD_VDD 与卡检测脚 CD(10) 之间。
9. `Q1`（2301）+ D2 + D3 + R6 + R7 为功放电源切换：USB 无电时 Q1 导通，PVCC = VBAT；有 USB 时 Q1 关断，PVCC 经 D3 取自 VUSB。注释写明「实际应用 VBAT 和 PVCC 短接」。
10. `MCU_BAT` 与 `VBAT` 之间是 JP2（电流测试跳线）；`VUSB` 与 `VPWR` 之间是 JP1。
