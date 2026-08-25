"""Extractor (A4) del Banco Mundial.

Elegido como primera fuente porque es gratis, no pide clave, cubre a todos los
paises de Latinoamerica y es una institucion citable sin discusion.

Su limitacion es real y hay que respetarla: publica series ANUALES y con retraso.
No sirve para una noticia de hoy; sirve para contexto, educacion e investigacion
-lo que en el perfil editorial se etiqueta como 'Permanente', que es justo lo que
llena el pool base-. Cuando el dato viene viejo, este extractor lo dice en
'advertencias' en vez de dejar que alguien lo presente como actual.
"""

import json
import socket
import urllib.error
import urllib.request
from datetime import date

from motor.paquete import Cifra, Fuente, Paquete, formato_es, magnitud_es

# Una fuente colgada no puede trabar la corrida (regla de oro #3 de los repos).
TIEMPO_LIMITE = 25
AGENTE = "SurEconomics/1.0 (medio de economia; contacto: redaccion@sureconomics.com)"

# Cada indicador trae como se llama en español, su unidad y si es magnitud grande.
INDICADORES = {
    "inflacion":   ("FP.CPI.TOTL.ZG",    "inflación anual",              "%",   False),
    "crecimiento": ("NY.GDP.MKTP.KD.ZG", "crecimiento del PIB",          "%",   False),
    "pib":         ("NY.GDP.MKTP.CD",    "PIB a precios corrientes",     "USD", True),
    "pib_per_capita": ("NY.GDP.PCAP.CD", "PIB por habitante",            "USD", False),
    "desempleo":   ("SL.UEM.TOTL.ZS",    "desempleo",                    "%",   False),
    "deuda":       ("GC.DOD.TOTL.GD.ZS", "deuda del gobierno central",   "% del PIB", False),
    "remesas":     ("BX.TRF.PWKR.CD.DT", "remesas recibidas",            "USD", True),
    "pobreza":     ("SI.POV.NAHC",       "pobreza segun linea nacional", "%",   False),
}

# ISO3 -> nombre en español. Solo Latinoamerica: es el foco del medio.
PAISES = {
    "ARG": "Argentina", "BOL": "Bolivia", "BRA": "Brasil", "CHL": "Chile",
    "COL": "Colombia", "CRI": "Costa Rica", "CUB": "Cuba", "DOM": "República Dominicana",
    "ECU": "Ecuador", "SLV": "El Salvador", "GTM": "Guatemala", "HTI": "Haití",
    "HND": "Honduras", "MEX": "México", "NIC": "Nicaragua", "PAN": "Panamá",
    "PRY": "Paraguay", "PER": "Perú", "URY": "Uruguay", "VEN": "Venezuela",
    "LCN": "América Latina y el Caribe",
}


def _pedir(url):
    """Descarga JSON. Si falla, devuelve None: nunca inventa una respuesta."""
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE) as r:
            return json.load(r)
    except (urllib.error.URLError, socket.timeout, ValueError) as exc:
        print(f"[aviso] el Banco Mundial no respondio: {exc}")
        return None


def ranking(indicador="pib", paises=None, top=10):
    """Ordena a los paises por un indicador y arma el paquete con la tabla.

    Existe porque «Colombia es la cuarta economia de America Latina» es una
    afirmacion que NADIE publica como noticia: es el resultado de ordenar una
    tabla. La prensa la repite sin fuente y nosotros no podiamos escribirla
    porque el buscador no encontraba de donde. La respuesta era no buscarla:
    calcularla. Se piden los PIB al Banco Mundial y se ordenan aqui, que es
    aritmetica y por tanto trabajo del codigo, no del modelo.

    El puesto sale como cifra propia, con su fuente y su año, igual que
    cualquier otra. Y como es nuestro calculo, el paquete lo dice.
    """
    if indicador not in INDICADORES:
        raise ValueError(f"indicador no reconocido: {indicador}. "
                         f"Disponibles: {', '.join(INDICADORES)}")
    codigo, nombre, unidad, es_magnitud = INDICADORES[indicador]

    # 'LCN' es el agregado regional, no un pais: ordenarlo junto a los demas
    # pondria a America Latina primera en el ranking de America Latina.
    objetivo = [p for p in (paises or PAISES) if p != "LCN"]

    filas = []
    for iso in objetivo:
        url = (f"https://api.worldbank.org/v2/country/{iso}/indicator/{codigo}"
               f"?format=json&mrnev=1")
        crudo = _pedir(url)
        if not crudo or len(crudo) < 2 or not crudo[1]:
            print(f"[aviso] sin {indicador} para {PAISES.get(iso, iso)}")
            continue
        obs = crudo[1][0]
        if obs.get("value") is None:
            continue
        filas.append((obs["value"], iso, obs["date"]))

    if len(filas) < 3:
        print(f"[aviso] el ranking de '{indicador}' se queda en {len(filas)} paises")
        return None

    filas.sort(reverse=True)
    filas = filas[:top]
    # Los años se cuentan DESPUES de recortar la tabla. Antes se contaban sobre
    # todos los paises consultados y Cuba, cuyo ultimo PIB publicado es de 2020
    # y que no entra ni en los ocho primeros, disparaba un aviso de «la tabla
    # mezcla años» sobre una tabla que no la mezclaba.
    anios = {f[2] for f in filas}
    anio_comun = max(anios)

    fuente = Fuente(
        id="bm1",
        institucion="Banco Mundial",
        documento=f"Indicadores del desarrollo mundial, {nombre}",
        url=f"https://data.worldbank.org/indicator/{codigo}",
        url_datos=(f"https://api.worldbank.org/v2/country/all/indicator/{codigo}"
                   f"?format=json&mrnev=1"),
    )

    cifras = []
    for puesto, (valor, iso, anio) in enumerate(filas, start=1):
        cifras.append(Cifra(
            clave=f"{indicador}_{iso.lower()}",
            valor=magnitud_es(valor) if es_magnitud else formato_es(valor),
            unidad=unidad,
            periodo=anio,
            fuente_id=fuente.id,
            valor_crudo=valor,
            nota=f"{PAISES.get(iso, iso)}, puesto {puesto} de {len(filas)}",
        ))

    lider = filas[0]
    paquete = Paquete(
        hecho=(f"Ranking de {nombre} en América Latina según el Banco Mundial, "
               f"datos de {anio_comun}: encabeza {PAISES.get(lider[1], lider[1])}"),
        fecha_hecho=anio_comun,
        cifras=cifras,
        entidades=["Banco Mundial"] + [PAISES.get(f[1], f[1]) for f in filas],
        fuentes=[fuente],
    )
    paquete.advertencias.extend(paquete.avisos_de_formato())
    paquete.advertencias.append(
        "EL PUESTO EN LA TABLA LO CALCULAMOS NOSOTROS ordenando los datos del "
        "Banco Mundial. La cifra es del Banco Mundial y se le atribuye; el "
        "orden es trabajo de la redacción y se puede decir como tal."
    )
    # Justo porque el orden lo ponemos nosotros, el enlace a la serie es
    # obligatorio: es lo unico que le permite al lector rehacer la cuenta.
    paquete.advertencias.append(
        "ATRIBUCIÓN OBLIGATORIA: la pieza cierra con el enlace a la serie del "
        "Banco Mundial."
    )

    # Los paises no publican a la vez. Si la tabla mezcla años, compararlos
    # como si fueran el mismo momento es falso, y hay que decirlo.
    if len(anios) > 1:
        paquete.advertencias.append(
            f"CUIDADO: la tabla mezcla datos de distintos años ({', '.join(sorted(anios))}). "
            f"No los presentes como una foto del mismo momento."
        )
    antiguedad = date.today().year - int(anio_comun)
    if antiguedad >= 2:
        paquete.advertencias.append(
            f"El dato más reciente es de {anio_comun}: tiene {antiguedad} años. "
            f"El texto tiene que decir el año expresamente."
        )
    return paquete


