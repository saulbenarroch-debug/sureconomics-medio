"""El economista (A13): decide el contexto y critica el razonamiento.

Dos tareas en dos momentos distintos del proceso, y el orden importa:

    pertinencia()  ANTES de redactar — que contexto pide esta noticia
    criticar()     DESPUES del borrador — se sostiene lo que dice

La pertinencia tiene que ir antes porque el redactor solo puede usar lo que hay
en el paquete: si el contexto se elige mal, revisarlo despues no arregla nada,
hay que rehacer la pieza entera.

Este agente NO aporta cifras: no tiene el paquete verificado y no puede
comprobar nada. Y aunque se le escapara una, el auditor la bloquea igual, porque
sigue estando al final de la cadena. Meter un agente de opinion no debilita el
KPI: la arquitectura lo absorbe.
"""

import pathlib

from motor import biblioteca, ia

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _perfil():
    return (RAIZ / "perfiles" / "economista.md").read_text(encoding="utf-8")


def pertinencia(hecho, resumen, pais_sugerido=""):
    """Que contexto pide esta noticia. Devuelve dict o None.

    Ve la BIBLIOTECA COMPLETA, no una sola fuente: si solo conociera el Banco
    Mundial siempre pediria eso, y tener mas fuentes no serviria de nada.

    Salida: {"peticiones": ["dam:Venezuela"], "razon": "...",
             "faltan": ["..."], "sin_contexto": false}
    """
    prompt = "\n\n".join([
        "=== QUIÉN ERES ===", _perfil(),
        "=== TAREA ===",
        "Estás en la tarea 1: pertinencia. Todavía no hay pieza escrita.",
        "=== LA NOTICIA ===",
        f"Hecho: {hecho}",
        f"Resumen de la nota: {resumen or '(no hay más que el titular)'}",
        f"País principal sugerido: {pais_sugerido or 'dedúcelo del hecho'}",
        "=== BIBLIOTECA DE FUENTES DISPONIBLES ===",
        biblioteca.catalogo_texto(),
        "Fíjate en la CADENCIA de cada fuente antes de pedirla: una serie anual "
        "con dos años de retraso no contextualiza una noticia de esta semana. Y "
        "fíjate en la COBERTURA: pedir un país que la fuente no cubre no "
        "devuelve nada.",
        "=== TU RESPUESTA ===",
        'Solo este JSON: {"sin_contexto": false, "peticiones": ["dam:Venezuela"], '
        '"razon": "una frase", "faltan": ["qué dato haría falta y no está en la '
        'biblioteca"]}. Como mucho tres peticiones: más es relleno. Si la noticia '
        'se cuenta sola, responde sin_contexto=true con la lista vacía y di por qué. '
        'Esa tercera respuesta es legítima y se usa a menudo.',
    ])
    return ia.pedir_json(prompt, etiqueta="economista/pertinencia", temperatura=0.2)


def criticar(pieza, paquete):
    """Revisa el razonamiento del borrador. Devuelve dict o None.

    Salida: {"veredicto": "publicable"|"revisar",
             "observaciones": [{"gravedad","que","por_que","sugerencia"}],
             "sobra": [...], "falta": [...]}
    """
    partes_pieza = "\n".join([
        f"TIPO: {pieza.get('tipo')}",
        f"TITULAR: {pieza.get('titulo')}",
        f"CUERPO:\n{pieza.get('cuerpo')}",
        f"BLOQUE SurEconomics:\n{pieza.get('bloque_sureconomics') or '(vacío)'}",
    ])
    prompt = "\n\n".join([
        "=== QUIÉN ERES ===", _perfil(),
        "=== TAREA ===",
        "Estás en la tarea 2: crítica de un borrador.",
        "=== LA PIEZA ===", partes_pieza,
        "=== EL PAQUETE DE DATOS DEL QUE SALIÓ ===",
        paquete.a_json(),
        "Las cifras con rol='hecho' las publicó el medio citado; las de "
        "rol='contexto' las aporta SurEconomics.",
        "=== TU RESPUESTA ===",
        'Solo este JSON: {"veredicto": "publicable" o "revisar", '
        '"observaciones": [{"gravedad": "alta|media|baja", "que": "", '
        '"por_que": "", "sugerencia": ""}], "sobra": ["contexto que no viene al '
        'caso"], "falta": ["lo que el lector necesitaba y no está"]}. '
        'Máximo cinco observaciones, las que de verdad importen. Si la pieza '
        'está bien, veredicto "publicable" y lista vacía: no inventes objeciones.',
    ])
    return ia.pedir_json(prompt, etiqueta="economista/crítica", temperatura=0.3)


def resumen_critica(critica):
    """La critica en texto, para el log y para que la vea el editor."""
    if not critica:
        return "(el economista no respondió)"
    lineas = [f"Veredicto: {critica.get('veredicto', '?')}"]
    for o in critica.get("observaciones", []) or []:
        lineas.append(f"  [{o.get('gravedad', '?')}] {o.get('que', '')}")
        if o.get("por_que"):
            lineas.append(f"      porque: {o['por_que']}")
        if o.get("sugerencia"):
            lineas.append(f"      hacer:  {o['sugerencia']}")
    for s in critica.get("sobra", []) or []:
        lineas.append(f"  [sobra] {s}")
    for f in critica.get("falta", []) or []:
        lineas.append(f"  [falta] {f}")
    return "\n".join(lineas)
