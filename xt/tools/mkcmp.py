import pymupdf, sys
from PIL import Image
def img(path,pg,w):
    p=pymupdf.open(path)[pg]; z=w/p.rect.width; pm=p.get_pixmap(matrix=pymupdf.Matrix(z,z)); return Image.frombytes("RGB",(pm.width,pm.height),pm.samples)
W=950
jobs={'v15':('KUNLUNV1.5.pdf','KunLun_V1.5/KunLun_V1.5_rebuilt.pdf',18),'q':('SCH_0.5青春版主板v1.0_2024-10-24.pdf','QingChun_0.5/QingChun_0.5_rebuilt.pdf',12),'v13':('SCH_KunLunV1.3.pdf','KunLun_V1.3/KunLun_V1.3_rebuilt.pdf',18)}
for tag,(o,r,n) in jobs.items():
    for i in range(n):
        a=img(o,i,W); b=img(r,i+1,W)
        im=Image.new('RGB',(W,a.height+b.height),'white'); im.paste(a,(0,0)); im.paste(b,(0,a.height)); im.save(f'_cmp/{tag}_p{i+1:02d}.png')
