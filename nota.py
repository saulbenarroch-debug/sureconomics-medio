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

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _plano(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


TIPOS = ["Noticia", "Opinión", "Editorial", "Investigación", "Educación"]


def leer_encargo(texto, tipo_por_defecto="Noticia"):
    """Del pie de foto saca el tipo de pieza y deja el resto como instruccion.

    El pie es lo que la persona escribio junto a la captura: "hazla editorial",
    "enfocala en Venezuela". Lo primero cambia el tipo, lo segundo es una orden
    de edicion y viaja en --encargo, que es el mismo camino por el que entro la
    tesis de Óscar en la serie del acuerdo petrolero.

    "ARTICULO" NO ES UN TIPO QUE EL MOTOR SEPA ESCRIBIR. El panel lo tiene como
    formato y el redactor no: sus cinco prompts son Noticia, Opinion, Editorial,
    Investigacion y Educacion. Si alguien lo pide, se dice en vez de mandar
    calladamente una noticia y que parezca que se ignoro la instruccion.
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
    if re.search(r"\barticulo", plano):
        return (tipo_por_defecto, texto,
                "Pediste artículo. El motor escribe Noticia, Opinión, Editorial, "
                "Investigación o Educación; va como %s y el resto del pie se "
                "usa igual." % tipo_por_defecto)
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


def _mensaje_telegram(chat, texto):
    """Un mensaje suelto al chat. Devuelve True si Telegram lo acepto."""
    import json as _json

    ficha = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not ficha or not chat:
        return False
    pet = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % ficha,
        data=_json.dumps({"chat_id": chat, "text": texto, "parse_mode": "HTML",
                          "disable_web_page_preview": True}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pet, timeout=30):
        return True


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
    if hallado.get("dudoso") and hallado.get("candidatos"):
        partes += ["", "Lo más parecido que encontré:"]
        for c in hallado["candidatos"]:
            partes.append("· <b>%s</b> · %s\n<code>/nota %s</code>" % (
                _escapar((c.get("medio") or "")[:26]),
                _escapar((c.get("titular") or "")[:110]),
                _escapar(c.get("url") or "")))
        partes += ["", "Si alguna es, cópiame su línea <code>/nota</code>."]
    else:
        partes += ["", "Solo escribo desde el artículo original de un medio de "
                   "la lista, para que las cifras se puedan verificar. Si tienes "
                   "el enlace, mándalo con <code>/nota &lt;enlace&gt;</code>."]
    return _mensaje_telegram(chat, "\n".join(partes))


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
    ap.add_argument("--chat", default="", help="chat de Telegram al que devolverla")
    ap.add_argument("--sin-subir", action="store_true",
                    help="escribe y entrega, pero no toca el panel")
    ap.add_argument("--forzar", action="store_true",
                    help="escribe aunque la memoria la de por publicada")
    ap.add_argument("--encargo", default="",
                    help="instruccion de edicion; en Telegram, el pie de foto")
    args = ap.parse_args()

    peticion = args.peticion.strip()
    print("=" * 70)
    # El pie de foto manda sobre el --tipo del workflow: lo escribio una persona
    # ahora mismo, y el otro es el valor por defecto del formulario.
    tipo, encargo, aviso_tipo = leer_encargo(args.encargo, args.tipo)
    print("NOTA A PETICION%s" % (" · pedida por " + args.quien if args.quien else ""))
    if encargo:
        print("pie de foto: %s" % encargo[:110])
        print("se escribe como: %s" % tipo)
    if aviso_tipo:
        print("[aviso] %s" % aviso_tipo)
    print(peticion[:100] if peticion else "(captura de pantalla)")
    print("=" * 70)

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
        print("  original encontrado: %s" % hallado.get("medio", "")[:40])
        print("  %s" % peticion[:100])

    es_enlace = peticion.startswith("http://") or peticion.startswith("https://")

    if not es_enlace:
        # Sin enlace no hay documento que verificar. Se podria buscar en los
        # feeds, pero eso es justo lo que hace la tanda: si el tema esta ahi,
        # saldra sola. Se pide el enlace, que es barato para quien lo manda.
        print("\nEsto no es un enlace. Manda la direccion de la nota:")
        print("  /nota https://medio.com/la-noticia")
        print("\nCon el enlace hay un documento concreto que verificar. Con un")
        print("tema suelto habria que fiarse de lo que el modelo recuerde, y")
        print("eso es exactamente lo que este motor no hace.")
        return 1

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
        titulo_previo, _, _ = leer_enlace(peticion)
        ya = (None if forzar else
              (memoria.ya_cubierto(titulo_previo) if titulo_previo else None))
        if ya:
            print("  SI. Coincide con: %s" % ya["titulo"])
            print("  https://www.sureconomics.com/%s" % ya["slug"])
            print("\nNo se escribe nada. Si aun asi la quieres, dilo y se fuerza.")
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

    print("\n--- 2. LEER LA FUENTE ---")
    try:
        titulo, parrafos, sitio = leer_enlace(peticion)
    except Exception as exc:  # noqa: BLE001
        print("  No pude leer ese enlace: %s" % str(exc)[:90])
        # SE LE CONTESTA SIEMPRE A QUIEN LO PIDIO. El 02/09/2026 una peticion
        # murio aqui y el dueño no recibio nada: desde su lado el bot se quedo
        # mudo y tuvo que ir a mirar el registro de Actions.
        _mensaje_telegram(args.chat, "⚠️ <b>No pude leer ese enlace.</b>\n\n"
                          + _escapar(str(exc)[:120]) +
                          "\n\nAlgunos medios bloquean la lectura automática. "
                          "Prueba con otro medio que cuente lo mismo.")
        return 0
    if not parrafos:
        print("  El enlace responde pero no encuentro texto de nota.")
        _mensaje_telegram(args.chat, "⚠️ <b>Ese enlace no tiene texto de nota.</b>"
                          "\n\nPuede ser un vídeo, una galería o un muro de pago. "
                          "Mándame el enlace del artículo y lo escribo.")
        return 0
    print("  %s" % titulo[:90])
    print("  %d parrafos, %d caracteres" % (len(parrafos), sum(len(p) for p in parrafos)))

    nombre = _apodo(titulo or peticion)
    archivo = AQUI / "fuentes_manuales" / (nombre + ".txt")
    archivo.parent.mkdir(exist_ok=True)
    archivo.write_text(
        "url: %s\nmedio: %s\nfecha: %s\n\n%s\n" % (
            peticion, sitio or medio_de(peticion), date.today().isoformat(),
            "\n\n".join(parrafos)),
        encoding="utf-8")

    r = subprocess.run([sys.executable, str(AQUI / "agregar_fuente.py"), str(archivo)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("  No se pudo registrar la fuente:")
        print((r.stdout or "") + (r.stderr or "")[-300:])
        return 1

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
         "--tipo", tipo, "--manual", nombre, "--encargo", encargo],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=25 * 60)
    print((r.stdout or "")[-1500:])
    if r.returncode != 0 and (r.stderr or "").strip():
        print("  FALLO:")
        for l in (r.stderr or "").strip().splitlines()[-6:]:
            print("    " + l[:150])

    borrador = AQUI / "borradores" / ("%s_%s.txt" % (nombre, args.tipo.lower()))
    if not borrador.exists():
        print("\nNo se genero el borrador. Revisa el fallo de arriba.")
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
