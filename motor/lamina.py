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

# Wikimedia exige un User-Agent propio y devuelve 403 sin el. Ver bajar().
AGENTE = "SurEconomics/1.0 (motor editorial)"


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
        "- 'titular': máximo 9 palabras, directo y con gancho. Es lo que se lee "
        "de lejos.\n"
        "- 'bajada': una línea corta que complete al titular, máximo 12 "
        "palabras.\n\n"
        "Reglas:\n"
        "- NO inventes ni una cifra ni un hecho: solo puedes usar lo que está "
        "en el titular y la entradilla que te doy.\n"
        # SE DICE ASI DE EXPLICITO PORQUE YA SE FUE AL OTRO EXTREMO. El prompt
        # decia "en caja mixta (no mayúsculas)" queriendo decir "no todo en
        # mayúsculas", y el modelo devolvio TODO en minúscula: "clave minera
        # para atraer inversiones a venezuela", con el pais en minúscula.
        "- ORTOGRAFÍA NORMAL DE UNA FRASE: mayúscula en la primera letra de "
        "cada uno de los dos textos, y los nombres propios con su mayúscula "
        "(Venezuela, Apple, Estados Unidos). Lo que NO se quiere es el texto "
        "entero en mayúsculas.\n"
        "- Nada de signos de exclamación.\n"
        "- Si hay una cifra que sea el gancho, va en la bajada.\n\n"
        'Devuelve solo JSON: {"titular": "...", "bajada": "..."}\n\n'
        "Titular: %s\nEntradilla: %s" % (titulo, (resumen or "")[:300]))

    r = pedir_json(prompt, etiqueta="lámina", temperatura=0.4)
    if not isinstance(r, dict) or not r.get("titular"):
        print("  [lámina] el modelo no contestó; recorto el titular por código")
        return _mayuscula_inicial(_recortar(titulo)), ""
    # Sin punto final: ninguna de las laminas que publica el medio lo lleva. Se
    # quita solo el ultimo, para no destrozar un "EE. UU." ni un "US$2.000".
    bajada = _mayuscula_inicial(str(r.get("bajada") or "").strip()).rstrip(".")
    return _mayuscula_inicial(str(r["titular"]).strip()).rstrip("."), bajada


def _mayuscula_inicial(texto):
    """La primera letra en mayúscula, y el resto intacto.

    RED DEBAJO DEL PROMPT, no en vez de el. Al modelo se le pide la ortografía
    correcta, pero esto es mecánico y comprobable, así que no se deja a su
    criterio: la primera lámina que se pidió de verdad salió con los dos textos
    enteros en minúscula. Un prompt se puede desobedecer; esto no.

    NO se usa capitalize(): eso pondría en minúscula todo lo demás y se llevaría
    por delante los nombres propios («Apple va por su iPhone» -> «Apple va por
    su iphone»).
    """
    texto = (texto or "").strip()
    if not texto:
        return texto
    # Los signos de apertura no son letra: «¿Nueva carrera...» empieza en la N.
    for i, c in enumerate(texto):
        if c.isalpha():
            return texto[:i] + c.upper() + texto[i + 1:]
    return texto


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

# LO QUE EDICION PUEDE IMPONER A MANO, Y POR QUE SE PARECEN TANTO LOS TRES.
#
# Hasta el 23/09/2026 solo se podia imponer la categoria: el titular corto y la
# bajada los escribia siempre el modelo. Es lo primero que pidio quien usa la
# lamina a diario, y tiene razon: acortar un titular es criterio de redes, no
# un dato que haya que auditar. El modelo propone porque suele acertar y ahorra
# trabajo, no porque decida el.
#
# NO SE CORTA POR EL PUNTO, al reves que la categoria: un titular lleva puntos
# dentro («EE. UU.», «US$2.000») y cortar ahi los destrozaba. Se corta por
# salto de linea, que es como se escriben en el pie de foto, uno por renglon.
def titular_pedido(pie):
    """El titular corto escrito a mano: «titular: Trump aprieta a México»."""
    m = re.search(r"titular\s*:\s*([^\n]{2,90})", pie or "", re.I)
    return m.group(1).strip() if m else ""


