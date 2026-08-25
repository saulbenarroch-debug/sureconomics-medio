"""Extractor (A4) de las bases de Aswath Damodaran (NYU Stern).

Sugerida por la gerencia como sustituto de las bases de banca privada: gratis,
sin clave, y -lo importante- CUBRE A VENEZUELA, que es justo donde el Banco
Mundial no llega. Da prima de riesgo pais, calificacion soberana, spread por
impago, CDS y tasa impositiva.

Actualizacion ANUAL (cada enero, con revisiones sueltas). No sirve para la
noticia del dia; sirve para contexto financiero, informes y educacion. La fecha
real de actualizacion se lee del propio archivo y va en el periodo de cada cifra:
nunca se presenta el dato como si fuera de hoy.

El archivo pesa ~380 KB, asi que se guarda en cache local. Bajarlo en cada
corrida seria maltratar un servidor universitario que nos da los datos gratis.
"""

import io
import pathlib
import socket
import urllib.error
import urllib.request
import warnings
from datetime import date, datetime

from motor.paquete import Cifra, Fuente, Paquete, formato_es

warnings.filterwarnings("ignore", module="openpyxl")

TIEMPO_LIMITE = 45
AGENTE = "SurEconomics/1.0 (medio de economia; redaccion@sureconomics.com)"
URL_DATOS = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
URL_HUMANA = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datacurrent.html"

CACHE = pathlib.Path(__file__).resolve().parent.parent.parent / ".cache"
DIAS_CACHE = 30

# Columna (base 0) -> (clave, nombre en español, unidad). El archivo trae los
# porcentajes como fraccion: 0,175 = 17,5 %.
COLUMNAS = {
    2: ("calificacion", "calificación soberana de Moody's", "", False),
    3: ("spread_impago", "spread por riesgo de impago", "%", True),
    4: ("prima_total", "prima de riesgo de renta variable", "%", True),
    5: ("prima_pais", "prima de riesgo país", "%", True),
    6: ("cds", "CDS soberano a 10 años", "%", True),
}

# Nombre en el archivo (ingles) -> nombre del medio (español).
PAISES = {
    "Argentina": "Argentina", "Bolivia": "Bolivia", "Brazil": "Brasil",
    "Chile": "Chile", "Colombia": "Colombia", "Costa Rica": "Costa Rica",
    "Cuba": "Cuba", "Dominican Republic": "República Dominicana",
    "Ecuador": "Ecuador", "El Salvador": "El Salvador", "Guatemala": "Guatemala",
    "Haiti": "Haití", "Honduras": "Honduras", "Mexico": "México",
    "Nicaragua": "Nicaragua", "Panama": "Panamá", "Paraguay": "Paraguay",
    "Peru": "Perú", "Uruguay": "Uruguay", "Venezuela": "Venezuela",
    "United States": "EE. UU.", "Spain": "España", "China": "China",
}


