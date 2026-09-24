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


# LAS CLAVES DE GEMINI, EN ORDEN DE USO. La cuota de Gemini va POR PROYECTO, no
# por clave: dos claves del mismo proyecto comparten el mismo cubo y esto no
# serviria de nada. Tienen que ser de proyectos distintos -en la practica, de
# cuentas distintas- o el embudo es decorativo.
#
# LA PRINCIPAL ES LA INSTITUCIONAL, Y NO ES UN CAPRICHO. El medio es un producto
# de la empresa: si la clave que lo sostiene cuelga de la cuenta personal de
# alguien, el dia que esa cuenta cambie se cae la produccion con ella. La
# personal va de reserva, que es el papel que aguanta un cambio sin avisar.
CLAVES_GEMINI = (("principal", "GEMINI_API_KEY"),
                 ("reserva", "GEMINI_API_KEY_RESERVA"))

# Errores que dicen "esta clave no vale" y no "el modelo fallo". Con una sola
# clave daba igual -se moria igual-, pero con dos hay que distinguirlos: si la
# principal esta mal escrita, la reserva tiene que poder salvar la corrida en
# vez de heredar el error.
_CLAVE_MALA = ("API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED",
               "403", "400 INVALID_ARGUMENT")

# Fallos pasajeros: merecen reintento en el MISMO modelo antes de pasar de largo.
# Los de red entraron el 17/09/2026: "Server disconnected without sending a
# response" tumbo una peticion que la reserva podria haber salvado, y encima
# reintentar en el sitio suele bastar, que es mas barato que cambiar de cuenta.
_TEMPORAL = ("503", "500", "UNAVAILABLE", "overloaded",
             "Server disconnected", "Connection", "connection",
             "timed out", "timeout", "RemoteProtocol", "Broken pipe")


# UNA SEGUNDA VUELTA AL EMBUDO CUANDO LO QUE FALLO FUE SATURACION, NO CUOTA.
#
# El 24/09/2026 a las 13:56 UTC una /nota murio con las dos cuentas: flash de la
# principal sin cuota y los otros tres modelos con 503 «This model is currently
# experiencing high demand». La reserva TENIA cuota; lo que estaba era Google
# saturado. Con dos intentos y 5 s de espera por modelo el embudo entero se
# rendia en unos 15 s de espera, y un pico de demanda dura mas que eso: la
# corrida de un minuto antes habia salido bien.
#
# Asi que si al terminar la vuelta hubo algun fallo pasajero, se espera y se
# vuelve a empezar, saltandose lo que ya se sabe sin cuota (eso no se recupera
# en un minuto). Si todo fue cuota, no se espera: no serviria de nada.
PAUSA_SEGUNDA_RONDA = 45

# Y SOLO SE ESPERA UNA VEZ POR PROCESO SI LA SEGUNDA VUELTA TAMBIEN FALLA. Una
# tanda hace unas treinta llamadas: si Google esta caido de verdad, esperar 45 s
# en cada una se comeria el limite de 60 minutos del job y se perderian tambien
# las piezas que si habrian salido al volver el servicio. Con la segunda vuelta
# ya fallida una vez, las llamadas siguientes dan una sola vuelta, como antes.
_segunda_ronda_fallida = False


def claves_gemini():
    """Las claves configuradas, en orden. Lista de (nombre, clave)."""
    return [(nombre, os.environ.get(var, "").strip())
            for nombre, var in CLAVES_GEMINI
            if os.environ.get(var, "").strip()]


def _gemini(prompt, temperatura, reintentos=2, imagen=None):
    """imagen: (bytes, mime) para leer una captura. Ver pedir_json()."""
    from google import genai
    from google.genai import types

    claves = claves_gemini()
    if not claves:
        raise RuntimeError("falta GEMINI_API_KEY")
    contenido = prompt
    if imagen:
        datos, mime = imagen
        contenido = [types.Part.from_bytes(data=datos, mime_type=mime), prompt]

    global _segunda_ronda_fallida
    ultimo = None
    # Lo que ya se sabe que no sirve no se vuelve a probar en la segunda vuelta:
    # una cuota agotada no vuelve en 45 s y una clave mala tampoco.
    agotados, inservibles = set(), set()
    rondas = 1 if _segunda_ronda_fallida else 2
    for ronda in range(1, rondas + 1):
        hubo_pasajero = False
        if ronda == 2:
            print("[aviso] Gemini saturado (no es cuota); espero %ss y lo "
                  "intento otra vez" % PAUSA_SEGUNDA_RONDA)
            time.sleep(PAUSA_SEGUNDA_RONDA)
        for nombre, clave in claves:
            if nombre in inservibles:
                continue
            cliente = genai.Client(api_key=clave)
            # El nombre de la clave solo se pone en la etiqueta cuando hay mas
            # de una: con una sola, "gemini-3.5-flash (principal)" es ruido.
            sello = ("%s (%s)" % ("%s", nombre)) if len(claves) > 1 else "%s"
            for modelo in MODELOS_GEMINI:
                if nombre in inservibles:
                    break
                if (nombre, modelo) in agotados:
                    continue
                espera = 5
                for intento in range(1, reintentos + 1):
                    try:
                        r = cliente.models.generate_content(
                            model=modelo, contents=contenido,
                            config={"response_mime_type": "application/json",
                                    "temperature": temperatura})
                        return r.text, sello % modelo
                    except Exception as exc:  # noqa: BLE001
                        msg, ultimo = str(exc), exc
                        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                            print("[aviso] %s: cuota agotada, paso al siguiente"
                                  % (sello % modelo))
                            agotados.add((nombre, modelo))
                            break
                        if any(s in msg for s in _CLAVE_MALA):
                            # No se prueban los demas modelos con una clave que
                            # no sirve: fallarian todos igual.
                            print("[aviso] la clave '%s' no vale (%s); paso a la "
                                  "siguiente cuenta" % (nombre, msg[:60]))
                            inservibles.add(nombre)
                            break
                        if any(s in msg for s in _TEMPORAL):
                            if intento < reintentos:
                                print("[aviso] %s caido, reintento en %ss"
                                      % (sello % modelo, espera))
                                time.sleep(espera)
                                espera *= 2
                                continue
                            hubo_pasajero = True
                            break
                        # CUALQUIER OTRO ERROR TAMBIEN PASA AL SIGUIENTE, Y
                        # ESTO ANTES ERA UN 'raise' QUE SE CARGABA EL EMBUDO.
                        #
                        # El 17/09/2026 la principal contesto "Server
                        # disconnected without sending a response", un corte de
                        # red que no era ninguno de los casos de arriba. El
                        # raise aborto la cadena antes de tocar la reserva, que
                        # estaba intacta: se perdio la pieza teniendo una
                        # cuenta entera sin usar.
                        #
                        # El sentido de una cadena de respaldo es SOBREVIVIR a
                        # lo que no se previo. El error no se pierde: queda en
                        # 'ultimo' y se lanza al final si no responde nadie.
                        # No cuenta como pasajero: sin saber que es, esperar
                        # 45 s por el seria adivinar.
                        print("[aviso] %s fallo con algo no previsto (%s); sigo "
                              "con el siguiente" % (sello % modelo, msg[:90]))
                        break
        if not hubo_pasajero:
            # Todo lo que fallo fue cuota, clave o algo desconocido: esperar no
            # cambia nada, asi que no se hace esperar a nadie.
            break
    if rondas == 2 and hubo_pasajero:
        _segunda_ronda_fallida = True
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
