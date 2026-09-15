"""Llamada a los modelos de lenguaje, con cadena de respaldo.

Extraido de redactor.py cuando aparecio el segundo agente que necesita IA (el
economista). Dos copias de la logica de reintentos y fallback se desincronizan a
la primera correccion.

Orden al reves que en el bot de Telegram: aqui va primero el modelo de mas
calidad. Son pocas llamadas al dia y en un medio la prosa ES el producto; en el
bot, que manda dos resumenes diarios, pesa mas no agotar la cuota.
"""

import json
import os
import time

# Los 2.5 dan 404 en proyectos nuevos ("no longer available to new users").
# Se descubrio al migrar la clave a la cuenta de la empresa (24/08/2026).
MODELOS_GEMINI = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
# Groq retiro la familia llama-3.3 (404 "does not exist"). El respaldo
# llevaba tiempo roto sin que se notara, porque solo se activa cuando
# Gemini falla. Comprobado el 24/08/2026 desde Actions.
MODELO_GROQ = "openai/gpt-oss-120b"


def _gemini(prompt, temperatura, reintentos=2, imagen=None):
    """imagen: (bytes, mime) para leer una captura. Ver pedir_json()."""
    from google import genai
    from google.genai import types

    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise RuntimeError("falta GEMINI_API_KEY")
    cliente = genai.Client(api_key=clave)
    contenido = prompt
    if imagen:
        datos, mime = imagen
        contenido = [types.Part.from_bytes(data=datos, mime_type=mime), prompt]
    ultimo = None
    for modelo in MODELOS_GEMINI:
        espera = 5
        for intento in range(1, reintentos + 1):
            try:
                r = cliente.models.generate_content(
                    model=modelo, contents=contenido,
                    config={"response_mime_type": "application/json",
                            "temperature": temperatura})
                return r.text, modelo
            except Exception as exc:  # noqa: BLE001
                msg, ultimo = str(exc), exc
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    print(f"[aviso] {modelo}: cuota agotada, paso al siguiente")
                    break
                if any(s in msg for s in ("503", "500", "UNAVAILABLE", "overloaded")):
                    if intento < reintentos:
                        print(f"[aviso] {modelo} caido, reintento en {espera}s")
                        time.sleep(espera)
                        espera *= 2
                        continue
                    break
                raise
    raise ultimo


def _groq(prompt, temperatura):
    """Respaldo. NO usa response_format a proposito.

    Los modelos actuales de Groq devuelven 400 con {"type": "json_object"}. En
    vez de depender de una funcion que el respaldo puede no tener, se pide el
    JSON en el propio prompt y se parsea: pedir_json ya sabe desenvolver una
    respuesta metida en ```json. Un plan B tiene que exigir lo minimo posible.
    """
    import requests

    clave = os.environ.get("GROQ_API_KEY", "").strip()
    if not clave:
        raise RuntimeError("falta GROQ_API_KEY")
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {clave}",
                 "Content-Type": "application/json"},
        json={"model": MODELO_GROQ,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": temperatura},
        timeout=90)
    if not r.ok:
        # EL CODIGO SOLO NO DICE NADA, Y ESO COSTO UN DIA ENTERO. El 14/09/2026
        # Gemini se quedo sin credito, Groq contesto 413 y en el log solo puso
        # "Groq respondio 413": no se sabia si era el tamaño, la cuota por
        # minuto o la clave, que son tres arreglos distintos. Medido despues
        # desde Actions: 413 es "Request too large" -limite POR PETICION- y 429
        # es la cuota por minuto. El mensaje de Groq lo dice con esas palabras,
        # asi que se pasa tal cual.
        #
        # La clave va en la cabecera y no en la URL, pero el cuerpo puede
        # reflejar parte de la peticion: se recorta antes de imprimirlo.
        try:
            detalle = (r.json().get("error") or {}).get("message", "")
        except Exception:  # noqa: BLE001
            detalle = r.text or ""
        raise RuntimeError(
            "Groq respondio %s: %s" % (r.status_code, str(detalle)[:200]))
    return r.json()["choices"][0]["message"]["content"], MODELO_GROQ


def pedir_json(prompt, etiqueta="ia", temperatura=0.4, imagen=None):
    """Devuelve el objeto que responda el modelo, o None si nadie contesta.

    Degradacion suave: si ningun modelo responde, no hay resultado. Nunca se
    devuelve algo inventado para rellenar.

    imagen es (bytes, mime) y sirve para leer una captura de pantalla. OJO: el
    respaldo de Groq es un modelo de TEXTO y no puede ver imagenes, asi que con
    imagen no hay respaldo. Se dice y se devuelve None en vez de mandarle el
    prompt a ciegas, que es como se acaba describiendo una foto que nadie miro.
    """
    try:
        crudo, modelo = _gemini(prompt, temperatura, imagen=imagen)
    except Exception as exc:  # noqa: BLE001
        if imagen:
            print(f"[error] Gemini no disponible ({str(exc)[:220]}) y Groq no ve "
                  "imagenes. Sin lectura de la captura.")
            return None
        print(f"[aviso] Gemini no disponible ({str(exc)[:220]}); uso Groq")
        try:
            crudo, modelo = _groq(prompt, temperatura)
        except Exception as exc2:  # noqa: BLE001
            print(f"[error] tampoco Groq ({str(exc2)[:220]}).")
            return None
    print(f"[{etiqueta}] {modelo}")

    try:
        return json.loads(crudo)
    except json.JSONDecodeError:
        # A veces el modelo envuelve el JSON en ```json ... ```
        limpio = (crudo.strip().removeprefix("```json").removeprefix("```")
                  .removesuffix("```"))
        try:
            return json.loads(limpio)
        except json.JSONDecodeError:
            print(f"[error] {etiqueta}: la IA no devolvio JSON valido.")
            return None
