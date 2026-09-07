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
    # Añadido el 05/09/2026 a peticion de Edicion. El sitio ya tenia el formato
    # 'articulo' y el motor era el unico que no sabia escribirlo: cuando alguien
    # pedia "un articulo", nota.py avisaba de que no existia y entregaba una
    # noticia. Es la pieza intermedia: la noticia cuenta el hecho, la opinion
    # defiende una tesis firmada, y el analisis explica el mecanismo sin
    # defender nada.
    "Análisis": "60-analisis.md",
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
        cuerpo = re.sub(r"\n{3,}", "\n\n", cuerpo[:corte]).strip()

    # A veces deja el encabezado solo, sin el texto debajo, y la pieza salia con
    # «SurEconomics:» dos veces seguidas: la linea huerfana del cuerpo y la de
    # verdad. El corte de arriba no la ve porque compara contra el texto del
    # bloque, y aqui no hay texto que comparar, solo el rotulo.
    cuerpo = re.sub(r"\n*\s*SurEconomics\s*:\s*$", "", cuerpo).strip()
    pieza["cuerpo"] = cuerpo

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
        # SENSIBLE A MAYUSCULAS Y CON LIMITES DE PALABRA, a proposito. El nombre
        # de un medio es un nombre propio, y buscarlo en minusculas acredita
        # cualquier frase que lo contenga: la pieza sobre las sanciones a Cuba
        # decia "el comercio exterior" y el pie salio acreditando a El Comercio,
        # de Peru, con dos enlaces que la pieza jamas uso. "El Comercio" con
        # mayusculas solo aparece cuando de verdad se nombra al diario.
        lineas, acreditadas = [], set()
        for f in paquete.fuentes:
            nombrada = re.search(r"\b" + re.escape(f.institucion) + r"\b",
                                 texto_pieza)
            # Un medio se acredita una vez. Si el paquete trae tres notas del
            # mismo diario, nombrarlo no dice cual de las tres se uso, y colgar
            # las tres es peor que colgar la primera.
            if f.institucion in acreditadas:
                continue
            if nombrada or not lineas:
                acreditadas.add(f.institucion)
                lineas.append(f"{f.institucion}, {paquete.fecha_hecho or 's/f'} · {f.url}")
        pieza["sacado_de"] = "Sacado de: " + "\nSacado de: ".join(lineas)
        # El modelo tambien la escribe aunque el prompt ya no se la pida, y
        # entonces sale dos veces. La linea es del codigo: se limpia del cuerpo.
        # Ojo: no basta con filtrar lineas enteras, porque la pega al final de un
        # parrafo, en la misma linea. Hay que quitarla este donde este.
        for campo in ("cuerpo", "bloque_sureconomics"):
            texto = pieza.get(campo) or ""
            # La bibliografia academica es el mismo problema con otra ropa. En
            # el articulo sobre el PIB el modelo cerro con un bloque
            # «Referencias» en formato APA que repetia, enlace incluido, la
            # linea que el codigo ya escribe debajo. Un medio no publica
            # bibliografia: publica de donde lo saco, una vez.
            # El «#» del principio hace falta: en el articulo sobre las licencias
            # de la OFAC el modelo escribio «### Referencias», con cabecera de
            # markdown, y la regla sin almohadillas no lo reconocio.
            texto = re.sub(r"\n\s*#*\s*(Referencias|Bibliograf[ií]a|Fuentes"
                           r"|Referencias bibliogr[aá]ficas)\s*:?\s*\n.*$",
                           "", texto, flags=re.IGNORECASE | re.DOTALL)
            limpio = re.sub(r"\s*Sacado de:.*?(?=\n|$)", "", texto,
                            flags=re.IGNORECASE)
            pieza[campo] = re.sub(r"\n{3,}", "\n\n", limpio).strip()

        # LOS CREDITOS SE COMPRUEBAN CONTRA EL TEXTO FINAL, no contra el que
        # habia al armarlos. Es un problema de orden: la linea «Sacado de» se
        # arma arriba y la limpieza del cuerpo ocurre despues, asi que si el
        # modelo nombraba a un medio dentro de un bloque que luego se borra -una
        # bibliografia, por ejemplo- el credito sobrevivia al nombre. Paso el
        # 28/08/2026: el articulo de las licencias acreditaba al Banco Central de
        # Venezuela, que no aparecia en ninguna parte del texto publicado.
        # Acreditar una fuente que la pieza no usa es tan falso como no acreditar
        # la que si usa.
        final = " ".join(str(pieza.get(c) or "") for c in
                         ("titulo", "cuerpo", "bloque_sureconomics"))
        vivas = []
        for i, linea in enumerate(pieza["sacado_de"].split("\nSacado de: ")):
            nombre = linea.replace("Sacado de: ", "").split(",")[0].strip()
            # La primera se conserva siempre: es la fuente de la que sale la
            # pieza, se la nombre o no en la prosa.
            if i == 0 or re.search(r"\b" + re.escape(nombre) + r"\b", final):
                vivas.append(linea.replace("Sacado de: ", ""))
        pieza["sacado_de"] = "Sacado de: " + "\nSacado de: ".join(vivas)

    # LA NOTICIA NO LLEVA BLOQUE DE OPINION, y se le quita aqui. El prompt ya no
    # lo pide y el auditor lo bloquea, pero el modelo lo sigue escribiendo por
    # inercia: la primera noticia del 27/08/2026 salio bloqueada por eso. Pedirlo
    # en el prompt no basta; la norma la aplica el codigo.
    if pieza.get("tipo") == "Noticia":
        pieza["bloque_sureconomics"] = ""

    # EL TITULAR VA EN MAYUSCULAS. Norma del medio, decidida el 26/08/2026. Se
    # aplica AQUI y no al maquetar: hasta ahora solo se veia en mayusculas en el
    # correo y en el Word, porque quien lo ponia asi era la funcion que arma el
    # texto legible. Al cargar las piezas en el panel del sitio, el titulo
    # llegaba en minusculas, que es donde de verdad importa.
    if pieza.get("titulo"):
        pieza["titulo"] = pieza["titulo"].strip().upper()

    # Ultimo paso, sobre TODO lo que sale publicado: fuera los guiones largos.
    for campo, valor in list(pieza.items()):
        if isinstance(valor, str):
            pieza[campo] = sin_guiones_largos(valor)
        elif isinstance(valor, list):
            pieza[campo] = [sin_guiones_largos(v) if isinstance(v, str) else v
                            for v in valor]

    return pieza


