r"""Convierte una pieza escrita en la lamina de Instagram.

    from motor import lamina
    png = lamina.hacer(foto, titulo, resumen, lugares, "post.png")

POR QUE ESTE ARCHIVO Y NO METERLO EN plantillas/post.py

Porque son dos trabajos distintos y mezclarlos se paga. post.py DIBUJA: recibe
un titular, una categoria y una foto, y devuelve un PNG. Este archivo DECIDE:
que categoria toca, y que titular cabe.

EL TITULAR DEL PANEL NO SIRVE PARA LA LAMINA. En el sitio va en mayusculas y
largo -"EL ESTRECHO DE ORMUZ PRESIONA AL ALZA EL PRECIO DEL PETROLEO Y DISPARA
LA COTIZACION DE LOS BUQUES"- y en la lamina hay sitio para ocho o nueve
palabras en caja mixta. Meter uno en el otro da un ladrillo ilegible a 100px.

Asi que la lamina lleva su propio par: un titular corto y una bajada, que es
exactamente lo que hacen a mano las que ya publica el medio ("Apple va por su
iPhone mas caro" / "el primer plegable superaria los US$2.000").

ESO ES PROSA, Y POR TANTO LO ESCRIBE EL MODELO. Pero no inventa: se le da el
titular y la entradilla ya auditados y solo tiene que acortar. Si no responde,
se recorta el titular por codigo y la lamina sale igual.
"""

import re
import unicodedata

# Lo que va en la etiqueta roja. Sale del pais de la pieza, que el motor ya
# clasifica, y no de una lista aparte que habria que mantener.
#
# SIN PAIS ES "MUNDO", que es lo que hacen las laminas del medio: la del iPhone
# dice MUNDO y la del petroleo dice ESTADOS UNIDOS. La regla es la misma.
SIN_PAIS = "MUNDO"


def categoria_de(lugares, region=""):
    """La etiqueta roja: el pais en mayusculas, o MUNDO."""
    lugares = [l for l in (lugares or []) if l]
    if not lugares:
        return SIN_PAIS
    if len(lugares) > 1:
        # Varios paises: no se enumeran, se dice la region. Una etiqueta con
        # tres nombres no cabe y ademas no dice nada.
        return (region or "LATINOAMÉRICA").upper()
    return lugares[0].upper()


def _recortar(titulo, palabras=9):
    """El titular del panel, acortado por codigo. Reserva si el modelo falla."""
    limpio = re.sub(r"\s+", " ", (titulo or "").strip())
    trozos = limpio.split(" ")
    corto = " ".join(trozos[:palabras])
    # El panel escribe en mayusculas; la lamina va en caja mixta.
    if corto.isupper():
        corto = corto.capitalize()
    return corto.rstrip(",;:") + ("…" if len(trozos) > palabras else "")


def textos_para(titulo, resumen=""):
    """(titular_corto, bajada) para la lamina. Nunca inventa datos."""
    from motor.ia import pedir_json

    prompt = (
        "Eres editor de redes de un medio de economía. Te doy el titular y la "
        "entradilla de una pieza YA PUBLICADA, y tienes que convertirlos en el "
        "texto de una lámina de Instagram.\n\n"
        "Devuelve dos cosas:\n"
        "- 'titular': máximo 9 palabras, en caja mixta (no mayúsculas), directo "
        "y con gancho. Es lo que se lee de lejos.\n"
        "- 'bajada': una línea corta que complete al titular, en minúscula "
        "inicial, máximo 12 palabras.\n\n"
        "Reglas:\n"
        "- NO inventes ni una cifra ni un hecho: solo puedes usar lo que está "
        "en el titular y la entradilla que te doy.\n"
        "- Nada de signos de exclamación ni de mayúsculas de más.\n"
        "- Si hay una cifra que sea el gancho, va en la bajada.\n\n"
        'Devuelve solo JSON: {"titular": "...", "bajada": "..."}\n\n'
        "Titular: %s\nEntradilla: %s" % (titulo, (resumen or "")[:300]))

    r = pedir_json(prompt, etiqueta="lámina", temperatura=0.4)
    if not isinstance(r, dict) or not r.get("titular"):
        print("  [lámina] el modelo no contestó; recorto el titular por código")
        return _recortar(titulo), ""
    return str(r["titular"]).strip(), str(r.get("bajada") or "").strip()


def _plano(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# Como se pide la lamina en el pie de foto. Va aparte del resto de
# instrucciones porque no cambia lo que se escribe, sino lo que se entrega.
PIDE_LAMINA = re.compile(
    r"\b(post|publicacion para instagram|instagram|lamina|placa|"
    r"plantilla|flyer|para redes)\b")


def la_piden(pie):
    """¿El pie de foto pide la lámina de Instagram?"""
    return bool(PIDE_LAMINA.search(_plano(pie)))


def categoria_pedida(pie):
    """La categoría escrita a mano en el pie: «categoria: ESTADOS UNIDOS»."""
    m = re.search(r"categor[ií]a\s*:\s*([^\n,.;]{2,28})", pie or "", re.I)
    return m.group(1).strip().upper() if m else ""


def hacer(foto, titulo, resumen, lugares, salida, categoria="", region=""):
    """Dibuja la lámina y devuelve la ruta, o None si no se pudo."""
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from plantillas import post

    corto, bajada = textos_para(titulo, resumen)
    etiqueta = categoria or categoria_de(lugares, region)
    print("  [lámina] %s · %s" % (etiqueta, corto))
    if bajada:
        print("  [lámina] bajada: %s" % bajada)
    html = post.componer(foto, etiqueta, corto, bajada)
    return salida if post.dibujar(html, salida) else None
