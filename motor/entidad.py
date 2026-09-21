r"""La foto de QUIEN o de QUE va la nota, preguntandoselo a Wikidata.

    from motor import entidad
    c = entidad.para("Trump anuncia aranceles al acero", ["Estados Unidos"])

EL PROBLEMA QUE RESUELVE

buscar_foto.buscar() pregunta a Commons "que hay sobre estas palabras" y
devuelve lo que comparta un termino. De ahi salieron el Museu do Ipiranga
encabezando una nota de morosidad y un Lamborghini para el ataque de Times
Square: imagenes correctas, bien acreditadas, y de otra cosa.

Aqui no se busca. Se pregunta por una ENTIDAD -una persona, una empresa, un
pais, una mercancia- y Wikidata devuelve CUAL ES SU IMAGEN. La diferencia no es
de precision, es de pregunta: "fotos donde salga la palabra Nvidia" no es lo
mismo que "la imagen de Nvidia".

  P18   imagen         cualquier cosa: personas, mercancias, lugares
  P154  logotipo       empresas y marcas
  P41   bandera        paises

POR QUE ESTO ARREGLA LO DE LAS PERSONAS SIN ABRIR NINGUN AGUJERO

La norma vieja era "nunca propongas fotografiar a una persona por su nombre,
no hay imagenes con licencia de particulares". Lo segundo es cierto de un
particular y falso de un jefe de Estado: de Trump o de Delcy Rodriguez hay
retratos oficiales libres, y la nota se quedaba sin la unica portada que decia
de quien hablaba.

Lo que no se podia era distinguirlos, y con una lista de nombres tampoco: habria
que mantenerla y se quedaria corta el dia que aparezca un ministro nuevo.

Wikidata lo distingue sin que nadie lo decida: una figura publica documentada
tiene ficha y retrato libre; la victima de un apunalamiento, no. Cuando no hay
ficha no hay foto, que es exactamente el resultado que se queria. La proteccion
del particular deja de depender de que alguien se acuerde de la regla.

LO QUE ESTE ARCHIVO SIGUE SIN PODER HACER

Decidir si la imagen es DIGNA para la nota. Que la foto sea de Trump no la
convierte en la foto adecuada para lo que se cuenta de el. Sigue en borrador y
sigue mirandolo una persona.
"""

import json
import sys
import unicodedata
import urllib.parse
import urllib.request

API = "https://www.wikidata.org/w/api.php"
AGENTE = ("SurEconomics/1.0 (medio de economia; "
          "contacto: redaccion@sureconomics.com)")

# Wikidata dice de que tipo es cada cosa en P31 ("instancia de"). Solo hace
# falta reconocer a las personas, que son las que llevan retrato en vez de logo.
HUMANO = "Q5"

IMAGEN, LOGO, BANDERA = "P18", "P154", "P41"
PAIS = "P17"


def _plano(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _pedir(parametros):
    url = API + "?" + urllib.parse.urlencode(parametros)
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=30) as r:
            return json.load(r)
    except Exception as exc:  # noqa: BLE001
        print("[aviso] Wikidata no respondio: %s" % exc)
        return {}


