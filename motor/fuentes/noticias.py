"""Extractor (A4) de diarios. La via principal para la noticia del dia.

Decision editorial del dueño: se trabaja como el bot de Telegram — se leen los
diarios importantes y **se los cita**. Eso es periodismo normal: la cifra no es
nuestra, es de quien la publico, y se dice.

De ahi salen las dos reglas de este modulo:

1. **Feeds directos del diario, nunca Google News.** Google no entrega el enlace
   del medio sino un redirector suyo que desde 2024 salta por JavaScript, asi
   que no se puede resolver desde el servidor. Sin enlace real no hay
   "Sacado de:", y sin eso no hay atribucion.
2. **Lista blanca.** Solo se leen los medios de MEDIOS. Que diarios cita el medio
   es una decision editorial, no tecnica, y esta lista es donde vive.

Verificado el 24 de agosto de 2026.
"""

import re
import socket
import urllib.parse
from datetime import datetime, timezone
# OJO: timegm(), no mktime(). feedparser devuelve la fecha del feed ya en UTC
# como struct_time, pero mktime() la interpreta como hora LOCAL: en una maquina
# en Venezuela (UTC-4) desplazaba todo 4 horas y una nota de las 20:25 UTC salia
# fechada al dia siguiente. En GitHub Actions (que corre en UTC) coincidia por
# casualidad, por eso el fallo solo se veia en local. timegm() es correcto en
# las dos.
from calendar import timegm

import feedparser

from motor.paquete import Cifra, Fuente, Paquete

# Regla de oro #3: feedparser/urllib NO traen timeout y una fuente que acepta la
# conexion y luego se cuelga traba el proceso ~15 minutos.
socket.setdefaulttimeout(25)

AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Lista blanca. 'economia' = el feed ya viene filtrado por seccion; si es False,
# hay que filtrar por palabras clave porque el feed trae de todo.
MEDIOS = {
    "elpais":      dict(nombre="El País", pais="España", economia=True,
                        url="https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"),
    "clarin":      dict(nombre="Clarín", pais="Argentina", economia=True,
                        url="https://www.clarin.com/rss/economia/"),
    "folha":       dict(nombre="Folha de S.Paulo", pais="Brasil", economia=True,
                        url="https://feeds.folha.uol.com.br/mercado/rss091.xml"),
    "estadao":     dict(nombre="O Estado de S. Paulo", pais="Brasil", economia=True,
                        url="https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/economia/"),
    "eltiempo":    dict(nombre="El Tiempo", pais="Colombia", economia=True,
                        url="https://www.eltiempo.com/rss/economia.xml"),
    "elcomercio":  dict(nombre="El Comercio", pais="Perú", economia=False,
                        url="https://elcomercio.pe/arcio/rss/"),
    "latercera":   dict(nombre="La Tercera", pais="Chile", economia=False,
                        url="https://www.latercera.com/arcio/rss/"),
    "elnacional":  dict(nombre="El Nacional", pais="Venezuela", economia=False,
                        url="https://www.elnacional.com/economia/feed/"),
    "descifrado":  dict(nombre="Descifrado", pais="Venezuela", economia=True,
                        url="https://www.descifrado.com/category/economia/feed/"),
    # La SECCION de economia, no el feed general: el general trae de todo y
    # obligaba a filtrar por palabras. Asi lo tiene el bot de Telegram.
    "cocuyo":      dict(nombre="Efecto Cocuyo", pais="Venezuela", economia=True,
                        url="https://efectococuyo.com/economia/feed/"),
    "talcual":     dict(nombre="TalCual", pais="Venezuela", economia=True,
                        url="https://talcualdigital.com/category/economia/feed/"),
    "elestimulo":  dict(nombre="El Estímulo", pais="Venezuela", economia=False,
                        url="https://elestimulo.com/feed/"),
    "bbcmundo":    dict(nombre="BBC Mundo", pais="Reino Unido", economia=True,
                        url="https://feeds.bbci.co.uk/mundo/economia/rss.xml"),
    # Venezuela, ampliacion del 24/08/2026: con cinco medios venezolanos habia
    # temas -petroleo, reconstruccion- que no aparecian en ninguno.
    "elpitazo":    dict(nombre="El Pitazo", pais="Venezuela", economia=False,
                        url="https://elpitazo.net/feed/"),
    "runrunes":    dict(nombre="Runrunes", pais="Venezuela", economia=False,
                        url="https://runrun.es/feed/"),
    "cronicauno":  dict(nombre="Crónica Uno", pais="Venezuela", economia=False,
                        url="https://cronica.uno/feed/"),
    # Energia. Van en INGLES: parafrasear y atribuir, nunca entrecomillar una
    # traduccion propia.
    "oilprice":    dict(nombre="OilPrice", pais="EE. UU.", economia=True,
                        idioma="en", url="https://oilprice.com/rss/main"),
    "worldoil":    dict(nombre="World Oil", pais="EE. UU.", economia=True,
                        idioma="en", url="https://worldoil.com/rss?feed=news"),
    # Internacional en español, para lo que no cubre la prensa latinoamericana.
    "dw":          dict(nombre="DW", pais="Alemania", economia=True,
                        url="https://rss.dw.com/rdf/rss-sp-eco"),
    "france24":    dict(nombre="France 24", pais="Francia", economia=True,
                        url="https://www.france24.com/es/economia/rss"),
    # Ampliacion del 25/08/2026. Salio de cruzar los temas del dia con lo que
    # teniamos: de doce, seis no tenian ninguna fuente, y cinco de esos seis eran
    # comercio internacional y economia de paises que no cubriamos.
    "mercopress":  dict(nombre="MercoPress", pais="Latam", economia=False,
                        url="https://es.mercopress.com/rss/"),
    "larepublica": dict(nombre="La República", pais="Colombia", economia=True,
                        url="https://www.larepublica.co/rss/economia"),
    "semana":      dict(nombre="Semana", pais="Colombia", economia=True,
                        url="https://www.semana.com/arc/outboundfeeds/rss/"
                            "category/economia/?outputType=xml"),
    "elfinanciero": dict(nombre="El Financiero", pais="México", economia=True,
                         url="https://www.elfinanciero.com.mx/arc/outboundfeeds/"
                             "rss/category/economia/?outputType=xml"),
    "expansionmx": dict(nombre="Expansión", pais="México", economia=True,
                        url="https://expansion.mx/rss/economia"),
    "expansiones": dict(nombre="Expansión", pais="España", economia=True,
                        url="https://e00-expansion.uecdn.es/rss/economia.xml"),
    "oncuba":      dict(nombre="OnCuba", pais="Cuba", economia=False,
                        url="https://oncubanews.com/feed/"),
    # FUENTE PRIMARIA, no prensa: comunicados del propio Mercosur. Los acuerdos
    # comerciales los anuncia el bloque, no un diario, y ahi la fuente original
    # vale mas que cualquier reseña.
    "mercosur":    dict(nombre="Mercosur", pais="Latam", economia=False,
                        primaria=True,
                        url="https://www.mercosur.int/feed/"),
    # Pedidos por la gerencia el 24/08/2026. Sus direcciones "clasicas" dan 404;
    # las buenas son las de ARC (el gestor de contenidos que usan varios diarios).
    "infobae":     dict(nombre="Infobae", pais="Argentina", economia=True,
                        url="https://www.infobae.com/arc/outboundfeeds/rss/"
                            "category/economia/?outputType=xml"),
    "infobaeam":   dict(nombre="Infobae América", pais="Argentina", economia=False,
                        url="https://www.infobae.com/arc/outboundfeeds/rss/"
                            "category/america/?outputType=xml"),
    # Feeds de SECCION, no el del sitio completo. El generalista trae de todo:
    # en la primera prueba devolvio una nota sobre cuanto dinero le deja Harry
    # Potter a Rupert Grint. Ya estaba resuelto asi en el bot de Telegram
    # (`FEEDS` en cloudflare-worker/worker.js), con el mismo aviso al lado.
    "bbglinea":    dict(nombre="Bloomberg Línea", pais="Latam", economia=True,
                        url="https://www.bloomberglinea.com/arc/outboundfeeds/"
                            "rss/category/economia/?outputType=xml"),
    "bbglinmerc":  dict(nombre="Bloomberg Línea", pais="Latam", economia=True,
                        url="https://www.bloomberglinea.com/arc/outboundfeeds/"
                            "rss/category/mercados/?outputType=xml"),
    # Nicho latinoamericano que ya usaba el bot: negocios, M&A, capital de riesgo
    # y fintech. Utiles para la linea de Conocimiento.
    # Publica POCO: suele haber varios dias entre notas. Consultarla con ventana
    # ancha (--horas 168 o mas) o parecera que esta caida cuando no lo esta.
    "latamlist":   dict(nombre="LatamList", pais="Latam", economia=True,
                        idioma="en",
                        url="https://latamlist.com/feed/"),
    "iupana":      dict(nombre="iupana", pais="Latam", economia=True,
                        url="https://iupana.com/feed/"),
    # Bloomberg va en INGLES y con muro de pago: ver la nota de abajo.
    "bloomberg":   dict(nombre="Bloomberg", pais="EE. UU.", economia=True,
                        idioma="en", muro_de_pago=True,
                        url="https://feeds.bloomberg.com/economics/news.rss"),
    "bbgmercados": dict(nombre="Bloomberg", pais="EE. UU.", economia=True,
                        idioma="en", muro_de_pago=True,
                        url="https://feeds.bloomberg.com/markets/news.rss"),
}

