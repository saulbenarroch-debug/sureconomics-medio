r"""Pone una imagen en una direccion publica, para poder adjuntarla al panel.

    from motor import imagen_publica
    url = imagen_publica.publicar(datos, "portada.png")

POR QUE HACE FALTA ESTO

El panel NO tiene forma de subir un archivo. Comprobado contra la API el
02/09/2026: solo existe POST /admin/media/external, que registra una imagen
POR DIRECCION WEB. No hay endpoint que acepte el binario.

Y la direccion que da Telegram no vale por dos motivos: lleva el token del bot
dentro de la propia URL, asi que publicarla lo expondria en el sitio, y ademas
caduca.

ESTO ES UN APAÑO Y ESTA HECHO PARA QUITARLO. Se sube al repositorio publico, que
ya sirve el JSON del cintillo con CORS abierto. Funciona hoy y no depende de
nadie, pero engorda el repositorio para siempre y es el mismo enlace externo
fragil que ya esta apuntado como pendiente del CMS.

Cuando los desarrolladores añadan el endpoint de subida (se lo pedimos con la
migracion a Cloudflare R2), se cambia SOLO la funcion publicar() y nada mas.
Por eso todo el trato con GitHub vive aqui dentro y no repartido por el codigo.

Se usa la API de contenidos de GitHub y no comandos de git: no hay que clonar,
ni configurar usuario, ni resolver conflictos, y funciona igual desde una
maquina y desde Actions.
"""

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import date

REPO = "saulbenarroch-debug/sureconomics-medio"
CARPETA = "imagenes"
AGENTE = "SurEconomics/1.0 (motor editorial)"


def _ficha():
    """El token con el que se escribe. En Actions llega solo."""
    return (os.environ.get("GITHUB_TOKEN", "")
            or os.environ.get("GITHUB_PAT", "")).strip()


def _extension(datos, nombre):
    if nombre and "." in nombre:
        cola = nombre.rsplit(".", 1)[-1].lower()
        if 2 <= len(cola) <= 4 and cola.isalnum():
            return "." + cola
    # Por los primeros bytes, que es mas fiable que el nombre.
    if datos[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if datos[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"


def publicar(datos, nombre="imagen"):
    """Devuelve la direccion publica de la imagen, o None si no se pudo.

    El nombre lleva la huella del contenido: si la misma imagen se manda dos
    veces, se reutiliza la que ya esta en vez de acumular copias.
    """
    ficha = _ficha()
    if not ficha:
        print("  [imagen] sin GITHUB_TOKEN ni GITHUB_PAT: no puedo publicarla")
        return None

    huella = hashlib.sha256(datos).hexdigest()[:16]
    ruta = "%s/%s-%s%s" % (CARPETA, date.today().isoformat(), huella,
                           _extension(datos, nombre))
    api = "https://api.github.com/repos/%s/contents/%s" % (REPO, ruta)
    cabeceras = {"Authorization": "Bearer " + ficha,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": AGENTE,
                 "Content-Type": "application/json"}

    # Si ya esta (misma imagen, mismo dia), se devuelve la de antes.
    try:
        p = urllib.request.Request(api, headers=cabeceras)
        with urllib.request.urlopen(p, timeout=40) as r:
            ya = json.loads(r.read().decode())
        print("  [imagen] ya estaba publicada, la reutilizo")
        return ya.get("download_url")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print("  [imagen] no pude comprobar si existia: HTTP %s" % e.code)
    except Exception:  # noqa: BLE001
        pass

    cuerpo = json.dumps({
        "message": "Imagen de portada mandada por Telegram [skip ci]",
        "content": base64.b64encode(datos).decode(),
    }).encode()
    try:
        p = urllib.request.Request(api, data=cuerpo, method="PUT", headers=cabeceras)
        with urllib.request.urlopen(p, timeout=90) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("  [imagen] no pude publicarla: HTTP %s %s"
              % (e.code, e.read().decode()[:120]))
        return None
    except Exception as exc:  # noqa: BLE001
        print("  [imagen] no pude publicarla: %s" % str(exc)[:90])
        return None

    url = (d.get("content") or {}).get("download_url")
    print("  [imagen] publicada (%d KB)" % (len(datos) // 1024))
    return url
