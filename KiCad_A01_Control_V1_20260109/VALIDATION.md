# 檢查結果
KiCad CLI 10.0.7 可讀取專案、匯出全部7頁PDF與XML網表。
296元件、792腳位；所有已連接腳位的匯出網路與人工抄錄表一致，差異0。
來源PDF文字獨立擷取的266個元件編號無遺漏；另30個黏在數值/圖形中的編號經圖面補入。
原理圖ERC：0 errors、1 warning（U29 AUX僅接一腳，原圖即如此）；沒有隱藏或排除該警告。
注意所有元件電氣腳位型態為passive，以上不是完整電氣驗證，不能據此認定可製板。
已查看輸出MCU及驅動頁與全頁縮圖；來源原圖的幾處模糊/矛盾另見REVIEW.md。
詳細資料見validation/summary.json、validation/erc.json、connectivity.csv。
