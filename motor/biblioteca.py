"""La biblioteca de fuentes: que hay disponible y como se pide.

Un solo sitio que sabe de todas las fuentes de datos. Existe por dos razones:

1. El economista tiene que ver la biblioteca ENTERA para elegir bien. Si solo
   conoce una fuente, siempre pedira esa, y tener quince fuentes no servira de
   nada.
2. Agregar una fuente nueva tiene que ser tocar un sitio, no tres.

Las fuentes de NOTICIAS (diarios) no estan aqui: eso es `fuentes/noticias.py` y
es de donde sale el hecho. Aqui esta lo que el medio APORTA como contexto.
"""

from motor.fuentes import (banco_mundial, bcv, damodaran, embi, fmi,
                           manual, oficiales)

# Cada entrada describe una fuente para que el economista pueda elegirla, y dice
# como se le pide. 'cadencia' es lo mas importante de todo: una fuente anual no
# sirve para contextualizar una noticia de hoy, y el economista tiene que saberlo
# antes de pedirla, no despues.
FUENTES = {
    "Prensa reciente (los 28 diarios de la lista blanca)": {
        "forma": "prensa:<palabras clave>",
        "ejemplo": "prensa:inflaci|bcv",
        "da": "la cifra más ACTUAL que existe: lo que publicaron los diarios en "
              "los últimos 30 días. Es fuente secundaria, se cita al diario",
        "cadencia": "DIARIA. Es lo más reciente de toda la biblioteca",
        "cobertura": "lo que hayan cubierto los diarios. Para Venezuela suele "
                     "ser la única vía con datos del mes en curso",
        "opciones": lambda: "cualquier palabra clave; acepta alternativas con | "
                            "(ej. 'inflaci|precios|canasta')",
    },
    "Comunicados oficiales (FMI, BID, CEPAL, bancos centrales)": {
        "forma": "oficial:ENTIDAD",
        "ejemplo": "oficial:FMI",
        "da": "el comunicado original del organismo, no la reseña de un diario",
        "cadencia": "cuando publican. Entra por el índice de Tavily, porque estos "
                    "organismos bloquean la lectura directa",
        "cobertura": "FMI, BID, CEPAL, Banxico, DANE y otros bancos centrales",
        "opciones": lambda: ", ".join(oficiales.ENTIDADES),
    },
    "BCV (Banco Central de Venezuela)": {
        "forma": "bcv:",
        "ejemplo": "bcv:",
        "da": "la tasa oficial del dólar y del euro en bolívares, del día",
        "cadencia": "DIARIA. Fuente primaria venezolana, leída del propio BCV",
        "cobertura": "solo Venezuela. Es la tasa OFICIAL: convive con el mercado "
                     "paralelo, y para hablar de precios reales eso hay que decirlo",
        "opciones": lambda: "sin opciones: bcv:",
    },
    "FMI (World Economic Outlook)": {
        "forma": "fmi:Pais:indicador",
        "ejemplo": "fmi:Venezuela:inflacion",
        "da": "inflación y crecimiento del PIB, CON PROYECCIONES hasta 2027",
        "cadencia": "SEMESTRAL (abril y octubre). Captura manual: el FMI bloquea "
                    "la lectura automática",
        "cobertura": "9 países de Latam. Es la ÚNICA fuente con datos recientes y "
                     "proyectados de VENEZUELA — el Banco Mundial se detiene en 2016",
        "opciones": lambda: ", ".join(fmi.paises_disponibles()),
    },
    "Banco Mundial": {
        "forma": "ISO3:indicador",
        "ejemplo": "VEN:inflacion",
        "da": "series macroeconómicas por país",
        "cadencia": "ANUAL y con 1 o 2 años de retraso",
        "cobertura": "los 20 países de Latinoamérica y el agregado regional (LCN)",
        "opciones": lambda: ", ".join(banco_mundial.INDICADORES),
    },
    "Damodaran (NYU Stern)": {
        "forma": "dam:Pais",
        "ejemplo": "dam:Venezuela",
        "da": "riesgo financiero: prima de riesgo país, calificación soberana, "
              "spread por impago y CDS",
        "cadencia": "ANUAL (enero). Es una estimación académica, no una cifra oficial",
        "cobertura": "Latinoamérica completa, INCLUIDA VENEZUELA (que el Banco "
                     "Mundial no cubre)",
        "opciones": lambda: ", ".join(damodaran.paises_disponibles()),
    },
    "EMBI de J.P. Morgan (vía BCRP)": {
        "forma": "embi:Pais",
        "ejemplo": "embi:Argentina",
        "da": "riesgo país en puntos básicos, el indicador que cita la prensa",
        "cadencia": "MENSUAL. Es lo más actual de la biblioteca",
        "cobertura": "solo Perú y Argentina. NO cubre a Venezuela: J.P. Morgan "
                     "la excluyó de sus índices tras las sanciones",
        "opciones": lambda: ", ".join(embi.paises_disponibles()),
    },
}


