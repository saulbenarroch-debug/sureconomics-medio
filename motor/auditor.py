"""El auditor (A8): compara la pieza redactada contra el paquete de datos.

Es codigo determinista y NO usa IA, a proposito. Un modelo revisando a otro
modelo no garantiza nada: comparte sus mismos puntos ciegos y ademas falla de
forma distinta cada vez. Aqui, la misma pieza con el mismo paquete da siempre el
mismo veredicto, y cualquiera puede reproducirlo.

Lo que audita se divide en dos, y la diferencia importa:

  BLOQUEO — comprobable sin opinar. Si falla, la pieza no llega al editor.
  AVISO   — necesita criterio humano. Se le marca al editor, no se bloquea.

No se inventan bloqueos sobre cosas que exigen juicio: un auditor que da falsos
positivos se desactiva a la semana, y entonces no audita nada.
"""

import re
import unicodedata
from dataclasses import dataclass

# Numero escrito con CUALQUIERA de las dos normas, la española (1.234.567,89) o
# la inglesa (1,234,567.89), o entero suelto.
#
# La inglesa hace falta porque con esto se lee TAMBIEN EL EXPEDIENTE, y el
# expediente copia la cifra tal como la publico el medio: El Economista escribe
# «2.61%» y aqui se troceaba en un 2 y un 61 sueltos, con lo que el 2,61 legitimo
# de la pieza salia como cifra inventada. Que la pieza no pueda escribir punto
# decimal es otra cosa y se comprueba aparte, en DECIMAL_INGLES.
#
# El orden no se puede alterar: los millares van primero porque «1.500» es mil
# quinientos en español.
_NUM_ES = (
    r"\d{1,3}(?:\.\d{3})+(?:,\d+)?"   # 1.234.567,89  norma española
    r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # 1,234,567.89  norma inglesa
    r"|\d+,\d+"                       # 2,61          decimal español
    r"|\d+\.\d+"                      # 2.61          decimal ingles
    r"|\d+")
NUMERO = re.compile(_NUM_ES)
# Decimal a la inglesa: punto seguido de 1 o 2 digitos. Con 3 seria un millar.
DECIMAL_INGLES = re.compile(r"\b\d+\.\d{1,2}\b")
URL = re.compile(r"https?://[^\s)>\]\"']+")
# Comillas de todo tipo: el modelo mezcla rectas, tipograficas y angulares.
ENTRECOMILLADO = re.compile("[\"«“]([^\"»”]{10,300})[\"»”]")

# Valores validos del eje 'pais'. Latinoamerica completa mas los paises que el
# medio cubre por su peso economico. Se amplia cuando Edicion lo pida; lo que no
# se admite es texto libre, porque el corte por pais es como se mide el medio.
PAISES_VALIDOS = {
    "Argentina", "Bolivia", "Brasil", "Chile", "Colombia", "Costa Rica", "Cuba",
    "República Dominicana", "Ecuador", "El Salvador", "Guatemala", "Haití",
    "Honduras", "México", "Nicaragua", "Panamá", "Paraguay", "Perú", "Uruguay",
    "Venezuela", "Latam",
    "EE. UU.", "Canadá", "China", "Japón", "India", "Reino Unido", "Alemania",
    "Francia", "Italia", "España", "Rusia", "Unión Europea", "Sudáfrica",
    "Australia", "Suiza", "Corea del Sur",
    # Añadidos el 24/08/2026: sin Irán en la lista, una pieza sobre
    # sanciones a Teherán quedó clasificada con país "EE. UU." y
    # subregión "Asia". Un país ausente no da error: da una
    # clasificación falsa, que es peor que un hueco.
    "Irán", "Israel", "Arabia Saudita", "Turquía", "Egipto", "Nigeria",
    "Emiratos Árabes Unidos", "Catar", "Indonesia", "Vietnam",
    "Países Bajos", "Bélgica", "Suecia", "Noruega", "Polonia",
    "Portugal", "Ucrania", "Sudán", "Etiopía", "Kenia", "Marruecos",
    "Nueva Zelanda", "Global",
}

TAXONOMIA = {
    "region": {"Latinoamérica", "Mundo"},
    "subregion": {"Centroamérica", "Norteamérica", "Región Andina", "Caribe",
                  "Cono Sur", "América Latina", "América", "Europa", "Asia",
                  "África", "Oceanía"},
    "topico": {"Economía", "Finanzas", "Política"},
    "vigencia": {"Perecedero", "Permanente"},
    "idioma": {"ES", "EN"},
}

