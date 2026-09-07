r"""Lee una captura de pantalla y busca la noticia original.

    from motor import captura
    hallado = captura.desde_telegram(file_id)   # {'url': ..., 'titular': ...}

POR QUE EXISTE

Los jefes mandan las noticias por Telegram como capturas de Instagram. Hasta
hoy habia que abrirlas a mano, leer que decian, buscar el articulo original y
solo entonces pedirle al motor que escribiera.

LA CAPTURA ES UNA PISTA, NO UNA FUENTE. Es la decision de fondo de este archivo
y conviene que quede escrita. Todo el motor se sostiene en que cada cifra
rastrea a un documento verificable; si se escribiera desde la captura, se
heredarian los errores del post de Instagram y el auditor no tendria contra que
comprobar nada. En una sola jornada apareci tres veces ese problema con fuentes
secundarias: unos 50.000 millones que no cuadraban, 900 escuelas que eran 91, y
una cita atribuida a quien decia justo lo contrario.

Asi que la captura solo sirve para saber QUE buscar. Con el titular que saca el
modelo se busca el articulo en la lista blanca de medios, y se escribe desde el
original. SI NO APARECE, NO SE ESCRIBE: se dice que no se encontro y se termina.
Decision del dueño el 01/09/2026, sabiendo que a veces dira que no.

El modelo NO redacta aqui. Solo transcribe lo que se ve y dice de que trata,
que es justo lo que un modelo de vision hace bien y sin inventar.
"""

import json
import os
import urllib.request

MIMES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
         "webp": "image/webp", "gif": "image/gif"}

PROMPT = (
    "Esta es una captura de pantalla de una publicacion de una red social o de "
    "un medio, que alguien mando por chat para avisar de una noticia.\n\n"
    "TRANSCRIBE lo que se ve. No interpretes, no completes, no redactes.\n\n"
    "Devuelve solo JSON con estas claves:\n"
    '  "titular": el titular tal como aparece, literal. "" si no hay.\n'
    '  "medio": el nombre del medio o de la cuenta que publica. "" si no se ve.\n'
    '  "fecha": la fecha que aparezca, en formato AAAA-MM-DD. "" si no hay.\n'
    '  "texto": el resto del texto legible, tal cual.\n'
    '  "busqueda": entre tres y ocho palabras para buscar esta noticia en un '
    'buscador. Nombres propios y cifras, sin palabras vacias.\n'
    '  "legible": true si se lee bien, false si esta borrosa o cortada.\n\n'
    "Si la imagen no es una noticia (una foto cualquiera, un meme, una "
    'conversacion), pon "titular" vacio y "texto" con lo que sea que se vea. '
    "No inventes una noticia que no esta."
)


def bajar_de_telegram(file_id, tiempo_espera=60):
    """Devuelve (bytes, mime) de una foto mandada al bot.

    Se pide con el file_id y NO con la direccion de descarga. Esa direccion
    lleva el token del bot dentro, y pasarla como entrada de un workflow la deja
    escrita en el registro de Actions para siempre.
    """
    ficha = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not ficha:
        raise RuntimeError("falta TELEGRAM_TOKEN")

    with urllib.request.urlopen(
            "https://api.telegram.org/bot%s/getFile?file_id=%s" % (ficha, file_id),
            timeout=tiempo_espera) as r:
        ficha_archivo = json.loads(r.read().decode())
    if not ficha_archivo.get("ok"):
        raise RuntimeError("Telegram no da el archivo: %s"
                           % str(ficha_archivo.get("description"))[:90])

    ruta = ficha_archivo["result"]["file_path"]
    with urllib.request.urlopen(
            "https://api.telegram.org/file/bot%s/%s" % (ficha, ruta),
            timeout=tiempo_espera) as r:
        datos = r.read()
    return datos, MIMES.get(ruta.rsplit(".", 1)[-1].lower(), "image/jpeg")


def leer(imagen):
    """imagen es (bytes, mime). Devuelve lo transcrito, o None."""
    from motor.ia import pedir_json

    r = pedir_json(PROMPT, etiqueta="captura", temperatura=0.0, imagen=imagen)
    if not isinstance(r, dict):
        return None
    return {k: r.get(k, "") for k in
            ("titular", "medio", "fecha", "texto", "busqueda", "legible")}


