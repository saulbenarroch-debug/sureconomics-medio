"""Criterio de selección de noticias, portado del bot de Telegram.

NO INVENTADO AQUI. Es una traduccion literal de la logica que lleva meses en
produccion en `cloudflare-worker/worker.js` del bot de Telegram: JUNK_RE,
ECON_RE, MACRO_FUERTE_RE, MEDIOS_OK_RE, CLICKBAIT_RE, puntuar() y
filtrarNoticias(). Si algo hay que afinar, conviene afinarlo en los dos sitios o
decidir que uno es el bueno; lo que no vale es que diverjan en silencio.

POR QUE PUNTUAR Y NO BLOQUEAR POR DOMINIO
La primera version de nuestro buscador restringia Tavily a la lista blanca. Eso
deja fuera informacion buena que no publica ninguno de nuestros medios —los
comunicados de Hacienda de Mexico, por ejemplo— y ademas no filtra el ruido de
dentro. El bot lo resuelve al reves y mejor: **no bloquea a nadie, puntua a
todos**. Un medio reconocido suma tres puntos, pero uno desconocido puede
compensarlos si trae cifras, es macro y es reciente.

Estos patrones ya evitan errores que aqui habiamos parcheado uno a uno:
  - CLICKBAIT_RE atrapa "en vivo" y "minuto a minuto": las cotizaciones que se
    actualizan solas y no traen ningun dato aprovechable.
  - JUNK_RE atrapa faranduela, recetas y horoscopos: la nota de cuanto dinero le
    deja Harry Potter a Rupert Grint habria muerto aqui.
"""

import re
from datetime import datetime, timezone

JUNK = re.compile(
    r"(receta|hor[oó]scopo|farándula|far[aá]ndula|f[uú]tbol|futbol|deportiv|"
    r"selecci[oó]n nacional|clima|lluvia|hurac[aá]n|visa|pasaporte|migrator|"
    r"migrante|turismo|viral|tiktok|belleza|dieta|bicarbonato|limpieza|truco|"
    r"ciudad flotante|anses|jubilad|loter[íi]a|netflix|serie|pel[íi]cula|famoso|"
    r"astrolog|zodiac)", re.IGNORECASE)

ECON = re.compile(
    r"(econom|inflaci|ipc|pib|d[oó]lar|euro|peso|real |bolívar|bol[íi]var|"
    r"banco central|tasa|inter[eé]s|bono|deuda|d[eé]ficit|fiscal|export|import|"
    r"inversi|mercado|bolsa|acciones|adquisici|fusi[oó]n|compra|adquiere|opa|"
    r"petr[oó]leo|crudo|barril|gas|miner|litio|cobre|energ|fmi|\bbid\b|"
    r"banco mundial|moody|fitch|riesgo pa[íi]s|reservas|remesas|empleo|"
    r"desempleo|salario|impuesto|arancel|comercio|superávit|super[aá]vit|pdvsa|"
    r"bcv|selic|banxico|cepal|petrobras|pemex|ecopetrol|codelco|cemex|empresa|"
    r"compañ|grupo |banco |fintech|financiamiento|financiaci|refinanc|"
    r"cr[eé]dito)", re.IGNORECASE)

MACRO_FUERTE = re.compile(
    r"(inflaci|ipc|pib|devaluaci|default|reestructuraci|sanci[oó]n|sanciones|"
    r"licencia|ofac|fmi|banco mundial|banco central|tasa de inter[eé]s|"
    r"d[eé]ficit|super[aá]vit|deuda|bonos|adquisici|fusi[oó]n|emisi[oó]n|"
    r"arancel|reservas|barril|opep|producci[oó]n petrolera|recorte|"
    r"alza de tasas|calificaci[oó]n)", re.IGNORECASE)

MEDIOS_OK = re.compile(
    r"(reuters|bloomberg|financial times|wall street journal|el pa[íi]s|"
    r"expansi[oó]n|banca y negocios|finanzas ?digital|efecto cocuyo|descifrado|"
    r"el nacional|el est[íi]mulo|talcual|infobae|el cronista|la naci[oó]n|"
    r"clar[íi]n|folha|valor econ|estad[aã]o|semana|la rep[uú]blica|portafolio|"
    r"el mercurio|diario financiero|el economista|el financiero|forbes|"
    r"am[eé]rica econom[íi]a|latamlist|iupana|world oil|argus|platts|"
    r"s&p global|cepal|mercopress|oncuba|el pitazo|runrun|cr[oó]nica uno|"
    r"gob\.mx|dane|banrep|banxico|imf\.org|worldbank)", re.IGNORECASE)

CLICKBAIT = re.compile(
    r"(esto es lo que|todo lo que|as[íi] es como|mira c[oó]mo|no vas a creer|"
    r"te contamos|en vivo|minuto a minuto|paso a paso|lo que debes saber|"
    r"cu[áa]nto cuesta|as[íi] qued[oó]|ranking de|los \d+ mejores|conoce |sepa |"
    r"encuesta de opini)", re.IGNORECASE)

CON_CIFRAS = re.compile(r"(\d+[.,]?\d*\s?%|US\$|\$\s?\d|millones|billones|"
                        r"mil millones)", re.IGNORECASE)

DIAS_MAXIMO = 12