def _descargar():
    """Devuelve el archivo, de cache si es reciente. None si no hay forma."""
    CACHE.mkdir(exist_ok=True)
    destino = CACHE / "damodaran_ctryprem.xlsx"
    if destino.exists():
        edad = (date.today() - date.fromtimestamp(destino.stat().st_mtime)).days
        if edad < DIAS_CACHE:
            return destino.read_bytes()

    socket.setdefaulttimeout(TIEMPO_LIMITE)
    try:
        peticion = urllib.request.Request(URL_DATOS, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(peticion) as r:
            datos = r.read()
        destino.write_bytes(datos)
        return datos
    except (urllib.error.URLError, socket.timeout) as exc:
        print(f"[aviso] no pude bajar la base de Damodaran: {exc}")
        # Cache vencida es mejor que nada, pero se avisa: el dato tiene su fecha
        # dentro del archivo, asi que no se puede presentar como actual igual.
        if destino.exists():
            print("[aviso] uso la copia en cache, aunque este vencida")
            return destino.read_bytes()
        return None


def _hoja():
    """Devuelve (filas, fecha_de_actualizacion) o (None, None)."""
    import openpyxl

    datos = _descargar()
    if not datos:
        return None, None
    libro = openpyxl.load_workbook(io.BytesIO(datos), data_only=True)
    hoja = libro["ERPs by country"]
    filas = list(hoja.iter_rows(values_only=True))

    actualizado = ""
    for fila in filas[:5]:
        if fila and fila[0] and "Date of update" in str(fila[0]) and fila[1]:
            valor = fila[1]
            actualizado = (valor.date().isoformat()
                           if isinstance(valor, datetime) else str(valor)[:10])
            break
    return filas, actualizado


def paises_disponibles():
    return sorted(PAISES.values())


def extraer(pais, completo=False):
    """Paquete con el perfil de riesgo de un pais. None si no hay datos.

    'pais' es el nombre en español, tal como lo usa el medio: 'Venezuela'.

    Por defecto devuelve SOLO la calificacion soberana y la prima de riesgo pais,
    que son las dos que un lector entiende y que sostienen un argumento. El resto
    -spread por impago, prima de renta variable, CDS- se piden con completo=True
    para investigaciones e informes.

    Por que no se entregan siempre las cinco: pedirle al redactor que no las
    enumere no funciono. Tres versiones del prompt seguidas, y una noticia sobre
    un terremoto acababa con "spread de 17,50 %, prima de 26,66 %, renta variable
    de 30,89 % y CDS de 9,15 %" en la misma frase. Si el paquete no las tiene, no
    puede enumerarlas: es el mismo principio que con las cifras inventadas —lo
    que se puede resolver en la estructura no se le pide al modelo.
    """
    EDITORIALES = {"calificacion", "prima_pais"}
    objetivo = pais.strip()
    ingles = next((k for k, v in PAISES.items() if v.lower() == objetivo.lower()), None)
    if ingles is None:
        raise ValueError(f"pais no reconocido: {pais}. "
                         f"Disponibles: {', '.join(paises_disponibles())}")

    filas, actualizado = _hoja()
    if filas is None:
        return None

    fila = next((f for f in filas if f and f[0] and str(f[0]).strip() == ingles), None)
    if fila is None:
        print(f"[aviso] Damodaran no trae a {objetivo}")
        return None

    periodo = actualizado or "sin fecha en el archivo"
    fuente = Fuente(
        id="dam1",
        institucion="Aswath Damodaran (NYU Stern)",
        documento=f"Country Default Spreads and Risk Premiums, actualizado {periodo}",
        url=URL_HUMANA,
        url_datos=URL_DATOS,
    )

    cifras = []
    for col, (clave, nombre, unidad, es_pct) in COLUMNAS.items():
        if col >= len(fila) or fila[col] is None:
            continue
        if not completo and clave not in EDITORIALES:
            continue
        bruto = fila[col]
        if es_pct:
            try:
                numero = float(bruto)
            except (TypeError, ValueError):
                continue
            # El archivo guarda 0,175 para 17,5 %.
            cifras.append(Cifra(clave=clave, valor=formato_es(numero * 100, 2),
                                unidad=unidad, periodo=periodo, fuente_id="dam1",
                                valor_crudo=numero * 100, nota=nombre))
        else:
            cifras.append(Cifra(clave=clave, valor=str(bruto).strip(),
                                unidad="calificación", periodo=periodo,
                                fuente_id="dam1", nota=nombre))

    if not cifras:
        print(f"[aviso] la fila de {objetivo} vino vacia")
        return None

    prima = next((c for c in cifras if c.clave == "prima_pais"), cifras[0])
    paquete = Paquete(
        hecho=(f"Prima de riesgo país de {objetivo}: {prima.valor} %, "
               f"según la base de Damodaran actualizada en {periodo}"),
        fecha_hecho=periodo,
        cifras=cifras,
        entidades=[objetivo, "NYU Stern", "Aswath Damodaran"],
        fuentes=[fuente],
        advertencias=[
            "USA ESTE CONTEXTO SOLO SI VIENE AL CASO, y casi nunca hace falta la "
            "cifra. En la mayoría de las piezas basta con «la alta prima de riesgo "
            "país encarece el crédito y ahuyenta la inversión»: es una realidad "
            "conocida que no necesita número ni fuente. Mete el número solo si el "
            "argumento se apoya en su magnitud.",
            "LA ATRIBUCIÓN VA CON LA CIFRA, NO SIN ELLA. Si escribes el número, "
            f"nombra a Damodaran (NYU Stern) y di que es de {periodo}: es la "
            "estimación de un académico, no una cifra oficial, y presentarla sin "
            "dueño sería falsa precisión. Pero si solo haces la afirmación "
            "cualitativa, NO lo menciones: nombrar a un académico para decir que "
            "el riesgo es alto suena a nota al pie y estorba la lectura.",
        ],
    )

    antiguedad = date.today().year - int(periodo[:4]) if periodo[:4].isdigit() else 0
    if antiguedad >= 2:
        paquete.advertencias.append(
            f"La copia disponible es de {periodo[:4]}: tiene {antiguedad} años. "
            f"Revisar si hay una actualización más reciente antes de publicar.")
    return paquete
