"""Extractor (A4) del EMBI de J.P. Morgan, vía el Banco Central de Perú.

El EMBI (Emerging Markets Bond Index) es EL indicador de "riesgo país" en
Latinoamerica: cuando la prensa argentina dice "el riesgo país subió a 700
puntos", habla de esto.

POR QUE NO VAMOS DIRECTO A J.P. MORGAN
El portal de research de J.P. Morgan es de suscripcion institucional. No hay API
publica, y raspar un sitio con acceso restringido seria un problema tecnico y de
terminos de uso. Pero el dato en si lo republican bancos centrales: el BCRP
(Peru) lo publica gratis y por API, que es de donde sale esto.

La atribucion correcta es doble y no se puede recortar: el indice es de
J.P. Morgan, la serie consultada es del BCRP.

VENEZUELA NO ESTA. J.P. Morgan saco a Venezuela y a PDVSA de sus indices EMBI
tras las sanciones de EE.UU. Para riesgo venezolano hay que ir a Damodaran, que
si lo cubre.
"""

import json
import socket
import urllib.error
import urllib.request
from datetime import date

from motor.paquete import Cifra, Fuente, Paquete, formato_es

TIEMPO_LIMITE = 25
AGENTE = "SurEconomics/1.0 (medio de economia; redaccion@sureconomics.com)"
BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

# Series mensuales verificadas el 24/08/2026. Cada una es el diferencial de
# rendimientos del EMBIG en puntos basicos.
SERIES = {
    "Perú":      "PN01129XM",
    "Argentina": "PN01130XM",
}

# Paises que la prensa pide y que esta via NO cubre. Se nombran para que quede
# claro que es un limite conocido y no un olvido.
SIN_COBERTURA = {
    "Venezuela": "J.P. Morgan excluyó a Venezuela y PDVSA de sus índices EMBI "
                 "tras las sanciones de EE.UU. Para riesgo venezolano, usar "
                 "Damodaran.",
}


def _pedir(url):
    socket.setdefaulttimeout(TIEMPO_LIMITE)
    try:
        peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(peticion) as r:
            return json.load(r)
    except (urllib.error.URLError, socket.timeout, ValueError) as exc:
        print(f"[aviso] el BCRP no respondio: {exc}")
        return None


def paises_disponibles():
    return sorted(SERIES)


def extraer(pais, meses=6):
    """Paquete con el riesgo país de los ultimos meses. None si no hay datos."""
    objetivo = pais.strip()
    clave = next((k for k in SERIES if k.lower() == objetivo.lower()), None)
    if clave is None:
        if objetivo in SIN_COBERTURA:
            print(f"[aviso] {objetivo}: {SIN_COBERTURA[objetivo]}")
            return None
        raise ValueError(f"pais sin serie EMBI: {pais}. "
                         f"Disponibles: {', '.join(paises_disponibles())}")

    hoy = date.today()
    desde_anio = hoy.year - (1 if hoy.month <= meses else 0)
    desde_mes = (hoy.month - meses) % 12 or 12
    url = (f"{BASE}/{SERIES[clave]}/json/"
           f"{desde_anio}-{desde_mes:02d}/{hoy.year}-{hoy.month:02d}")

    crudo = _pedir(url)
    if not crudo or not crudo.get("periods"):
        print(f"[aviso] sin datos de EMBI para {clave}")
        return None

    titulo = crudo["config"]["series"][0]["name"]
    # El BCRP marca los meses sin dato como 'n.d.'. Se descartan en vez de
    # convertirlos en cero, que seria decir que el riesgo pais fue nulo.
    observados = []
    for p in crudo["periods"]:
        valores = [v for v in p.get("values", []) if v not in ("n.d.", "", None)]
        if not valores:
            continue
        try:
            observados.append((p["name"], float(valores[0])))
        except ValueError:
            continue
    if not observados:
        print(f"[aviso] la serie de {clave} viene sin valores utiles")
        return None

    # La institucion que se nombra en la prosa es J.P. Morgan, dueño del indice.
    # El BCRP es de donde bajamos la serie y queda registrado en 'documento' y en
    # 'url_datos' para poder rastrearlo, pero NO va en el texto: ningun diario
    # escribe "el EMBI de J.P. Morgan via el Banco Central de Reserva del Peru".
    # Decision editorial del dueño (24/08/2026): sobreexplicaba y sonaba forzado.
    fuente = Fuente(
        id="embi1",
        institucion="J.P. Morgan",
        documento=f"{titulo} — serie consultada en el Banco Central de Reserva "
                  f"del Perú",
        url="https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/"
            "resultados/PN01129XM/html",
        url_datos=url,
    )

    cifras = [Cifra(clave=f"embi_{n.replace('.', '_').lower()}",
                    valor=formato_es(v, 0), unidad="puntos básicos",
                    periodo=n, fuente_id="embi1", valor_crudo=v,
                    nota="diferencial de rendimientos del EMBIG")
              for n, v in observados]

    ultimo_nombre, ultimo_valor = observados[-1]
    return Paquete(
        hecho=(f"El riesgo país de {clave} se ubicó en "
               f"{formato_es(ultimo_valor, 0)} puntos básicos en {ultimo_nombre}, "
               f"según el índice EMBIG de J.P. Morgan"),
        fecha_hecho=ultimo_nombre,
        cifras=cifras,
        entidades=[clave, "J.P. Morgan", "Banco Central de Reserva del Perú"],
        fuentes=[fuente],
        advertencias=[
            "El índice es de J.P. Morgan: se le atribuye a él y basta. NO menciones "
            "el Banco Central de Reserva del Perú en el texto —es solo de donde se "
            "consultó la serie— ni expliques la metodología del índice.",
            "Si la pieza va para lector general, explica qué es un punto básico "
            "con naturalidad y en su propia frase. No metas la definición entre "
            "guiones a mitad de otra frase: estorba la lectura.",
        ],
    )
