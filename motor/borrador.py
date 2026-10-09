"""El formato del borrador en texto (.txt) que deja producir.py.

EL TITULAR VA EN SU PROPIA LINEA, MARCADA, desde el 09/10/2026. Hasta entonces
iba en MAYUSCULAS y asi lo reconocian todos los que leen el borrador (el armado
de la carga, el correo, el chat, la reauditoria y los Word de entrega): «la
linea larga toda en mayusculas es el titular». Esa fecha el medio paso a
titulares con ortografia normal de frase (mayuscula inicial y nombres propios),
y un titular bien escrito ya no se distingue por la forma. Asi que se marca:

    [Titular] El FMI abrirá una oficina en Caracas en 2027

Los borradores viejos, con el titular en mayusculas, se siguen reconociendo.
"""

MARCA = "[Titular]"


def linea_de_titular(titulo):
    return "%s %s" % (MARCA, (titulo or "").strip())


def titular_de(linea):
    """El titular si la linea lo es, o "". Acepta el formato nuevo y el viejo."""
    s = (linea or "").strip()
    if s.startswith(MARCA):
        return s[len(MARCA):].strip()
    if s.isupper() and len(s) > 25:
        return s
    return ""


def desde_mayusculas(titulo, cuerpo):
    """Un titular que llego ENTERO EN MAYUSCULAS, devuelto a su ortografia.

    En mayusculas se pierde que «Caracas» va con mayuscula y «oficina» no, pero
    el cuerpo de la misma pieza lo dice: cada palabra toma la forma con que
    aparece alli. Si aparece alguna vez en minuscula, va en minuscula; si solo
    aparece con mayuscula A MITAD DE FRASE (no despues de un punto), es nombre
    propio; si aparece entera en mayusculas, es una sigla (FMI, BCV). Lo que no
    aparece en el cuerpo, en minuscula. La primera letra la pone despues
    mayuscula_inicial(). Es codigo y no otra llamada al modelo: la informacion
    ya esta en la pieza.
    """
    import re
    formas = {}
    for m in re.finditer(r"[\wÁÉÍÓÚÜÑáéíóúüñ$.]+", cuerpo or ""):
        w = m.group(0).strip(".")
        if not w:
            continue
        antes = (cuerpo[:m.start()].rstrip()[-1:] or ".")
        inicio_de_frase = antes in ".!?:\n«\"(" or m.start() == 0
        formas.setdefault(w.lower(), []).append((w, inicio_de_frase))

    def forma(palabra):
        if palabra.lower() in SIEMPRE_ASI:
            return SIEMPRE_ASI[palabra.lower()]
        lista = formas.get(palabra.lower())
        if not lista:
            return palabra.lower()
        if any(w.islower() for w, _ in lista):
            return palabra.lower()
        if any(w.isupper() and len(w) > 1 for w, _ in lista):
            return next(w for w, _ in lista if w.isupper() and len(w) > 1)
        dentro = [w for w, ini in lista if not ini]
        return dentro[0] if dentro else palabra.lower()

    return re.sub(r"[\wÁÉÍÓÚÜÑáéíóúüñ]+", lambda m: forma(m.group(0)), titulo or "")


# NOMBRES QUE VAN SIEMPRE ASI, digan lo que digan el modelo o la fuente. PDVSA
# entero en mayusculas: norma de la casa, decidida por Saul el 09/10/2026 (la
# fuente y el modelo escriben «Pdvsa» la mitad de las veces).
SIEMPRE_ASI = {"pdvsa": "PDVSA"}


def estilo_casa(texto):
    """Los nombres de SIEMPRE_ASI con su forma fija, en cualquier texto."""
    import re
    for k, v in SIEMPRE_ASI.items():
        texto = re.sub(r"\b%s\b" % k, v, texto or "", flags=re.I)
    return texto


def mayuscula_inicial(texto):
    """La primera letra en mayuscula y el resto TAL CUAL: no se toca ningun
    nombre propio (capitalize() los pasaria a minuscula). Los signos de
    apertura no son letra: «¿Nueva carrera…» empieza en la N."""
    texto = (texto or "").strip()
    for i, c in enumerate(texto):
        if c.isalpha():
            return texto[:i] + c.upper() + texto[i + 1:]
    return texto
