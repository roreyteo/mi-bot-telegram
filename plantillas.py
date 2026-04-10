import io, textwrap
from PIL import Image, ImageDraw, ImageFont

PALETAS = [
    {"fondo": (15,15,35),   "acento": (120,80,220),  "texto": (240,230,255)},
    {"fondo": (10,30,50),   "acento": (0,150,200),   "texto": (200,240,255)},
    {"fondo": (30,15,15),   "acento": (200,60,60),   "texto": (255,230,220)},
    {"fondo": (10,35,20),   "acento": (40,180,100),  "texto": (210,255,230)},
    {"fondo": (40,30,10),   "acento": (210,160,30),  "texto": (255,245,200)},
    {"fondo": (30,10,35),   "acento": (180,50,180),  "texto": (255,220,255)},
]
ANCHO, ALTO = 1080, 1080

def _fuente(size):
    for ruta in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                 "assets/fuente.ttf"]:
        try:
            return ImageFont.truetype(ruta, size)
        except:
            continue
    return ImageFont.load_default()

def _fondo(draw, paleta):
    f, a = paleta["fondo"], paleta["acento"]
    for y in range(ALTO):
        t = y / ALTO
        draw.line([(0,y),(ANCHO,y)], fill=(
            int(f[0]+(a[0]-f[0])*t*0.3),
            int(f[1]+(a[1]-f[1])*t*0.3),
            int(f[2]+(a[2]-f[2])*t*0.3)))

def _deco(draw, paleta):
    a = paleta["acento"]
    draw.rectangle([(0,0),(ANCHO,8)], fill=a)
    draw.rectangle([(0,ALTO-8),(ANCHO,ALTO)], fill=a)
    draw.ellipse([(ANCHO-200,-200),(ANCHO+200,200)], fill=a)

def _bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()

def generar_plantillas_capitulo(titulo, idea, moraleja, idx=0):
    p = PALETAS[idx % len(PALETAS)]
    imgs = []

    img1 = Image.new("RGB",(ANCHO,ALTO))
    d1 = ImageDraw.Draw(img1)
    _fondo(d1,p); _deco(d1,p)
    d1.text((60,120), f"CAPÍTULO {idx+1}", font=_fuente(28), fill=p["acento"])
    y=200
    for l in textwrap.wrap(titulo.upper(), width=22)[:3]:
        d1.text((60,y), l, font=_fuente(52), fill=p["texto"]); y+=70
    d1.rectangle([(60,y+20),(200,y+24)], fill=p["acento"])
    y+=60
    for l in textwrap.wrap(f'"{idea}"', width=30)[:6]:
        d1.text((60,y), l, font=_fuente(34), fill=p["texto"]); y+=48
    imgs.append(_bytes(img1))

    img2 = Image.new("RGB",(ANCHO,ALTO))
    d2 = ImageDraw.Draw(img2)
    _fondo(d2,p); _deco(d2,p)
    d2.text((40,60), '"', font=_fuente(180), fill=p["acento"])
    lineas = textwrap.wrap(moraleja, width=26)
    y=(ALTO-len(lineas)*60)//2
    for l in lineas[:8]:
        bbox=d2.textbbox((0,0),l,font=_fuente(42))
        d2.text(((ANCHO-(bbox[2]-bbox[0]))//2, y), l, font=_fuente(42), fill=p["texto"]); y+=60
    d2.text((60,ALTO-80), f"— {titulo[:40]}", font=_fuente(26), fill=p["acento"])
    imgs.append(_bytes(img2))

    img3 = Image.new("RGB",(ANCHO,ALTO))
    d3 = ImageDraw.Draw(img3)
    d3.rectangle([(0,0),(ANCHO,ALTO)], fill=p["fondo"])
    d3.rectangle([(0,0),(12,ALTO)], fill=p["acento"])
    d3.text((60,100), "✦  IDEA CLAVE", font=_fuente(24), fill=p["acento"])
    d3.rectangle([(60,145),(ANCHO-60,148)], fill=p["acento"])
    y=200
    for l in textwrap.wrap(' '.join(idea.split()[:20]), width=18)[:5]:
        d3.text((60,y), l, font=_fuente(56), fill=p["texto"]); y+=75
    imgs.append(_bytes(img3))

    return imgs
