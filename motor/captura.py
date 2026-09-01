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


# Cuanto tiene que parecerse el candidato al titular de la captura. Sale de
# medirlo, igual que el umbral de memoria.py: ver la prueba del 01/09/2026 en
# pruebas_captura.py. Es MAS EXIGENTE que el de duplicados (0.31) a proposito:
# alli equivocarse significa no publicar algo nuevo, aqui significa publicar una
# noticia distinta de la que mandaron.
PARECIDO_MINIMO = 0.45


def _es_portada(url):
    from urllib.parse import urlparse
    p = urlparse(url or "")
    return p.scheme in ("http", "https") and p.path.strip("/") == "" and not p.query


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
    crudos = []
    try:
        from motor.fuentes import noticias
        for paq in noticias.extraer(horas=max(24, dias * 24 // 8), limite=60):
            f = paq.fuentes[0] if paq.fuentes else None
            if f and f.url:
                crudos.append({"titular": paq.hecho, "url": f.url,
                               "medio": f.institucion, "fecha": paq.fecha_hecho,
                               "extracto": "", "via": "feed"})
    except Exception as exc:  # noqa: BLE001
        print("  [aviso] no pude leer los feeds (%s); voy al buscador" % str(exc)[:70])

    crudos += buscador.buscar(consulta, dias=dias, maximo=8, solo_lista_blanca=True)
    # Segundo intento con el titular entero: "busqueda" son palabras sueltas y
    # a veces el titular literal encuentra lo que ellas no.
    if titular:
        crudos += buscador.buscar(titular[:120], dias=dias, maximo=8,
                                  solo_lista_blanca=True)

    vistos, buenos = set(), []
    for c in crudos:
        url = c.get("url") or ""
        if url in vistos or _es_portada(url):
            continue
        vistos.add(url)
        p = memoria.parecido(titular, c.get("titular", "")) if titular else 0.0
        if p >= umbral:
            c = dict(c)
            c["parecido"] = round(p, 3)
            buenos.append(c)
    buenos.sort(key=lambda c: -c["parecido"])
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
    return {"ok": True, "lectura": lectura, "candidatos": candidatos,
            "url": candidatos[0]["url"], "titular": candidatos[0]["titular"],
            "medio": candidatos[0].get("medio", "")}
