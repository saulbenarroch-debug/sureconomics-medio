r"""Ilustraciones simbolicas generadas, para cuando no hay foto que valga.

    from motor import ilustrar
    ruta, pie = ilustrar.para("El turismo en Republica Dominicana subio 12 %",
                              ["Republica Dominicana"])

LA REGLA, QUE ES LO IMPORTANTE DE ESTE ARCHIVO

Una imagen generada NUNCA representa el hecho que se cuenta. Si la nota es de
una avalancha, no se dibuja una avalancha: seria una escena falsa presentada
como cobertura, y eso es desinformar aunque el pie diga que es un dibujo.

Lo que si se genera son SIMBOLOS del asunto. Si el turismo dominicano subio un
12 %, se compone un avion, una playa y la bandera dominicana. Nadie puede
confundir eso con el registro de un hecho, porque no pretende serlo: es la
misma funcion que cumple un icono en la portada de un informe.

De ahi salen las tres prohibiciones que el aviso lleva escritas y que no se
pueden desactivar con un parametro:

  - nada de escenas del suceso,
  - nada de personas reconocibles ni figuras publicas,
  - nada de lugares reales concretos presentados como si fueran ese lugar.

Y el pie siempre lo dice con todas las letras. Una ilustracion sin etiquetar es
una foto falsa, por muy simbolica que sea la intencion de quien la encargo.

CUOTA

El plan gratuito de Gemini da CERO imagenes: los modelos aparecen en la cuenta
pero el limite es 0, comprobado el 28/08/2026. Esto necesita facturacion
activada. Sin ella, `para()` devuelve None y la pieza se sube sin imagen, que
es preferible a subirla con una imagen equivocada.
"""

import os
import pathlib
import re

MODELOS = ["gemini-3.1-flash-image", "gemini-3-pro-image", "gemini-2.5-flash-image"]

# Formatos donde una ilustracion simbolica tiene sentido. En una noticia de un
# hecho concreto se prefiere no poner nada: el lector espera una foto ahi.
FORMATOS_QUE_ADMITEN = {"articulo", "informe", "editorial"}

PIE = ("Ilustración generada con inteligencia artificial a partir de elementos "
       "simbólicos. No representa un hecho ni un lugar real.")

AVISO = """Compón una ilustración editorial SIMBÓLICA para un medio de economía.

Asunto: {asunto}
Elementos que deben aparecer: {elementos}

REGLAS QUE NO PUEDES SALTARTE:
- NO representes el suceso ni ninguna escena de lo ocurrido.
- NO incluyas personas reconocibles, retratos ni figuras públicas.
- NO representes un lugar real concreto como si fuera ese lugar.
- NO escribas texto, cifras, letras ni logotipos dentro de la imagen.

Estilo: composición limpia de objetos y símbolos sobre fondo liso, ilustración
plana y sobria, paleta contenida. Formato apaisado."""


def _elementos(titular, lugares):
    """Saca los simbolos del titular. Codigo, no modelo: si de aqui saliera una
    escena, la regla de arriba dependeria de que un modelo se porte bien."""
    simbolos = []
    t = titular.lower()
    for palabra, simbolo in (
            ("turismo", "un avión y una playa"),
            ("petról", "una torre de perforación"),
            ("gas", "una tubería industrial"),
            ("inflaci", "una cesta de la compra y una curva ascendente"),
            ("licencia", "un sello y un documento oficial"),
            ("sanci", "un candado sobre un documento"),
            ("ciberata", "un candado y un circuito"),
            ("banco", "una fachada con columnas"),
            ("deuda", "una balanza"),
            ("export", "un contenedor de carga"),
            ("import", "un contenedor de carga"),
            ("empleo", "un casco de trabajo"),
            ("miner", "un pico y una veta de mineral")):
        if palabra in t:
            simbolos.append(simbolo)
    for lugar in lugares or []:
        simbolos.append("la bandera de %s" % lugar)
    if not simbolos:
        simbolos = ["un gráfico de barras abstracto", "una moneda"]
    return ", ".join(simbolos[:3])


def para(titular, lugares=None, formato="articulo", destino=None):
    """Devuelve (ruta, pie) o None si no se puede o no procede."""
    if formato not in FORMATOS_QUE_ADMITEN:
        return None

    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        return None

    asunto = re.sub(r"\s+", " ", titular).strip()[:160]
    aviso = AVISO.format(asunto=asunto, elementos=_elementos(asunto, lugares))

    try:
        from google import genai
    except ImportError:
        return None

    cliente = genai.Client(api_key=clave)
    for modelo in MODELOS:
        try:
            r = cliente.models.generate_content(model=modelo, contents=aviso)
            partes = r.candidates[0].content.parts
            datos = [p.inline_data for p in partes if getattr(p, "inline_data", None)]
            if not datos:
                continue
            ruta = pathlib.Path(destino or "ilustracion.png")
            ruta.write_bytes(datos[0].data)
            return str(ruta), PIE
        except Exception as exc:  # noqa: BLE001
            if "429" in str(exc):
                # Sin cuota. Se avisa una vez y se sigue sin imagen: una pieza
                # sin foto se arregla en un minuto, una con la foto equivocada
                # se arregla despues de que la lea alguien.
                print("      ilustracion: sin cuota de imagen en Gemini "
                      "(el plan gratuito da 0). Se sube sin ilustracion.")
                return None
            continue
    return None
