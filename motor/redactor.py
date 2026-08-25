"""El redactor (A5): la unica pieza del motor que usa IA.

Recibe el paquete de datos y devuelve la pieza escrita. No busca nada, no
calcula nada y no elige fuentes: todo eso ya venia decidido. Su trabajo es
prosa, clasificacion y titulo.

El prompt no vive aqui: se ensambla de archivos que edita quien manda en la voz
(perfiles/ y prompts/). Cambiar la linea editorial no deberia exigir tocar
Python.

Orden de modelos al reves que en el bot: aqui va primero el de mas calidad. Son
pocas llamadas al dia y en un medio la prosa ES el producto; en el bot, que
manda dos resumenes diarios, pesa mas no agotar la cuota.
"""

import re
import pathlib
from datetime import date

from motor import auditor, ia

RAIZ = pathlib.Path(__file__).resolve().parent.parent

PROMPTS = {
    "Noticia": "10-noticia.md",
    "Opinión": "20-opinion.md",
    "Editorial": "30-editorial.md",
    "Investigación": "40-investigacion.md",
    "Educación": "50-educacion.md",
}


def _leer(*partes):
    return (RAIZ.joinpath(*partes)).read_text(encoding="utf-8")


def construir_prompt(tipo, paquete, autor=None, encargo=""):
    """Ensambla perfil + prompt base + prompt del tipo + paquete de datos."""
    if tipo not in PROMPTS:
        raise ValueError(f"tipo no reconocido: {tipo}. Use: {', '.join(PROMPTS)}")

    partes = [
        "=== PERFIL EDITORIAL DEL MEDIO ===",
        _leer("perfiles", "medio-web.md"),
        "=== REGLAS COMUNES ===",
        _leer("prompts", "00-base.md"),
        f"=== REGLAS DEL TIPO: {tipo} ===",
        _leer("prompts", PROMPTS[tipo]),
        "=== PAQUETE DE DATOS ===",
        paquete.a_json(),
    ]
    if paquete.advertencias:
        partes += ["=== ADVERTENCIAS (obligatorias, no son sugerencias) ===",
                   "\n".join(f"- {a}" for a in paquete.advertencias)]
    if autor:
        partes += ["=== AUTOR ===", autor]
    if encargo:
        partes += ["=== ENCARGO DE EDICIÓN ===", encargo]
    # Sin esto el modelo se inventa la fecha con la del final de su entrenamiento.
    # En la primera prueba fecho una pieza en mayo de 2024.
    partes += ["=== FECHA ===",
               f"Hoy es {date.today().isoformat()}. Ese es el valor de "
               f"'fecha_publicacion'. No uses ninguna otra."]
    partes += ["=== PAÍSES ADMITIDOS EN LA ETIQUETA 'pais' ===",
               ", ".join(sorted(auditor.PAISES_VALIDOS)) +
               ". 'Mundo' NO es un pais: si la pieza es global, usa el pais "
               "principal del que salen los datos."]
    partes += ["=== TU RESPUESTA ===",
               "Devuelve solo el objeto JSON. Nada antes, nada despues."]
    return "\n\n".join(partes)


