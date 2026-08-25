r"""Genera el resumen para la reunion en Word.

    .pyruntime\python.exe hacer_resumen.py

Se deja como script y no como documento suelto porque el resumen se va a
rehacer despues de cada avance: cambiar una cifra aqui y volver a correrlo es
mas seguro que editar el .docx a mano y que se descuadre el formato.
"""

import pathlib
import sys

# El Python portatil no agrega la carpeta del script a sys.path (embeddable
# ._pth), asi que hay que meter tanto .libs como el propio proyecto.
AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI / ".libs"))
sys.path.insert(0, str(AQUI))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm

from docx_util import (GRIS, ROJO, TINTA, VERDE, evidencia, linea_inferior,
                       parrafo, tabla, titulo_seccion, viñeta)

# ---------------------------------------------------------------- documento --
doc = Document()
for seccion in doc.sections:
    seccion.top_margin = Cm(2.2)
    seccion.bottom_margin = Cm(2.2)
    seccion.left_margin = Cm(2.4)
    seccion.right_margin = Cm(2.4)

estilo = doc.styles["Normal"]
estilo.font.name = "Calibri"
estilo.font.size = Pt(10.5)
estilo.font.color.rgb = TINTA

parrafo(doc, "SURECONOMICS · IA Y AUTOMATIZACIÓN", tam=8.5, negrita=True,
        color=GRIS, espacio_despues=2)
p = parrafo(doc, "Revisión del plan de contenido y estado de las automatizaciones",
            tam=19, negrita=True, espacio_despues=4)
p.paragraph_format.line_spacing = 1.0
linea_inferior(parrafo(doc, "Saúl Benarroch · Especialista en IA y Automatización · "
                            "23 de agosto de 2026", tam=9.5, color=GRIS,
                       espacio_despues=10))

# -- En una frase
titulo_seccion(doc, "En una frase")
parrafo(doc,
        "Revisamos el plan de contenido de la semana y el prompt que lo generó. "
        "Los fallos que encontramos no son de estilo: son de verificación, y son "
        "exactamente los que un sistema puede impedir. Ya están construidas y "
        "probadas las dos piezas que los frenan antes de que lleguen a Edición.")

# -- Hallazgos
titulo_seccion(doc, "Qué encontramos en el plan de la semana")
parrafo(doc,
        "El documento tiene 142 piezas. Conviene decir de entrada que los textos "
        "los generó un modelo de IA y después se corrigieron a mano durante horas: "
        "los fallos son del modelo, no de quien los revisó. Por eso importan — "
        "son sistemáticos y se repiten en cada tanda.", espacio_despues=8)

tabla(doc,
      ["Hallazgo", "Cantidad", "Por qué importa"],
      [["Enlaces que son la portada de la institución, no el documento",
        "233 de 256", "Una portada no permite comprobar la cifra"],
       ["Piezas que citan a sureconomics.com como fuente",
        "3", "Es una fuente inventada, y nos nombra a nosotros"],
       ["Errores en el editorial del lunes 24",
        "6", "Incluye «35 trillones» por 35 billones, y «MFI» por FMI"],
       ["Piezas de opinión firmadas «XXX»",
        "59", "Una opinión sin autor no es opinión"],
       ["Marcadores internos «PARA MEJORAR» dentro del texto",
        "2", "Quedaron en el documento que se iba a publicar"],
       ["Decimales escritos con punto (3.8 % en vez de 3,8 %)",
        "varios", "Viola la norma que fija el propio prompt"]],
      [7.5, 2.4, 6.6])

# -- Causa
titulo_seccion(doc, "La causa está en una línea del prompt")
parrafo(doc, "El prompt pide, para cada pieza:", espacio_despues=4)
p = parrafo(doc, "«Datos impactantes usando cifras. Usar data numérica.»",
            tam=11, cursiva=True, color=ROJO, sangria=0.8, espacio_despues=6)
parrafo(doc,
        "Pero no le entrega ninguna cifra al modelo. Eso no es una instrucción de "
        "estilo: es una orden de inventar. Ningún ajuste de redacción lo corrige, "
        "porque el modelo está haciendo exactamente lo que se le pidió.")

# -- El cambio
titulo_seccion(doc, "El cambio de fondo: invertir el orden")
tabla(doc, ["", "Cómo se hace hoy", "Cómo debe hacerse"],
      [["1º", "La IA escribe la prosa con cifras inventadas",
        "El código trae las cifras de la fuente oficial"],
       ["2º", "Alguien caza las cifras a mano para cuadrarla",
        "La IA escribe la prosa alrededor de esas cifras"],
       ["3º", "Se publica y se espera que no falle nada",
        "Un auditor verifica y bloquea lo que no cuadra"]],
      [1.0, 7.7, 7.8])
parrafo(doc,
        "Con este orden, las horas de corrección manual no se reducen: desaparecen, "
        "porque no queda nada que corregir.", espacio_antes=8)

# -- Lo construido
titulo_seccion(doc, "Qué está construido y funcionando")
viñeta(doc, "El extractor. Va a la fuente oficial y trae los números con su "
            "enlace exacto. Cubre los 20 países de Latinoamérica: inflación, "
            "crecimiento, PIB, desempleo, deuda, remesas y pobreza. Ya conectado "
            "también a noticieros por RSS.",
       negritas=["El extractor."])