# DOS UMBRALES, PORQUE UN NUMERO SOLO NO PUEDE DECIDIR ESTO.
#
# Medido el 01/09/2026 con capturas reales:
#   1.000  el mismo titular, redactado igual        -> es la nota, seguro
#   0.571  captura en español, original en portugues -> es la nota, pero dudoso
#   0.500  "inflacion de la Fed" contra "inflacion de la zona euro" -> NO es
#
# Fijate en el problema: el falso positivo (0.500) puntua casi igual que el
# acierto dificil (0.571). No es que el umbral este mal calibrado, es que dos
# titulares sobre inflacion son casi identicos como texto y lo que los separa es
# la entidad, "Fed" contra "euro". Ninguna medida de parecido entre titulares va
# a distinguir eso de forma fiable, y afinar el numero solo mueve el error de
# sitio.
#
# Asi que por encima de AUTOMATICO se escribe sin preguntar, y en la franja de
# en medio se le manda al que pidio la nota lo que se encontro y decide el. Es
# la unica parte de todo esto que de verdad necesita criterio humano, y es
# barata: un mensaje. Publicar la noticia equivocada no lo es.
PARECIDO_AUTOMATICO = 0.75
PARECIDO_MINIMO = 0.45


# Medios de la lista que casi siempre devuelven 401 o 403 al leerlos: su
# contenido esta tras un muro de pago. Siguen en la lista blanca porque son
# fuentes excelentes y a veces dejan pasar una nota, pero no se ofrecen los
# primeros. Se amplia cuando aparezca otro; la comprobacion de verdad la hace
# nota.py al intentar leerlos.
# reuters.com entro el 03/09/2026: en una sola corrida devolvio 401 siete
# veces. No cobra por leer, pero bloquea a los lectores automaticos igual que un
# muro de pago, y para esto es lo mismo: no se puede leer.
TRAS_MURO = ("wsj.com", "ft.com", "bloomberg.com", "economist.com",
             "reuters.com")


def _tras_muro(url):
    return 1 if any(d in (url or "") for d in TRAS_MURO) else 0


def _es_portada(url):
    from urllib.parse import urlparse
    p = urlparse(url or "")
    return p.scheme in ("http", "https") and p.path.strip("/") == "" and not p.query


PROMPT_TEXTO = (
    "Este es el texto de una publicacion de red social que alguien mando para "
    "avisar de una noticia.\n\n"
    "Devuelve solo JSON con:\n"
    '  "titular": el hecho en una linea, como lo titularia un medio.\n'
    '  "busqueda": entre tres y seis palabras para encontrar esa noticia en un '
    'buscador. Nombres propios y cifras, sin palabras vacias y sin hashtags.\n\n'
    "No inventes nada que no este en el texto.\n\nTexto: %s")


def leer_texto(texto):
    """Saca titular y palabras de busqueda de un texto suelto (un tuit).

    POR QUE NO VALE PASAR EL TEXTO TAL CUAL AL BUSCADOR. Se probo el 02/09/2026
    con un tuit sobre las licencias de la OFAC: mandando 180 caracteres crudos
    como consulta, con sus guiones, sus hashtags y sus arrobas, el buscador
    devolvio cero. Una consulta es un puñado de palabras distintivas, no un
    parrafo.
    """
    from motor.ia import pedir_json

    r = pedir_json(PROMPT_TEXTO % (texto or "")[:1200], etiqueta="tuit",
                   temperatura=0.0)
    if not isinstance(r, dict):
        return None
    return {"titular": r.get("titular", ""), "busqueda": r.get("busqueda", ""),
            "medio": "", "fecha": "", "texto": texto, "legible": True}