# Frases donde el modelo nombra la instruccion que recibio en vez de cumplirla.
# Un medio no anuncia su linea editorial, la ejerce; y "para el lector normal" es
# literalmente el prompt asomandose en la prosa. Aparecio tres veces seguidas en
# las pruebas, asi que se bloquea en vez de confiar en que el prompt lo evite.
FUGA_DE_PROMPT = re.compile(
    r"desde nuestra perspectiva progresista|"
    r"(nuestra|esta|la) (perspectiva|l[ií]nea|visi[oó]n) editorial|"
    r"l[ií]nea editorial (progresista )?(de este medio|del medio)|"
    r"para (el lector|una persona|el p[uú]blico|el ciudadano|la gente) "
    r"(normal|com[uú]n|de a pie|corriente)|"
    r"como medio progresista|este medio progresista|"
    # La maquinaria por su nombre. La pieza del ranking de PIB cerraba diciendo
    # que «la falta de datos desagregados EN ESTE PAQUETE limita una lectura mas
    # fina»: el lector no sabe que existe un paquete, y enterarse de que hay uno
    # es enterarse de que la nota se escribio con lo que habia a mano.
    # OJO CON «PAQUETE» A SECAS. La primera version de esta regla bloqueaba
    # cualquier «el paquete», y en un medio de economia eso es vocabulario
    # corriente: paquete fiscal, paquete de medidas, paquete de estimulo. La
    # nota de la OFAC decia «el paquete de licencias» y quedo bloqueada por
    # hablar bien el castellano. Solo es fuga cuando nombra NUESTRO paquete.
    r"(en |de |del )?(este|el) paquete de datos|"
    r"el paquete (de datos )?no (trae|tiene|incluye)|"
    r"(los )?datos (disponibles |que manejamos )?no permiten|"
    r"la (falta|ausencia) de datos [^.]{0,40}(limita|impide)", re.IGNORECASE)

# Siglas mal escritas que ya aparecieron publicadas. La izquierda es el error.
# Se agregan a medida que edicion detecte otras; cada una es un error que no
# vuelve a ocurrir.
SIGLAS_MAL = {"MFI": "FMI", "FMI Internacional": "FMI", "BCV Central": "BCV"}

# El instituto de estadistica de cada pais. No se puede meter en SIGLAS_MAL
# porque ninguna de estas siglas esta mal en si misma: INEC es correcto para
# Ecuador y equivocado para Argentina, que tiene INDEC.
#
# Salio de una pieza PUBLICADA el 28/08/2026: el cuerpo decia «el Instituto
# Nacional de Estadistica y Censos (INEC)» hablando de la inflacion argentina,
# mientras su propio bloque de fuentes enlazaba al INDEC. Nombrar mal al
# organismo que produce la cifra es un error de fondo, no una errata: pone en
# duda que se haya mirado la fuente.
#
# Va como AVISO y no como bloqueo: una pieza sobre Argentina puede citar al DANE
# de Colombia para comparar, y eso es correcto. Lo que se marca es la sospecha.
INSTITUTOS = {
    "INDEC": "Argentina", "INEC": "Ecuador y Costa Rica", "INEI": "Perú",
    "DANE": "Colombia", "INEGI": "México", "IBGE": "Brasil",
    "INE": "Chile, España y Venezuela", "DGEEC": "Paraguay",
    "ONEI": "Cuba", "BCU": "Uruguay",
}


@dataclass
class Hallazgo:
    nivel: str      # 'bloqueo' o 'aviso'
    codigo: str
    mensaje: str

    def __str__(self):
        marca = "X" if self.nivel == "bloqueo" else "!"
        return f"  {marca} [{self.codigo}] {self.mensaje}"


def _texto_de(pieza):
    """Todo el texto publicable de la pieza, para buscar cifras y enlaces."""
    return "\n".join(str(pieza.get(c, "") or "") for c in
                     ("titulo", "cuerpo", "bloque_sureconomics"))


def _es_anio(token):
    """Un 4 digitos entre 1900 y 2100 suelto es casi siempre un año.

    Heuristica deliberada: sin ella el auditor bloquearia toda pieza que diga
    'en 2016'. El riesgo asumido es que una cifra real de ese rango (por ejemplo
    '2.000 empleos' escrito sin punto) pase sin verificar. Se prefiere ese falso
    negativo raro a un falso positivo constante, que desactivaria el auditor.
    """
    return token.isdigit() and 1900 <= int(token) <= 2100


