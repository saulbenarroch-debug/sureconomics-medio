r"""Escribe UNA pieza a peticion, desde un enlace o un tema.

    .pyruntime\python.exe nota.py "https://elpais.com/economia/..."
    .pyruntime\python.exe nota.py "Petrobras sube el precio del queroseno"

Es lo que dispara el comando /nota del bot de Telegram. Cuando alguien de la
redaccion ve algo que el robot no ha cogido, lo pega en el chat y esto corre la
cadena completa: fuente, expediente, cifras, redaccion, auditoria y correo.

DOS ENTRADAS, UNA SALIDA

Con un ENLACE se lee la nota, se registra como fuente verificada y se escribe
sobre ella. Es el caso bueno: hay un documento concreto detras.

Con un TEMA suelto se busca en la lista blanca de medios. Si no aparece nada,
NO se inventa: se dice que no se encontro y se termina. Un motor que escribe
sobre un tema sin fuente es exactamente lo que este proyecto evita.

COMPRUEBA SI YA ESTA PUBLICADO ANTES DE ESCRIBIR. Alguien puede pedir algo que
salio en la tanda de la mañana, y de hecho paso el 31/08/2026 con una captura
que llego por el chat. Si ya esta, lo dice y no gasta nada.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

# Cuantos medios se meten en el expediente de una misma noticia. Tres bastan
# para contrastar y no disparan el coste: mas texto es mas tokens en cada
# llamada al modelo, y a partir del tercero repiten lo mismo.
MAX_FUENTES = 3

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _plano(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


TIPOS = ["Noticia", "Análisis", "Opinión", "Editorial", "Investigación",
         "Educación"]

# Como se llama cada tipo cuando lo pide una persona. "Análisis" va PRIMERO en
# TIPOS y "artículo" apunta aquí porque en el sitio ese formato se llama
# 'articulo': quien escribe "hazme un artículo" está pidiendo eso, no una
# columna de opinión.
#
# 'reportaje' e 'informe' caen en Investigación, que es el formato al que
# corresponden en el panel.
SINONIMOS = {
    "articulo": "Análisis", "analisis": "Análisis",
    "columna": "Opinión", "opinion": "Opinión",
    "reportaje": "Investigación", "informe": "Investigación",
    "explicador": "Educación", "explicativo": "Educación",
}


def leer_encargo(texto, tipo_por_defecto="Noticia"):
    """Del pie de foto saca el tipo de pieza y deja el resto como instruccion.

    El pie es lo que la persona escribio junto a la captura: "hazla editorial",
    "enfocala en Venezuela". Lo primero cambia el tipo, lo segundo es una orden
    de edicion y viaja en --encargo, que es el mismo camino por el que entro la
    tesis de Óscar en la serie del acuerdo petrolero.

    "ARTICULO" YA ES UN TIPO, desde el 05/09/2026. Hasta entonces el motor tenia
    cinco prompts y ninguno se llamaba asi, aunque el sitio si tenia el formato
    'articulo': quien pedia un articulo recibia un aviso y una noticia. Ahora
    existe Análisis (prompts/60-analisis.md) y "articulo" apunta a el.

    Los sinonimos importan porque nadie escribe el nombre interno del tipo. Se
    pide "una columna", "un reportaje", "un explicador", y cada uno de esos
    tiene un tipo al que corresponde. Ver SINONIMOS.
    """
    texto = (texto or "").strip()
    if not texto:
        return tipo_por_defecto, "", ""

    plano = _plano(texto)
    for t in TIPOS:
        # Se busca la raiz para que valgan "editorial", "un editorial",
        # "hazla editorial" y "opinion" tanto con tilde como sin ella.
        if re.search(r"\b" + _plano(t)[:6], plano):
            return t, texto, ""
    # LA PALABRA ENTERA, no la raiz de seis letras que se usa arriba. Con la
    # raiz, "inform" casaba con «informó» y "report" con «reportó», que son
    # verbos corrientes en un encargo: "hazme algo sobre lo que informó el BCV"
    # habria pedido una Investigación. Los nombres de TIPOS si aguantan la raiz
    # porque son palabras raras; estos no.
    for palabra, tipo in SINONIMOS.items():
        if re.search(r"\b%ss?\b" % palabra, plano):
            return tipo, texto, ""
    return tipo_por_defecto, texto, ""


# Como se dice en el pie que la foto es la PORTADA y no una captura para leer.
# La misma imagen puede ser las dos cosas y solo el pie lo distingue.
DE_PORTADA = re.compile(
    r"\b(con esta (imagen|foto|portada)|usa(la)? esta (imagen|foto)|"
    r"esta (imagen|foto) de portada|de portada|ponle esta|con la imagen adjunta)",
    re.I)

# Norma del 31/08/2026: las imagenes generadas con IA se declaran AL PIE DEL
# CUERPO, en cursiva. Va dentro del texto y nunca en el campo de credito del
# panel, que no persiste y borro en silencio la declaracion de siete piezas.
LINEA_IA = "<p><em>Imagen generada con inteligencia artificial.</em></p>"

# Como se dice que NO es de IA. Por defecto se declara, porque el dueño confirmo
# el 02/09/2026 que las portadas que manda por Telegram son generadas. Ponerle
# la linea a una foto real seria mentir en la otra direccion, asi que hay como
# desactivarla.
NO_ES_IA = re.compile(r"\b(foto real|fotografia real|no es de ia|no es ia|"
                      r"imagen real|foto de archivo)\b", re.I)


def papel_de_la_foto(pie):
    """Devuelve 'portada' o 'captura' segun lo que diga el pie."""
    return "portada" if DE_PORTADA.search(pie or "") else "captura"


def _apodo(texto):
    """Nombre de archivo corto y sin sorpresas.

    Se recorta y DESPUES se quitan los guiones: al reves, cortar a 38 puede
    dejar uno al final, y agregar_fuente.py se lo quita al registrar. Ver el
    comentario de main() sobre los dos nombres que no coincidian.
    """
    s = re.sub(r"[^a-z0-9]+", "-", _plano(texto)).strip("-")
    return (s[:38].strip("-") or "peticion")


def leer_enlace(url):
    """Trae titular, texto y nombre del medio. Sin IA: solo limpieza de etiquetas.

    EL NOMBRE SALE DE og:site_name, NO DEL DOMINIO. Deducirlo del dominio da una
    sola palabra pegada: bloomberglinea.com daba "Bloomberglinea" mientras el
    redactor escribia "Bloomberg Línea", que es el nombre de verdad. El auditor
    no reconocia la atribucion y bloqueaba una pieza que citaba bien su fuente.
    Ademas ese nombre se publica en la linea de fuentes, y ahi se ve.
    """
    peticion = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(peticion, timeout=45) as r:
        crudo = r.read().decode("utf-8", "replace")

    titulo = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", crudo, re.S | re.I)
    if m:
        titulo = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                  crudo, re.I)
    if m:
        titulo = re.sub(r"\s+", " ", m.group(1)).strip()

    # Fuera lo que no es texto de la nota antes de recoger parrafos.
    cuerpo = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form)[^>]*>.*?</\1>",
                    " ", crudo)
    parrafos = []
    for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", cuerpo):
        t = re.sub(r"(?s)<[^>]+>", " ", p)
        t = re.sub(r"&nbsp;", " ", t)
        t = re.sub(r"&amp;", "&", t)
        t = re.sub(r"\s+", " ", t).strip()
        # Los parrafos cortos de una web son pies, menus y avisos de cookies.
        if len(t) > 90:
            parrafos.append(t)
    sitio = ""
    m = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)',
                  crudo, re.I)
    if m:
        sitio = re.sub(r"\s+", " ", m.group(1)).strip()
    return titulo, parrafos[:14], sitio


def medio_de(url):
    """Ultimo recurso: el dominio. Se prefiere og:site_name, ver leer_enlace()."""
    d = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return d.split(".")[0].replace("-", " ").title()


# El relleno con que se pide un encargo hablando. "Redáctame algo de lo que dijo
# María Corina Machado hoy" no se busca entero: se busca "María Corina Machado".
#
# POR QUE IMPORTA TANTO. El 03/09/2026 la frase completa devolvio de primero
# "Trump announces new round of drug-pricing deals", que no tiene nada que ver, y
# la pieza acabo escribiendose de otra cosa. Con el nombre solo, los seis
# primeros eran de ese mismo dia y sobre lo que ella habia dicho. Un buscador
# reparte el peso entre todas las palabras, y "lo", "que", "dijo" y "hoy" pesan
# lo mismo que el nombre sin decir nada.
_RELLENO = re.compile(
    r"\b(lo\s+que\s+dijo|que\s+dijo|lo\s+de|algo\s+de|sobre\s+lo\s+de|"
    r"qu[eé]\s+pas[oó]\s+con|qu[eé]\s+hay\s+de|las?\s+declaraciones?\s+de|"
    r"la\s+noticia\s+de|una\s+nota\s+de|hoy|ayer|esta\s+ma[nñ]ana|"
    r"esta\s+tarde|ahora\s+mismo|[uú]ltima\s+hora)\b", re.I)


def _consulta_limpia(texto):
    """El encargo hablado, convertido en terminos de busqueda."""
    limpio = _RELLENO.sub(" ", texto)
    limpio = re.sub(r"\s{2,}", " ", limpio).strip(" ,.:;¿?¡!")
    # Si al quitar el relleno no queda casi nada, se busca el original: mejor
    # una busqueda floja que una vacia.
    return limpio if len(limpio) >= 4 else texto


def _habla_de(candidato, consulta):
    """¿El candidato nombra de verdad lo que se busco?

    EL BUSCADOR NO GARANTIZA QUE SI. Con topic="news" e include_domains, Tavily
    a veces contesta con lo ULTIMO de esos dominios en vez de con lo que casa:
    el 03/09/2026, buscando "María Corina Machado", devolvio en dos corridas
    seguidas seis piezas correctas y, minutos despues, «Giorgia Meloni's
    enviable stability» y un exlider de Reform Wales. La misma consulta y los
    mismos parametros. Sin esta comprobacion, la pieza se escribe de lo que
    saliera, y eso ya paso: una nota pedida sobre Machado se redacto desde una
    ficha de podcast sobre el acuerdo petrolero.

    Es la misma idea que ya filtra las fotos: no basta con que el buscador lo
    devuelva, tiene que NOMBRAR la cosa.
    """
    palabras = [p for p in re.findall(r"[^\W\d_]{4,}", _plano(consulta))
                if p not in _VACIAS_CONSULTA]
    if not palabras:
        return True
    ficha = _plano("%s %s" % (candidato.get("titular", ""),
                              candidato.get("extracto", "")))
    return any(p in ficha for p in palabras)


# Palabras que no distinguen nada aunque midan mas de tres letras.
_VACIAS_CONSULTA = {
    "sobre", "para", "como", "desde", "hasta", "entre", "esta", "este",
    "todos", "todas", "cada", "nuevo", "nueva", "segun", "tras", "ante",
    "noticia", "noticias", "nota", "pieza", "medio", "medios",
}


# QUIEN FIRMA, sacado de lo que se escribio a mano.
#
# La opinion EXIGE nombre y apellido: sin autor devuelve faltantes:["autor"] y no
# hay pieza. Pidiendola por Telegram no llegaba ninguno, asi que las columnas
# simplemente no se podian encargar desde el bot.
#
# SE EXIGEN DOS PALABRAS EN MAYUSCULA, o sea nombre y apellido. Con una sola,
# "una columna de Venezuela" habria firmado la pieza como "Venezuela": en
# español "de" introduce tanto al autor como el tema, y no hay forma de
# distinguirlos por la gramatica. Un nombre completo si es una señal fiable, y
# ademas es lo que la opinion necesita: firmar con solo el nombre de pila no
# vale para un medio.
_NOMBRE = (r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ'’-]+"
           r"(?:\s+(?:de|del|la|las|los|van|von|da|di)\b)?"
           r"(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ'’-]+){1,3}")
# Y HAY DOS CASOS, no uno, porque "de" no basta como señal. "una noticia de
# Nicolás Maduro" habria firmado la pieza como Maduro: en español "de"
# introduce igual al autor que al tema, y con un nombre propio detras el
# sentido lo decide QUE TIPO DE PIEZA es, no la gramatica.
#
#   "una columna de Óscar Doval"  -> la escribe Óscar Doval
#   "una noticia de Óscar Doval"  -> habla de Óscar Doval
#
# El "de" suelto solo cuenta en los tipos que van firmados; para el resto hay
# que decirlo: "firma: X", "firmada por X".
AUTORIA_EXPLICITA = re.compile(
    r"\b(?:firmad[ao]\s+por|firma\s*:\s*|firma\s+|escrit[ao]\s+por)\s+("
    + _NOMBRE + r")", re.UNICODE)
AUTORIA_IMPLICITA = re.compile(r"\b(?:de|por)\s+(" + _NOMBRE + r")", re.UNICODE)

# Los que no se publican sin nombre y apellido. El editorial no entra: lo firma
# la redaccion por definicion, que es lo que lo separa de una columna.
TIPOS_FIRMADOS = ("Opinión", "Investigación")


def leer_autor(texto, tipo="Noticia"):
    """Devuelve (autor, texto_sin_esa_parte). Si no hay nombre, (None, texto).

    Se quita del texto porque lo que queda se usa como tema de busqueda o como
    instruccion de edicion, y "Óscar Doval" dentro de la consulta busca notas
    SOBRE Óscar Doval, que es justo lo contrario de lo que se pidio.
    """
    texto = texto or ""
    m = AUTORIA_EXPLICITA.search(texto)
    if not m and tipo in TIPOS_FIRMADOS:
        m = AUTORIA_IMPLICITA.search(texto)
    if not m:
        return None, texto
    resto = (texto[:m.start()] + " " + texto[m.end():])
    return m.group(1).strip(), re.sub(r"\s{2,}", " ", resto).strip()


ES_TUIT = re.compile(r"^https?://(www\.)?(x|twitter)\.com/[^/]+/status/(\d+)", re.I)


def leer_tuit(url):
    """Devuelve (autor, texto) de un tuit, o (None, None).

    X es una aplicacion de JavaScript: el HTML que llega no trae la publicacion,
    asi que leer_enlace() encuentra cero parrafos y corta. Paso el 02/09/2026 con
    un enlace que mando el dueño y la corrida salio marcada en rojo.

    El oEmbed de la propia X es publico y no pide credenciales. fxtwitter queda
    de respaldo porque devuelve el texto sin recortar.
    """
    m = ES_TUIT.match(url or "")
    if not m:
        return None, None
    import json as _json

    ident = m.group(3)
    intentos = [
        ("https://publish.twitter.com/oembed?url=" +
         urllib.parse.quote("https://twitter.com/i/status/" + ident)),
        "https://api.fxtwitter.com/i/status/" + ident,
    ]
    for u in intentos:
        try:
            pet = urllib.request.Request(u, headers={"User-Agent": NAVEGADOR})
            with urllib.request.urlopen(pet, timeout=30) as r:
                d = _json.loads(r.read().decode())
        except Exception:  # noqa: BLE001
            continue
        if d.get("html"):
            t = re.sub(r"<[^>]+>", " ", d["html"])
            return d.get("author_name", ""), re.sub(r"\s+", " ", t).strip()
        tuit = d.get("tweet") or {}
        if tuit.get("text"):
            return (tuit.get("author") or {}).get("name", ""), tuit["text"]
    return None, None


ES_INSTAGRAM = re.compile(
    r"^https?://(www\.)?instagram\.com/(p|reel|tv)/([\w-]+)", re.I)


def leer_instagram(url):
    """Devuelve (cuenta, texto) de una publicacion de Instagram, o (None, None).

    EL TRUCO ES EL USER-AGENT, y no hace falta ni Tavily ni credenciales.
    Instagram es una aplicacion de JavaScript como X: a un navegador le sirve una
    pagina vacia y leer_enlace() encuentra cero parrafos ("sin texto de nota:
    instagram.com", que es lo que salio el 07/09/2026 con dos enlaces que
    mandaron Edicion y Ariana). Pero a un RASTREADOR le sirve las etiquetas
    Open Graph para poder previsualizar el enlace, y ahi va el pie entero.

    Medido ese mismo dia con un post real: con agente de navegador, og:title y
    og:description vienen VACIOS; con 'facebookexternalhit' -el que usa Telegram
    para sus previsualizaciones- vienen los dos, con la cuenta, la fecha y 524
    caracteres de pie.

    No es un rodeo: es la via que Instagram publica a proposito para que se
    puedan previsualizar sus enlaces. La alternativa, su API oficial, exige una
    app de Meta revisada.

    og:description trae "cuenta on September 2, 2026: «el pie»", que es de donde
    salen la cuenta y el texto.
    """
    if not ES_INSTAGRAM.match(url or ""):
        return {}
    import html as _html

    try:
        pet = urllib.request.Request(
            url, headers={"User-Agent": "facebookexternalhit/1.1"})
        with urllib.request.urlopen(pet, timeout=30) as r:
            doc = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return {}

    def meta(prop):
        m = re.search(r'property="og:%s"[^>]+content="([^"]*)"' % prop, doc)
        if not m:
            m = re.search(r'content="([^"]*)"[^>]+property="og:%s"' % prop, doc)
        return _html.unescape(m.group(1)) if m else ""

    desc, titulo = meta("description"), meta("title")
    if not desc and not titulo:
        return {}

    # EL CONTADOR VA DELANTE CUANDO EL POST TIENE INTERACCIONES, y no siempre:
    # de un post sin ellas llega "beycocapital on September 2, 2026: ...", y de
    # uno con ellas "167 likes, 2 comments - bloomberglinea on September 7...".
    # Sin quitarlo, el usuario salia vacio, y el usuario es lo que permite
    # comprobar DE QUIEN es la cuenta: sin el, una publicacion de una figura
    # publica no se podria verificar y no se escribiria. Se vio el 07/09/2026.
    desc = re.sub(r"^\s*[\d.,KMkm]+\s+likes?,\s*[\d.,KMkm]+\s+comments?\s*-\s*",
                  "", desc)

    # "beycocapital on September 2, 2026: «...»"  ->  cuenta, FECHA y pie.
    #
    # LA FECHA ES DEL POST Y NO DE HOY. Se guardaba date.today(), y eso solo
    # acierta cuando el post es del dia: mandando uno de julio, la fuente
    # quedaba fechada hoy y la pieza databa como de hoy algo dicho hace dos
    # meses. Para un medio eso no es un detalle. Lo pregunto Edicion el
    # 07/09/2026 mirando una pieza que, por casualidad, si era del dia.
    m = re.match(r"\s*([A-Za-z0-9._]+)\s+on\s+([^:]+):\s*(.*)", desc, re.S)
    cuenta, cuando, texto = (m.group(1), m.group(2), m.group(3)) if m \
        else ("", "", desc)
    # El nombre visible ("Bloomberg Línea") dice mas que el usuario y es lo que
    # luego se busca en la lista blanca. Va delante del " on Instagram:".
    visible = titulo.split(" on Instagram")[0].strip()
    texto = re.sub(r'^[«"“]|[»"”]\.?$', "", texto.strip()).strip()
    return {"autor": visible or cuenta or None, "texto": texto or None,
            "usuario": cuenta or None, "fecha": _fecha_en_ingles(cuando)}


# Los meses vienen en ingles porque asi los sirve Instagram, sea cual sea el
# idioma del post.
_MESES_EN = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
             "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
             "november": 11, "december": 12}


def _fecha_en_ingles(texto):
    """«September 7, 2026» -> «2026-09-07». Cadena vacía si no se reconoce.

    No se inventa una fecha por defecto: si no se entiende, se deja vacía y el
    expediente lo dice. Poner la de hoy es peor que no poner ninguna, porque
    parece un dato y no lo es.
    """
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", texto or "")
    if not m:
        return ""
    mes = _MESES_EN.get(m.group(1).lower())
    return "%s-%02d-%02d" % (m.group(3), mes, int(m.group(2))) if mes else ""


def _foto_telegram(chat, ruta, pie=""):
    """Manda una imagen al chat. Devuelve True si Telegram la acepto.

    Va por multipart y no por URL: la lamina se acaba de dibujar en el disco del
    runner y no esta publicada en ninguna parte. Publicarla solo para poder
    mandarla seria dejar un archivo tirado en el repositorio por cada peticion.
    """
    import mimetypes
    import uuid

    ficha = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not ficha or not chat or not pathlib.Path(ruta).exists():
        return False
    limite = "----" + uuid.uuid4().hex
    datos = pathlib.Path(ruta).read_bytes()
    mime = mimetypes.guess_type(str(ruta))[0] or "image/png"

    def campo(nombre, valor):
        return ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                % (limite, nombre, valor)).encode()

    cuerpo = campo("chat_id", str(chat)) + campo("caption", pie[:1000])
    cuerpo += campo("parse_mode", "HTML")
    cuerpo += ('--%s\r\nContent-Disposition: form-data; name="photo"; '
               'filename="%s"\r\nContent-Type: %s\r\n\r\n'
               % (limite, pathlib.Path(ruta).name, mime)).encode()
    cuerpo += datos + ("\r\n--%s--\r\n" % limite).encode()

    pet = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendPhoto" % ficha, data=cuerpo,
        headers={"Content-Type": "multipart/form-data; boundary=%s" % limite})
    try:
        with urllib.request.urlopen(pet, timeout=60):
            return True
    except Exception as exc:  # noqa: BLE001
        print("  [lámina] no pude mandarla al chat (%s)" % str(exc)[:70])
        return False


def leer_publicacion(url):
    """Una publicacion de red social, o None si no lo es o no se pudo leer.

    Devuelve un diccionario y no una tupla porque le fueron haciendo falta mas
    campos -el USUARIO ademas del nombre visible, para poder comprobar de quien
    es la cuenta- y una tupla que crece se rompe en el sitio que nadie mira.

    X e Instagram tienen el mismo problema y la misma forma de resolverse, asi
    que se atienden por la misma puerta. Tener dos ramas paralelas en el flujo
    es como se llega a que una se arregle y la otra no: paso con la comprobacion
    de duplicados, que distinguia el tuit en un sitio y no en el otro.
    """
    m = ES_TUIT.match(url or "")
    if m:
        autor, texto = leer_tuit(url)
        # El usuario va en la propia direccion: x.com/<usuario>/status/<id>.
        usuario = (url.split("x.com/")[-1].split("twitter.com/")[-1]
                   .split("/")[0].split("?")[0])
        return {"autor": autor, "usuario": usuario, "texto": texto,
                "red": "x", "que_es": "tuit"}
    if ES_INSTAGRAM.match(url or ""):
        d = dict(leer_instagram(url))
        d.update(red="instagram", que_es="publicación de Instagram")
        return d
    return None


def fuente_de_la_publicacion(post):
    """¿Se puede escribir DESDE esta publicacion? Devuelve como citarla, o None.

    LA REGLA DE LA CASA ERA "UN POST NO ES FUENTE", y sigue siendo cierta para
    un post cualquiera: no se puede auditar lo que dice una cuenta que no se
    sabe de quien es. Pero hay dos casos en los que la publicacion SI es una
    fuente legitima, y negarse a escribirlos era perder noticias reales:

      1. LA CUENTA ES DE UN MEDIO DE LA LISTA. Lo que Bloomberg Línea publica en
         su Instagram lo publica Bloomberg Línea. Es fuente secundaria, igual
         que su web, y se cita igual.

      2. LA CUENTA ES DE UNA FIGURA PUBLICA. Que un jefe de Estado diga algo en
         su cuenta ES la noticia, y es fuente PRIMARIA: no se cuenta que ocurrio
         algo, se cuenta que lo dijo. Los diarios llevan haciendo esto desde que
         existen las redes.

    LA DIFERENCIA ENTRE LAS DOS IMPORTA Y VIAJA EN LA INSTRUCCION. En la primera
    los datos son reporteria del medio; en la segunda son AFIRMACIONES DE QUIEN
    HABLA, y presentarlas como hechos comprobados seria justo el error que este
    sistema existe para impedir.

    Y EN NINGUN CASO LO DECIDE UN MODELO. El medio se comprueba contra la lista
    blanca y la persona contra Wikidata, que guarda la cuenta oficial de cada
    figura publica. De cualquiera de ellas hay cuentas de parodia y de
    suplantacion; escribir "Trump dijo" desde una que no es la suya seria el
    peor fallo posible de este motor.
    """
    if not post or not post.get("texto"):
        return None
    from motor import buscador, entidad

    red = post.get("red") or "instagram"
    donde = "Instagram" if red == "instagram" else "X"
    usuario = (post.get("usuario") or "").lstrip("@")

    # 1. ¿Es la cuenta de un medio de la lista?
    if buscador.dominios_de(post.get("autor")) or buscador.dominios_de(usuario):
        medio = post.get("autor") or usuario
        return {
            "medio": medio,
            "por": "medio de la lista",
            "declarante": "",
            "instruccion": (
                "La fuente es lo que %s publicó en su cuenta de %s. Cítalo así, "
                "por su nombre y diciendo que fue en %s. Es fuente secundaria "
                "como cualquier diario." % (medio, donde, donde)),
        }

    # 2. ¿Es la cuenta oficial de una figura publica?
    quien = entidad.de_quien_es_la_cuenta(usuario, red)
    if quien:
        return {
            "medio": "%s (cuenta oficial en %s)" % (quien["nombre"], donde),
            "por": "figura pública verificada en Wikidata",
            "declarante": quien["nombre"],
            "instruccion": (
                "La fuente es lo que %s publicó en su cuenta oficial de %s. La "
                "noticia es QUE LO DIJO, no que sea cierto: atribúyele cada "
                "afirmación y cada cifra ('según dijo', 'afirmó', 'sostuvo'). No "
                "escribas como hecho comprobado nada que solo diga esa "
                "publicación." % (quien["nombre"], donde)),
        }
    return None


def registrar_publicacion(url, post, propia):
    """Deja la publicacion en fuentes_manuales/ y devuelve su nombre.

    Es la misma via que usa la redaccion para los medios que no se dejan leer
    por maquina: el texto se guarda entero y el auditor comprueba contra el.
    """
    import json as _json

    (AQUI / "fuentes_manuales").mkdir(exist_ok=True)
    texto = post.get("texto") or ""
    nombre = _apodo(texto[:60] or url)
    # LA FECHA DEL POST, no la de hoy. Si Instagram no la da, se deja la de hoy
    # y se AVISA: una fuente sin fecha es un problema conocido, una fuente con
    # una fecha inventada es un dato falso que nadie va a mirar dos veces.
    cuando = post.get("fecha") or ""
    if not cuando:
        cuando = date.today().isoformat()
        print("  [aviso] la publicación no dice su fecha; uso la de hoy (%s)"
              % cuando)
    elif cuando != date.today().isoformat():
        print("  ojo: la publicación es del %s, no de hoy" % cuando)
    ficha = {
        "hecho": texto[:180],
        "fecha": cuando,
        "medio": propia["medio"],
        "url": url,
        "texto": texto,
        # El pie entero es la cita: es contra esto que el auditor comprueba que
        # una frase entrecomillada exista de verdad.
        "citas": [texto],
    }
    if propia.get("declarante"):
        ficha["declarante"] = propia["declarante"]
    (AQUI / "fuentes_manuales" / (nombre + ".json")).write_text(
        _json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  publicación registrada como fuente '%s'" % nombre)
    return nombre


def _escapar(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _trozos(texto, tope=3900):
    """Parte por parrafos, nunca a mitad de frase.

    Telegram corta en 4096 caracteres. Partir por el numero pelado deja una nota
    cortada en mitad de una cifra, que es justo donde no se puede cortar en un
    medio que publica cifras.
    """
    partes, actual = [], ""
    for parrafo in texto.split("\n\n"):
        if len(actual) + len(parrafo) + 2 > tope and actual:
            partes.append(actual.rstrip())
            actual = ""
        # Un parrafo mas largo que el tope entero: se parte por lineas.
        while len(parrafo) > tope:
            corte = parrafo.rfind(" ", 0, tope)
            corte = corte if corte > tope // 2 else tope
            partes.append(parrafo[:corte])
            parrafo = parrafo[corte:].lstrip()
        actual += parrafo + "\n\n"
    if actual.strip():
        partes.append(actual.rstrip())
    return partes


def _mensaje_telegram(chat, texto, botones=None):
    """Un mensaje suelto al chat. Devuelve True si Telegram lo acepto.

    'botones' es una lista de (etiqueta, dato) y sale como teclado en linea.
    El dato viaja en callback_data, que Telegram limita a 64 bytes: NO CABE UN
    ENLACE. Por eso se manda solo el numero de la opcion y el Worker recupera
    la direccion del propio texto del mensaje, que ya la lleva.
    """
    import json as _json

    ficha = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not ficha or not chat:
        return False
    cuerpo = {"chat_id": chat, "text": texto, "parse_mode": "HTML",
              "disable_web_page_preview": True}
    if botones:
        cuerpo["reply_markup"] = {"inline_keyboard": [
            [{"text": etiqueta, "callback_data": dato}]
            for etiqueta, dato in botones]}
    pet = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % ficha,
        data=_json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pet, timeout=30):
        return True


def _avisar_fallo(chat, titulo, explicacion):
    """Le dice al chat por que no hubo nota.

    TODA SALIDA SIN PIEZA TIENE QUE PASAR POR AQUI. Quien pide una nota desde
    Telegram no ve el log de Actions: si el proceso termina sin escribir y sin
    decir nada, la corrida consta en verde y la persona se queda mirando el
    "escribiendo" hasta que se cansa. Pasaba en tres sitios de este mismo
    archivo -ya publicada, sin fuentes, redaccion fallida- y el 03/09/2026
    aparecio como si el bot llevara seis minutos colgado, cuando en realidad
    habia acabado en dieciocho segundos haciendo lo correcto.

    No corta nada si falla: la pieza, si existe, ya se entrego por correo.
    """
    if not chat:
        return False
    try:
        return _mensaje_telegram(
            chat, "⚠️ <b>%s.</b>\n\n%s" % (_escapar(titulo), _escapar(explicacion)))
    except Exception as exc:  # noqa: BLE001
        print("  [chat] no pude avisar (%s)" % str(exc)[:70])
        return False


def _avisar_captura(chat, hallado):
    """Le dice a quien mando la captura por que no se escribio.

    Se le contesta SIEMPRE. Mandar una foto y no recibir nada parece que el bot
    esta roto, y a la tercera vez la gente deja de mandarlas.
    """
    lectura = hallado.get("lectura") or {}
    partes = ["🔍 <b>No escribo esta.</b>", "", _escapar(hallado.get("motivo", ""))]
    if lectura.get("titular"):
        partes += ["", "Lo que leí en la imagen:",
                   "<i>" + _escapar(lectura["titular"][:200]) + "</i>"]

    # LO QUE GOOGLE NEWS SI VE, cuando no hay ningun candidato. Decir "no
    # encuentro nada" desperdicia lo que si se sabe: Google News encuentra notas
    # que el rastreo de RSS no ve -el 07/09/2026, una de tecnologia de Bloomberg
    # Línea, porque de ese medio solo tenemos los feeds de economia-, pero su
    # enlace es un redirector cifrado que no lleva a ninguna parte.
    #
    # Asi que se enseña el TITULAR EXACTO y se pide el enlace. La persona lo
    # encuentra en un clic: un callejon sin salida pasa a ser cinco segundos.
    if not hallado.get("candidatos"):
        try:
            from motor import buscador
            vistos = buscador.titulares_google(
                lectura.get("busqueda") or lectura.get("titular", ""),
                buscador.dominios_de(lectura.get("medio")))
        except Exception:  # noqa: BLE001
            vistos = []
        if vistos:
            partes += ["", "Pero <b>sí existe</b>. Esto es lo que encuentro:"]
            for v in vistos:
                # La fecha llega como "Fri, 04 Sep 2026": el dia de la semana
                # no aporta nada en un aviso de dos lineas.
                fecha = (v.get("fecha") or "")[5:]
                partes.append("· <b>%s</b>%s\n<i>%s</i>" % (
                    _escapar(v["medio"][:26]),
                    (" · " + _escapar(fecha)) if fecha else "",
                    _escapar(v["titular"][:150])))
            partes += ["", "No puedo abrirla desde ahí: Google News da un enlace "
                       "que no lleva al diario. Búscala y mándame el enlace con "
                       "<code>/nota</code> y la escribo."]
            return _mensaje_telegram(chat, "\n".join(partes))

    # CUANDO HAY CANDIDATOS DUDOSOS SE ENSEÑAN. Decir "no la encuentro" cuando
    # en realidad hay algo parecido pero incierto desperdicia el trabajo y deja
    # a la persona sin nada que hacer. Con el enlace delante, decide en dos
    # segundos algo que ninguna medida de parecido decide bien.
    botones = []
    if hallado.get("dudoso") and hallado.get("candidatos"):
        partes += ["", "Lo más parecido que encontré:"]
        for n, c in enumerate(hallado["candidatos"], 1):
            partes.append("<b>%d · %s</b> · %s\n<code>/nota %s</code>" % (
                n,
                _escapar((c.get("medio") or "")[:26]),
                _escapar((c.get("titular") or "")[:110]),
                _escapar(c.get("url") or "")))
            # La etiqueta va corta a proposito: el titular ya esta arriba y un
            # boton largo se parte en varias lineas y se lee peor que el texto.
            botones.append(("%d · %s" % (n, (c.get("medio") or "ese medio")[:24]),
                            "nota:%d" % n))
        # La linea /nota se queda aunque haya botones. Es la reserva si el
        # teclado falla, y ademas es de donde el Worker saca la direccion.
        partes += ["", "Toca la que sea y la escribo."]
    else:
        partes += ["", "Solo escribo desde el artículo original de un medio de "
                   "la lista, para que las cifras se puedan verificar. Si tienes "
                   "el enlace, mándalo con <code>/nota &lt;enlace&gt;</code>."]
    return _mensaje_telegram(chat, "\n".join(partes), botones)


def mandar_al_chat(borrador, chat, quien=""):
    """Manda el borrador al chat que lo pidio. Devuelve True si salio.

    EL CORREO SIGUE SIENDO EL CANAL PRINCIPAL y esto no lo sustituye: si
    Telegram falla, la pieza ya se envio por correo y no se pierde. Por eso los
    fallos aqui se avisan y no cortan nada.
    """
    import json as _json
    import urllib.error

    ficha = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not ficha or not chat:
        print("  [chat] sin TELEGRAM_TOKEN o sin chat: no se manda.")
        return False

    lineas = [l for l in borrador.read_text(encoding="utf-8").split("\n")]
    # El archivo trae [Noticia] [tags], titulo, [Fecha] y luego el cuerpo.
    utiles = [l.strip() for l in lineas if l.strip()]
    titulo = next((l for l in utiles[:4] if l.isupper() and len(l) > 25), "(sin titulo)")
    desde = utiles.index(titulo) + 1
    cuerpo = [l for l in utiles[desde:]
              if not l.startswith(("[Fecha]", "Perecedero", "[Autor]"))]

    # Si el auditor la bloqueo hay que decirlo ARRIBA. Un borrador que llega al
    # chat sin esa marca invita a publicarlo tal cual.
    estado = ""
    ruta_json = borrador.with_suffix(".json")
    if ruta_json.exists():
        try:
            if _json.loads(ruta_json.read_text(encoding="utf-8")).get("bloqueada"):
                estado = "⛔ <b>BLOQUEADA POR EL AUDITOR.</b> No publicar sin revisar.\n\n"
        except Exception:  # noqa: BLE001
            pass

    cabecera = "📝 <b>Borrador listo</b>%s\n\n" % (" · pedido por " + _escapar(quien) if quien else "")
    texto = (cabecera + estado + "<b>" + _escapar(titulo) + "</b>\n\n"
             + "\n\n".join(_escapar(l) for l in cuerpo)
             + "\n\n<i>Queda en borrador. No se publica solo.</i>")

    enviados = 0
    for i, trozo in enumerate(_trozos(texto)):
        cuerpo_pet = _json.dumps({"chat_id": chat, "text": trozo,
                                  "parse_mode": "HTML",
                                  "disable_web_page_preview": True}).encode()
        pet = urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % ficha,
            data=cuerpo_pet, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pet, timeout=30):
                enviados += 1
        except urllib.error.HTTPError as exc:
            print("  [chat] trozo %d rechazado: %s" % (i + 1, exc.read().decode()[:130]))
        except Exception as exc:  # noqa: BLE001
            print("  [chat] trozo %d fallo: %s" % (i + 1, str(exc)[:90]))
    print("  [chat] %d mensaje(s) enviados a %s" % (enviados, chat))
    return enviados > 0


def producir_y_entregar(nombre, tipo, encargo, autor, args,
                        portada_url="", declarar_ia=False,
                        foto_local=None, lamina_pedida=False):
    """Escribe desde una fuente ya registrada, audita y entrega.

    UNA SOLA VIA DE ENTREGA. Aqui llegan los dos caminos: el normal,
    que lee uno o varios articulos y los registra, y el de una
    publicacion de red social que es fuente por si misma. Correo,
    Telegram y panel son los mismos para los dos, y tenerlos dos veces
    es como se llega a que uno se arregle y el otro no.
    """
    print("\n--- 3. ESCRIBIR Y AUDITAR ---")
    r = subprocess.run(
        [sys.executable, str(AQUI / "motor" / "producir.py"),
         "--tipo", tipo, "--manual", nombre, "--encargo", encargo]
        + (["--autor", autor] if autor else []),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=25 * 60)
    print((r.stdout or "")[-1500:])
    if r.returncode != 0 and (r.stderr or "").strip():
        print("  FALLO:")
        for l in (r.stderr or "").strip().splitlines()[-6:]:
            print("    " + l[:150])

    # SE LEE EL NOMBRE QUE DIJO producir.py, NO SE VUELVE A CALCULAR.
    #
    # Calcularlo aqui por segunda vez ya costo caro: producir.py bautiza el
    # borrador con la PRIMERA fuente y aqui se pasaba la lista entera, asi que
    # desde que /nota lee varias fuentes el exists() daba False SIEMPRE. La
    # pieza se escribia, pasaba el auditor y se quedaba en el disco del runner,
    # sin llegar a Telegram ni al panel, y la corrida terminaba diciendo que no
    # se habia generado.
    #
    # Y ahora producir.py ademas numera el archivo cuando ya existe uno igual,
    # para no pisar una columna anterior. O sea que el nombre depende de lo que
    # haya en el disco y NO se puede deducir desde fuera. Se lee de su salida,
    # que es la unica fuente de verdad, y el calculo local queda solo de reserva
    # por si algun dia cambia ese mensaje.
    dicho = re.search(r"Borrador guardado en borradores/(\S+\.txt)",
                      r.stdout or "")
    borrador = AQUI / "borradores" / dicho.group(1) if dicho else None
    if not borrador or not borrador.exists():
        # LA RESERVA NO REPITE LA REGLA DEL NOMBRE, BUSCA POR EL PRINCIPIO. Que
        # las dos partes calculen el nombre completo es justo lo que fallo dos
        # veces esta semana; con un glob, cualquier cambio de sufijo -el tipo,
        # el numero de los repetidos- sigue encontrandolo.
        base = nombre.split(",")[0].strip()
        hallados = sorted((AQUI / "borradores").glob(base + "_*.txt"),
                          key=lambda p: p.stat().st_mtime)
        borrador = hallados[-1] if hallados else (
            AQUI / "borradores" / ("%s_%s.txt" % (base, tipo.lower())))
    if not borrador.exists():
        print("\nNo se genero el borrador. Revisa el fallo de arriba.")
        print("  buscaba: %s" % borrador.name)
        _avisar_fallo(args.chat, "No pude escribirla",
                      "La fuente se leyó bien, pero la redacción falló. "
                      "Vuelve a pedírmela; si insiste, hay que mirar el log.")
        return 1

    print("\n--- 4. ENTREGA ---")
    carpeta = AQUI / ("peticion-" + date.today().isoformat() + "-" + nombre[:18])
    carpeta.mkdir(exist_ok=True)
    for sufijo in (".txt", ".json"):
        origen = borrador.with_suffix(sufijo)
        if origen.exists():
            (carpeta / ("1-" + nombre[:26] + sufijo)).write_bytes(origen.read_bytes())
    r = subprocess.run([sys.executable, str(AQUI / "enviar.py"), str(carpeta), args.correo],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "")[-300:])

    # El correo va primero y siempre. Esto es un extra: quien la pidio por el
    # chat la recibe por el chat, sin cambiar de aplicacion para leerla.
    #
    # Y VA ENVUELTO PORQUE ES UN EXTRA. La primera version no lo estaba y un
    # simple "import os" que faltaba tumbo la corrida entera DESPUES de haber
    # escrito la pieza y mandado el correo: el trabajo estaba hecho, la nota
    # entregada, y GitHub mando un aviso de fallo. Nada que ocurra despues de la
    # entrega puede marcar la corrida como fallida.
    if args.chat:
        try:
            mandar_al_chat(borrador, args.chat, args.quien)
        except Exception as exc:  # noqa: BLE001
            print("  [chat] no se pudo mandar (%s). El correo ya salio." % str(exc)[:90])

    # 5. Al panel, COMO BORRADOR. Ni aqui ni en subir.py hay forma de publicar:
    #    publicar es un acto editorial y lo hace una persona.
    #
    #    Va al final y envuelto, por lo mismo de siempre: si el panel esta caido
    #    o la cuenta de servicio no responde, la pieza ya se escribio, se auditó
    #    y se entrego por dos canales. No se pierde nada.
    if not args.sin_subir and os.environ.get("SURECONOMICS_USUARIO", "").strip():
        print("\n--- 5. AL PANEL ---")
        try:
            r = subprocess.run([sys.executable, str(AQUI / "armar_carga.py"), str(carpeta)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=20 * 60)
            print((r.stdout or "")[-400:])
            carga = carpeta / "carga.json"

            # La portada que llego por el chat se mete AQUI, pisando lo que
            # hubiera decidido armar_carga.py. Si una persona se molesto en
            # mandar una imagen concreta, manda ella y no el buscador.
            if carga.exists() and portada_url:
                import json as _json
                d = _json.loads(carga.read_text(encoding="utf-8"))
                piezas = d if isinstance(d, list) else d.get("piezas", [])
                for pieza in piezas:
                    pieza["foto"] = portada_url
                    pieza["credito"] = ""
                    if declarar_ia and LINEA_IA not in (pieza.get("cuerpo_html") or ""):
                        pieza["cuerpo_html"] = (pieza.get("cuerpo_html") or "") + LINEA_IA
                carga.write_text(_json.dumps(d, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
                print("  portada puesta en la carga%s"
                      % (" y declarada como IA" if declarar_ia else ""))

            # LA LAMINA DE INSTAGRAM, si se pidio en el pie de foto.
            #
            # Se dibuja DESPUES de armar la carga y no antes, porque de ahi
            # salen el titular ya auditado, la entradilla y el pais clasificado,
            # que es lo que la lamina necesita. Hacerla antes obligaria a
            # repetir esa clasificacion, que es como se llega a que la lamina
            # diga un pais y el sitio diga otro.
            if carga.exists() and foto_local and lamina_pedida:
                import json as _json

                from motor import lamina as _lamina
                d = _json.loads(carga.read_text(encoding="utf-8"))
                piezas = d if isinstance(d, list) else d.get("piezas", [])
                if piezas:
                    p0 = piezas[0]
                    destino = carpeta / "lamina-instagram.png"
                    try:
                        hecha = _lamina.hacer(
                            foto_local, p0.get("titulo", ""),
                            p0.get("resumen", ""), p0.get("lugares") or [],
                            str(destino),
                            categoria=_lamina.categoria_pedida(encargo))
                    except Exception as exc:  # noqa: BLE001
                        hecha = None
                        print("  [lámina] no se pudo dibujar (%s)" % str(exc)[:80])
                    if hecha and args.chat:
                        _foto_telegram(args.chat, hecha,
                                       "🖼️ <b>Lámina para Instagram</b>\n"
                                       "1080×1350. Revisa el titular antes de "
                                       "publicar.")

            if carga.exists():
                # Se suben tambien las bloqueadas, marcadas con el aviso. Es lo
                # que pidio el dueño: mejor tenerla en el panel y arreglarla ahi.
                r = subprocess.run([sys.executable, str(AQUI / "subir.py"), str(carga),
                                    "--subir-bloqueadas"],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=20 * 60)
                print((r.stdout or "")[-700:] + (r.stderr or "")[-300:])
            else:
                print("  No se armo la carga. No se sube nada.")
        except Exception as exc:  # noqa: BLE001
            print("  [panel] no se pudo subir (%s)." % str(exc)[:90])
            print("  La pieza esta entregada por correo y por el chat.")
    elif not args.sin_subir:
        print("\n[panel] sin SURECONOMICS_USUARIO: no se sube. Solo correo y chat.")

    print("\nListo. Queda en borrador, como todo.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Una pieza a peticion")
    ap.add_argument("peticion", nargs="?", default="",
                    help="un enlace, o un tema en palabras")
    ap.add_argument("--foto", default="",
                    help="file_id de una captura mandada al bot de Telegram")
    ap.add_argument("--tipo", default="Noticia")
    ap.add_argument("--correo", default="saul@rendigroup.com")
    ap.add_argument("--quien", default="", help="quien la pidio, para el correo")
    # OJO: --autor y --quien no son lo mismo y confundirlos publica mal. --quien
    # es quien hizo el encargo, y solo sale en el correo interno; --autor es
    # quien FIRMA la pieza en el sitio. Un jefe puede encargar una columna que
    # firma otra persona.
    ap.add_argument("--autor", default="",
                    help="quien firma la pieza. Obligatorio en Opinión")
    ap.add_argument("--chat", default="", help="chat de Telegram al que devolverla")
    ap.add_argument("--sin-subir", action="store_true",
                    help="escribe y entrega, pero no toca el panel")
    ap.add_argument("--forzar", action="store_true",
                    help="escribe aunque la memoria la de por publicada")
    ap.add_argument("--encargo", default="",
                    help="instruccion de edicion; en Telegram, el pie de foto")
    args = ap.parse_args()

    peticion = args.peticion.strip()
    # Los demas medios que cuentan lo mismo, cuando la noticia viene de una
    # captura o de un tuit. Con /nota a secas es una lista vacia.
    alternativas = []
    # Se rellena solo cuando la fuente acaba siendo la propia publicación de una
    # red social. Ver fuente_de_la_publicacion().
    nombre_manual = None
    print("=" * 70)
    # El pie de foto manda sobre el --tipo del workflow: lo escribio una persona
    # ahora mismo, y el otro es el valor por defecto del formulario.
    tipo, encargo, aviso_tipo = leer_encargo(args.encargo, args.tipo)
    # El Worker ya suele mandarlo aparte; esto cubre el otro camino, cuando se
    # escribe a mano "/nota <enlace> firma: Óscar Doval".
    autor = args.autor.strip()
    if not autor:
        autor, encargo = leer_autor(encargo, tipo)
    print("NOTA A PETICION%s" % (" · pedida por " + args.quien if args.quien else ""))
    if encargo:
        print("pie de foto: %s" % encargo[:110])
        print("se escribe como: %s" % tipo)
    if autor:
        print("firma: %s" % autor)
    if aviso_tipo:
        print("[aviso] %s" % aviso_tipo)
    print(peticion[:100] if peticion else "(captura de pantalla)")
    print("=" * 70)

    # SE AVISA ANTES DE GASTAR LA CORRIDA. Opinión e Investigación devuelven
    # faltantes:["autor"] y no entregan pieza si nadie firma, y eso desde
    # Telegram se ve como que el bot no hizo nada: veinte minutos de corrida en
    # verde y ningun borrador. Vale mas decirlo aqui, en dos segundos.
    #
    # El editorial NO entra: lo firma la redaccion por definicion, que es
    # justamente lo que lo distingue de una columna.
    if tipo in ("Opinión", "Investigación") and not autor:
        print("  %s necesita firma con nombre y apellido, y no llego ninguna."
              % tipo)
        if args.chat:
            _mensaje_telegram(
                args.chat,
                "✍️ <b>Falta quién firma.</b>\n\nUna %s va con nombre y "
                "apellido: sin firma sería un editorial anónimo, que es otra "
                "cosa.\n\nVuelve a pedírmela añadiendo quién la firma, por "
                "ejemplo:\n<code>firma: Óscar Doval</code>" % tipo.lower())
        return 0

    # UNA CAPTURA ES UNA PISTA, NO UNA FUENTE. Se lee para saber QUE buscar y se
    # escribe desde el articulo original. Si no aparece en la lista blanca, no
    # se escribe: decision del dueño el 01/09/2026, sabiendo que a veces dira
    # que no. Ver el encabezado de motor/captura.py.
    # LA MISMA FOTO PUEDE SER DOS COSAS OPUESTAS y solo el pie lo dice: material
    # para leer, o la portada de la pieza. Si es portada, la noticia tiene que
    # venir del texto del pie, porque una imagen no es una fuente.
    portada_url, declarar_ia, foto_local = None, False, None
    # ¿Se pidió además la lámina de Instagram? Va aparte de lo demás porque no
    # cambia lo que se escribe, sino lo que se entrega. Ver motor/lamina.py.
    from motor import lamina as _lam
    lamina_pedida = _lam.la_piden(encargo)
    if lamina_pedida:
        print("se pidió también la lámina de Instagram")
    if args.foto and papel_de_la_foto(encargo) == "portada":
        print("\n--- 0. LA FOTO ES LA PORTADA ---")
        enlace_pie = (re.search(r"https?://\S+", encargo or "") or [None])
        enlace_pie = enlace_pie.group(0) if hasattr(enlace_pie, "group") else None
        if enlace_pie:
            peticion = enlace_pie
        if not (peticion.startswith("http://") or peticion.startswith("https://")):
            print("  Me mandas la portada pero no la noticia. Necesito el enlace")
            print("  del articulo: una imagen no es una fuente que se pueda")
            print("  verificar. Mandalo en el mismo pie de foto.")
            if args.chat:
                try:
                    _mensaje_telegram(args.chat,
                        "🖼️ <b>Tengo la portada, me falta la noticia.</b>\n\n"
                        "Mándame el enlace del artículo en el mismo pie de foto. "
                        "Una imagen no es una fuente que pueda verificar.")
                except Exception:  # noqa: BLE001
                    pass
            return 1

        from motor import captura, imagen_publica
        try:
            datos, _mime = captura.bajar_de_telegram(args.foto)
            portada_url = imagen_publica.publicar(datos, "portada")
            # SE GUARDA TAMBIEN EN EL DISCO. La portada se publica para que el
            # panel pueda enlazarla, pero la lamina de Instagram se dibuja aqui
            # y necesita el archivo: bajarlo dos veces seria pedirle a Telegram
            # lo mismo por segunda vez.
            foto_local = AQUI / ("portada-recibida" +
                                 (".jpg" if "jpeg" in (_mime or "") else ".png"))
            foto_local.write_bytes(datos)
        except Exception as exc:  # noqa: BLE001
            print("  [imagen] no pude traerla (%s). Sigo sin portada." % str(exc)[:70])
        # Por defecto se declara generada con IA: el dueño confirmo el
        # 02/09/2026 que las portadas que manda por el chat son generadas. Con
        # "foto real" en el pie no se declara, porque ponersela a una foto de
        # verdad seria mentir en la otra direccion.
        declarar_ia = portada_url is not None and not NO_ES_IA.search(encargo or "")
        print("  portada: %s" % (portada_url or "no disponible"))
        print("  se declara generada con IA: %s" % ("si" if declarar_ia else "no"))

    elif args.foto:
        print("\n--- 0. LEER LA CAPTURA ---")
        from motor import captura
        hallado = captura.desde_telegram(args.foto)
        lectura = hallado.get("lectura") or {}
        if lectura.get("titular"):
            print("  dice: %s" % lectura["titular"][:88])
            if lectura.get("medio"):
                print("  medio que aparece: %s" % lectura["medio"][:50])
        if not hallado.get("ok"):
            print("\n  %s" % hallado.get("motivo", "no se pudo usar la captura"))
            print("\nNo se escribe nada. Si tienes el enlace de la nota, mandalo")
            print("con /nota y se escribe desde ahi.")
            if args.chat:
                try:
                    _avisar_captura(args.chat, hallado)
                except Exception as exc:  # noqa: BLE001
                    print("  [chat] no pude avisar (%s)" % str(exc)[:70])
            return 0
        peticion = hallado["url"]
        alternativas = hallado.get("candidatos") or []
        print("  original encontrado: %s  (%d medios lo cuentan)"
              % (hallado.get("medio", "")[:40], len(alternativas) or 1))
        print("  %s" % peticion[:100])

    es_enlace = peticion.startswith("http://") or peticion.startswith("https://")

    if not es_enlace and peticion:
        # UN TEMA SUELTO YA VALE. Hasta el 03/09/2026 se exigia enlace, y la
        # razon era buena cuando se escribio: sin buscador, escribir sobre un
        # tema era escribir de lo que el modelo recordara. Pero el buscador
        # existe desde hace dias y buscar en la lista blanca ES tener fuente.
        # La regla se quedo vieja y nadie la reviso.
        #
        # SI NO APARECE NADA, SIGUE SIN ESCRIBIRSE. Eso no cambia.
        print("\n--- 0. TEMA SUELTO: BUSCO DE QUE HABLA ---")
        from motor import buscador, captura

        # LOS DOS MODOS, PORQUE NINGUNO BASTA SOLO. El de noticias trae fecha y
        # lo reciente, pero su relevancia es INESTABLE: el 03/09/2026, con
        # "María Corina Machado", devolvio seis piezas correctas de ese dia y,
        # minutos despues y con los mismos parametros, «Giorgia Meloni's
        # enviable stability» y un exlider de Reform Wales. El general acierta
        # el tema pero no filtra por fecha ni la devuelve. Juntarlos y quedarse
        # con lo que NOMBRA el asunto sale mejor que elegir uno.
        consulta = _consulta_limpia(peticion)
        if consulta != peticion:
            print("  busco por: %s" % consulta)
        crudos = []
        for dias, noticias in ((3, True), (15, True), (15, False)):
            crudos += buscador.buscar(consulta, dias=dias, maximo=10,
                                      solo_lista_blanca=True,
                                      como_noticias=noticias, ordenar=False)
        vistos, candidatos = set(), []
        for c in crudos:
            u = (c.get("url") or "").split("?")[0]
            if not u or u in vistos or not _habla_de(c, consulta):
                continue
            vistos.add(u)
            candidatos.append(c)
        print("  %d de %d candidatos nombran el asunto"
              % (len(candidatos), len(crudos)))
        if not candidatos:
            # Ultimo recurso: el emparejador de capturas, que rastrea tambien
            # los RSS de la lista. Para un tema que no es de esta semana -un
            # acuerdo en marcha, una serie- suele tenerlo.
            print("  nada en el buscador; pruebo el rastreo de la lista")
            lectura = {"titular": peticion, "busqueda": consulta, "medio": "",
                       "fecha": "", "texto": "", "legible": True}
            # umbral=0: aqui el "titular" es lo que escribio la persona, no un
            # titular real, asi que medir parecido contra el no dice nada. Lo
            # que filtra es la lista blanca y el propio buscador.
            candidatos = [c for c in captura.buscar_original(lectura, umbral=0.0)
                          if _habla_de(c, consulta)]
        if not candidatos:
            print("  No encuentro nada de eso en los medios de la lista.")
            _mensaje_telegram(args.chat,
                              "🔍 <b>No encuentro nada sobre eso.</b>\n\n"
                              + _escapar(peticion[:120]) +
                              "\n\nPuede que aún no lo haya publicado ningún "
                              "medio de la lista. Si tienes el enlace, mándamelo "
                              "con <code>/nota</code>.")
            return 0
        # LOS QUE NO SE DEJAN LEER, AL FINAL. Reuters devolvio 401 siete veces
        # seguidas en la corrida del 03/09/2026 y se llevo casi todos los
        # intentos; lo unico que quedo legible fue una ficha de podcast. Ir en
        # ese orden no es una preferencia editorial: los de arriba simplemente
        # no tienen texto que leer.
        candidatos.sort(key=lambda c: captura._tras_muro(c.get("url", "")))
        print("  %d medios lo cuentan. El primero:" % len(candidatos))
        print("  %s · %s" % (candidatos[0].get("medio", ""),
                             candidatos[0].get("titular", "")[:70]))
        peticion = candidatos[0]["url"]
        alternativas = candidatos
        es_enlace = True

    # Lo barato primero: ¿ya lo contamos?
    # FORZAR ES UNA PALABRA EN EL CHAT, no una bandera que nadie va a recordar.
    # Con "igual" detras del enlace basta, que es como se dice en castellano:
    # "escríbela igual". El propio bot lo explica cuando para una repetida, y
    # hasta hoy lo ofrecia sin que existiera manera de hacerlo.
    forzar = args.forzar or bool(
        re.search(r"\b(igual|forzar|for[zc]ala|aunque (ya )?(este|est[eé]|salga))\b",
                  _plano(args.encargo)))

    print("\n--- 1. ¿YA ESTA PUBLICADO? ---")
    if forzar:
        print("  (pedida a la fuerza: no se comprueba)")
    try:
        from motor import memoria
        # UN TUIT SE LEE COMO TUIT TAMBIEN AQUI. El paso 2 ya lo distingue, pero
        # esta comprobacion llamaba a leer_enlace() sobre la direccion de x.com,
        # que no sirve el texto a un lector automatico: devuelve su muro de
        # acceso. El titulo que salia de ahi no era el del tuit, y se comparaba
        # ESO contra lo publicado. El 04/09/2026 un tuit sobre la inflacion de
        # Venezuela se bloqueo señalando una nota del oro de Países Bajos, que
        # no tiene nada que ver: el bloqueo era correcto -esa noticia si estaba
        # publicada- pero la pieza que se nombraba salia de comparar basura.
        # Un motivo equivocado hace que una decision buena parezca un fallo.
        post = leer_publicacion(peticion)
        if post is not None:
            titulo_previo = (post.get("texto") or "")[:200]
        else:
            titulo_previo, _, _ = leer_enlace(peticion)
        # Se compara contra las piezas DE SU MISMO FORMATO: una columna sobre lo
        # que ya se reporto no es un duplicado. Ver memoria.ya_cubierto().
        from armar_carga import FORMATOS
        formato = FORMATOS.get(_plano(tipo), "noticia")
        ya = (None if forzar else
              (memoria.ya_cubierto(titulo_previo, formato=formato)
               if titulo_previo else None))
        if ya:
            print("  SI. Coincide con: %s" % ya["titulo"])
            print("  https://www.sureconomics.com/%s" % ya["slug"])
            print("\nNo se escribe nada. Si aun asi la quieres, dilo y se fuerza.")
            # ESTO SE AVISA AL CHAT O PARECE QUE EL BOT SE COLGO. Salia solo por
            # el log de Actions, que no lo mira nadie desde Telegram: se pedia
            # una nota, no llegaba nada, y la corrida constaba en verde. Paso el
            # 03/09/2026 con el relevo en Apple, que ya estaba publicada.
            if args.chat:
                try:
                    _mensaje_telegram(
                        args.chat,
                        "📌 <b>Esa ya está publicada.</b>\n\n"
                        "<i>%s</i>\nhttps://www.sureconomics.com/%s\n\n"
                        "Si aun así la quieres, la escribo otra vez:\n"
                        "<code>/nota %s igual</code>"
                        % (_escapar(ya["titulo"]), ya["slug"],
                           _escapar(peticion)),
                        [("Escribirla igual", "forzar:1")])
                except Exception as exc:  # noqa: BLE001
                    print("  [chat] no pude avisar (%s)" % str(exc)[:70])
            return 0
        print("  no, es nueva")
    except Exception as exc:  # noqa: BLE001
        print("  [aviso] no pude comprobarlo (%s). Se sigue." % str(exc)[:60])

    # UN TUIT ES UNA PISTA, NO UNA FUENTE. Mismo criterio que las capturas: se
    # lee para saber QUE buscar, y se escribe desde el articulo original. Un
    # tuit no se puede auditar, y en esta misma casa uno afirmaba algo falso
    # sobre las Malvinas que solo se detecto comprobandolo aparte.
    if ES_TUIT.match(peticion) or ES_INSTAGRAM.match(peticion):
        post = leer_publicacion(peticion) or {}
        # 'cuenta' y NO 'autor': aqui vivia un fallo callado. Esta rama asignaba
        # a 'autor' el nombre de la cuenta y pisaba la firma de la pieza, asi que
        # "/nota <tuit> firma: Óscar Doval" habria publicado firmado por la
        # cuenta del tuit. Quien firma y quien publico el post no son lo mismo.
        cuenta, texto = post.get("autor"), post.get("texto")
        que_es = post.get("que_es") or "publicación"
        print("\n--- 2. ES UN %s: LO LEO Y BUSCO EL ORIGINAL ---"
              % que_es.upper())
        if not texto:
            print("  No pude leer ese %s." % que_es)
            _mensaje_telegram(args.chat,
                              "🔍 <b>No pude leer ese enlace.</b>\n\nPuede estar "
                              "borrado o ser una cuenta privada. Si tienes el "
                              "enlace de la noticia, mándamelo con "
                              "<code>/nota</code>.")
            return 0
        print("  @%s: %s" % (cuenta, texto[:110]))
        from motor import captura
        # El texto crudo del tuit NO sirve como consulta: hashtags, arrobas y
        # guiones dan cero resultados. Se destila a titular y palabras clave.
        lectura = captura.leer_texto(texto) or {
            "titular": texto[:180], "busqueda": texto[:180],
            "medio": cuenta, "fecha": "", "texto": texto, "legible": True}
        lectura["medio"] = cuenta
        print("  busco: %s" % lectura.get("busqueda", ""))
        candidatos = captura.buscar_original(lectura)
        if not candidatos:
            # SI NO HAY ARTICULO, LA PUBLICACION PUEDE SER LA FUENTE, pero solo
            # cuando se sabe DE QUIEN ES la cuenta. Ver fuente_de_la_publicacion.
            propia = fuente_de_la_publicacion(post)
            if propia:
                print("  sin artículo, pero la cuenta es de %s (%s): escribo "
                      "desde la publicación" % (propia["medio"], propia["por"]))
                # Se registra y se SIGUE la cadena de siempre. No hay una via
                # aparte: auditoria, correo, Telegram y panel son los mismos, y
                # duplicarlos es como se llega a que uno se arregle y el otro no.
                nombre_manual = registrar_publicacion(peticion, post, propia)
                encargo = (encargo + " " + propia["instruccion"]).strip()
            else:
                print("  No encuentro esta noticia en ninguna fuente verificable.")
                _avisar_captura(args.chat, {
                    "lectura": lectura,
                    "motivo": "leí la publicación, pero no encuentro la noticia "
                              "en ninguna fuente verificable, y la cuenta que la "
                              "publica no es de un medio de la lista ni de una "
                              "figura pública con cuenta registrada."})
                return 0
        # Solo si HAY original. Cuando la fuente acaba siendo la propia
        # publicación, `candidatos` está vacía y esto reventaba con IndexError
        # justo después de registrarla bien.
        if candidatos:
            print("  original: %s · %s" % (candidatos[0].get("medio", ""),
                                           candidatos[0].get("titular", "")[:70]))
            peticion = candidatos[0]["url"]
            alternativas = candidatos

    if nombre_manual:
        # La fuente ya está registrada: es la propia publicación. No hay nada
        # que leer y se entra directo a escribir, por la cadena de siempre.
        print("\n--- 2. LA FUENTE ES LA PROPIA PUBLICACIÓN ---")
        print("  registrada como '%s'" % nombre_manual)
        # portada_url y declarar_ia van por defecto: una publicación de red
        # social no trae portada adjunta, y de la portada se ocupa armar_carga.
        return producir_y_entregar(nombre_manual, tipo, encargo, autor, args,
                                   "", False, foto_local, lamina_pedida)

    print("\n--- 2. LEER LA FUENTE ---")

    # SE PRUEBAN TODOS LOS CANDIDATOS, NO SOLO EL PRIMERO. Cuando la noticia
    # viene de una captura o de un tuit hay varios medios contando lo mismo, y
    # unos cuantos bloquean la lectura automatica o estan tras un muro de pago.
    # Rendirse con el primero es tirar la noticia teniendo cinco alternativas
    # buenas en la mano: el 03/09/2026 pasó dos veces seguidas.
    #
    # Un enlace pedido a mano con /nota es una lista de uno: si ese falla, no
    # hay nada que probar y se avisa igual que antes.
    por_probar = [peticion] + [c["url"] for c in (alternativas or [])
                               if c.get("url") and c["url"] != peticion]
    leidas, fallos, dominios = [], [], set()
    for url in por_probar:
        if len(leidas) >= MAX_FUENTES:
            break
        # UN MEDIO UNA VEZ. El buscador devuelve la misma nota de La Nacion dos
        # veces, con y sin "www", y meter dos copias del mismo texto en el
        # expediente no contrasta nada: solo duplica sus errores.
        dom = re.sub(r"^www\.", "", urllib.parse.urlparse(url).netloc)
        if dom in dominios:
            continue
        try:
            t, p, s = leer_enlace(url)
        except Exception as exc:  # noqa: BLE001
            fallos.append((url, str(exc)[:70]))
            print("  no se pudo leer %s (%s)" % (dom[:32], str(exc)[:46]))
            continue
        if not p:
            fallos.append((url, "responde pero no trae texto de nota"))
            print("  sin texto de nota: %s" % dom[:40])
            continue
        dominios.add(dom)
        leidas.append({"url": url, "titulo": t, "parrafos": p,
                       "medio": s or medio_de(url)})
        print("  leído: %-24s %d parrafos" % (dom[:24], len(p)))

    if leidas:
        # La primera manda: da el titular y el hecho. Las demas entran como
        # contraste, con su propia fuente citada.
        titulo = leidas[0]["titulo"]
        parrafos = leidas[0]["parrafos"]
        peticion = leidas[0]["url"]
    else:
        parrafos = None

    if not parrafos:
        print("  Ninguno de los %d enlaces se pudo leer." % len(por_probar))
        # SE LE CONTESTA SIEMPRE A QUIEN LO PIDIO. El 02/09/2026 una peticion
        # murio aqui y el dueño no recibio nada: desde su lado el bot se quedo
        # mudo y tuvo que ir a mirar el registro de Actions.
        detalle = "\n".join("• " + _escapar(u.split("/")[2]) for u, _ in fallos[:5])
        _mensaje_telegram(
            args.chat,
            "⚠️ <b>No pude leer ninguna de las fuentes.</b>\n\n" + detalle +
            "\n\nUnos bloquean la lectura automática y otros están tras un muro "
            "de pago. Si encuentras la misma noticia en otro medio, mándamela "
            "con <code>/nota</code>.")
        return 0
    print("  %s" % titulo[:90])
    print("  %d parrafos, %d caracteres" % (len(parrafos), sum(len(p) for p in parrafos)))

    # SE REGISTRAN TODAS LAS QUE SE PUDIERON LEER. Dos o tres medios contando el
    # mismo hecho no es comodidad: si uno se equivoca en una cifra, el otro no
    # la respalda y el auditor lo ve. producir.py las funde con componer().
    (AQUI / "fuentes_manuales").mkdir(exist_ok=True)
    nombres = []
    for i, f in enumerate(leidas):
        apodo = _apodo(f["titulo"] or f["url"])
        if apodo in nombres:                      # dos titulares casi iguales
            apodo = "%s-%d" % (apodo[:34], i + 1)
        archivo = AQUI / "fuentes_manuales" / (apodo + ".txt")
        archivo.write_text(
            "url: %s\nmedio: %s\nfecha: %s\n\n%s\n" % (
                f["url"], f["medio"], date.today().isoformat(),
                "\n\n".join(f["parrafos"])),
            encoding="utf-8")

        r = subprocess.run([sys.executable, str(AQUI / "agregar_fuente.py"), str(archivo)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode != 0:
            print("  no se pudo registrar %s" % f["medio"][:30])
            print((r.stdout or "") + (r.stderr or "")[-200:])
            continue
        # Se lee el nombre que dice el registro, no se vuelve a calcular. Ver
        # abajo: dos sitios calculando el mismo nombre se desincronizan.
        dicho = re.search(r"manual:(\S+)", r.stdout or "")
        nombres.append(dicho.group(1) if dicho else apodo.rstrip("-"))

    if not nombres:
        print("  No se pudo registrar ninguna fuente.")
        _avisar_fallo(args.chat, "No pude registrar ninguna fuente",
                      "Leí la página pero el expediente salió vacío. "
                      "Prueba con otro medio que cuente lo mismo.")
        return 1
    print("  %d fuente(s) en el expediente: %s" % (len(nombres), ", ".join(nombres)))
    r = type("R", (), {"stdout": "manual:" + ",".join(nombres), "returncode": 0})()

    # SE LEE EL NOMBRE QUE DICE EL REGISTRO, no se vuelve a calcular aqui.
    # agregar_fuente.py limpia el nombre a su manera y le quita el guion final;
    # _apodo() corta a 38 caracteres y puede dejarlo. El 01/09/2026 una peticion
    # se guardo como "u-s-strikes-iran-as-tehran-retaliates" y se pidio como
    # "...retaliates-": el extractor no la encontro y la corrida murio despues de
    # haber bajado la fuente. Dos sitios calculando el mismo nombre con reglas
    # distintas se desincronizan siempre; uno lo dice y el otro obedece.
    dicho = re.search(r"manual:(\S+)", r.stdout or "")
    if dicho:
        nombre = dicho.group(1)
    else:
        nombre = nombre.rstrip("-")
        print("  [aviso] el registro no dijo el nombre; uso '%s'" % nombre)
    print("  fuente registrada como '%s'" % nombre)

    return producir_y_entregar(nombre, tipo, encargo, autor, args,
                               portada_url, declarar_ia, foto_local,
                               lamina_pedida)


if __name__ == "__main__":
    sys.exit(main())
