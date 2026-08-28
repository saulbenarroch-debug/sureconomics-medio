r"""Consulta la ficha de una foto de Commons: licencia, autor, fecha y tamaño.

    .pyruntime\python.exe ver_licencia.py "File:Nepal China Border.JPG"

buscar_foto.py ya devuelve el credito, pero cuando la foto viene de un medio
estatal o de una agencia conviene mirar la ficha entera antes de publicar: esas
son las que mas a menudo estan mal etiquetadas en Commons, y publicar una foto
con la licencia equivocada no lo arregla despues una fe de erratas.
"""

import io
import json
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://commons.wikimedia.org/w/api.php"
AGENTE = "SurEconomics/1.0 (redaccion; contacto via sureconomics.com)"


def ficha(titulo):
    consulta = urllib.parse.urlencode({
        "action": "query", "prop": "imageinfo",
        "iiprop": "extmetadata|url|size", "titles": titulo, "format": "json"})
    peticion = urllib.request.Request(API + "?" + consulta,
                                      headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=30) as r:
        datos = json.load(r)

    for pagina in datos.get("query", {}).get("pages", {}).values():
        if "imageinfo" not in pagina:
            print("### %s\n  NO EXISTE en Commons\n" % titulo)
            continue
        info = pagina["imageinfo"][0]
        meta = info.get("extmetadata", {})

        def campo(clave):
            valor = (meta.get(clave, {}).get("value") or "")
            return valor.replace("<", "[").replace(">", "]").strip()

        print("### %s" % titulo)
        print("  licencia : %s" % (campo("LicenseShortName") or "?"))
        print("  autor    : %s" % (campo("Artist")[:110] or "?"))
        print("  fuente   : %s" % (campo("Credit")[:110] or "?"))
        print("  fecha    : %s" % (campo("DateTimeOriginal")[:40] or "?"))
        print("  aviso    : %s" % (campo("Restrictions") or "sin restricciones"))
        print("  tamaño   : %s x %s" % (info.get("width"), info.get("height")))
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for t in sys.argv[1:]:
        ficha(t)