def _dias_desde(fecha):
    """Antigüedad en días, o None si no se puede calcular."""
    if not fecha:
        return None
    for formato in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = datetime.strptime(str(fecha)[:len("2026-08-25T00:00:00")], formato)
            return (datetime.now(timezone.utc) - d.replace(tzinfo=timezone.utc)).days
        except ValueError:
            continue
    return None


def puntuar(titular, resumen="", url="", fecha=""):
    """Puntúa una nota. Más alto, mejor candidata. Copiado de puntuar() del bot."""
    p = 0
    if MEDIOS_OK.search(f"{titular} {url}"):
        p += 3
    if MACRO_FUERTE.search(titular):
        p += 3
    if ECON.search(titular):
        p += 1
    if re.search(r"\d", titular):
        p += 1
    if CON_CIFRAS.search(titular):
        p += 2
    # Un resumen que solo repite el titular no aporta: Google News hace eso.
    if resumen and resumen.strip()[:60].lower() != titular.strip()[:60].lower():
        p += 1

    dias = _dias_desde(fecha)
    if dias is None:
        pass
    elif dias <= 2:
        p += 3
    elif dias <= 5:
        p += 2
    elif dias <= 8:
        p += 1
    else:
        p -= 1
    return p


def sirve(titular, fecha="", exigir_economia=True):
    """Descarta lo que no debe pasar nunca. Copiado de filtrarNoticias()."""
    if not titular:
        return False
    if JUNK.search(titular):
        return False
    if CLICKBAIT.search(titular):
        return False
    if exigir_economia and not ECON.search(titular):
        return False
    dias = _dias_desde(fecha)
    if dias is not None and dias > DIAS_MAXIMO:
        return False
    return True


def ordenar(candidatos, clave_titular="titular", clave_resumen="extracto",
            clave_url="url", clave_fecha="fecha", exigir_economia=True):
    """Filtra y ordena una lista de dicts. Añade 'puntos' a cada uno."""
    salida = []
    for c in candidatos:
        titular = c.get(clave_titular, "") or ""
        if not sirve(titular, c.get(clave_fecha, ""), exigir_economia):
            continue
        c = dict(c)
        c["puntos"] = puntuar(titular, c.get(clave_resumen, "") or "",
                              c.get(clave_url, "") or "", c.get(clave_fecha, "") or "")
        salida.append(c)
    return sorted(salida, key=lambda x: x["puntos"], reverse=True)


# Deteccion de pais, portada de PAISES en worker.js. Detecta por gentilicio pero
# tambien por POLITICO (Milei, Lula, Petro, Boric), por INDICE (Merval, Ibovespa,
# Colcap, IPSA) y por EMPRESA (Petrobras, Pemex, Ecopetrol, Codelco). Mucho mas
# fino que buscar solo el nombre del pais: "Ecopetrol cae en bolsa" es Colombia
# sin decir Colombia.
PAISES = [
    ("Argentina", r"argentin|milei|merval|buenos aires|afip|bcra"),
    ("Brasil", r"brasil|brazil|lula|selic|ibovespa|petrobras|real brasile"),
    ("México", r"m[eé]xico|mexican|banxico|sheinbaum|pemex|cemex|bmv"),
    ("Colombia", r"colombia|petro|ecopetrol|colcap|bancolombia|cibest|dane"),
    ("Chile", r"chile|codelco|ipsa|boric"),
    ("Perú", r"per[uú]|lima|sunat|bcrp"),
    ("Ecuador", r"ecuador|noboa"),
    ("Uruguay", r"uruguay|montevideo"),
    ("Bolivia", r"bolivia"),
    ("Paraguay", r"paraguay"),
    ("Panamá", r"panam[aá]"),
    ("República Dominicana", r"dominican"),
    ("Cuba", r"cuba|habana"),
    ("Haití", r"hait[ií]"),
    ("Venezuela", r"venezue|caracas|maiquet|la guaira|pdvsa|bcv|bol[íi]var|"
                  r"maduro|delcy|zulia|maracaibo"),
    ("Centroamérica", r"costa rica|guatemala|honduras|salvador|nicaragua"),
    ("EE. UU.", r"estados unidos|ee\.? ?uu|washington|trump|reserva federal|fed|"
                r"wall street|tesoro estadounidense"),
]
_PAISES_RE = [(n, __import__("re").compile(p, __import__("re").IGNORECASE))
              for n, p in PAISES]


def pais_de(texto):
    """El pais del que habla un texto, o None. Orden = prioridad."""
    for nombre, rx in _PAISES_RE:
        if rx.search(texto or ""):
            return nombre
    return None


# Maximo de notas por pais en una seleccion. Regla portada de
# seleccionarNoticias(): sin ella, un pais con mucha prensa acapara la cobertura
# y el medio deja de ser latinoamericano para ser de ese pais.
MAX_POR_PAIS = 2


def diversificar(candidatos, clave_titular="titular", maximo_por_pais=MAX_POR_PAIS):
    """Limita cuantas notas entran por pais, conservando el orden de puntuacion."""
    cuenta, salida = {}, []
    for c in candidatos:
        pais = pais_de(c.get(clave_titular, "")) or "sin país"
        cuenta[pais] = cuenta.get(pais, 0) + 1
        if cuenta[pais] <= maximo_por_pais:
            salida.append(c)
    return salida
