"""Extractor del FMI (World Economic Outlook), con captura manual.

POR QUE ESTA FUENTE ES DISTINTA A LAS DEMAS
El FMI devuelve 403 a cualquier lector automatico. Comprobado el 25/08/2026
desde GitHub Actions con IP limpia de Microsoft: da 403 igual que desde el
escritorio, asi que no es la VPN ni el servidor — bloquea maquinas y punto.

Pero SI se deja leer desde un navegador. Y aqui esta la clave: el World Economic
Outlook **se actualiza dos veces al año** (abril y octubre). Una fuente que
cambia dos veces al año no necesita una conexion diaria: se captura a mano
cuando publica, y se usa durante seis meses.

Automatizar esto seria montar un navegador sin ventana solo para consultar algo
que cambia en abril y en octubre. No compensa. La cadencia de la fuente decide
el nivel de automatizacion que merece, no al reves.

QUE APORTA QUE NO TENGAMOS
Es la unica fuente con datos RECIENTES Y PROYECTADOS de Venezuela. El Banco
Mundial se detiene en 2016; el FMI llega a 2027 con estimaciones. Para un medio
latinoamericano eso no es un detalle: es la diferencia entre poder hablar de la
economia venezolana con cifras o no poder.

COMO ACTUALIZARLA
1. Abrir en el navegador (no con un script, da 403):
   https://www.imf.org/external/datamapper/api/v1/PCPIPCH/VEN   (inflacion)
   https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/VEN (PIB real)
2. Copiar los valores del pais que interese.
3. Actualizar DATOS aqui abajo y cambiar CAPTURADO.
Toca hacerlo en abril y en octubre. El resto del año, esto sirve tal cual.
"""

from datetime import date

from motor.paquete import Cifra, Fuente, Paquete, formato_es

# Fecha en que se copiaron los datos. Va en el periodo de cada cifra: nunca se
# presenta como si se hubiera consultado hoy.
CAPTURADO = "2026-08-25"
EDICION_WEO = "World Economic Outlook"

URL = "https://www.imf.org/external/datamapper/PCPIPCH@WEO"

# pais -> indicador -> {año: valor}. Los años futuros son PROYECCION del FMI y
# hay que decirlo siempre: presentar una proyeccion como dato es un error grave.
DATOS = {
    "Venezuela": {
        "inflacion": {"2023": 337.5, "2024": 49.4, "2025": 252.0,
                      "2026": 387.4, "2027": 94.4},
        "crecimiento": {"2023": 4.0, "2024": 5.3, "2025": 1.5,
                        "2026": 4.0, "2027": 6.0},
    },
    "Argentina":  {"crecimiento": {"2023": -1.9, "2024": -1.3, "2025": 4.4,
                                   "2026": 3.5, "2027": 4.0}},
    "Colombia":   {"crecimiento": {"2023": 0.8, "2024": 1.5, "2025": 2.6,
                                   "2026": 2.3, "2027": 2.5}},
    "Brasil":     {"crecimiento": {"2023": 3.2, "2024": 3.4, "2025": 2.3,
                                   "2026": 1.9, "2027": 2.0}},
    "Chile":      {"crecimiento": {"2023": 0.5, "2024": 2.6, "2025": 2.3,
                                   "2026": 2.4, "2027": 2.6}},
    "México":     {"crecimiento": {"2023": 3.1, "2024": 1.4, "2025": 0.6,
                                   "2026": 1.6, "2027": 2.2}},
    "Perú":       {"crecimiento": {"2023": -0.4, "2024": 3.5, "2025": 3.4,
                                   "2026": 2.8, "2027": 2.8}},
    "Ecuador":    {"crecimiento": {"2023": 1.8, "2024": -1.9, "2025": 3.7,
                                   "2026": 2.5, "2027": 2.5}},
    "Bolivia":    {"crecimiento": {"2023": 2.5, "2024": -1.1, "2025": -1.2,
                                   "2026": -3.3}},
}

NOMBRES = {"inflacion": "inflación anual",
           "crecimiento": "crecimiento del PIB real"}


def paises_disponibles():
    return sorted(DATOS)


def indicadores_de(pais):
    return sorted(DATOS.get(pais, {}))


def extraer(pais, indicador="crecimiento"):
    """Paquete con la serie del FMI para un pais. None si no lo tenemos."""
    objetivo = next((p for p in DATOS if p.lower() == pais.strip().lower()), None)
    if objetivo is None:
        raise ValueError(f"pais no capturado del FMI: {pais}. "
                         f"Disponibles: {', '.join(paises_disponibles())}")
    serie = DATOS[objetivo].get(indicador)
    if not serie:
        raise ValueError(f"del FMI solo tenemos {', '.join(indicadores_de(objetivo))} "
                         f"para {objetivo}")

    fuente = Fuente(
        id="fmi1",
        institucion="Fondo Monetario Internacional",
        documento=f"{EDICION_WEO} — {NOMBRES[indicador]} de {objetivo}, "
                  f"consultado el {CAPTURADO}",
        url=URL,
    )

    anio_actual = date.today().year
    cifras = []
    for anio, valor in sorted(serie.items()):
        proyeccion = int(anio) >= anio_actual
        cifras.append(Cifra(
            clave=f"fmi_{indicador}_{anio}",
            valor=formato_es(valor, 1),
            unidad="%",
            periodo=f"{anio} (proyección del FMI)" if proyeccion else anio,
            fuente_id="fmi1",
            valor_crudo=valor,
            nota=f"{NOMBRES[indicador]}" + (" — PROYECCIÓN, no dato observado"
                                            if proyeccion else ""),
        ))

    ultimo_real = max((a for a in serie if int(a) < anio_actual), default=None)
    return Paquete(
        hecho=(f"{NOMBRES[indicador].capitalize()} de {objetivo} según el "
               f"{EDICION_WEO} del FMI"
               + (f": {formato_es(serie[ultimo_real], 1)} % en {ultimo_real}"
                  if ultimo_real else "")),
        fecha_hecho=ultimo_real or CAPTURADO,
        cifras=cifras,
        entidades=[objetivo, "Fondo Monetario Internacional"],
        fuentes=[fuente],
        advertencias=[
            f"LOS AÑOS {anio_actual} EN ADELANTE SON PROYECCIONES del FMI, no "
            f"datos observados. Si usas una, dilo expresamente: presentar una "
            f"estimación como hecho consumado es un error grave.",
            f"Datos capturados a mano el {CAPTURADO} porque el FMI bloquea la "
            f"lectura automática. El WEO se actualiza en abril y en octubre; "
            f"si estamos pasados de esas fechas, conviene refrescarlos.",
        ],
    )
