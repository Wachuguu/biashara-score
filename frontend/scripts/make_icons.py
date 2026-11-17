# Regenerates public/icons/*. Usage: python scripts/make_icons.py public/icons  (needs Pillow)
import sys, math
from PIL import Image, ImageDraw
out = sys.argv[1]
MAIZE=(242,194,48,255); INK=(20,33,61,255)
def icon(size, maskable=False, s=4):
    S=size*s
    im=Image.new("RGBA",(S,S),MAIZE)
    d=ImageDraw.Draw(im)
    safe = 0.62 if maskable else 0.78   # content box as share of icon
    box=S*safe; cx=S/2; cy=S/2+box*0.16
    r=box/2; w=box*0.17
    # track arc (lighter ink), then score fill ~75%
    track=(189,155,51,255)
    bb=[cx-r,cy-r,cx+r,cy+r]
    d.arc(bb,180,360,fill=track,width=int(w))
    d.arc(bb,180,180+180*0.74,fill=INK,width=int(w))
    for ang in (180,180+180*0.74):  # round caps
        a=math.radians(ang); rr=r-w/2
        x=cx+rr*math.cos(a); y=cy+rr*math.sin(a)
        d.ellipse([x-w/2,y-w/2,x+w/2,y+w/2],fill=INK)
    # needle hub + needle to score
    a=math.radians(180+180*0.74); L=r*0.62
    d.line([cx,cy,cx+L*math.cos(a),cy+L*math.sin(a)],fill=INK,width=int(w*0.45))
    hub=w*0.55; d.ellipse([cx-hub,cy-hub,cx+hub,cy+hub],fill=INK)
    # baseline (shop counter)
    d.rounded_rectangle([cx-r,cy+w*0.9,cx+r,cy+w*0.9+w*0.5],radius=w*0.25,fill=INK)
    if not maskable and size>=64:
        pass
    return im.resize((size,size),Image.LANCZOS)
icon(192).save(f"{out}/icon-192.png")
icon(512).save(f"{out}/icon-512.png")
icon(512,True).save(f"{out}/icon-maskable-512.png")
icon(180).convert("RGB").save(f"{out}/apple-touch-icon.png")
icon(32).save(f"{out}/favicon-32.png")