# NO ESCRIBIR NI USAR LOS GUIONES LARGOS. Ni el largo (—) ni el mediano (–), ni
# en la prosa que escribe el modelo ni en las plantillas que escribe el codigo.
# Es norma de estilo del medio, decidida por el dueño el 25/08/2026.
#
# Se aplica AQUI, con codigo, ademas de pedirse en el prompt. El prompt lo cumple
# "casi siempre" y "casi" no sirve: de las seis piezas del 25 de agosto, las seis
# traian guiones largos sin que nadie los hubiera pedido. La norma la aplica el
# codigo; el prompt solo evita que haya que arreglar tanto despues.
GUIONES_LARGOS = "—–"


def sin_guiones_largos(texto):
    """Cambia los guiones largos por puntuacion normal en español.

    No se borran a secas, porque un guion largo esta haciendo un trabajo en la
    frase y quitarlo deja la prosa coja. Se traduce a lo que corresponde:

        Canadá–EE.UU.        ->  Canadá-EE.UU.      (compuesto: guion corto)
        texto —inciso— mas   ->  texto (inciso) mas (inciso: parentesis)
        texto — mas texto    ->  texto, mas texto   (pausa: coma)
        «— Perecedero · ES»  ->  «Perecedero · ES»  (pie de pieza: sobra)
    """
    if not texto:
        return texto
    clase = "[" + GUIONES_LARGOS + "]"
    fuera = []
    for linea in texto.split("\n"):
        # 1. Pegado entre dos palabras no es una pausa sino un compuesto.
        linea = re.sub(r"(?<=[\w.])" + clase + r"(?=\w)", "-", linea)
        # 2. Al principio de la linea es la firma o el pie: sobra.
        linea = re.sub(r"^\s*" + clase + r"\s*", "", linea)
        # 3. Un inciso entre dos guiones se vuelve parentesis.
        while sum(linea.count(g) for g in GUIONES_LARGOS) >= 2:
            m = re.search(r"\s*" + clase + r"\s*([^" + GUIONES_LARGOS + r"]+?)"
                          r"\s*" + clase + r"\s*", linea)
            if not m:
                break
            linea = linea[:m.start()] + " (" + m.group(1) + ") " + linea[m.end():]
        # 4. El que quede suelto era una pausa: coma.
        linea = re.sub(r"\s*" + clase + r"\s*", ", ", linea)
        # 5. Las costuras que dejan los pasos anteriores.
        linea = re.sub(r"\s+([,.;:)])", r"\1", linea)
        linea = re.sub(r"\(\s+", "(", linea)
        linea = re.sub(r",\s*,", ",", linea)
        linea = re.sub(r"[ \t]{2,}", " ", linea)
        fuera.append(re.sub(r",\s*$", "", linea.rstrip()))
    return "\n".join(fuera)


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