def extraer(pais, indicador, observaciones=3):
    """Arma el paquete de datos de un indicador para un pais.

    'observaciones' es cuantos años recientes traer: con dos o mas, el redactor
    puede contar una evolucion en vez de un dato suelto, y sin salirse de la caja.

    Devuelve None si la fuente no responde o no hay datos. Un hueco declarado se
    resuelve en veinte segundos; un dato inventado es un error publicado.
    """
    pais = pais.upper()
    if pais not in PAISES:
        raise ValueError(f"pais no reconocido: {pais}. Use ISO3, ej. VEN, MEX, COL")
    if indicador not in INDICADORES:
        raise ValueError(f"indicador no reconocido: {indicador}. "
                         f"Disponibles: {', '.join(INDICADORES)}")

    codigo, nombre, unidad, es_magnitud = INDICADORES[indicador]
    # mrnev = most recent non-empty values: salta los años sin dato en vez de
    # devolver huecos que despues alguien rellena a ojo.
    url_datos = (f"https://api.worldbank.org/v2/country/{pais}/indicator/{codigo}"
                 f"?format=json&mrnev={observaciones}")

    crudo = _pedir(url_datos)
    if not crudo or len(crudo) < 2 or not crudo[1]:
        print(f"[aviso] sin datos de '{indicador}' para {PAISES[pais]}")
        return None

    observados = [o for o in crudo[1] if o.get("value") is not None]
    if not observados:
        print(f"[aviso] la serie de '{indicador}' para {PAISES[pais]} viene vacia")
        return None

    fuente = Fuente(
        id="bm1",
        institucion="Banco Mundial",
        documento=f"Indicadores del desarrollo mundial — {nombre} ({PAISES[pais]})",
        url=f"https://data.worldbank.org/indicator/{codigo}?locations={pais[:2]}",
        url_datos=url_datos,
    )

    cifras = []
    for obs in observados:
        anio = obs["date"]
        valor = obs["value"]
        cifras.append(Cifra(
            clave=f"{indicador}_{anio}",
            valor=magnitud_es(valor) if es_magnitud else formato_es(valor),
            unidad=unidad,
            periodo=anio,
            fuente_id=fuente.id,
            valor_crudo=valor,
        ))

    reciente = observados[0]
    paquete = Paquete(
        hecho=(f"{nombre[0].upper() + nombre[1:]} de {PAISES[pais]} en {reciente['date']}: "
               f"{magnitud_es(reciente['value']) if es_magnitud else formato_es(reciente['value'])}"
               f"{'' if es_magnitud else ' ' + unidad}"),
        fecha_hecho=reciente["date"],
        cifras=cifras,
        entidades=[PAISES[pais], "Banco Mundial"],
        fuentes=[fuente],
    )

    paquete.advertencias.extend(paquete.avisos_de_formato())

    # El dato viejo presentado como actual es el error mas facil de cometer y el
    # mas dificil de detectar leyendo. Venezuela es el caso extremo: la ultima
    # inflacion que publica el Banco Mundial es de 2016.
    antiguedad = date.today().year - int(reciente["date"])
    if antiguedad >= 2:
        paquete.advertencias.append(
            f"El dato mas reciente es de {reciente['date']}: tiene {antiguedad} "
            f"años. NO puede presentarse como actual. El texto debe decir el año "
            f"expresamente."
        )
    if len(cifras) < observaciones:
        paquete.advertencias.append(
            f"Se pidieron {observaciones} observaciones y solo hay {len(cifras)}."
        )

    return paquete
