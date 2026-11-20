# KunLun_V1.3.kicad_sch vs KunLun_V1.5.kicad_sch

## Parts only in A (4)

- C2332  4.7nF  C0402
- FPC4  ~  0.3mm_fpc_39p
- R2324  10K  R0402
- R2360  100K  R0402

## Parts only in B (28)

- C10000  4.7uF  C0402
- C10001  220nF  C0402
- C10002  470pF  C0402
- C10003  4.7uF  C0402
- C10004  100nF  C0402
- C10005  47pF  C0402
- C10006  100nF  C0402
- C9999  100nF  C0402
- FPC1  ~  0.3mm_fpc_39p
- R10000  0R  R0402
- R10001  0R  R0805
- TP4028  TP  
- TP4029  TP  
- TP4030  TP  
- TP4031  TP  
- TP4032  TP  
- TP4033  TP  
- TP4034  TP  
- TP4035  TP  
- TP4036  TP  
- TP4037  TP  
- TP4038  TP  
- TP4039  TP  
- TP4040  TP  
- TP4041  TP  
- TP4042  TP  
- TP4043  TP  
- TP4044  TP  

## Value changes (12)

- R2320: 220K -> 150K
- R2322: 47K -> 33K
- R2532: 5.1K -> 7.15K
- R2533: 12K -> 30K
- R2540: 1% -> 10K
- R7261: 2R -> 6.2R
- R7262: 2R -> 6.2R
- TP4010: ~ -> TP
- U2303: default R=0R,, delay time=0ms -> ETA3448
- U2306: SGM804-2.93YN5G/TR -> SGM809B
- U2310: default R=0R,, delay time=0ms -> SY8089A1AAC
- U4014: ~ -> GXHTC3

## Connectivity differences among common parts (15 nets)

- A net `GND` / B net `GND`: only-in-A ['U2306.3', 'U4014.2'] ; only-in-B ['C2336.2', 'U2306.1', 'U4014.6']
- A net `I2C4_SCL_M0` / B net `I2C4_SCL_M0`: only-in-A ['U4014.6'] ; only-in-B ['U4014.3']
- A net `I2C4_SDA_M0` / B net `I2C4_SDA_M0`: only-in-A ['U4014.1'] ; only-in-B ['U4014.4']
- A net `LED_GR` / B net `LED_GR`: only-in-A [] ; only-in-B ['LED2.3']
- A net `LED_OR` / B net `LED_OR`: only-in-A [] ; only-in-B ['LED2.2']
- A net `Net-(C2344-Pad1)` / B net `VDD_LOGIC`: only-in-A [] ; only-in-B ['C1007.1', 'C1008.1', 'C1009.1', 'C1010.1', 'C1011.1', 'C2336.1', 'L2304.2', 'R2336.1']
- A net `Net-(U2306-OUT)` / B net `GND`: only-in-A [] ; only-in-B ['C1000.2', 'C1001.2', 'C1002.2', 'C1003.2', 'C1004.2', 'C1005.2', 'C1006.2', 'C1007.2']
- A net `RESET` / B net `RESET`: only-in-A [] ; only-in-B ['U2306.3']
- A net `VCC5V0_USB` / B net `VCC5V0_USB`: only-in-A ['C2520.1', 'C2521.1', 'R2530.1', 'U2500.3'] ; only-in-B []
- A net `VCC_3V3` / B net `VCC_3V3`: only-in-A ['U4014.5'] ; only-in-B ['U4014.1']
- A net `VDD_LOGIC` / B net `VDD_LOGIC`: only-in-A ['C2336.2'] ; only-in-B ['C2344.1', 'R2336.2', 'R2340.1']
- A net `unconnected-(LED2-Pad2)` / B net `LED_OR`: only-in-A [] ; only-in-B ['U1000.V7']
- A net `unconnected-(LED2-Pad3)` / B net `LED_GR`: only-in-A [] ; only-in-B ['U1000.U7']
- A net `unconnected-(U4014-NC1-Pad3)` / B net `I2C4_SCL_M0`: only-in-A [] ; only-in-B ['FPC3.3', 'R1802.1', 'U1000.E20']
- A net `unconnected-(U4014-NC2-Pad4)` / B net `I2C4_SDA_M0`: only-in-A [] ; only-in-B ['FPC3.2', 'R1803.1', 'U1000.E19']
