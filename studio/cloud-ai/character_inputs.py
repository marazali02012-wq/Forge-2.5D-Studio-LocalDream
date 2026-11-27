"""Original transparent silhouettes for the reconstruction regression set."""
from pathlib import Path
from PIL import Image, ImageDraw
import sys

def draw(folder):
    roles = ['astronaut','mage','robot','guard','archer','miner','pilot','knight','healer','scout']
    palettes = ['#dae3ef','#7759ba','#5999aa','#b74f36','#497d4a','#c68c47','#527eab','#798aa1','#e8d6b4','#52695c']
    for i, (role, color) in enumerate(zip(roles, palettes)):
        img = Image.new('RGBA',(384,448))
        d = ImageDraw.Draw(img)
        cx = 192
        shoulder = [48,33,58,53,35,50,39,51,36,32][i]
        hip = [37,42,36,40,25,41,32,39,41,27][i]
        top = [158,144,174,157,151,176,160,152,148,142][i]
        for s in (-1,1):
            ankle = cx+s*(hip+7)
            d.line([(cx+s*hip//2,277),(ankle,379)],fill='#35465b',width=24)
            d.rounded_rectangle((ankle-17,367,ankle+17,390),8,fill=color)
            wrist = cx+s*(shoulder+22)
            d.line([(cx+s*shoulder,top+10),(wrist,top+63),(wrist+s*6,top+97)],fill=color,width=23)
            d.ellipse((wrist+s*6-11,top+87,wrist+s*6+11,top+109),fill='#bc947d')
        d.polygon([(cx-shoulder,top),(cx,top-12),(cx+shoulder,top),(cx+hip,278),(cx-hip,278)],fill=color)
        d.rectangle((cx-hip,250,cx+hip,262),fill='#343e4c')
        if role in ('mage','healer'):
            d.polygon([(cx-24,231),(cx+24,231),(cx+52,346),(cx-51,346)],fill=color)
        d.rounded_rectangle((cx-32,top-82,cx+32,top-7),16 if role!='robot' else 3,fill='#ceb095')
        if role=='mage':
            d.polygon([(cx-47,top-58),(cx+8,top-120),(cx+43,top-58)],fill=color)
        elif role in ('robot','astronaut','pilot','knight'):
            d.rounded_rectangle((cx-38,top-86,cx+38,top-12),20 if role!='robot' else 3,fill=color)
            d.rounded_rectangle((cx-28,top-60,cx+28,top-37),5,fill='#234050')
            d.line((cx-20,top-49,cx+16,top-49),fill='#83dae4',width=3)
        else:
            d.pieslice((cx-36,top-89,cx+36,top-34),180,360,fill=color)
            for x in [cx-12,cx+12]: d.ellipse((x-2,top-50,x+2,top-45),fill='#333644')
        if role in ('guard','knight'):
            d.polygon([(110,208),(147,199),(151,248),(130,271),(110,249)],fill='#617381')
        if role in ('mage','healer','miner','archer'):
            d.line((268,146,263,342),fill='#755643',width=8)
            if role=='miner': d.arc((241,136,296,181),190,345,fill='#97a7a9',width=9)
            elif role=='archer': d.arc((241,147,295,294),260,100,fill='#af8650',width=6)
            else: d.ellipse((257,130,280,153),fill='#9bcae7')
        d.polygon([(cx,top+15),(cx+10,top+27),(cx,top+42),(cx-10,top+27)],fill='#d9c17b')
        img.save(folder/(role+'.png'))

if __name__=='__main__':
    dest=Path(sys.argv[1]);dest.mkdir(parents=True,exist_ok=True);draw(dest)