# OJO CON BLOOMBERG (bloomberg.com, no Bloomberg Línea):
#   1. Sus notas estan tras MURO DE PAGO. Citarlo significa mandar al lector a
#      algo que no puede abrir. Se marca en el paquete para que Edicion decida.
#   2. Viene en INGLES: cualquier cita textual habria que traducirla, y una cita
#      traducida ya no es textual. Mejor parafrasear y atribuir.
#   Bloomberg Línea no tiene ninguno de los dos problemas: es español y abierto.

# DE DONDE SALE ESTA LISTA
# Los medios venezolanos y los de nicho latinoamericano vienen del bot de
# Telegram, que lleva meses en produccion con ellos: `SOURCES` en
# telegram-finance-bot/bot.py y, mas completa, `FEEDS` en
# cloudflare-worker/worker.js. Antes de buscar un feed nuevo por tu cuenta,
# mira ahi: la primera version de este archivo se salto ese paso y repitio dos
# errores que el bot ya tenia resueltos y documentados.

# PENDIENTES DE DECISION EDITORIAL — responden, pero NO se agregan sin que lo
# apruebe Jefatura Editorial, porque son medios de Estado:
#   RT en Español   https://actualidad.rt.com/feeds/all.rss   (Estado ruso)
#   Prensa Latina   https://www.prensa-latina.cu/feed/        (Estado cubano)
# Sirven para conocer la posicion oficial de esos gobiernos, que a veces ES la
# noticia. Pero un medio que presume de verificar no mete medios estatales en su
# lista blanca sin decidirlo, y si los mete tiene que etiquetarlos como tales.
# Que diarios cita el medio es decision editorial, no tecnica.

# Comprobados el 24/08/2026 y NO funcionan: no volver a agregarlos sin verificar.
#   Infobae https://www.infobae.com/feeds/rss/            -> 404 (usar la de ARC)
#   La Nación https://www.lanacion.com.ar/economia/rss/   -> 404
#   El Universal MX https://www.eluniversal.com.mx/rss.xml -> 404
#   Bloomberg Línea https://www.bloomberglinea.com/feed/   -> 404 (usar la de ARC)
# Y los que ya venian marcados como caidos en el bot de Telegram:
#   bancaynegocios, finanzasdigital, lapatilla, eleconomista.com.mx, portafolio.co

ECONOMICO = re.compile(
    r"econom|inflaci|precio|d[oó]lar|peso|real |banco central|tasa|inter[eé]s|"
    r"pib|fiscal|d[eé]ficit|deuda|impuesto|salario|empleo|desemple|export|import|"
    r"inversi|mercado|bolsa|acciones|bono|reservas|remesa|cambiari|devaluaci|"
    r"presupuesto|subsidi|combustible|petr[oó]leo|gas |miner|agro|cosecha|"
    r"empresa|negocio|industri|comercio|fmi|banco mundial|cepal", re.IGNORECASE)

_NUMERO_ES = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+"
UNIDADES = re.compile(
    r"(?P<num>" + _NUMERO_ES + r")\s*"
    r"(?P<uni>%|por ciento|puntos b[aá]sicos|millones|mil millones|billones|"
    r"d[oó]lares|USD|euros|EUR|bolivianos|pesos|reales|soles|bol[ií]vares)",
    re.IGNORECASE)