def redactar(tipo, paquete, autor=None, encargo="", critica=None):
    """Devuelve la pieza como diccionario, o None si la IA no responde.

    Si se le pasa 'critica', esta es la SEGUNDA pasada: reescribe aplicando lo
    que señalo el economista. Es el mismo redactor, no otro: dos agentes
    distintos escribirian con voces distintas, que es lo que no queremos.

    Degradacion suave: si ningun modelo contesta, no hay pieza. Nunca se inventa
    una: el hecho y sus cifras siguen en el paquete y se puede escribir a mano.
    """
    problemas = paquete.validar()
    if problemas:
        # Redactar sobre un paquete roto es gastar cuota para producir algo que
        # el auditor va a bloquear igual.
        print("[error] el paquete no es valido, no se redacta:")
        for p in problemas:
            print(f"   x {p}")
        return None

    prompt = construir_prompt(tipo, paquete, autor, encargo)
    if critica:
        prompt += "\n\n" + _bloque_critica(critica)
    pieza = ia.pedir_json(prompt, etiqueta="redactor")
    if pieza is None:
        return None

    pieza.setdefault("tipo", tipo)

    # El modelo escribe el bloque SurEconomics al final del cuerpo Y ademas en su
    # propio campo, asi que salia dos veces seguidas. Se quita del cuerpo: el
    # campo es el que manda, porque es el que el auditor y el panel tratan como
    # bloque de opinion separado del hecho.
    bloque = (pieza.get("bloque_sureconomics") or "").strip()
    cuerpo = (pieza.get("cuerpo") or "").strip()
    if bloque and len(bloque) > 40 and bloque[:60] in cuerpo:
        corte = cuerpo.index(bloque[:60])
        pieza["cuerpo"] = re.sub(r"\n{3,}", "\n\n", cuerpo[:corte]).strip()

    # La linea de atribucion la escribe el codigo, no el modelo. Es puramente
    # mecanica -medio, fecha y enlace ya estan en el paquete- y pedirsela a la IA
    # solo agrega una forma de fallar: en la primera prueba se la salto pese a
    # estar pedida en el prompt, en el tipo y en las advertencias.
    if any("ATRIBUCIÓN OBLIGATORIA" in a for a in paquete.advertencias):
        # Se acreditan TODAS las fuentes que la pieza nombra, no solo la primera.
        # Una nota con tres medios citados en el cuerpo y un solo "Sacado de" al
        # pie deja sin credito a dos de ellos.
        texto_pieza = " ".join(str(pieza.get(c) or "") for c in
                               ("titulo", "cuerpo", "bloque_sureconomics"))
        lineas = []
        for f in paquete.fuentes:
            if f.institucion.lower() in texto_pieza.lower() or not lineas:
                lineas.append(f"{f.institucion}, {paquete.fecha_hecho or 's/f'} — {f.url}")
        pieza["sacado_de"] = "Sacado de: " + "\nSacado de: ".join(lineas)
        # El modelo tambien la escribe aunque el prompt ya no se la pida, y
        # entonces sale dos veces. La linea es del codigo: se limpia del cuerpo.
        # Ojo: no basta con filtrar lineas enteras, porque la pega al final de un
        # parrafo, en la misma linea. Hay que quitarla este donde este.
        for campo in ("cuerpo", "bloque_sureconomics"):
            texto = pieza.get(campo) or ""
            limpio = re.sub(r"\s*Sacado de:.*?(?=\n|$)", "", texto,
                            flags=re.IGNORECASE)
            pieza[campo] = re.sub(r"\n{3,}", "\n\n", limpio).strip()

    return pieza


def _bloque_critica(critica):
    """Convierte la critica del economista en instrucciones para reescribir."""
    lineas = ["=== REVISIÓN DEL ECONOMISTA DE LA REDACCIÓN ===",
              "Tu borrador anterior fue revisado. Reescribe la pieza completa "
              "aplicando estas observaciones. Mantén lo que estaba bien.",
              ""]
    for o in critica.get("observaciones", []) or []:
        lineas.append(f"- [{o.get('gravedad', 'media')}] {o.get('que', '')}")
        if o.get("por_que"):
            lineas.append(f"  Por qué: {o['por_que']}")
        if o.get("sugerencia"):
            lineas.append(f"  Qué hacer: {o['sugerencia']}")
    for s_ in critica.get("sobra", []) or []:
        lineas.append(f"- QUITA: {s_}")
    for f_ in critica.get("falta", []) or []:
        lineas.append(f"- FALTA: {f_}. Si el paquete no lo tiene, decláralo en "
                      f"'faltantes' y NO lo inventes.")
    lineas += ["",
               "La regla dura sigue en pie: ninguna cifra que no esté en el "
               "paquete, aunque el economista parezca sugerirla."]
    return "\n".join(lineas)
