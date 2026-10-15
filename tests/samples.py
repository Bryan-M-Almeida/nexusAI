"""Small valid sample files for the tests (PDF with a real xref table, DOCX, EPUB, ZIP)."""
import zipfile
from pathlib import Path


def make_pdf(path: Path, lines: list[str]) -> Path:
    content = "BT /F1 16 Tf 20 160 Td 18 TL " + " ".join(f"({x}) Tj T*" for x in lines) + " ET"
    objs = ["<</Type/Catalog/Pages 2 0 R>>", "<</Type/Pages/Kids[3 0 R]/Count 1>>",
            "<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            f"<</Length {len(content)}>>\nstream\n{content}\nendstream", "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<</Size {len(objs) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)
    return path


def make_docx(path: Path, paragraphs: list[str]) -> Path:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")
    return path


def make_epub(path: Path, chapters: list[tuple[str, str]]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        items = "".join(f'<item id="c{i}" href="c{i}.xhtml"/>' for i in range(len(chapters)))
        spine = "".join(f'<itemref idref="c{i}"/>' for i in range(len(chapters)))
        z.writestr("OEBPS/content.opf", f"<package><manifest>{items}</manifest><spine>{spine}</spine></package>")
        for i, (title, text) in enumerate(chapters):
            z.writestr(f"OEBPS/c{i}.xhtml", f"<html><head><title>x</title></head><body><h1>{title}</h1><p>{text}</p></body></html>")
    return path
