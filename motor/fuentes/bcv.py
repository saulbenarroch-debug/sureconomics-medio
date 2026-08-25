"""Extractor del Banco Central de Venezuela: tasa oficial del dólar y del euro.

PORTADO DEL BOT, NO INVENTADO AQUI. La logica de lectura y el manejo de la
"fecha valor" vienen de `al-cierre/fetch_data.py` del bot de Telegram, que lleva
meses publicando estas tasas a diario. Aqui solo se envuelve en un paquete de
datos.

Es FUENTE PRIMARIA y venezolana, que es justo lo que faltaba: llevabamos dias
diciendo que no habia datos actuales de Venezuela mientras el bot leia el BCV
todos los dias.

DOS TRAMPAS QUE EL BOT YA PAGO

1. **Fecha valor.** El BCV publica cada tarde la tasa que rige el DIA SIGUIENTE.
   Si se toma sin mirar eso, se publica como tasa de hoy una que todavia no rige.
   Por eso se lee la fecha valor y se dice a que dia corresponde.

2. **El certificado del BCV falla.** Hay que desactivar la verificacion TLS o la
   peticion no entra. Es un riesgo asumido y consciente: se lee una pagina
   publica, no se envia nada, y no hay alternativa — es el unico sitio donde el
   BCV publica su tasa.
"""

import re
import socket
import ssl
import urllib.error
import urllib.request

from motor.paquete import Cifra, Fuente, Paquete, formato_es

URL = "https://www.bcv.org.ve/"
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIEMPO_LIMITE = 30

MONEDAS = {"dolar": ("usd", "dólar estadounidense"),
           "euro": ("eur", "euro")}


def _bajar():
    """Descarga la portada del BCV. None si no responde."""
    # verify_mode = CERT_NONE porque el certificado del BCV no valida. Igual que
    # en al-cierre/fetch_data.py: sin esto la peticion no entra.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    peticion = urllib.request.Request(URL, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE, context=ctx) as r:
            return r.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, socket.timeout) as exc:
        print(f"[aviso] el BCV no respondio: {exc}")
        return None


def extraer():
    """Paquete con la tasa oficial vigente. None si el BCV no responde."""
    html = _bajar()
    if not html:
        return None

    m = re.search(r"Fecha\s*Valor.*?content=\"(\d{4}-\d{2}-\d{2})", html, re.S)
    if not m:
        m = re.search(r'date-display-single[^>]*content="(\d{4}-\d{2}-\d{2})', html)
    if not m:
        print("[aviso] no encontre la fecha valor en la pagina del BCV")
        return None
    fecha_valor = m.group(1)

    cifras = []
    for id_html, (clave, nombre) in MONEDAS.items():
        m = re.search(r'id="%s".*?<strong[^>]*>\s*([\d.,]+)\s*</strong>' % id_html,
                      html, re.S)
        if not m:
            print(f"[aviso] no encontre la tasa de {nombre} en el BCV")
            continue
        # El BCV escribe en norma española: 784,66 y 1.234,56
        valor = float(m.group(1).replace(".", "").replace(",", "."))
        cifras.append(Cifra(
            clave=f"bcv_{clave}",
            valor=formato_es(valor, 2),
            unidad="bolívares",
            periodo=f"tasa vigente el {fecha_valor}",
            fuente_id="bcv1",
            valor_crudo=valor,
            nota=f"tasa oficial del {nombre} publicada por el BCV",
        ))

    if not cifras:
        return None

    usd = next((c for c in cifras if c.clave == "bcv_usd"), cifras[0])
    return Paquete(
        hecho=(f"El Banco Central de Venezuela fijó la tasa oficial del dólar en "
               f"{usd.valor} bolívares, vigente el {fecha_valor}"),
        fecha_hecho=fecha_valor,
        cifras=cifras,
        entidades=["Venezuela", "Banco Central de Venezuela"],
        fuentes=[Fuente(
            id="bcv1",
            institucion="Banco Central de Venezuela",
            documento=f"Tipo de cambio de referencia, fecha valor {fecha_valor}",
            url=URL,
            url_datos=URL,
            # El BCV publica la tasa en su portada y no tiene enlace
            # permanente por dia. Es la excepcion, marcada a mano.
            portada_es_la_fuente=True,
        )],
        advertencias=[
            f"OJO CON LA FECHA: el BCV publica cada tarde la tasa que rige el DÍA "
            f"SIGUIENTE. Esta rige el {fecha_valor}. No escribas «la tasa de hoy» "
            f"sin comprobar que hoy es esa fecha: se publicaría como vigente una "
            f"tasa que todavía no lo está.",
            "Es la tasa OFICIAL. En Venezuela convive con el mercado paralelo, y "
            "si la pieza habla de precios o de poder de compra, decir solo la "
            "oficial da una imagen incompleta.",
        ],
    )
