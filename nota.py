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
    portada_url, declarar_ia = None, False
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
        if ES_TUIT.match(peticion):
            _, texto_tuit = leer_tuit(peticion)
            titulo_previo = (texto_tuit or "")[:200]
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
    if ES_TUIT.match(peticion):
        print("\n--- 2. ES UN TUIT: LO LEO Y BUSCO EL ORIGINAL ---")
        autor, texto = leer_tuit(peticion)
        if not texto:
            print("  No pude leer ese tuit.")
            _mensaje_telegram(args.chat, "🔍 <b>No pude leer ese tuit.</b>\n\n"
                              "Puede estar borrado o ser una cuenta protegida. "
                              "Si tienes el enlace de la noticia, mándamelo con "
                              "<code>/nota</code>.")
            return 0
        print("  @%s: %s" % (autor, texto[:110]))
        from motor import captura
        # El texto crudo del tuit NO sirve como consulta: hashtags, arrobas y
        # guiones dan cero resultados. Se destila a titular y palabras clave.
        lectura = captura.leer_texto(texto) or {
            "titular": texto[:180], "busqueda": texto[:180],
            "medio": autor, "fecha": "", "texto": texto, "legible": True}
        lectura["medio"] = autor
        print("  busco: %s" % lectura.get("busqueda", ""))
        candidatos = captura.buscar_original(lectura)
        if not candidatos:
            print("  No encuentro esta noticia en ninguna fuente verificable.")
            _avisar_captura(args.chat, {
                "lectura": lectura,
                "motivo": "leí el tuit, pero no encuentro la noticia en ninguna "
                          "fuente verificable. Un tuit solo no se puede auditar."})
            return 0
        print("  original: %s · %s" % (candidatos[0].get("medio", ""),
                                       candidatos[0].get("titular", "")[:70]))
        peticion = candidatos[0]["url"]
        alternativas = candidatos

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

    # EL NOMBRE SE CALCULA EN DOS SITIOS Y HABIA QUE MIRAR EL OTRO. producir.py
    # bautiza el borrador con la PRIMERA fuente (`args.manual.split(",")[0]`),
    # pero aqui se pasaba la lista entera: desde que /nota lee varias fuentes,
    # `nombre` es "n1,n2,n3" y este exists() daba False SIEMPRE. La pieza se
    # escribia, pasaba el auditor y se quedaba en el disco del runner: no
    # llegaba a Telegram ni subia al panel, y la corrida terminaba diciendo que
    # no se habia generado. Estuvo asi desde que se añadio el multi-fuente.
    #
    # Y el tipo tiene que ser el RESUELTO, no args.tipo: con "hazla editorial"
    # en el encargo, producir.py escribe `_editorial.txt` y aqui se buscaba
    # `_noticia.txt`.
    base = nombre.split(",")[0].strip()
    borrador = AQUI / "borradores" / ("%s_%s.txt" % (base, tipo.lower()))
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


if __name__ == "__main__":
    sys.exit(main())
