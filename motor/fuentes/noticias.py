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

from motor import criterio
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
    # Nos faltaba y era el que mejor cubre esta fuente. Lo trajo Edicion el
    # 26/08/2026 como origen de una noticia que ninguna de las 44 fuentes tenia:
    # de 50 acuerdos petroleros y gasiferos anunciados, nueve se han hecho
    # publicos. Es venezolano, es solo economia y el feed general ya viene
    # limpio, asi que no hace falta apuntar a una seccion.
    "bitacora":    dict(nombre="Bitácora Económica", pais="Venezuela",
                        economia=True, url="https://bitacoraeconomica.com/feed/"),
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
    # Unica superviviente de una tanda de once propuestas el 25/08/2026: las
    # otras diez eran fuentes ya verificadas como bloqueadas (FMI, DANE, BID,
    # El Economista, EFE, Banxico, SHCP, Ultimas Noticias). Para esas, la via
    # que si funciona es fuentes/oficiales.py, que entra por el indice de Tavily.
    "cronista":    dict(nombre="El Cronista", pais="Argentina", economia=True,
                        url="https://www.cronista.com/files/rss/economia-politica.xml"),

    # LISTA DE JEFATURA EDITORIAL (Pablo Quintero), 25/08/2026. De 27 medios
    # pedidos, 11 ya estaban y 7 se verificaron y entran aqui. Los 9 que faltan
    # y por que, al final de este bloque.
    "contrapunto": dict(nombre="Contrapunto", pais="Venezuela", economia=False,
                        url="https://contrapunto.com/feed/"),
    # Responde con un 301 y feedparser falla en ese salto de vez en cuando: una
    # corrida devuelve cero y la siguiente trae veinte. No es que este caida.
    "lapatilla":   dict(nombre="La Patilla", pais="Venezuela", economia=False,
                        url="https://www.lapatilla.com/feed/"),
    # ESTATAL: Telesur es financiado por el Estado venezolano. Lo pide Jefatura
    # Editorial y por tanto entra, pero marcado: sirve para conocer la posicion
    # oficial —que a veces ES la noticia— y eso hay que decirlo al citarlo.
    "telesur":     dict(nombre="Telesur", pais="Venezuela", economia=False,
                        estatal=True,
                        url="https://www.telesurtv.net/feed/"),
    "euronews":    dict(nombre="Euronews", pais="Unión Europea", economia=False,
                        url="https://es.euronews.com/rss?level=theme&name=news"),
    "vanguardia":  dict(nombre="La Vanguardia", pais="España", economia=True,
                        url="https://www.lavanguardia.com/rss/economia.xml"),
    # INGLES y con MURO DE PAGO, como Bloomberg: parafrasear y atribuir, nunca
    # entrecomillar una traduccion propia, y avisar de que el lector no podra
    # abrir la nota sin suscripcion.
    "nytimes":     dict(nombre="The New York Times", pais="EE. UU.", economia=True,
                        idioma="en", muro_de_pago=True,
                        url="https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml"),
    "nytbusiness": dict(nombre="The New York Times", pais="EE. UU.", economia=True,
                        idioma="en", muro_de_pago=True,
                        url="https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
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

    # SECCIONES QUE NO SON ECONOMIA, DE MEDIOS QUE YA ESTABAN. Añadidas el
    # 07/09/2026 por un fallo concreto: una captura de Bloomberg Línea sobre
    # Radia Perlman y la IA no se encontraba en ninguna parte, y no era un
    # problema de fechas -sus feeds cubren tres semanas- sino de SECCION: la
    # nota es de tecnologia y de ese medio solo teniamos economia y mercados.
    # Cualquier nota de un diario aprobado que caiga fuera de su seccion
    # economica era invisible para el rastreo.
    #
    # VAN CON economia=False A PROPOSITO, y no es un descuido: extraer(), que
    # llena el pozo de las tandas, exige vocabulario economico a los feeds
    # marcados asi, mientras que titulares(), que empareja capturas, no filtra
    # nada. O sea que sirven para ENCONTRAR el original de lo que manda la
    # redaccion, pero no arrastran deportes ni farandula a las tandas diarias.
    #
    # Probadas una por una: estas seis responden con 100 notas y las del dia.
    # bloomberglinea/energia y elnacional/politica y /tecnologia devuelven cero
    # y por eso no estan.
    "bbglintec":   dict(nombre="Bloomberg Línea", pais="Latam", economia=False,
                        url="https://www.bloomberglinea.com/arc/outboundfeeds/"
                            "rss/category/tecnologia/?outputType=xml"),
    "bbglinneg":   dict(nombre="Bloomberg Línea", pais="Latam", economia=False,
                        url="https://www.bloomberglinea.com/arc/outboundfeeds/"
                            "rss/category/negocios/?outputType=xml"),
    "bbglinlat":   dict(nombre="Bloomberg Línea", pais="Latam", economia=False,
                        url="https://www.bloomberglinea.com/arc/outboundfeeds/"
                            "rss/category/latinoamerica/?outputType=xml"),
    "infobaetec":  dict(nombre="Infobae", pais="Argentina", economia=False,
                        url="https://www.infobae.com/arc/outboundfeeds/rss/"
                            "category/tecno/?outputType=xml"),
    "infobaepol":  dict(nombre="Infobae", pais="Argentina", economia=False,
                        url="https://www.infobae.com/arc/outboundfeeds/rss/"
                            "category/politica/?outputType=xml"),
    "elnacmundo":  dict(nombre="El Nacional", pais="Venezuela", economia=False,
                        url="https://www.elnacional.com/mundo/feed/"),

    # PAISES QUE NO TENIAN NINGUNO, añadidos el 08/09/2026. Ecuador, Paraguay y
    # Uruguay estaban a cero y Peru tenia uno solo, en un medio que se llama
    # latinoamericano.
    #
    # TODOS PROBADOS EN LAS DOS MITADES, que es la leccion de bancaynegocios: el
    # feed responde Y el articulo se deja leer. De 26 direcciones probadas
    # entraron 8. Las que no responden NO se apuntan aqui ni comentadas, porque
    # una URL muerta en la lista es una invitacion a volver a probarla.
    #
    # PARAGUAY SIGUE SIN NINGUNO. Se probaron ABC Color (cuatro direcciones),
    # Ultima Hora (dos) y La Nación PY (dos): todas devuelven vacio. Hace falta
    # buscar por otra via, no insistir con estas.
    "elcomercioec": dict(nombre="El Comercio (Ecuador)", pais="Ecuador",
                         # El nombre lleva el pais A PROPOSITO: ya hay un
                         # "El Comercio" peruano en esta lista, y el nombre es
                         # lo que compara buscador.dominios_de() cuando una
                         # captura dice de que medio es. Dos medios con el mismo
                         # nombre mandarian la busqueda al pais equivocado.
                         economia=False,
                         url="https://www.elcomercio.com/feed/"),
    "expresoec":   dict(nombre="Diario Expreso", pais="Ecuador", economia=False,
                        url="https://www.expreso.ec/rss.xml"),
    "gestionpe":   dict(nombre="Gestión", pais="Perú", economia=True,
                        url="https://gestion.pe/arcio/rss/?outputType=xml"),
    "rpp":         dict(nombre="RPP Noticias", pais="Perú", economia=False,
                        url="https://rpp.pe/feed/"),
    "observador":  dict(nombre="El Observador", pais="Uruguay", economia=True,
                        url="https://www.elobservador.com.uy/rss/pages/"
                            "economia.xml"),
    "mvdportal":   dict(nombre="Montevideo Portal", pais="Uruguay",
                        economia=False,
                        url="https://www.montevideo.com.uy/anxml.aspx?59"),
    "ambito":      dict(nombre="Ámbito", pais="Argentina", economia=True,
                        url="https://www.ambito.com/rss/economia.xml"),
    "valora":      dict(nombre="Valora Analitik", pais="Colombia", economia=True,
                        url="https://www.valoraanalitik.com/feed/"),
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

# DE LA LISTA DE JEFATURA EDITORIAL, LOS QUE NO SE PUDIERON AÑADIR (25/08/2026).
# Probados con su direccion habitual y con las alternativas de ARC y /rss/:
#   Ultimas Noticias   202 sin contenido (Cloudflare). Via: fuente manual.
#   El Universal (VE)  404 en las cuatro direcciones probadas
#   Globovision        301 sin entradas, en tres direcciones
#   Noticiero Digital  202 sin contenido
#   AVN / VTV          no responde
#   NTN24              404 en tres direcciones
#   Reuters            301: retiraron los feeds publicos. Se busca, no se lee
#   CNN en Español     no responde
#   Banca y Negocios   corta la conexion (ya estaba anotado como caido en el bot)
# Para todas ellas hay dos vias que si funcionan: buscarlas con buscador.py, o
# registrar una nota concreta con agregar_fuente.py. Lo que no hay es feed.

# MEDIOS ESTATALES PENDIENTES DE DECISION — responden, pero no se agregan sin
# que lo pida Jefatura Editorial:
#   RT en Español   https://actualidad.rt.com/feeds/all.rss   (Estado ruso)
#   Prensa Latina   https://www.prensa-latina.cu/feed/        (Estado cubano)
# Telesur sí entra porque Pablo lo pidio expresamente, y va marcado estatal=True.
# El criterio es el mismo para los tres: sirven para conocer la posicion oficial
# de esos gobiernos, y si se citan hay que decir lo que son.

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

# NO TODO EL MUNDO ESCRIBE LOS NUMEROS IGUAL, Y ESO LLEGO A FALSEAR UN DATO.
# Esto solo aceptaba la norma española (1.234.567,89). El Economista es mexicano
# y escribe «2.61%», con punto decimal: ninguna rama casaba en el «2.», el motor
# avanzaba y enganchaba «61 %». El expediente quedaba diciendo que las acciones
# de Apple subieron 61 % cuando la fuente decia 2,61 %. No es un fallo de
# formato, es una cifra falsa firmada por un medio que nunca la publico.
# Paso el 03/09/2026 con el relevo de Tim Cook.
#
# El orden de las ramas importa y no se puede alterar: las de millares van
# primero porque «1.500» es mil quinientos en español, y solo si ninguna casa se
# lee el separador como decimal.
_NUMERO_ES = (
    r"\d{1,3}(?:\.\d{3})+(?:,\d+)?"   # 1.234.567,89  norma española
    r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # 1,234,567.89  norma inglesa
    r"|\d+,\d+"                       # 2,61          decimal español
    r"|\d+\.\d+"                      # 2.61          decimal ingles
    r"|\d+")
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


def titulares(medios=None, horas=24, por_medio=15):
    """Solo titular, enlace y medio, de TODA la lista blanca. Sin expediente.

    POR QUE NO SIRVE extraer() PARA ESTO. Su 'limite' es un tope global y la
    funcion RETORNA en cuanto lo alcanza, recorriendo los medios en orden: con
    limite=60 los tres primeros llenaban el cupo y los otros cuarenta y siete ni
    se consultaban. Para armar el pool del dia eso esta bien, porque lo que se
    quiere son N piezas; para emparejar una captura con su original hace falta
    lo contrario, mirar en TODOS aunque sea por encima.

    Ademas extraer() construye el expediente completo de cada nota, que es caro
    y aqui no hace falta: para saber si un titular es el mismo hecho basta el
    titular.

    Se descubrio el 01/09/2026: una captura sobre la inflacion de la Fed no
    encontraba original y el motivo no era la noticia, era que solo se habian
    leido tres medios.
    """
    claves = medios or list(MEDIOS)
    corte = datetime.now(timezone.utc).timestamp() - horas * 3600
    salida, vistos = [], set()

    for clave in claves:
        medio = MEDIOS.get(clave)
        if not medio:
            continue
        try:
            feed = feedparser.parse(medio["url"], agent=AGENTE)
            if not feed.entries:      # ver el comentario de extraer()
                feed = feedparser.parse(medio["url"])
        except Exception:  # noqa: BLE001 - un diario caido no detiene al resto
            continue

        puestos = 0
        for entrada in feed.entries:
            if puestos >= por_medio:
                break
            titular = (entrada.get("title") or "").strip()
            enlace = _enlace_real((entrada.get("link") or "").strip())
            if not titular or not enlace.startswith("http") or enlace in vistos:
                continue
            if criterio.JUNK.search(titular) or criterio.JUNK_URL.search(enlace):
                continue
            marca = entrada.get("published_parsed") or entrada.get("updated_parsed")
            if marca and timegm(marca) < corte:
                continue
            vistos.add(enlace)
            salida.append({"titular": titular, "url": enlace,
                           "medio": medio["nombre"], "fecha": "", "via": "feed"})
            puestos += 1
    return salida


# CUANTAS NOTAS COMO MAXIMO SE COGEN DE UN MISMO MEDIO.
#
# Sin esto, un diario que publique mucho se lleva el pozo aunque haya cincuenta
# medios mas en la lista: el 09/09/2026 El Pais aporto 21 de 50 candidatas. No
# es que publicara mejor, es que publica mas y estaba el primero.
#
# Cuatro es suficiente para que un medio con un buen dia entre con varias y no
# tanto como para que tape a los demas.
POR_MEDIO = 4

# EL ORDEN EN QUE SE LEEN LOS MEDIOS, POR PRIORIDAD EDITORIAL.
#
# Lo pidio el dueno el 09/09/2026: "que lea primero diarios venezolanos, luego
# region, luego Espana, pero que igual catalogue por importancia". Esto es la
# primera mitad -a quien se lee antes-; la importancia la sigue decidiendo
# criterio.puntuar() sobre el pozo ya recogido, que es la segunda.
#
# Importa porque la recoleccion se corta al llegar al limite: lo que se lea
# tarde puede no leerse. Con el orden de escritura del diccionario, Venezuela
# quedaba fuera del pozo entera.
PRIORIDAD = (
    ("Venezuela",),                       # el pais del medio
    ("Latam", "Colombia", "Argentina", "Perú", "Chile", "Ecuador", "Uruguay",
     "Brasil", "México", "Paraguay", "Bolivia", "Cuba"),   # la region
    (),                                   # el resto: Espana, EE. UU., Europa
)


def _en_orden_de_prioridad():
    """Las claves de MEDIOS, primero Venezuela, luego la region, luego el resto."""
    por_nivel = [[] for _ in PRIORIDAD]
    for clave, medio in MEDIOS.items():
        pais = medio.get("pais", "")
        nivel = len(PRIORIDAD) - 1          # el resto, si no encaja en ninguno
        for i, paises in enumerate(PRIORIDAD):
            if pais in paises:
                nivel = i
                break
        por_nivel[nivel].append(clave)
    return [c for nivel in por_nivel for c in nivel]


def extraer(medios=None, horas=24, limite=6, tema=None, por_medio=POR_MEDIO):
    """Lee la lista blanca y devuelve un paquete por noticia.

    medios: claves de MEDIOS; por defecto, todas, EN ORDEN DE PRIORIDAD.
    tema:   filtra ademas por una palabra o expresion (ej. "inflaci|d[oó]lar").

    Una lista de paquetes, no uno: cada noticia se produce y falla por separado.

    EL ORDEN Y EL TOPE POR MEDIO NO SON COSMETICA: SON LO QUE DECIDE LA TANDA.

    Esta funcion recorre los medios y hace 'return' en cuanto junta 'limite'
    candidatas. Con los medios en el orden en que estaban escritos en MEDIOS
    -El Pais el primero, Clarin el segundo, los dos brasilenos tercero y
    cuarto- eso significaba que los cuatro primeros llenaban el cupo y LOS
    DEMAS NO SE LEIAN NUNCA.

    Medido el 09/09/2026 sobre un pozo real de 50: El Pais aporto 21 candidatas
    el solo, Folha y Estadao 27 entre los dos, Clarin 2. Total 50, corte, y los
    trece medios venezolanos -del octavo en adelante- ni se abrieron. Cero
    candidatas de Venezuela en el medio cuya tesis es Venezuela.

    Y explica de paso lo de Brasil de la vispera, que se habia tapado con un
    tope por pais en orquestar.py: no era que Folha publicara mejor, era que
    publicaba ANTES en la lista.
    """
    claves = medios or _en_orden_de_prioridad()
    filtro_tema = re.compile(tema, re.IGNORECASE) if tema else None
    corte = datetime.now(timezone.utc).timestamp() - horas * 3600
    paquetes, vistos = [], set()

    for clave in claves:
        if clave not in MEDIOS:
            print(f"[aviso] '{clave}' no esta en la lista blanca; lo salto")
            continue
        medio = MEDIOS[clave]
        del_medio = 0
        try:
            feed = feedparser.parse(medio["url"], agent=AGENTE)
            # SEGUNDO INTENTO SIN DISFRAZARSE. AGENTE imita a Chrome, que es lo
            # que hace falta en la mayoria de los sitios, pero algunos hacen lo
            # contrario: bloquean al navegador y dejan pasar al lector de feeds.
            # Bitacora Economica devolvia 403 con AGENTE y 200 con el agente por
            # defecto de feedparser, y el medio se quedaba fuera pareciendo
            # caido. Un feed vacio no cuesta casi nada de reintentar.
            if not feed.entries:
                feed = feedparser.parse(medio["url"])
        except Exception as exc:  # noqa: BLE001 - un diario caido no detiene al resto
            print(f"[aviso] {medio['nombre']} no respondio: {exc}")
            continue
        if not feed.entries:
            # UN FEED VACIO NO SIEMPRE ES UN MEDIO CAIDO, y confundirlos lleva a
            # sacar una fuente buena de la lista. Bitacora Economica respondia
            # 200 con diez notas y, tras varias consultas seguidas el mismo dia,
            # paso a responder 202 sin contenido: eso es el escudo antibots
            # diciendo "vuelve mas tarde", no el medio dejando de publicar.
            estado = feed.get("status")
            if estado in (202, 403, 429):
                print(f"[aviso] {medio['nombre']} nos esta limitando ({estado}), "
                      f"no esta caido. Reintentar mas tarde.")
            else:
                print(f"[aviso] {medio['nombre']} devolvio 0 noticias")
            continue

        for entrada in feed.entries:
            titular = (entrada.get("title") or "").strip()
            enlace = _enlace_real((entrada.get("link") or "").strip())
            if not titular or not enlace.startswith("http"):
                continue

            resumen = _limpiar(entrada.get("summary") or entrada.get("description"))
            texto = f"{titular}. {resumen}"

            # LA BASURA SE PARA AQUI, EN LA PUERTA. Hasta ahora este extractor no
            # filtraba nada y cada consumidor se defendia por su cuenta: el
            # documentalista aprendio a rechazar el Powerball, pero el contexto
            # de prensa no, y se trajo como fuente un publirreportaje de El Pais
            # sobre turismo español para un articulo sobre el PIB de Venezuela.
            # /branded/ es publicidad pagada con forma de reportaje.
            #
            # Se aplican SOLO los filtros de basura, no el de "exigir economia":
            # ese descarta por titular y ya vimos que deja fuera cosas buenas
            # («Trump dice que es hora de darle una leccion a Canada» no lleva
            # ninguna palabra de economia y es una noticia economica).
            if criterio.JUNK.search(titular) or criterio.JUNK_URL.search(enlace):
                continue

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
            if medio.get("estatal"):
                paquete.advertencias.append(
                    f"MEDIO ESTATAL: {medio['nombre']} está financiado por el "
                    f"Estado. Se cita diciendo lo que es —«el canal estatal "
                    f"{medio['nombre']}»— porque su versión de un hecho es la "
                    f"posición oficial, y eso el lector tiene derecho a saberlo. "
                    f"No lo presentes como un medio independiente ni des su "
                    f"versión por contrastada."
                )
            paquetes.append(paquete)
            del_medio += 1
            # UN MEDIO NO PUEDE LLEVARSE EL POZO ENTERO. Ver POR_MEDIO.
            if del_medio >= por_medio:
                break
            if len(paquetes) >= limite:
                return paquetes

    if not paquetes:
        print("[aviso] no hubo noticias que cumplan el filtro")
    return paquetes
