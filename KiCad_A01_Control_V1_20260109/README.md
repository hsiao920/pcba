# A01 補水棒控制板 KiCad 原理圖重建（待核對版）
開啟 A01_Control.kicad_pro -> 原理圖 -> 雙擊總覽子頁。六子頁對應原PDF，總覽多一頁。
使用可編輯原生元件、導線、全域標籤；相同全域標籤即為同網路。為方便查線採逐元件連線卡式布局，不複製原PDF的位置。
來源：D:\Users\jacky\zs\datasheet\SCH_控制板_V1.0_2026-01-09.pdf。主控JL7012F6；圖框版本V0.2。原檔未修改。
專案 sym-lib-table 已註冊 A01_Source.kicad_sym，各符號亦內嵌於原理圖。
connectivity.csv 為腳位/網路對照，source_manifest.json 為抄錄資料與來源SHA256。
這是人工重建待核對版，不是PADS/EDA原生檔轉換。所有封裝留空、未建立PCB；不得直接當作可生產設計。
符號腳位先採passive電氣型態，ERC不能驗證供電和輸出衝突。不同寫法電源名稱未擅自合併。
紅叉/斜線的DNP意圖不明，保留全部元件，Review屬性標記已注意到的紅記（非完整DNP清單）。
MOS/天線等原圖未印腳位號者採本地邏輯編號，詳REVIEW.md。製板前須原廠資料核對。
KiCad學習：E編輯元件、W連線、全域標籤跨頁連接；先核對原理圖/ERC，再指定封裝、更新PCB、擺件走線與DRC。
