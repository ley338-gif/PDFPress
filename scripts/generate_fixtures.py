from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image, ImageDraw, ImageFont
import fitz

OUT=Path(__file__).parents[1]/'tests'/'fixtures'; OUT.mkdir(parents=True,exist_ok=True)

def digital(path:Path, title='Digitales Testdokument'):
    c=canvas.Canvas(str(path),pagesize=A4)
    for n in range(1,4):
        c.setFont('Helvetica-Bold',18); c.drawString(72,780,f'{n}. {title}')
        c.setFont('Helvetica',11); c.drawString(72,750,'Originaltreue 12345 – Zahlen und Namen dürfen nicht verändert werden.')
        c.drawString(72,730,'- Erster Punkt'); c.drawString(72,712,'- Zweiter Punkt'); c.showPage()
    c.save()

def scan(path:Path):
    img=Image.new('RGB',(1240,1754),'white'); d=ImageDraw.Draw(img); d.text((120,180),'Scan Testdokument',fill='black'); d.text((120,250),'OCR soll diesen Text 67890 erkennen.',fill='black'); img.save(path,'PDF',resolution=150)

def hybrid(path:Path):
    tmp1=OUT/'_d.pdf'; tmp2=OUT/'_s.pdf'; digital(tmp1,'Hybrid digital'); scan(tmp2)
    out=fitz.open(); out.insert_pdf(fitz.open(tmp1),from_page=0,to_page=0); out.insert_pdf(fitz.open(tmp2)); out.save(path); tmp1.unlink(); tmp2.unlink()

digital(OUT/'digital-text.pdf')
scan(OUT/'scan.pdf')
hybrid(OUT/'hybrid.pdf')
digital(OUT/'headings-lists.pdf','1. Überschrift und Listen')
digital(OUT/'table.pdf','Tabelle: A | B | C')
print('fixtures generated in',OUT)
