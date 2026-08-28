r"""Crea el repositorio en GitHub y deja el remoto puesto.

    .pyruntime\python.exe crear_repo.py --ver
    .pyruntime\python.exe crear_repo.py --crear

Existe porque `gh` no esta instalado en esta maquina y el token vive en el .env
del bot de Telegram. NUNCA imprime el token: solo su huella y sus permisos, que
es lo que hace falta para saber si sirve.

EL REPOSITORIO SE CREA PRIVADO. No es una preferencia: aqui dentro estan las
rutas de la API del medio, la logica editorial y los nombres de los secretos
del workflow. Nada de eso es un secreto por si mismo, pero junto es un mapa de
como entrar. Publico se puede poner despues con un clic; lo que no se puede es
des-publicar algo que ya indexo alguien.
"""

import argparse
import hashlib
import io
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

API = "https://api.github.com"
NOMBRE = "sureconomics-medio"
DESCRIPCION = ("Motor editorial de SurEconomics: recoleccion, redaccion, "
               "auditoria determinista y publicacion en borrador.")


def _token():
    t = os.environ.get("GITHUB_PAT", "").strip()
    if not t:
        raise SystemExit("No hay GITHUB_PAT en el .env")
    return t


def _llamar(ruta, metodo="GET", cuerpo=None):
    t = _token()
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    p = urllib.request.Request(
        API + ruta, data=datos, method=metodo,
        headers={"Authorization": "Bearer " + t,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "sureconomics-medio"})
    try:
        with urllib.request.urlopen(p, timeout=45) as r:
            return json.loads(r.read().decode() or "{}"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_detalle": e.read().decode()[:280]}, dict(e.headers)


def ver():
    huella = hashlib.sha256(_token().encode()).hexdigest()[:8]
    print("huella del token: %s  (no es el token, es su hash)" % huella)
    yo, cab = _llamar("/user")
    if "_error" in yo:
        print("El token NO sirve: HTTP %s %s" % (yo["_error"], yo["_detalle"][:120]))
        return 1
    print("cuenta          : %s" % yo.get("login"))
    print("permisos        : %s" % (cab.get("x-oauth-scopes") or "(token fino, permisos por repo)"))

    existe, _ = _llamar("/repos/%s/%s" % (yo["login"], NOMBRE))
    print("¿ya existe %s? : %s" % (NOMBRE, "NO" if existe.get("_error") == 404 else "SI, cuidado"))
    return 0


def crear():
    yo, _ = _llamar("/user")
    if "_error" in yo:
        print("El token no sirve.")
        return 1
    r, _ = _llamar("/user/repos", "POST", {
        "name": NOMBRE,
        "description": DESCRIPCION,
        "private": True,          # Ver la cabecera de este archivo.
        "auto_init": False,
        "has_issues": True,
        "has_wiki": False,
    })
    if "_error" in r:
        print("No se pudo crear: HTTP %s %s" % (r["_error"], r["_detalle"]))
        return 1
    print("creado: %s" % r.get("full_name"))
    print("privado: %s" % r.get("private"))
    print("remoto : %s" % r.get("ssh_url"))
    print("web    : %s" % r.get("html_url"))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--crear", action="store_true")
    a = ap.parse_args()
    sys.exit(crear() if a.crear else ver())
