r"""Maqueta en Word las piezas de entrega/ para mandarlas a Edicion."""
import json, pathlib, sys
AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI / ".libs")); sys.path.insert(0, str(AQUI))
from docx import Document
from docx.shared import Cm, Pt
from docx_util import GRIS, TINTA, VERDE, linea_inferior, parrafo, sombrear, titulo_seccion

ORDEN = [("1-hanke", "Steve Hanke y la dolarización"),
         ("2-terremoto", "Dos meses del terremoto: el golpe económico"),
         ("3-huntoil", "Hunt Oil y Pdvsa"),
         ("4-ministra", "La ministra de Hidrocarburos en Houston"),
         ("5-iran", "Irán y el castigo económico")]

doc = Document()
for s in doc.sections:
    s.top_margin = s.bottom_margin = Cm(2.0); s.left_margin = s.right_margin = Cm(2.4)
e = doc.styles["Normal"]; e.font.name = "Calibri"; e.font.size = Pt(10.5); e.font.color.rgb = TINTA

parrafo(doc, "SURECONOMICS · BORRADORES PARA EDICIÓN", tam=8.5, negrita=True, color=GRIS, espacio_despues=2)
p = parrafo(doc, "Cinco piezas — 24 de agosto de 2026", tam=19, negrita=True, espacio_despues=4)
p.paragraph_format.line_spacing = 1.0
linea_inferior(parrafo(doc, "Generadas por el sistema de redacción asistida · "
                            "Ninguna está publicada: todas entran como borrador",
                       tam=9.5, color=GRIS, espacio_despues=10))

for archivo, titulo in ORDEN:
    ruta = AQUI / "final" / f"{archivo}.txt"
    if not ruta.exists():
        continue
    doc.add_page_break()
    titulo_seccion(doc, titulo)
    caja = doc.add_table(rows=1, cols=1); caja.style = "Table Grid"
    c = caja.rows[0].cells[0]; c.width = Cm(16.5); sombrear(c, "FBFAF8")
    c.paragraphs[0]._p.getparent().remove(c.paragraphs[0]._p)
    for linea in ruta.read_text(encoding="utf-8").strip().split("\n"):
        pr = c.add_paragraph()
        pr.paragraph_format.space_after = Pt(5); pr.paragraph_format.line_spacing = 1.15
        if not linea.strip():
            continue
        r = pr.add_run(linea)
        if linea.startswith("["):
            r.font.size, r.font.color.rgb, r.font.bold = Pt(8.5), GRIS, True
        elif linea.isupper() and len(linea) > 25:
            r.font.size, r.font.bold = Pt(13), True
        elif linea.startswith("SurEconomics:"):
            r.font.size, r.font.bold, r.font.color.rgb = Pt(10.5), True, VERDE
        elif linea.startswith(("Sacado de:", "—")):
            r.font.size, r.font.color.rgb = Pt(8.5), GRIS
        else:
            r.font.size = Pt(10.5)
    datos = json.loads((AQUI / "final" / f"{archivo}.json").read_text(encoding="utf-8"))
    parrafo(doc, "APROBADA por el auditor" if not datos["bloqueada"] else "BLOQUEADA",
            negrita=True, tam=9, color=VERDE, espacio_antes=8)

salida = AQUI / "SurEconomics - 5 borradores 24-08-2026 (v6).docx"
doc.save(salida)
print("Guardado:", salida)