def nombres_del_titular(titulo, resumen=""):
    """Los nombres propios de los que va la nota, del protagonista al ultimo.

    QUIEN DECIDE QUE AQUI. El modelo propone y Wikidata dispone. Un modelo puede
    inventarse un nombre o equivocarse de empresa; lo que no puede es hacer que
    Wikidata tenga una ficha con imagen para algo que no existe. Por eso esta
    parte se le puede dejar: si se equivoca, el paso siguiente lo tira.

    Se piden NOMBRES PROPIOS y no descripciones. "el presidente de EE. UU." no
    se resuelve contra Wikidata; "Donald Trump", si.
    """
    from motor.ia import pedir_json

    prompt = (
        "Eres editor grafico de un medio de economia. Te doy el titular de una "
        "noticia en español.\n\n"
        "Dime de QUE O DE QUIEN trata, en NOMBRES PROPIOS, del mas protagonista "
        "al menos. Vale una persona, una empresa o marca, un pais, o una "
        "mercancia (oro, petroleo, cafe).\n\n"
        "Reglas:\n"
        "- Nombres propios tal cual, no descripciones: 'Donald Trump', no 'el "
        "presidente'. 'Nvidia', no 'la empresa de chips'.\n"
        "- Solo lo que aparezca en el titular o el resumen. No añadas de tu "
        "conocimiento a nadie que no se nombre.\n"
        "- Una mercancia se nombra por su nombre comun: oro, petroleo, litio.\n"
        "- El pais va el ULTIMO, porque es lo menos concreto.\n"
        "- Entre uno y tres.\n\n"
        'Devuelve solo JSON: {"entidades": ["...", "..."]}\n\n'
        "Titular: %s\n%s" % (titulo, resumen[:300]))

    r = pedir_json(prompt, etiqueta="entidad", temperatura=0.1)
    if not isinstance(r, dict):
        # NO ES LO MISMO «NO HAY ENTIDAD» QUE «NO PUDE PREGUNTAR», y hasta el
        # 21/09/2026 las dos salian de aqui como lista vacia. Quien llama no
        # podia distinguirlas y trataba la averia como una respuesta. Devolver
        # None es lo que deja a foto.para() negarse a adivinar. Ver alli.
        return None
    return [str(x).strip() for x in (r.get("entidades") or []) if str(x).strip()][:3]


def para(titulo, lugares=None, resumen="", explicar=False):
    """La portada de la entidad de la que habla la nota, o None.

    Es la primera via que prueba foto.para(). Si devuelve None se sigue con la
    busqueda por texto de siempre.
    """
    from motor import foto

    nombres = nombres_del_titular(titulo, resumen)
    if nombres is None:
        # Sin IA no se ha podido preguntar de quien habla. Se devuelve None y
        # no [] para que foto.para() sepa que esto es una averia y no un
        # titular sin entidades.
        return None, None
    if not nombres:
        return None, []
    print("   [entidad] de quien/que habla: %s" % ", ".join(nombres))

    descartes = []
    posibles, conocidas = candidatas(nombres, lugares)
    for c in posibles:
        # A las que declara Wikidata no hay que exigirles que la ficha nombre a
        # la entidad: la ficha de Wikidata YA dice que esa es su imagen. A las
        # buscadas por texto, si, que es lo que evita que una busqueda de
        # "Nvidia" traiga cualquier placa base.
        asunto = None if c.get("de_wikidata") else [c["entidad_en"].split()[-1]]
        bien, motivo = foto.sirve(c, None, asunto)
        if bien:
            c["consulta"] = "entidad: %s" % c["entidad"]
            c["descartadas"] = descartes
            return c, conocidas
        descartes.append("%s: %s" % (c["titulo"][:34], motivo))
    if explicar:
        for d in descartes[:6]:
            print("        descartada %s" % d)
    return None, conocidas


# De quien es una cuenta, segun Wikidata. P2003 es el usuario de Instagram y
# P2002 el de X.
CUENTAS = {"instagram": "P2003", "x": "P2002", "twitter": "P2002"}


