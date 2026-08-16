import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from backend.app.main import app

client=TestClient(app)

def pdf_bytes():
    fd,path=tempfile.mkstemp(suffix='.pdf'); os.close(fd)
    c=canvas.Canvas(path); c.setFont('Helvetica-Bold',18); c.drawString(72,760,'1. Testdokument'); c.setFont('Helvetica',12); c.drawString(72,730,'Dies ist eingebetteter PDF Text mit 12345.'); c.save()
    data=Path(path).read_bytes(); os.unlink(path); return data

def test_health():
    assert client.get('/api/health').status_code==200

def test_reject_non_pdf():
    r=client.post('/api/documents',files={'file':('x.txt',b'hello','text/plain')})
    assert r.status_code==415

def test_upload_pdf():
    r=client.post('/api/documents',files={'file':('test.pdf',pdf_bytes(),'application/pdf')})
    assert r.status_code==202
    doc=r.json(); assert doc['filename']=='test.pdf'

def test_export_content_disposition_escapes_quotes():
    filename='weird "quoted" file.pdf'
    r=client.post('/api/documents',files={'file':(filename,pdf_bytes(),'application/pdf')})
    doc_id=r.json()['id']
    r=client.get(f'/api/documents/{doc_id}/export/markdown')
    assert r.status_code==200
    disposition=r.headers['content-disposition']
    fallback=disposition.split('filename="',1)[1].split('"; filename*=',1)[0]
    assert '"' not in fallback
    assert "filename*=UTF-8''" in disposition