def bajada_pedida(pie):
    """La bajada escrita a mano: «bajada: exige arrestos por corrupción»."""
    m = re.search(r"bajada\s*:\s*([^\n]{2,120})", pie or "", re.I)
    return m.group(1).strip() if m else ""



def bajar(url, destino):
    """Trae al disco la portada que eligio el motor. Devuelve la ruta o None.

    HACE FALTA PORQUE LA LAMINA NECESITA EL ARCHIVO Y LA CARGA SOLO TIENE LA
    DIRECCION. armar_carga.py guarda la foto como URL porque el panel se la
    enlaza; Chrome, en cambio, dibuja el fondo desde un fichero incrustado en
    base64 (ver plantillas/post._incrustar). Sin este paso, pedir la lamina
    desde un enlace suelto -sin adjuntar imagen- no dibujaba nada.

    EL USER-AGENT NO ES OPCIONAL: Wikimedia responde 403 a las peticiones sin
    uno propio, y es de donde vienen casi todas estas portadas.
    """
    import pathlib
    import urllib.request

    if not url:
        return None
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(pedido, timeout=40) as r:
            datos = r.read()
            tipo = (r.headers.get("Content-Type") or "").lower()
    except Exception as exc:  # noqa: BLE001
        print("  [lámina] no pude bajar la portada (%s)" % str(exc)[:70])
        return None
    # WIKIMEDIA DEVUELVE 200 CON UNA PAGINA HTML si el thumb no existe, no un
    # 404. Comprobado el 21/09/2026: 231 KB de HTML con Content-Type text/html.
    # Sin esta guarda se guardaban esos bytes con nombre .jpg, Chrome no podia
    # dibujarlos y la lamina salia con el fondo en negro sin que nada dijera por
    # que. Un fallo que no se ve hasta que alguien mira la imagen publicada.
    if not tipo.startswith("image/"):
        print("  [lámina] la portada no es una imagen (%s); no la uso"
              % (tipo.split(";")[0] or "sin tipo"))
        return None
    # La extension se saca del tipo que declara el servidor y no de la URL: las
    # de Commons acaban en .jpg con mayusculas, en .JPG, o en nada.
    ext = ".png" if "png" in tipo else (".webp" if "webp" in tipo else ".jpg")
    ruta = pathlib.Path(str(destino)).with_suffix(ext)
    ruta.write_bytes(datos)
    return ruta

def hacer(foto, titulo, resumen, lugares, salida, categoria="", region="",
          credito="", titular="", bajada=""):
    """Dibuja la lámina y devuelve la ruta, o None si no se pudo."""
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from plantillas import post

    # CON LOS DOS PUESTOS NO SE LLAMA AL MODELO. No es solo ahorro de cuota:
    # si Edicion ya escribio las dos lineas, preguntarle para luego tirar su
    # respuesta es una llamada que solo puede fallar, y esta cadena se queda
    # sin cuota a menudo. Con uno solo si se llama, para que el otro salga
    # escrito y no vacio.
    if titular and bajada:
        corto = titular
        print("  [lámina] titular y bajada puestos a mano")
    else:
        corto, auto = textos_para(titulo, resumen)
        corto = titular or corto
        bajada = bajada or auto
    etiqueta = categoria or categoria_de(lugares, region)
    print("  [lámina] %s · %s" % (etiqueta, corto))
    if bajada:
        print("  [lámina] bajada: %s" % bajada)
    if credito:
        print("  [lámina] crédito: %s" % credito)
    html = post.componer(foto, etiqueta, corto, bajada, credito=credito)
    return salida if post.dibujar(html, salida) else None