def de_quien_es_la_cuenta(usuario, red="instagram"):
    """¿A quien pertenece esa cuenta? Devuelve la ficha, o None.

    ES LA COMPROBACION QUE PERMITE ESCRIBIR DESDE UNA DECLARACION. Contar que
    "Trump dijo" apoyandose en una cuenta que no es la suya seria el peor error
    posible de este sistema, y no es un riesgo teorico: de cualquier figura
    publica hay cuentas de parodia, de fans y de suplantacion.

    Wikidata guarda la cuenta OFICIAL de cada persona e institucion, asi que la
    pregunta se responde con un dato y no con el criterio de un modelo: el
    usuario que firma el post o es el que Wikidata tiene registrado, o no se
    escribe desde ahi.

    Comprobado el 07/09/2026: realdonaldtrump, delcyrodriguezven y nicolasmaduro
    resuelven a su persona; beycocapital, espacio.media y bloomberglinea no
    resuelven a nadie, que es el resultado correcto para una cuenta que no es de
    una figura publica documentada.
    """
    propiedad = CUENTAS.get((red or "").lower())
    usuario = (usuario or "").strip().lstrip("@")
    if not propiedad or not usuario:
        return None
    d = _pedir({"action": "query", "list": "search",
                "srsearch": "haswbstatement:%s=%s" % (propiedad, usuario),
                "srlimit": "3", "format": "json"})
    for r in (d.get("query") or {}).get("search", []):
        f = ficha(r["title"])
        # Solo personas. Una empresa o un medio con cuenta se atiende por la
        # lista blanca, que es donde se decide si es fuente aceptable.
        if f and f.get("persona"):
            return f
    return None


def buscar_ficha(nombre, idioma="es"):
    """El identificador de Wikidata que mejor case con ese nombre, o None."""
    d = _pedir({"action": "wbsearchentities", "search": nombre[:120],
                "language": idioma, "uselang": idioma, "type": "item",
                "limit": "5", "format": "json"})
    for r in d.get("search") or []:
        return r.get("id")
    # Muchas empresas y mercancias solo estan catalogadas en ingles.
    if idioma != "en":
        return buscar_ficha(nombre, "en")
    return None


def _valor(reclamaciones, propiedad):
    """El primer valor de una propiedad, o None."""
    for c in reclamaciones.get(propiedad) or []:
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict) and v.get("id"):
            return v["id"]
    return None


def _tipos(reclamaciones):
    fuera = []
    for c in reclamaciones.get("P31") or []:
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            fuera.append(v["id"])
    return fuera


def ficha(identificador):
    """Lo que hace falta de una entidad: como se llama y cual es su imagen."""
    d = _pedir({"action": "wbgetentities", "ids": identificador,
                "props": "claims|labels", "languages": "es|en",
                "format": "json"})
    e = (d.get("entities") or {}).get(identificador) or {}
    if not e:
        return None
    rec = e.get("claims") or {}
    etiquetas = e.get("labels") or {}
    return {
        "id": identificador,
        "nombre": ((etiquetas.get("es") or {}).get("value")
                   or (etiquetas.get("en") or {}).get("value") or ""),
        "nombre_en": (etiquetas.get("en") or {}).get("value") or "",
        "persona": HUMANO in _tipos(rec),
        # De que pais es. Solo se mira en las entidades con bandera; ver
        # es_de_aqui().
        "pais_id": _valor(rec, PAIS),
        IMAGEN: _valor(rec, IMAGEN),
        LOGO: _valor(rec, LOGO),
        BANDERA: _valor(rec, BANDERA),
    }


def _etiqueta(identificador):
    """Como se llama una entidad, para poder comparar paises por nombre."""
    d = _pedir({"action": "wbgetentities", "ids": identificador,
                "props": "labels", "languages": "es|en", "format": "json"})
    e = (d.get("entities") or {}).get(identificador) or {}
    et = e.get("labels") or {}
    return ((et.get("es") or {}).get("value")
            or (et.get("en") or {}).get("value") or "")


def es_de_aqui(f, lugares):
    """¿Esa bandera es del pais del que habla la nota?

    EL ERROR QUE ESTO EVITA, del 03/09/2026: una nota sobre la inversion
    britanica en el Fundo Florida, que es una finca venezolana. El modelo
    propuso "Florida", Wikidata devolvio el ESTADO DE FLORIDA y la portada iba a
    ser su bandera. Una bandera equivocada no es una imprecision: le dice al
    lector que la noticia es de otro pais.

    Solo se comprueba en las entidades CON BANDERA, es decir paises y regiones.
    Una empresa o una persona de otro pais no tiene nada de raro -Nvidia es
    estadounidense y puede protagonizar una nota venezolana-, y aplicarles esta
    regla dejaria fuera media portada legitima.
    """
    if not f[BANDERA] or not lugares:
        return True
    quiero = {_plano(x) for x in lugares}
    if _plano(f["nombre"]) in quiero or _plano(f["nombre_en"]) in quiero:
        return True
    # Una region vale si su pais es uno de los del que habla la nota: la
    # bandera de Zulia sirve para una pieza de Venezuela.
    if f["pais_id"]:
        return _plano(_etiqueta(f["pais_id"])) in quiero
    return False