def _limpiar(html_crudo):
    texto = re.sub(r"<[^>]+>", " ", html_crudo or "")
    texto = re.sub(r"&[a-z]+;", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _enlace_real(url):
    """Desenvuelve los redirectores que algunos feeds ponen delante.

    Folha envuelve todo en redir.folha.com.br/redir/.../*<url real>. El enlace
    que se publica tiene que ser el del diario, no el del redirector.
    """
    if "redir.folha.com.br" in url and "*http" in url:
        return url.split("*", 1)[1]
    return url


def cifras_del_texto(texto, fuente_id, medio):
    """Recoge las cifras que trae la nota, cada una atribuida al diario.

    No convierte ni recalcula: copia el numero como lo escribio el medio. El
    unico dato honesto aqui es "esto fue lo que publico este diario".
    """
    encontradas, vistos = [], set()
    for m in UNIDADES.finditer(texto):
        etiqueta = f"{m.group('num')} {m.group('uni')}".lower()
        if etiqueta in vistos:
            continue
        vistos.add(etiqueta)
        encontradas.append(Cifra(
            clave=f"cifra_{len(encontradas) + 1}",
            valor=m.group("num"),
            unidad=m.group("uni"),
            periodo="según la nota",
            fuente_id=fuente_id,
            nota=f"publicada por {medio}: hay que atribuirsela en el texto",
        ))
    return encontradas


def extraer(medios=None, horas=24, limite=6, tema=None):
    """Lee la lista blanca y devuelve un paquete por noticia.

    medios: claves de MEDIOS; por defecto, todas.
    tema:   filtra ademas por una palabra o expresion (ej. "inflaci|d[oó]lar").

    Una lista de paquetes, no uno: cada noticia se produce y falla por separado.
    """
    claves = medios or list(MEDIOS)
    filtro_tema = re.compile(tema, re.IGNORECASE) if tema else None
    corte = datetime.now(timezone.utc).timestamp() - horas * 3600
    paquetes, vistos = [], set()

    for clave in claves:
        if clave not in MEDIOS:
            print(f"[aviso] '{clave}' no esta en la lista blanca; lo salto")
            continue
        medio = MEDIOS[clave]
        try:
            feed = feedparser.parse(medio["url"], agent=AGENTE)
        except Exception as exc:  # noqa: BLE001 - un diario caido no detiene al resto
            print(f"[aviso] {medio['nombre']} no respondio: {exc}")
            continue
        if not feed.entries:
            print(f"[aviso] {medio['nombre']} devolvio 0 noticias")
            continue

        for entrada in feed.entries:
            titular = (entrada.get("title") or "").strip()
            enlace = _enlace_real((entrada.get("link") or "").strip())
            if not titular or not enlace.startswith("http"):
                continue

            resumen = _limpiar(entrada.get("summary") or entrada.get("description"))
            texto = f"{titular}. {resumen}"

            # Si el feed no viene filtrado por seccion, hay que filtrarlo aqui:
            # los feeds generales traen deportes y sucesos.
            if not medio["economia"] and not ECONOMICO.search(texto):
                continue
            if filtro_tema and not filtro_tema.search(texto):
                continue

            publicado = entrada.get("published_parsed") or entrada.get("updated_parsed")
            if publicado and timegm(publicado) < corte:
                continue
            fecha = (datetime.fromtimestamp(timegm(publicado), tz=timezone.utc)
                     .date().isoformat()) if publicado else ""

            firma = titular.lower()[:70]
            if firma in vistos:
                continue
            vistos.add(firma)

            fuente = Fuente(
                id=clave,
                institucion=medio["nombre"],
                documento=titular,
                url=enlace,
            )
            paquete = Paquete(
                hecho=titular,
                fecha_hecho=fecha,
                cifras=cifras_del_texto(texto, clave, medio["nombre"]),
                citas=([{"texto": resumen, "autor": medio["nombre"],
                         "fuente_id": clave}] if resumen else []),
                entidades=[medio["nombre"], medio["pais"]],
                fuentes=[fuente],
                advertencias=[
                    f"ATRIBUCIÓN OBLIGATORIA: la información es de "
                    f"{medio['nombre']}. El cuerpo tiene que nombrar al diario "
                    f"({medio['nombre']}) y la pieza cierra con «Sacado de: "
                    f"{medio['nombre']}, {fecha} — {enlace}»."
                ],
            )

            if medio.get("muro_de_pago"):
                paquete.advertencias.append(
                    f"MURO DE PAGO: la nota de {medio['nombre']} no se puede "
                    f"abrir sin suscripcion. El lector no podra comprobar la "
                    f"fuente. Que Edicion decida si se cita igual o se busca el "
                    f"hecho en una fuente abierta."
                )
            if medio.get("idioma") == "en":
                paquete.advertencias.append(
                    f"FUENTE EN INGLÉS: {medio['nombre']} publica en ingles. NO "
                    f"entrecomilles una traduccion tuya: una cita traducida ya "
                    f"no es textual. Parafrasea y atribuye."
                )
            paquetes.append(paquete)
            if len(paquetes) >= limite:
                return paquetes

    if not paquetes:
        print("[aviso] no hubo noticias que cumplan el filtro")
    return paquetes