def catalogo_texto():
    """La biblioteca escrita, para meterla en el prompt del economista."""
    bloques = []
    for nombre, f in FUENTES.items():
        bloques.append(
            f"### {nombre}\n"
            f"- Se pide como: `{f['forma']}` (ejemplo: `{f['ejemplo']}`)\n"
            f"- Da: {f['da']}\n"
            f"- Cadencia: {f['cadencia']}\n"
            f"- Cobertura: {f['cobertura']}\n"
            f"- Opciones válidas: {f['opciones']()}"
        )
    return "\n\n".join(bloques)


def _contexto_de_prensa(busqueda, dias=30):
    """Busca en los diarios de la lista blanca una nota que sirva de contexto.

    Es la fuente MAS ACTUAL que tenemos, y durante un tiempo estuvo desperdiciada:
    el codigo trataba a los diarios solo como "el hecho" y nunca como contexto. La
    inflacion de Venezuela de julio de 2026 -19,9 % segun el BCV- llevaba dias en
    El Nacional mientras el economista declaraba que faltaban datos actuales.

    Lo que devuelve es fuente SECUNDARIA y viene marcado como tal: se cita al
    diario, y la cifra no se publica como propia sin confirmarla.
    """
    from motor.fuentes import noticias

    # Se piden varias y se elige la que MAS CIFRAS trae, no la mas reciente. La
    # primera version cogia la ultima publicada y devolvia "precio del dolar BCV
    # hoy", que no lleva ningun dato aprovechable, mientras la nota del BCV con
    # la inflacion de julio estaba dos puestos mas abajo. Para contexto vale mas
    # una nota con datos que una nota de hace una hora.
    lote = noticias.extraer(None, horas=dias * 24, limite=8, tema=busqueda)
    if not lote:
        print(f"[aviso] sin notas recientes sobre '{busqueda}'")
        return None
    p = max(lote, key=lambda x: len(x.cifras))
    if not p.cifras:
        print(f"[aviso] hay notas sobre '{busqueda}' pero ninguna trae cifras")
    p.advertencias.append(
        "CONTEXTO DE PRENSA: esta cifra la publicó otro diario, no la calculamos "
        "nosotros. Cítalo por su nombre igual que al medio de la noticia principal."
    )
    return p


def traer(peticion, observaciones=3):
    """Resuelve una peticion contra la biblioteca. Devuelve un Paquete o None.

        VEN:inflacion       Banco Mundial (forma por defecto)
        bm:VEN:inflacion    lo mismo, explicito
        dam:Venezuela       Damodaran
        embi:Argentina      EMBI
    """
    peticion = peticion.strip()
    if peticion.startswith("manual:"):
        return manual.extraer(peticion[7:])
    if peticion.startswith("prensa:"):
        return _contexto_de_prensa(peticion[7:])
    if peticion.startswith("oficial:"):
        lote = oficiales.buscar_comunicados_entidad(peticion[8:], dias=21, limite=1)
        if not lote:
            return None
        paquetes = oficiales.extraer(dias=21, limite_por_entidad=1)
        entidad = peticion[8:].upper()
        return next((p for p in paquetes
                     if entidad in p.fuentes[0].id.upper()), None)
    if peticion.startswith("bcv"):
        return bcv.extraer()
    if peticion.startswith("fmi:"):
        partes = peticion[4:].split(":")
        return fmi.extraer(partes[0], partes[1] if len(partes) > 1 else "crecimiento")
    if peticion.startswith("dam:"):
        return damodaran.extraer(peticion[4:])
    if peticion.startswith("embi:"):
        return embi.extraer(peticion[5:])

    resto = peticion[3:] if peticion.startswith("bm:") else peticion
    try:
        pais, indicador = resto.split(":")
    except ValueError:
        raise ValueError(f"'{peticion}' no tiene forma reconocible. Use "
                         f"ISO3:indicador, dam:Pais o embi:Pais")
    return banco_mundial.extraer(pais, indicador, observaciones)


def describir(peticion):
    """Como nombrar la peticion en pantalla, para que se vea que se esta pidiendo."""
    peticion = peticion.strip()
    if peticion.startswith("manual:"):
        return f"fuente verificada a mano: {peticion[7:]}"
    if peticion.startswith("prensa:"):
        return f"prensa reciente sobre «{peticion[7:]}»"
    if peticion.startswith("oficial:"):
        lote = oficiales.buscar_comunicados_entidad(peticion[8:], dias=21, limite=1)
        if not lote:
            return None
        paquetes = oficiales.extraer(dias=21, limite_por_entidad=1)
        entidad = peticion[8:].upper()
        return next((p for p in paquetes
                     if entidad in p.fuentes[0].id.upper()), None)
    if peticion.startswith("bcv"):
        return bcv.extraer()
    if peticion.startswith("oficial:"):
        return f"comunicado oficial de {peticion[8:]}"
    if peticion.startswith("bcv"):
        return "BCV, tasa oficial del día"
    if peticion.startswith("fmi:"):
        return f"FMI, {peticion[4:].replace(':', ' ')}"
    if peticion.startswith("dam:"):
        return f"Damodaran, {peticion[4:]}"
    if peticion.startswith("embi:"):
        return f"EMBI, {peticion[5:]}"
    return f"Banco Mundial, {peticion.replace('bm:', '').replace(':', ' ')}"