def archivos_de(f, con_bandera=True):
    """Que archivo de Commons le corresponde, en orden de preferencia.

    EL ORDEN ES LA REGLA QUE PIDIO EDICION, escrita: si la nota habla de una
    persona, la persona; si de una marca, su logo; si de un pais y nada mas
    concreto, su bandera. Una persona nunca lleva logo aunque presida una
    empresa, y por eso el retrato va aparte y primero.
    """
    if f["persona"]:
        return [x for x in (f[IMAGEN],) if x]
    # LA BANDERA SOLO SI EL PAIS ES EL ASUNTO, no si es lo que quedaba.
    # Decision de Edicion el 04/09/2026, viendo la primera tanda con foto: de
    # tres portadas, dos eran banderas. «LA BANCA ESPAÑOLA AFRONTA PRESIONES»
    # salio con la bandera de España, que dice el pais y nada del asunto, y
    # «BRAVONIX PROYECTA INGRESOS EN BRASIL» con la de Brasil porque la empresa
    # no tiene ficha. El pais entra el ultimo de la lista justo por ser lo menos
    # concreto, y usarlo cuando lo concreto fallo es rellenar. Mejor sin
    # portada. Si la pieza es DE Venezuela y de nada mas, su bandera sigue
    # siendo la imagen correcta, y eso es lo que mide con_bandera.
    #
    # Y SE CAE LA ENTIDAD ENTERA, no solo su bandera. Quitando unicamente la
    # bandera, el hueco lo ocupaba su P18: «Spain - Location Map» para la banca
    # española y «Brazil topo.jpg» para Bravonix. Un mapa del pais no dice mas
    # que su bandera; el problema no era la bandera, era ilustrar con el pais.
    # Tener P41 es la señal de que la entidad ES un pais o una region: nada mas
    # la tiene.
    if not con_bandera and f[BANDERA]:
        return []
    # LA BANDERA VA ANTES QUE LA IMAGEN, y esto no es un detalle: P18 de
    # Venezuela es una foto del embalse La Vueltosa. Es de Venezuela y no dice
    # nada. Solo los paises y las regiones tienen P41, asi que tener bandera es
    # ya la señal de que la entidad es un pais y de que su imagen util es esa.
    # El logo va el primero de todos porque de una empresa P18 suele ser su
    # sede, que dice mucho menos que la marca.
    return [x for x in (f[LOGO], f[BANDERA], f[IMAGEN]) if x]


def resolver(nombres, lugares=None):
    """De los nombres propuestos, las fichas que Wikidata si conoce.

    Se conserva el ORDEN en que llegan: quien propone los nombres los da de mas
    a menos protagonista, y la portada tiene que ser del protagonista.
    """
    fichas, conocidas = [], []
    # ¿Es el pais el unico asunto de la pieza? Si el titular nombra algo mas
    # -una empresa, una mercancia, una persona-, la bandera deja de valer como
    # portada. Ver archivos_de().
    utiles = [n for n in nombres[:4] if n and len(n) >= 3]
    con_bandera = len(utiles) == 1
    for n in nombres[:4]:
        if not n or len(n) < 3:
            continue
        ident = buscar_ficha(n)
        if not ident:
            print("   [entidad] Wikidata no conoce a '%s': sin foto por aqui" % n)
            continue
        f = ficha(ident)
        if not f:
            continue
        # Se apunta aunque no tenga imagen. Saber DE QUIEN habla la pieza vale
        # por si solo: es lo que impide que, al no encontrar su foto, se acabe
        # cogiendo cualquier archivo que comparta el nombre. Ver para().
        conocidas.append(f["nombre"] or n)
        if not archivos_de(f, con_bandera):
            print("   [entidad] '%s' (%s) no tiene imagen" % (n, ident))
            continue
        if not es_de_aqui(f, lugares):
            print("   [entidad] '%s' resolvio a %s, que no es de %s: lo dejo"
                  % (n, f["nombre"] or ident, " ni ".join(lugares)))
            continue
        f["pedido"] = n
        f["con_bandera"] = con_bandera
        fichas.append(f)
    return fichas, conocidas


