r"""Lanza la corrida diaria en GitHub Actions y trae el resultado.

    .pyruntime\python.exe disparar_diario.py --sin-subir
    .pyruntime\python.exe disparar_diario.py --leer

Igual que disparar_groq.py pero para el workflow del medio. Existe por lo mismo:
para no tener que ir a la web a mirar como fue, y para poder leer el registro
sin gastar otra corrida.
"""

import argparse
import io
import sys
import time
import zipfile
import pathlib
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from crear_repo import _llamar, _token  # noqa: E402

REPO = "saulbenarroch-debug/sureconomics-medio"
FLUJO = "diario.yml"


def _registro(ident):
    peticion = urllib.request.Request(
        "https://api.github.com/repos/%s/actions/runs/%s/logs" % (REPO, ident),
        headers={"Authorization": "Bearer " + _token(),
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "sureconomics-medio"})
    with urllib.request.urlopen(peticion, timeout=120) as resp:
        crudo = resp.read()
    partes = []
    with zipfile.ZipFile(io.BytesIO(crudo)) as z:
        for nombre in sorted(z.namelist()):
            if "/" in nombre:
                continue
            texto = z.read(nombre).decode("utf-8", "replace")
            partes.append("\n".join(l.split(" ", 1)[-1] for l in texto.splitlines()))
    return "\n".join(partes)


def _ultima():
    runs, _ = _llamar("/repos/%s/actions/workflows/%s/runs?per_page=1" % (REPO, FLUJO))
    if "_error" in runs:
        return None
    return (runs.get("workflow_runs") or [{}])[0]


def leer():
    r = _ultima()
    if not r or not r.get("id"):
        print("no hay ejecuciones todavia")
        return 1
    print("ejecucion %s  %s  %s" % (r["id"], r.get("status"), r.get("conclusion")))
    print("web: %s\n" % r.get("html_url"))
    if r.get("status") != "completed":
        print("aun corriendo")
        return 0
    try:
        texto = _registro(r["id"])
    except Exception as exc:  # noqa: BLE001
        print("no pude bajar el registro: %s" % str(exc)[:90])
        return 1
    for linea in texto.splitlines():
        s = linea.strip()
        if not s or s.startswith(("##", "\x1b[36", "shell:", "env:", "Requirement",
                                  "Download", "Collecting", "Using cached")):
            continue
        print("  " + s[:150])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-subir", action="store_true", default=True)
    ap.add_argument("--piezas", default="6")
    ap.add_argument("--leer", action="store_true")
    a = ap.parse_args()
    if a.leer:
        return leer()

    antes = (_ultima() or {}).get("id")
    r, _ = _llamar("/repos/%s/actions/workflows/%s/dispatches" % (REPO, FLUJO), "POST",
                   {"ref": "main",
                    "inputs": {"piezas": a.piezas,
                               "sin_subir": "true" if a.sin_subir else "false"}})
    if isinstance(r, dict) and r.get("_error") not in (None, 204):
        print("no pude lanzarlo: HTTP %s %s" % (r["_error"], r["_detalle"][:160]))
        return 1
    print("lanzado (piezas=%s, sin_subir=%s). Puede tardar bastante." % (
        a.piezas, a.sin_subir))
    for _ in range(4):
        time.sleep(12)
        actual = _ultima() or {}
        if actual.get("id") and actual["id"] != antes:
            print("corriendo: %s" % actual.get("html_url"))
            return 0
    print("aun no aparece. Miralo en github.com/%s/actions" % REPO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