def buscar_original(lectura, dias=15, umbral=PARECIDO_MINIMO):
    """Busca en la lista blanca la noticia que la captura anuncia.

    SOLO LISTA BLANCA. Una captura sin original verificable no se escribe, y
    encontrarlo en cualquier sitio de internet no es encontrarlo: la lista es
    la que hace que la fuente valga.

    Y EL CANDIDATO TIENE QUE PARECERSE AL TITULAR DE LA CAPTURA. Sin esto, el
    buscador devuelve lo que sea que tenga a mano y la primera version de este
    archivo se quedaba con el primero de la lista, sin mirar. Probando con una
    captura real de El Pais sobre Trump y el lago Ontario, los tres candidatos
    eran paginas de Euronews (uno de ellos la portada, sobre judo) y el motor
    habria escrito desde ahi. Una fuente verificable que habla de otra cosa no
    es la fuente: es peor que no encontrar nada, porque parece que si.
    """
    from motor import buscador, memoria

    titular = (lectura.get("titular") or "").strip()
    consulta = (lectura.get("busqueda") or titular).strip()
    if not consulta:
        return []

    # PRIMERO LOS FEEDS DE LOS PROPIOS MEDIOS, y no el buscador. Los jefes
    # mandan las capturas CUANDO ACABA DE SALIR la noticia, que es justo cuando
    # el indice de Tavily todavia no la tiene: la prueba del 01/09/2026 con una
    # nota de El Pais de dos horas de antiguedad no devolvia nada, ni siquiera
    # buscando sin restringir dominios. Los RSS, en cambio, la tienen al minuto,
    # y ademas son la lista blanca por construccion.
    # LO PRIMERO DE TODO: SI SE SABE DE QUE MEDIO ES, SE BUSCA AHI.
    #
    # La captura trae el logo del diario y el modelo lo lee; un post de
    # Instagram trae la cuenta que lo publico. Esa es la pista mas fuerte que
    # hay y se estaba tirando: el 07/09/2026 una captura de Bloomberg Línea
    # sobre Radia Perlman se buscaba por palabras del titular en los 45 medios
    # de la lista, no encontraba nada, y la corrida terminaba diciendo "no
    # encuentro esta noticia en ninguna fuente verificable" con el nombre del
    # medio impreso dos lineas mas arriba.
    #
    # Buscar en su diario es otra pregunta, no la misma con menos ruido: dentro
    # de un solo dominio, un titular parecido casi siempre ES la nota.
    crudos = []
    suyos = buscador.dominios_de(lectura.get("medio"))
    if suyos:
        print("  dice que es de %s: voy ahi primero" % ", ".join(suyos))
        # SUS FEEDS, A FONDO. El rastreo general mira 45 horas y 12 notas por
        # medio, que para 51 medios ya es mucho pedir. Pero cuando se sabe de
        # cual es, son dos o tres feeds y se pueden leer enteros: la nota de
        # Bloomberg Línea del 07/09/2026 estaba en su feed de tecnologia, en la
        # posicion 30 y con tres dias, o sea fuera de la ventana por partida
        # doble. Leer hondo en UN medio cuesta lo mismo que leer por encima en
        # cuarenta y encuentra lo que aquello no puede.
        claves = buscador.claves_de(lectura.get("medio"))
        if claves:
            try:
                from motor.fuentes import noticias as _n
                crudos += _n.titulares(medios=claves, horas=24 * 21,
                                       por_medio=100)
                print("  %d titulares de sus propios feeds" % len(crudos))
            except Exception as exc:  # noqa: BLE001
                print("  [aviso] no pude leer sus feeds (%s)" % str(exc)[:60])
        antes = len(crudos)
        crudos += buscador.buscar(consulta, dias=dias, maximo=8,
                                  dominios=suyos, como_noticias=False,
                                  ordenar=False)
        if len(crudos) > antes:
            print("  %d resultado(s) buscando en su dominio" % (len(crudos) - antes))

    try:
        from motor.fuentes import noticias
        # titulares() y no extraer(): el 'limite' de extraer es un tope GLOBAL y
        # retorna en cuanto lo alcanza, asi que con 60 solo se leian los tres
        # primeros medios de la lista y los otros cuarenta y siete ni se
        # consultaban. Aqui hace falta amplitud, no profundidad.
        crudos += noticias.titulares(horas=max(24, dias * 24 // 8), por_medio=12)
    except Exception as exc:  # noqa: BLE001
        print("  [aviso] no pude leer los feeds (%s); voy al buscador" % str(exc)[:70])

    # como_noticias=False y ordenar=False en LAS DOS busquedas. Se busca UNA
    # noticia concreta, no se descubre nada: topic="news" excluye a los medios
    # que no estan en el indice de noticias de Tavily, y criterio.ordenar()
    # puntua interes periodistico, que es otra pregunta y descarta aciertos.
    #
    # LA PRIMERA SE QUEDO SIN EL ARREGLO Y NO SE VIO. El 02/09 se corrigio solo
    # la segunda porque el reemplazo automatico no encajo con el texto real y no
    # aviso de nada, y la prueba paso igual porque la noticia la encontro la de
    # respaldo. Al dia siguiente el bot no encontro que John Ternus era el nuevo
    # CEO de Apple, que estaba en seis medios de la lista.
    crudos += buscador.buscar(consulta, dias=dias, maximo=8, solo_lista_blanca=True,
                              como_noticias=False, ordenar=False)
    # Segundo intento con el titular entero: "busqueda" son palabras sueltas y
    # a veces el titular literal encuentra lo que ellas no.
    if titular:
        crudos += buscador.buscar(titular[:120], dias=dias, maximo=8,
                                  solo_lista_blanca=True,
                                  como_noticias=False, ordenar=False)

    # SE DEJA ESCRITO QUE SE BUSCO Y QUE SE ENCONTRO. Sin esto, un "no encuentro
    # esta noticia" no se puede diagnosticar: el 03/09/2026 el bot rechazo la
    # noticia de que John Ternus es el nuevo CEO de Apple y hubo que reproducir
    # la busqueda a mano para ver que el fallo no estaba donde parecia. Cuesta
    # dos lineas de registro y ahorra media hora cada vez.
    print("     busque: %s  ->  %d candidatos" % (consulta[:70], len(crudos)))

    vistos, buenos, descartados = set(), [], []
    for c in crudos:
        url = c.get("url") or ""
        if url in vistos or _es_portada(url):
            continue
        vistos.add(url)
        p = memoria.parecido(titular, c.get("titular", "")) if titular else 0.0
        if p < umbral:
            descartados.append((p, c.get("titular", "")))
        if p >= umbral:
            c = dict(c)
            c["parecido"] = round(p, 3)
            buenos.append(c)
    # A IGUAL PARECIDO, PRIMERO EL QUE SE PUEDA LEER. Los siete candidatos de la
    # noticia de Apple puntuaban exactamente 0.571 y los dos primeros eran del
    # Wall Street Journal, que devuelve 401 tras su muro de pago. nota.py ya
    # prueba el siguiente, pero el que se le enseña a la persona en la franja
    # dudosa tambien debe ser uno que pueda abrir.
    buenos.sort(key=lambda c: (-c["parecido"], _tras_muro(c.get("url", ""))))
    # Si no pasa ninguno, se dice CUAL estuvo mas cerca y con cuanto. La
    # diferencia entre "no existe la noticia" y "existe pero el umbral la corto"
    # es la unica que importa para arreglarlo, y sin este registro no se ve.
    if not buenos and descartados:
        descartados.sort(reverse=True)
        p, t = descartados[0]
        print("     ninguno pasa el %.2f. El mas cercano: %.3f  %s"
              % (umbral, p, t[:60]))
    return buenos


def desde_telegram(file_id, dias=15):
    """Todo junto: baja, lee y busca. Devuelve un diccionario con el resultado.

    Nunca lanza por un fallo de lectura: devuelve 'motivo' explicando por que no
    se pudo, para que quien lo pidio reciba una respuesta y no un silencio.
    """
    try:
        imagen = bajar_de_telegram(file_id)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "motivo": "no pude bajar la imagen: %s" % str(exc)[:90]}

    lectura = leer(imagen)
    if not lectura:
        return {"ok": False, "motivo": "no pude leer la imagen"}
    if not (lectura.get("titular") or "").strip():
        return {"ok": False, "lectura": lectura,
                "motivo": "la imagen no parece una noticia"}

    candidatos = buscar_original(lectura, dias=dias)
    if not candidatos:
        return {"ok": False, "lectura": lectura,
                "motivo": "no encuentro esta noticia en ninguna fuente verificable"}

    # Solo se escribe solo cuando no hay duda. Ver los dos umbrales arriba.
    if candidatos[0]["parecido"] < PARECIDO_AUTOMATICO:
        return {"ok": False, "lectura": lectura, "candidatos": candidatos[:3],
                "dudoso": True,
                "motivo": "encontré algo parecido, pero no estoy seguro de que "
                          "sea la misma noticia"}

    return {"ok": True, "lectura": lectura, "candidatos": candidatos,
            "url": candidatos[0]["url"], "titular": candidatos[0]["titular"],
            "medio": candidatos[0].get("medio", "")}