def candidatas(nombres, lugares=None):
    """Las imagenes de esas entidades, ya con licencia y medidas de Commons."""
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    from buscar_foto import buscar, credito
    from buscar_foto import fichas as fichas_commons

    salida = []
    fichas_utiles, conocidas = resolver(nombres, lugares)
    for f in fichas_utiles:
        archivos = archivos_de(f, f["con_bandera"])
        # HAY QUE REORDENAR. fichas_commons() pide todos los archivos en una
        # sola llamada y la API los devuelve en SU orden, no en el que se
        # pidieron: de Venezuela llegaba el embalse antes que la bandera y de
        # Nvidia la sede antes que el logo, con lo que el orden de preferencia
        # de archivos_de() no servia de nada. Se recoloca por posicion pedida.
        orden = {a.replace("File:", ""): i for i, a in enumerate(archivos)}
        propias = sorted(fichas_commons(archivos),
                         key=lambda c: orden.get(c["titulo"], 99))
        # Cuales de estos archivos son SIMBOLOS y no fotografias. Hace falta
        # distinguirlo porque Commons fecha una bandera o un logo por cuando se
        # adopto el diseño: la del Reino Unido consta como de 1801 y la regla
        # que descarta las imagenes anteriores a 1980 -puesta por una lamina de
        # 1885 que ilustro una nota de mercados- la tiraba. A una fotografia esa
        # regla le sigue aplicando entera, venga de Wikidata o no.
        simbolos = {x.replace("File:", "")
                    for x in (f[LOGO], f[BANDERA]) if x}
        for c in propias:
            c["de_wikidata"] = True
            c["simbolo"] = c["titulo"] in simbolos
            # El credito se calculo antes de saber que era un simbolo, y para
            # un simbolo la linea es otra. Ver buscar_foto.credito().
            c["credito"] = credito(c)
        # Y ADEMAS SE BUSCA POR SU NOMBRE. La imagen canonica de una persona
        # suele ser un retrato VERTICAL -el oficial de Trump es 1638x2048- y en
        # portada se recorta mal. Wikidata sigue haciendo lo esencial, que es
        # confirmar que esa persona es una figura publica documentada con
        # imagenes libres; para la forma que necesita la apertura hace falta
        # mirar mas fotos de la misma persona, y esas se buscan en Commons
        # exigiendo que la ficha la nombre.
        # LA MAS RECIENTE PRIMERO, entre las buscadas. Commons ordena por
        # relevancia de texto, y para un cargo publico eso saca retratos de
        # hace diez años: la primera candidata apaisada de Delcy Rodriguez era
        # de 2014. La edad de la foto no la ve el lector en el pie, la ve en la
        # cara. Las que no declaran fecha van detras, no delante.
        buscadas = sorted(buscar(f["nombre_en"] or f["pedido"], n=10),
                          key=lambda c: int(c["anio"]) if c["anio"] else 0,
                          reverse=True)
        for c in propias + buscadas:
            c["entidad"] = f["nombre"] or f["pedido"]
            c["entidad_id"] = f["id"]
            c["es_persona"] = f["persona"]
            c["entidad_en"] = f["nombre_en"] or f["pedido"]
            salida.append(c)
    return salida, conocidas
