r"""Dispara el workflow "Comprobar Groq" y trae su resultado.

    .pyruntime\python.exe disparar_groq.py

Groq bloquea las IP de VPN, y el dueño trabaja con VPN: desde esta maquina
siempre da 403 de red y no se puede saber nada. El workflow del bot de Telegram
corre desde una IP limpia y ya hace la comprobacion completa, incluido el modo
JSON que el medio necesita. Esto solo lo lanza y espera.

Es de SOLO LECTURA: consulta modelos y pide una respuesta minima. No manda nada
a Telegram ni cambia ningun estado.
"""

import io
import sys
import time
import zipfile
import pathlib
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from crear_repo import _llamar, _token  # noqa: E402

REPO = "saulbenarroch-debug/telegram-finance-bot"
FLUJO = "comprobar-groq.yml"


def _registro(ident):
    peticion = urllib.request.Request(
        "https://api.github.com/repos/%s/actions/runs/%s/logs" % (REPO, ident),
        headers={"Authorization": "Bearer " + _token(),
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "sureconomics-medio"})
    with urllib.request.urlopen(peticion, timeout=90) as resp:
        crudo = resp.read()
    partes = []
    with zipfile.ZipFile(io.BytesIO(crudo)) as z:
        for nombre in sorted(z.namelist()):
            if "/" in nombre:
                continue
            texto = z.read(nombre).decode("utf-8", "replace")
            partes.append("\n".join(l.split(" ", 1)[-1] for l in texto.splitlines()))
    return "\n".join(partes)


def leer_ultimo():
    """Lee la ultima ejecucion SIN volver a lanzarla.

    Se separo porque cada llamada a main() disparaba una corrida nueva, y para
    releer un resultado no hace falta gastar otra.
    """
    runs, _ = _llamar("/repos/%s/actions/workflows/%s/runs?per_page=1" % (REPO, FLUJO))
    r = (runs.get("workflow_runs") or [{}])[0]
    if not r.get("id"):
        print("no hay ejecuciones")
        return 1
    print("ejecucion %s  %s  %s\n" % (r["id"], r.get("status"), r.get("conclusion")))
    texto = _registro(r["id"])
    interesa = ("GET /models", "FUNCIONA", "Modelos disponibles", "RESULTADO",
                "Fin de la prueba", "clave no vale", "Bloqueo por RED", "huella")
    for linea in texto.splitlines():
        s = linea.strip()
        if not s or s.startswith(("##", "\x1b", "shell:", "env:")):
            continue
        if any(k in s for k in interesa) or (
                "/" in s and len(s) < 46 and " " not in s and not s.startswith("http")):
            print("  " + s)
    return 0


def main():
    if "--leer" in sys.argv:
        return leer_ultimo()
    antes, _ = _llamar("/repos/%s/actions/workflows/%s/runs?per_page=1" % (REPO, FLUJO))
    if "_error" in antes:
        print("No puedo ver las ejecuciones: HTTP %s" % antes["_error"])
        print("Al token le falta el permiso 'Actions'. Lo puedes lanzar tu a mano:")
        print("  github.com/%s/actions -> Comprobar Groq -> Run workflow" % REPO)
        return 1
    ultimo = (antes.get("workflow_runs") or [{}])[0].get("id")

    r, _ = _llamar("/repos/%s/actions/workflows/%s/dispatches" % (REPO, FLUJO),
                   "POST", {"ref": "main"})
    if isinstance(r, dict) and r.get("_error") not in (None, 204):
        print("No pude dispararlo: HTTP %s %s" % (r["_error"], r["_detalle"][:120]))
        print("Lanzalo tu: github.com/%s/actions" % REPO)
        return 1
    print("lanzado. esperando...")

    ident = None
    for _ in range(40):
        time.sleep(9)
        runs, _ = _llamar("/repos/%s/actions/workflows/%s/runs?per_page=1" % (REPO, FLUJO))
        actual = (runs.get("workflow_runs") or [{}])[0]
        if actual.get("id") and actual["id"] != ultimo:
            ident = actual["id"]
            if actual.get("status") == "completed":
                print("terminado: %s\n" % actual.get("conclusion"))
                break
            print("  %s..." % actual.get("status"))
    if not ident:
        print("no arranco a tiempo. Miralo en github.com/%s/actions" % REPO)
        return 1

    peticion = urllib.request.Request(
        "https://api.github.com/repos/%s/actions/runs/%s/logs" % (REPO, ident),
        headers={"Authorization": "Bearer " + _token(),
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "sureconomics-medio"})
    try:
        with urllib.request.urlopen(peticion, timeout=90) as resp:
            crudo = resp.read()
    except Exception as exc:  # noqa: BLE001
        print("no pude bajar el registro: %s" % str(exc)[:90])
        print("Miralo en github.com/%s/actions/runs/%s" % (REPO, ident))
        return 1

    with zipfile.ZipFile(io.BytesIO(crudo)) as z:
        for nombre in sorted(z.namelist()):
            if "/" in nombre:
                continue
            texto = z.read(nombre).decode("utf-8", "replace")
            limpio = "\n".join(l.split(" ", 1)[-1] for l in texto.splitlines())
            print("===== %s" % nombre)
            print(limpio[:2400])
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
