from __future__ import annotations
import io
import zipfile
import pikepdf
import fitz


def strip_metadata(data: bytes) -> bytes:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        if "/Metadata" in pdf.Root:
            del pdf.Root["/Metadata"]
        for key in list(pdf.docinfo.keys()):
            del pdf.docinfo[key]
        out = io.BytesIO()
        pdf.save(out)
        return out.getvalue()


def merge_pdfs(files: list[bytes]) -> bytes:
    merged = pikepdf.new()
    for data in files:
        with pikepdf.open(io.BytesIO(data)) as src:
            merged.pages.extend(src.pages)
    out = io.BytesIO()
    merged.save(out)
    return out.getvalue()


def extract_images(data: bytes) -> bytes:
    doc = fitz.open(stream=data, filetype="pdf")
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for page_index in range(len(doc)):
            for img_index, img in enumerate(doc[page_index].get_images(full=True), start=1):
                base = doc.extract_image(img[0])
                count += 1
                zf.writestr(f"seite-{page_index + 1}-bild-{img_index}.{base['ext']}", base["image"])
    if count == 0:
        return b""
    return buf.getvalue()