# Cuanto puede alejarse un redondeo del dato real. Al 1 %, 219,9 -> 220 pasa
# (se desvia 0,05 %) y 219,9 -> 200 no pasa (se desvia 9 %). Esa segunda no es un
# redondeo sino una cifra redonda de titular, y es decision editorial, no tecnica.
TOLERANCIA_REDONDEO = 0.01


def _a_numero(token):
    """Convierte '1.234.567,89' (norma española) a float, o None."""
    try:
        return float(token.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _valor_de(token):
    """El numero que representa el token, escrito con la norma que sea.

    EL PROBLEMA. El paquete copia la cifra tal como la escribio el medio, y ahi
    conviven las dos normas: El Economista publica «109,400 millones» y la
    redaccion, que escribe en español, lo pasa a «109.400 millones». Es el mismo
    numero, pero comparados como texto no coinciden y la pieza se bloqueaba por
    cifra inventada. Paso el 03/09/2026 con la nota del relevo en Apple.

    LA REGLA, aplicada igual a los dos lados: un separador seguido de EXACTAMENTE
    tres digitos son millares; cualquier otra cosa es decimal. Si aparecen los
    dos separadores, el ultimo manda. No se devuelven varias lecturas posibles
    porque eso abriria un agujero: con «2.61» valiendo tambien 261, el auditor
    dejaria pasar un 261 que nadie publico. Con una sola lectura, «261» frente a
    «2,61» sigue bloqueandose, que es justo lo que tiene que hacer.
    """
    t = token.strip()
    if not re.fullmatch(r"\d[\d.,]*", t):
        return None
    ultimo = max(t.rfind("."), t.rfind(","))
    if ultimo == -1:
        return float(t)
    cola = t[ultimo + 1:]
    if not cola.isdigit():
        return None
    # Aqui ya no se puede usar _a_numero(): esa funcion asume norma española y
    # convertiria el «2.61» ya normalizado en 261.
    if len(cola) == 3:                             # millares: 109.400
        limpio = re.sub(r"[.,]", "", t)
    else:                                          # decimal: 2,61
        limpio = re.sub(r"[.,]", "", t[:ultimo]) + "." + cola
    try:
        return float(limpio)
    except ValueError:
        return None


def _es(valor):
    """El float otra vez en norma española, para el mensaje al editor."""
    t = f"{valor:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return t.rstrip("0").rstrip(",") if "," in t else t


def _redondeo_de(token, crudos):
    """Si el numero del texto es un redondeo aceptable de alguno del paquete, lo
    devuelve; si no, None.

    Un medio escribe "220 %" donde la fuente dice 219,9 %, y eso es correcto y
    normal. Bloquearlo seria un falso positivo. Lo que no vale es pasar de 219,9
    a 200: ahi ya no se redondea, se cambia la cifra.
    """
    n = _a_numero(token)
    if n is None:
        return None
    mejor = None
    for real in crudos:
        if real == 0:
            continue
        # Se comparan tambien las escalas: la fuente guarda 21645000000 y el
        # texto dice "21.645 millones".
        for escala in (1, 1e3, 1e6, 1e9, 1e12):
            candidato = real / escala
            if candidato == 0:
                continue
            desvio = abs(n - candidato) / abs(candidato)
            if desvio <= TOLERANCIA_REDONDEO and (mejor is None or desvio < mejor[1]):
                mejor = (candidato, desvio)
    return mejor[0] if mejor else None


def _partes_del_nombre(institucion):
    """Trocea el nombre de una fuente en las instituciones que hay que nombrar.

    'J.P. Morgan (EMBIG), vía Banco Central de Reserva del Perú'
        -> ['J.P. Morgan', 'Banco Central de Reserva del Perú']

    Se quitan los parentesis (siglas del indice, aclaraciones) y se parte por
    coma y por 'via': cada trozo es una institucion distinta a la que hay que
    dar credito por separado.
    """
    limpio = re.sub(r"\([^)]*\)", " ", institucion)
    trozos = re.split(r",|\bv[ií]a\b", limpio, flags=re.IGNORECASE)
    return [t.strip(" .-") for t in trozos if len(t.strip(" .-")) > 3]


def auditar(pieza, paquete, encargo=""):
    """Devuelve la lista de hallazgos. Sin bloqueos = puede ir al editor.

    'pieza' es el objeto que devuelve el redactor (A5); 'paquete' es el que
    produjo el extractor (A4). 'encargo' es la instruccion que escribio edicion.

    Las cifras que vengan del encargo se admiten: ahi hay una persona de la
    redaccion aportando un hecho, que es una fuente legitima. Pero se avisa, para
    que quede constancia de que ese dato no salio de ninguna fuente automatica y
    responde quien lo escribio.
    """
    h = []
    texto = _texto_de(pieza)

    # --- 1. Cifras: toda cifra del texto tiene que venir del paquete ---------
    permitidas = set()
    for c in paquete.cifras:
        for token in NUMERO.findall(str(c.valor)):
            permitidas.add(token)
        if c.valor_crudo is not None:
            permitidas.add(str(int(c.valor_crudo)))
    for periodo in {str(c.periodo) for c in paquete.cifras}:
        permitidas.update(NUMERO.findall(periodo))

    # Las mismas cifras, pero como numero, para que la norma con que se escriban
    # deje de importar. Ver _valor_de().
    valores_permitidos = {v for v in (_valor_de(t) for t in permitidas)
                          if v is not None}

    # Los ceros a la izquierda cuentan como el mismo numero. Una fecha guardada
    # como '2026-01-01' se escribe "al 1 de enero de 2026": el texto dice '1' y
    # el paquete tiene '01', y sin esto el auditor bloqueaba una fecha correcta.
    for token in list(permitidas):
        if token.isdigit():
            permitidas.add(token.lstrip("0") or "0")
    # Los numeros que vienen dentro del propio material del paquete tambien son
    # del paquete: el titular y el resumen que publico el diario son la fuente.
    # Sin esto se bloqueaba "48 trimestres" o "12 años", que estaban en la nota
    # citada pero no llevaban una unidad que el extractor supiera reconocer.
    material = [paquete.hecho, paquete.fecha_hecho]
    material += [str(c.get("texto", "")) for c in paquete.citas]
    material += [f.documento for f in paquete.fuentes]
    # La 'nota' de cada cifra tambien es material del paquete: ahi vive el nombre
    # del indicador, y algunos llevan numero dentro ("CDS soberano a 10 años").
    # Sin esto se bloqueaba el 10 de un nombre que venia de la propia fuente.
    material += [c.nota for c in paquete.cifras if c.nota]

    del_encargo = set(NUMERO.findall(encargo)) if encargo else set()
    if del_encargo & set(NUMERO.findall(texto)):
        h.append(Hallazgo("aviso", "cifra-del-encargo",
                          "hay cifras que vienen del encargo de edición, no de una "
                          "fuente automática: responde quien lo escribió"))
    permitidas |= del_encargo
    for trozo in material:
        permitidas.update(NUMERO.findall(str(trozo)))

    # Las cifras hipoteticas ("supongamos un salario de 100 unidades") son
    # legitimas en Educacion, pero solo si la pieza las DECLARA. Asi el editor ve
    # cuales son inventadas a proposito, y el auditor no bloquea de mas: un
    # auditor que da falsas alarmas se desactiva, y entonces no audita nada.
    hipoteticas = set()
    for h_txt in pieza.get("cifras_hipoteticas", []) or []:
        hipoteticas.update(NUMERO.findall(str(h_txt)))

    # Las cifras DE DEFINICION son constantes de manual, no datos: la
    # hiperinflacion se define por subidas mensuales sobre el 50 %, un punto
    # basico es una centesima de punto. El auditor no puede comprobarlas contra
    # el paquete porque no salen de ninguna fuente, salen del diccionario de la
    # disciplina. Se admiten DECLARADAS, para que el editor las vea y confirme
    # que la definicion es correcta.
    definiciones = set()
    for d_txt in pieza.get("cifras_de_definicion", []) or []:
        definiciones.update(NUMERO.findall(str(d_txt)))
    if definiciones:
        h.append(Hallazgo("aviso", "cifra-de-definicion",
                          f"la pieza usa {len(pieza['cifras_de_definicion'])} cifra(s) "
                          f"de definición ({', '.join(pieza['cifras_de_definicion'])}): "
                          f"comprobar que la definición es correcta"))
    if hipoteticas:
        h.append(Hallazgo("aviso", "cifra-hipotetica",
                          f"la pieza declara {len(pieza['cifras_hipoteticas'])} cifra(s) "
                          f"hipotetica(s): comprobar que el texto las presenta como tales"))

    crudos = [c.valor_crudo for c in paquete.cifras if c.valor_crudo is not None]
    redondeos = []
    # LOS NUMEROS DE LOS ENLACES NO SON CIFRAS DE LA PIEZA. Un enlace lleva
    # dentro el titular convertido en direccion, y ahi «4,6 puntos» viaja como
    # «-46-puntos-». El articulo del PIB se bloqueo por un «46» que solo existia
    # dentro de la URL de su propia fuente: nadie lo habia escrito ni lo iba a
    # leer nadie. Se quitan las direcciones antes de buscar cifras.
    texto_sin_enlaces = re.sub(r"https?://\S+", " ", texto)
    # EL CREDITO DE LA FOTO TAMPOCO ES UNA CIFRA. Desde que el credito se anexa
    # al cuerpo -porque el campo del panel no lo guarda y CC BY obliga a
    # atribuir-, la version de la licencia entraba como dato inventado: «CC BY
    # 4.0» aportaba un 4 y un 0. Habria bloqueado toda pieza con foto licenciada.
    texto_sin_enlaces = re.sub(
        r"(?im)^\s*(archivo,\s*\d{4}\s*·\s*)?foto:.*$", " ", texto_sin_enlaces)

    # EL DIA DE UNA FECHA NO ES UNA CIFRA. _es_anio() exime el año, pero el dia
    # quedaba suelto: "el 2 de septiembre de 2026" metia un 2 que no estaba en
    # ningun expediente, y la pieza se bloqueaba. Paso el 02/09/2026 con la nota
    # de la deuda de EE. UU., y habria pasado con CUALQUIER pieza que feche su
    # fuente, que es justo lo que se les pide.
    #
    # Se quita la fecha entera, no solo el dia: si el mes va escrito con letra,
    # el año que le sigue tampoco tiene por que verificarse contra el paquete.
    texto_sin_enlaces = re.sub(
        r"\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|setiembre|octubre|noviembre|diciembre)"
        r"(?:\s+de\s+\d{4})?", " ", texto_sin_enlaces, flags=re.I)

    for token in NUMERO.findall(texto_sin_enlaces):
        if (token in permitidas or token in hipoteticas
                or token in definiciones or _es_anio(token)):
            continue
        if _valor_de(token) in valores_permitidos:
            continue
        original = _redondeo_de(token, crudos)
        if original is not None:
            redondeos.append((token, original))
            continue
        h.append(Hallazgo("bloqueo", "cifra-inventada",
                          f"el numero '{token}' aparece en el texto pero no esta "
                          f"en el paquete de datos"))
    if redondeos:
        detalle = "; ".join(f"'{t}' por {_es(o)}" for t, o in redondeos)
        h.append(Hallazgo("aviso", "redondeo",
                          f"el texto redondea cifras de la fuente ({detalle}). "
                          f"Dentro de la tolerancia, pero conviene mirarlo"))

    # --- 2. Lo declarado tiene que existir ----------------------------------
    claves = {c.clave for c in paquete.cifras}
    for clave in pieza.get("cifras_usadas", []) or []:
        if clave not in claves:
            h.append(Hallazgo("bloqueo", "clave-inexistente",
                              f"la pieza declara la cifra '{clave}', que no esta "
                              f"en el paquete"))

    # LOS GUIONES LARGOS SE COMPRUEBAN, no solo se limpian. La norma la aplicaba
    # unicamente redactor.py al generar, asi que una edicion a mano los volvia a
    # meter sin que saltara nada. Paso el 27/08/2026: al reescribir a mano dos
    # frases de la pieza de la OFAC escribi «cuatro destinos —Rusia, Iran...—» y
    # nada lo detecto, porque el unico que miraba era el paso que ya habia
    # corrido. Una norma que solo se aplica al generar no es una norma.
    for encontrado in set(re.findall(r"[^\s]*[—–][^\s]*", texto)):
        h.append(Hallazgo("bloqueo", "guion-largo",
                          f"'{encontrado[:40]}' lleva guion largo. La norma del "
                          f"medio es puntuacion normal: coma, parentesis o "
                          f"guion corto"))

    # El instituto de estadistica tiene que cuadrar con el pais de la pieza.
    pais_pieza = (pieza.get("etiquetas", {}) or {}).get("pais", "")
    if pais_pieza:
        for sigla, duenos in INSTITUTOS.items():
            if not re.search(r"\b" + sigla + r"\b", texto):
                continue
            if pais_pieza in duenos:
                continue
            # Si ademas nombra al que SI le corresponde, es una comparacion
            # legitima y no se dice nada.
            propio = next((s for s, d in INSTITUTOS.items() if pais_pieza in d), None)
            if propio and re.search(r"\b" + propio + r"\b", texto):
                continue
            h.append(Hallazgo("aviso", "instituto-de-otro-pais",
                              f"la pieza es de {pais_pieza} y nombra al {sigla}, "
                              f"que es el instituto de {duenos}"
                              + (f". El de {pais_pieza} es el {propio}" if propio else "")))

    # --- 3. Formato numerico ------------------------------------------------
    # Se mira el texto SIN enlaces ni credito de foto, por lo mismo que en el
    # apartado anterior: «CC BY 4.0» no es una cifra mal escrita, es el nombre
    # de una licencia, y una direccion web no la lee nadie.
    for mal in DECIMAL_INGLES.findall(texto_sin_enlaces):
        h.append(Hallazgo("bloqueo", "decimal-ingles",
                          f"'{mal}' usa punto decimal. La norma del medio es coma"))
    # La norma del medio pide espacio antes del %. Es mecanico, asi que se
    # comprueba en codigo en vez de confiarlo al prompt.
    sin_espacio = set(re.findall(r"\d+(?:[.,]\d+)?%", texto))
    for mal in sin_espacio:
        h.append(Hallazgo("bloqueo", "porcentaje-sin-espacio",
                          f"'{mal}' va sin espacio antes del %. La norma del "
                          f"medio es '{mal[:-1]} %'"))

    if re.search(r"trillon|trillón|trillones", texto, re.IGNORECASE):
        h.append(Hallazgo("bloqueo", "trillon",
                          "'trillon' traduce mal 'trillion': en español billon = "
                          "10^12 y el error es de un factor de un millon"))
    for mal, bien in SIGLAS_MAL.items():
        if mal != bien and re.search(rf"\b{mal}\b", texto):
            h.append(Hallazgo("bloqueo", "sigla",
                              f"'{mal}' esta mal escrito: es '{bien}'"))

    for fuga in set(FUGA_DE_PROMPT.findall(texto)):
        frase = fuga if isinstance(fuga, str) else " ".join(x for x in fuga if x)
        h.append(Hallazgo("bloqueo", "fuga-de-prompt",
                          f"el texto nombra la instruccion en vez de cumplirla "
                          f"('{frase.strip()}'). El medio ejerce su linea, no la anuncia"))

    # --- 3b. Citas textuales ------------------------------------------------
    # Toda frase entrecomillada tiene que estar en el material del paquete. Es
    # lo mismo que la regla de las cifras, aplicada a las palabras: si no lo dijo
    # la fuente, no lo escribimos.
    #
    # LIMITE CONOCIDO: esto comprueba que la frase existe, NO que se le atribuya
    # a quien la dijo. En una prueba el sistema le adjudico la misma cita a dos
    # personas opuestas en dos corridas. Un resumen de RSS no suele decir quien
    # habla, asi que eso no es comprobable aqui y va como aviso al editor.
    # SE COMPARA CON EL PORCENTAJE NORMALIZADO. La norma del medio obliga a
    # escribir «7,14 %» con espacio, y las fuentes casi siempre escriben
    # «7,14%» pegado. Al citar textualmente, el redactor aplica nuestra norma y
    # la frase deja de coincidir letra por letra con el original: la cita del
    # BCV sobre los 21 trimestres se bloqueo por ese unico espacio. El espacio
    # no cambia lo que dijo la fuente, asi que se ignora en la comparacion.
    def _sin_espacio_de_porcentaje(s):
        return re.sub(r"\s+%", "%", s)

    material_txt = _sin_espacio_de_porcentaje(
        " ".join(str(x) for x in material).lower())
    for cita in ENTRECOMILLADO.findall(texto):
        limpia = re.sub(r"\s+", " ", cita).strip().lower()
        if len(limpia) < 25:      # frases cortas dan falsos positivos
            continue
        if _sin_espacio_de_porcentaje(limpia) not in material_txt:
            h.append(Hallazgo("bloqueo", "cita-ajena",
                              f"la frase entrecomillada «{cita[:60]}…» no aparece "
                              f"en el material del paquete"))
    if ENTRECOMILLADO.search(texto):
        h.append(Hallazgo("aviso", "quien-lo-dijo",
                          "hay citas textuales: comprobar CONTRA LA NOTA ORIGINAL "
                          "a quien se le atribuyen. El sistema no puede verificarlo"))

    # --- 4. Fuentes ---------------------------------------------------------
    del_paquete = {f.url for f in paquete.fuentes}
    for u in URL.findall(texto):
        if u.rstrip(".,;") not in del_paquete:
            h.append(Hallazgo("bloqueo", "fuente-ajena",
                              f"el enlace {u[:60]} no esta en el paquete"))
    if "sureconomics" in texto.lower() and any(
            "sureconomics" in u for u in URL.findall(texto)):
        h.append(Hallazgo("bloqueo", "autocita",
                          "SurEconomics no puede citarse a si mismo como fuente"))
    for f in paquete.fuentes:
        h.extend(Hallazgo("bloqueo", "fuente-invalida", p) for p in f.problemas())

    # --- 5. Etiquetas -------------------------------------------------------
    etiquetas = pieza.get("etiquetas", {}) or {}
    for eje, validos in TAXONOMIA.items():
        valor = etiquetas.get(eje)
        if not valor:
            h.append(Hallazgo("bloqueo", "etiqueta-falta",
                              f"falta la etiqueta '{eje}'"))
        elif valor not in validos:
            h.append(Hallazgo("bloqueo", "etiqueta-invalida",
                              f"'{valor}' no es un valor valido de '{eje}'"))
    pais = etiquetas.get("pais")
    if not pais:
        h.append(Hallazgo("bloqueo", "etiqueta-falta", "falta la etiqueta 'pais'"))
    elif pais not in PAISES_VALIDOS:
        # Sin esta comprobacion el modelo pone cosas como pais='Mundo', y el
        # corte por pais -que es como se mide el medio entero- deja de servir.
        h.append(Hallazgo("bloqueo", "pais-invalido",
                          f"'{pais}' no es un pais. Use un pais concreto o 'Latam'"))

    # --- 6. Reglas por tipo de escrito --------------------------------------
    tipo = pieza.get("tipo", "")
    # LA NOTICIA YA NO LLEVA BLOQUE «SurEconomics:». Decision editorial del dueño
    # el 26/08/2026: en una noticia, la posicion del medio al pie genera sesgo.
    # La regla estaba justo al reves y BLOQUEABA la noticia que no lo traia, asi
    # que no bastaba con dejar de pedirlo: habia que invertirla. La opinion, el
    # editorial y la investigacion siguen tomando partido, cada uno a su manera.
    if tipo == "Noticia" and (pieza.get("bloque_sureconomics") or "").strip():
        h.append(Hallazgo("bloqueo", "noticia-con-opinion",
                          "una noticia no lleva bloque 'SurEconomics:': la "
                          "posicion del medio al pie de un hecho genera sesgo"))
    # Solo opinion e investigacion exigen persona con nombre: una opinion sin
    # firma es un editorial anonimo, y una investigacion sin autor no se puede
    # defender. Educacion si puede ir firmada por la redaccion.
    if tipo in ("Opinión", "Investigación"):
        autor = (pieza.get("autor") or "").strip()
        if not autor or autor.upper() in {"XXX", "N/A", "REDACCIÓN SURECONOMICS",
                                          "REDACCION SURECONOMICS"}:
            h.append(Hallazgo("bloqueo", "sin-autor",
                              f"un texto de tipo '{tipo}' necesita autor con "
                              f"nombre; llego '{autor or 'vacio'}'"))
    elif tipo == "Educación" and not (pieza.get("autor") or "").strip():
        h.append(Hallazgo("bloqueo", "sin-autor",
                          "falta la firma (puede ser 'Redacción SurEconomics')"))

    # --- 7. Las advertencias del paquete son obligatorias --------------------
    for aviso in paquete.advertencias:
        anios = re.findall(r"\b(19\d{2}|20\d{2})\b", aviso)
        # Si el extractor avisa que el dato es viejo, el año TIENE que aparecer
        # en el texto: es lo que impide presentar un dato de 2016 como de hoy.
        if "NO puede presentarse como actual" in aviso:
            if not any(a in texto for a in anios):
                h.append(Hallazgo("bloqueo", "dato-viejo",
                                  f"el paquete avisa que el dato es de {anios[0] if anios else '?'} "
                                  f"y el texto no lo dice en ninguna parte"))
        elif "ATRIBUCIÓN OBLIGATORIA" in aviso:
            # Publicar la cifra de un diario esta bien; publicarla sin decir de
            # quien es, no. La atribucion es lo que separa citar de apropiarse,
            # y se comprueba: el nombre del medio tiene que estar en el texto.
            # Solo se exige nombrar las fuentes que la pieza REALMENTE usa. Una
            # fuente de contexto que el redactor decidio no usar no tiene por que
            # aparecer: exigirlo bloqueaba piezas correctas, que es como se pierde
            # la confianza en el auditor.
            # Se mira si la cifra APARECE EN EL TEXTO, no si el modelo la declaro:
            # declara de mas con frecuencia, y entonces se exigia nombrar a una
            # fuente cuyo dato nunca llego a escribirse. Atribuir un dato que no
            # esta es tan raro como no atribuir uno que si.
            # Se busca con limites de palabra y se ignoran los valores de uno o
            # dos caracteres: la calificacion de Damodaran es "C", y un "in texto"
            # a secas la encontraba en cualquier parte, asi que se exigia
            # atribucion siempre.
            usadas = set()
            for c in paquete.cifras:
                valor = str(c.valor).strip()
                if len(valor) < 3:
                    continue
                if re.search(rf"(?<![\w,.]){re.escape(valor)}(?![\w])", texto):
                    usadas.add(c.fuente_id)
            # El medio de la noticia se nombra siempre: el hecho es suyo.
            usadas |= {f.id for f in paquete.fuentes[:1]}
            # Se comprueban las PARTES del nombre, no la cadena entera. Una
            # fuente puede llamarse "J.P. Morgan (EMBIG), vía Banco Central de
            # Reserva del Perú" y eso jamas aparece literal en un texto bien
            # escrito: la prosa nombra a los dos por separado, que es lo
            # correcto. Exigir la cadena completa bloqueaba piezas impecables.
            # SE COMPARA SIN ESPACIOS NI TILDES. El nombre guardado en el
            # expediente sale a veces del dominio, y un dominio no tiene
            # espacios: bloomberglinea.com se guardaba como "Bloomberglinea"
            # mientras el redactor escribia "Bloomberg Línea", que es el nombre
            # de verdad. El auditor no lo encontraba y bloqueaba una pieza que
            # citaba su fuente correctamente. Paso el 02/09/2026.
            def _pelado(s):
                s = unicodedata.normalize("NFKD", s.lower())
                s = "".join(c for c in s if not unicodedata.combining(c))
                return re.sub(r"[^a-z0-9]", "", s)

            texto_pelado = _pelado(texto)
            faltan = []
            for f in (f for f in paquete.fuentes if f.id in usadas):
                for parte in _partes_del_nombre(f.institucion):
                    if _pelado(parte) not in texto_pelado:
                        faltan.append(parte)
            if faltan:
                h.append(Hallazgo("bloqueo", "sin-atribucion",
                                  f"la informacion es de {', '.join(faltan)} y el "
                                  f"texto no lo nombra en ninguna parte"))
            if "sacado de" not in (pieza.get("sacado_de") or "").lower():
                h.append(Hallazgo("bloqueo", "sin-sacado-de",
                                  "falta la linea «Sacado de: <medio>, <fecha> · "
                                  "<enlace>» al cierre de la pieza"))
        elif "redirector de Google News" in aviso:
            h.append(Hallazgo("bloqueo", "enlace-redirector",
                              "el enlace de la fuente es un redirector de Google "
                              "News, no la nota del medio"))
        else:
            h.append(Hallazgo("aviso", "advertencia-paquete", aviso))

    # --- 8. Lo que NO audita, y se le dice al editor -------------------------
    # Estas dos exigen criterio. Marcarlas como bloqueo daria falsos positivos.
    if tipo == "Noticia":
        # El aviso decia "la postura va solo en el bloque". Ya no hay bloque en
        # las noticias, asi que ahora no hay ningun sitio donde ponerla: en una
        # noticia el criterio se ejerce eligiendo que se cuenta, no opinando.
        h.append(Hallazgo("aviso", "revision-humana",
                          "revisar a mano: que el cuerpo informe y no opine, y "
                          "que el titular no afirme mas que el cuerpo"))

    return h


def bloqueada(hallazgos):
    return any(x.nivel == "bloqueo" for x in hallazgos)


def informe(hallazgos):
    """Texto para consola. El editor no lee JSON."""
    if not hallazgos:
        return "APROBADA: sin hallazgos. Pasa a la cola editorial."
    bloqueos = [x for x in hallazgos if x.nivel == "bloqueo"]
    avisos = [x for x in hallazgos if x.nivel == "aviso"]
    lineas = []
    if bloqueos:
        lineas.append(f"BLOQUEADA — {len(bloqueos)} motivo(s). No llega al editor:")
        lineas += [str(x) for x in bloqueos]
    else:
        lineas.append("APROBADA para la cola editorial.")
    if avisos:
        lineas.append(f"\n{len(avisos)} aviso(s) para el editor:")
        lineas += [str(x) for x in avisos]
    return "\n".join(lineas)