viñeta(doc, "El auditor. Compara la pieza escrita contra esas cifras y bloquea la "
            "que no cuadre. Es código, no IA: un modelo revisando a otro modelo "
            "comparte sus mismos puntos ciegos.",
       negritas=["El auditor."])

parrafo(doc, "Prueba real: le pasamos el editorial del lunes 24.",
        negrita=True, espacio_antes=10, espacio_despues=6)

evidencia(doc, [
    ("BLOQUEADA — 9 motivos. No llega al editor:", TINTA),
    ("  X  el numero '35' no esta en el paquete de datos", ROJO),
    ("  X  el numero '124' no esta en el paquete de datos", ROJO),
    ("  X  el numero '890.000' no esta en el paquete de datos", ROJO),
    ("  X  el numero '5,25' no esta en el paquete de datos", ROJO),
    ("  X  'trillon' traduce mal 'trillion': en español billon = 10^12", ROJO),
    ("  X  'MFI' esta mal escrito: es 'FMI'", ROJO),
    ("  X  el enlace https://www.sureconomics.com no esta en el paquete", ROJO),
    ("  X  SurEconomics no puede citarse a si mismo como fuente", ROJO),
    ("  X  el dato es de 2016 y el texto no lo dice en ninguna parte", ROJO),
])
parrafo(doc, "Nueve motivos, en menos de un segundo, sin que nadie lea nada.",
        tam=9.5, color=GRIS, espacio_antes=4)

# -- Fuentes
titulo_seccion(doc, "Dos clases de fuente, y no se mezclan")
parrafo(doc,
        "Cuando el Banco Mundial publica una cifra, la produjo la institución. "
        "Cuando un diario titula «la inflación fue de 19,9 %», esa cifra la "
        "escribió un periodista. Si la publicamos como nuestra y está mal, el "
        "error es nuestro.", espacio_despues=8)
tabla(doc, ["", "Fuente primaria", "Fuente secundaria (noticieros)"],
      [["La cifra la produjo", "La institución", "Un periodista"],
       ["¿Se publica como propia?", "Sí", "No, hay que confirmarla antes"],
       ["Sirve para", "Contexto, educación, investigación",
        "Contar el hecho citando al medio"]],
      [4.2, 6.1, 6.2])
parrafo(doc, "El sistema marca cada cifra de noticiero como no verificada y se lo "
             "advierte al editor. No es burocracia: es la diferencia entre un bot "
             "y un medio.", espacio_antes=8)

# -- Decisiones
titulo_seccion(doc, "Lo que necesitamos decidir en esta reunión")
parrafo(doc, "El sistema de etiquetas de Pablo (tipo, región, subregión, país, "
             "tópico) se adopta tal cual. Tres cosas quedan abiertas:",
        espacio_despues=8)
tabla(doc, ["Decisión", "Propuesta", "Por qué ahora"],
      [["Subtópico",
        "«Tópico» tiene 3 valores (Economía, Finanzas, Política). No hay dónde "
        "clasificar energía y commodities, comercio internacional, M&A ni "
        "tecnología. Añadir un subtópico.",
        "Cambiar la taxonomía después obliga a reclasificar todo el archivo"],
       ["Eje «vigencia»",
        "Etiquetar cada pieza como Perecedera o Permanente.",
        "Es lo que hace funcionar el pool base: se llena solo con permanentes y "
        "lo caliente entra el mismo día"],
       ["Eje «idioma»",
        "Etiquetar ES o EN desde ahora.",
        "El lanzamiento es bilingüe y el portugués entra en el segundo trimestre"]],
      [3.4, 6.4, 6.7])
parrafo(doc,
        "Una cuarta, ya resuelta y solo para confirmar: la postura del medio va en "
        "el bloque «SurEconomics:» al final de la noticia, y el cuerpo va sin "
        "postura. El mecanismo ya lo tenía previsto Pablo; lo que hicimos fue "
        "escribirlo como regla, porque el prompt actual lo dice de una forma que "
        "un modelo lee como permiso para teñir también el cuerpo.",
        espacio_antes=8)

# -- Siguiente
titulo_seccion(doc, "Dependencias y siguiente paso")
viñeta(doc, "Bloqueado por Alalza: el panel de administración llega el 1 de "
            "octubre. Mientras tanto se construye contra archivo, así que la "
            "fecha no nos detiene, pero necesitamos la especificación de cómo "
            "recibe los borradores.",
       negritas=["Bloqueado por Alalza:"])
viñeta(doc, "Siguiente pieza: el redactor, que escribe la prosa entre el "
            "extractor y el auditor. Es la única que usa IA, y ahora ya tiene "
            "las cifras verificadas de un lado y al inspector del otro.",
       negritas=["Siguiente pieza:"])
viñeta(doc, "Límite conocido: la fuente actual (Banco Mundial) publica datos "
            "anuales y con retraso. Sirve para el pool base, no para la noticia "
            "del día. Para eso hacen falta extractores de bancos centrales, país "
            "por país.",
       negritas=["Límite conocido:"])

p = parrafo(doc, "Ninguna de estas piezas publica nada. Todo entra como borrador "
                 "y lo aprueba Edición. El objetivo del auditor es que el editor "
                 "apruebe o rechace, no que reescriba.",
            tam=10.5, negrita=True, color=VERDE, espacio_antes=14)
p.alignment = WD_ALIGN_PARAGRAPH.LEFT

salida = pathlib.Path(__file__).resolve().parent / "Resumen reunion - SurEconomics.docx"
doc.save(salida)
print("Guardado:", salida)
