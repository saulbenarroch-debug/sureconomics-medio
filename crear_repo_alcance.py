r"""Que alcanza el token de GitHub que hay en el .env.

    .pyruntime\python.exe crear_repo_alcance.py

Un token de permisos finos no dice lo que puede hacer hasta que se lo pides.
Esto lo pregunta sin adivinar: a que repositorios llega y si puede escribir en
ellos. Nunca imprime el token.
"""

import sys
import pathlib

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

# OJO: no se vuelve a envolver sys.stdout aqui. crear_repo ya lo envuelve al
# importarlo, y dos envoltorios sobre el mismo buffer lo cierran en cuanto el
# primero se recoge: "I/O operation on closed file" sin tocar ningun archivo.
from crear_repo import _llamar  # noqa: E402


def main():
    yo, cabeceras = _llamar("/user")
    print("cuenta del token: %s  (%s)" % (yo.get("login"), yo.get("name") or "sin nombre"))

    # GitHub devuelve la caducidad en una cabecera. Importa antes de ponerse a
    # editar permisos: si al token le quedan dias, se edita hoy y se rehace la
    # semana que viene, que es tocar lo mismo dos veces.
    caduca = cabeceras.get("github-authentication-token-expiration")
    print("caduca          : %s" % (caduca or "(no lo declara: puede no caducar)"))

    repos, _ = _llamar("/installation/repositories")
    if isinstance(repos, dict) and "repositories" in repos:
        lista = repos["repositories"]
    else:
        lista, _ = _llamar("/user/repos?per_page=100&affiliation=owner")
        if isinstance(lista, dict) and "_error" in lista:
            print("no pude listar repositorios: HTTP %s" % lista["_error"])
            return 1

    print("\nrepositorios a los que llega (%d):" % len(lista))
    for r in lista[:30]:
        permisos = r.get("permissions") or {}
        print("  %-42s privado:%-5s escritura:%s" % (
            r.get("full_name"), r.get("private"), permisos.get("push")))

    print("\norganizaciones visibles:")
    orgs, _ = _llamar("/user/orgs")
    if isinstance(orgs, list) and orgs:
        for o in orgs:
            print("  " + o.get("login", "?"))
    else:
        print("  (ninguna)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
