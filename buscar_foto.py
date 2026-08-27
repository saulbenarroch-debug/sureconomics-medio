r"""Busca una foto publicable en Wikimedia Commons, con autor y licencia.

    .pyruntime\python.exe buscar_foto.py "aeropuerto Maiquetia" [--n 5]

Devuelve, por cada candidata, el enlace, el autor, la licencia y el año, y arma
la linea de credito lista para pegar en el campo del panel.

POR QUE COMMONS Y NO UN BUSCADOR DE IMAGENES

Porque aqui la licencia y el autor vienen declarados en el propio registro. Una
imagen encontrada por ahi no se puede publicar aunque se vea bien: si no se sabe
quien la hizo ni bajo que licencia, no hay forma de acreditarla y publicarla es
una infraccion, no un descuido.

LO QUE HAY QUE SABER ANTES DE USAR LO QUE DEVUELVE

1. **Casi todo es de archivo.** Ninguna de estas fotos es del hecho que se
   cuenta. El credito lo dice ("Archivo, 2013") y el pie tiene que decirlo
   tambien, o la foto sugiere que es de ahora.
2. **CC BY-SA y CC BY EXIGEN atribucion por licencia**, no por cortesia. Si el
   panel no guarda el credito, esas fotos no se publican. CC0 y dominio publico
   no lo exigen, pero se acreditan igual.
3. **Que la foto sea del sitio del que se habla.** El 26/08/2026 aparecieron
   fotos buenisimas de migrantes venezolanos para una nota sobre el permiso de
   proteccion en Colombia, y eran del cruce entre Ecuador y Colombia. Un pie de
   foto falso es una noticia falsa mas pequeña.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
AGENTE = "SurEconomics/1.0 (medio de economia; contacto: redaccion@sureconomics.com)"


def _limpio(s):
    """Quita las etiquetas HTML que Commons mete en los metadatos."""
    fuera, dentro = [], False
    for c in str(s or ""):
        if c == "<":
            dentro = True
        elif c == ">":
            dentro = False
        elif not dentro:
            fuera.append(c)
    return " ".join("".join(fuera).split())


def buscar(consulta, n=5, ancho=1600):
    """Candidatas de Commons: [{titulo, url, autor, licencia, anio, credito}]."""
    parametros = {
        "action": "query",
        "generator": "search",
        # filetype:bitmap deja fuera SVG, PDF y mapas vectoriales, que no sirven
        # como foto de apertura.
        "gsrsearch": f"filetype:bitmap {consulta}",
        "gsrnamespace": "6",
        "gsrlimit": str(n),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": str(ancho),
        "format": "json",
    }
    url = API + "?" + urllib.parse.urlencode(parametros)
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=30) as r:
            datos = json.load(r)
    except Exception as exc:  # noqa: BLE001
        print(f"[aviso] Commons no respondio: {exc}")
        return []

    paginas = (datos.get("query") or {}).get("pages") or {}
    salida = []
    for p in paginas.values():
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            continue
        meta = ii.get("extmetadata") or {}
        autor = _limpio((meta.get("Artist") or {}).get("value"))
        licencia = _limpio((meta.get("LicenseShortName") or {}).get("value"))
        anio = _limpio((meta.get("DateTimeOriginal") or {}).get("value"))[:4]
        if licencia.lower().startswith("public domain"):
            licencia = "Dominio público"
        salida.append({
            "titulo": p["title"].replace("File:", ""),
            "url": ii.get("thumburl") or ii.get("url"),
            "autor": autor or "autor no declarado",
            "licencia": licencia or "licencia no declarada",
            "anio": anio if anio.isdigit() else "",
            "exige_credito": licencia.upper().startswith("CC BY"),
        })
    for c in salida:
        c["credito"] = credito(c)
    return salida


def credito(c):
    """La linea que se pega en el campo de credito del panel."""
    inicio = f"Archivo, {c['anio']} · " if c["anio"] else ""
    return f"{inicio}Foto: {c['autor']} · {c['licencia']} · Wikimedia Commons"


def main():
    ap = argparse.ArgumentParser(description="Fotos publicables desde Commons")
    ap.add_argument("consulta", help="que buscar, en ingles suele dar mas")
    ap.add_argument("--n", type=int, default=5)
    args = ap.parse_args()

    candidatas = buscar(args.consulta, n=args.n)
    if not candidatas:
        print("Sin resultados. Prueba otras palabras, o en inglés.")
        return 1
    for i, c in enumerate(candidatas, 1):
        marca = "  [EXIGE CRÉDITO]" if c["exige_credito"] else ""
        print(f"\n{i}. {c['titulo'][:70]}{marca}")
        print(f"   {c['url']}")
        print(f"   {c['credito']}")
    print("\nRecuerda: comprueba que la foto sea DEL SITIO del que habla la pieza.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
