r"""Empaqueta el respaldo de imagenes para mandarselo a los desarrolladores.

    .pyruntime\python.exe armar_zip_imagenes.py

SIN COMPRESION (ZIP_STORED) A PROPOSITO. Son JPG y PNG, que ya vienen
comprimidos: deflate tardaria varios minutos para ahorrar un uno por ciento. Lo
que se quiere aqui es un solo archivo, no un archivo pequeño.

Se ordena en dos carpetas porque son dos casos distintos y el que los reciba
tiene que notar la diferencia:

  assets/    el nombre es el ID DEL ASSET      (0181.jpg  -> asset 181)
  sin-asset/ el nombre es el ID DE LA PIEZA    (post0105.png -> post 105)

Al terminar comprueba que lo que quedo dentro del zip coincide con lo que hay en
los inventarios. Un respaldo que nadie verifica no es un respaldo.
"""

import json
import pathlib
import sys
import zipfile

AQUI = pathlib.Path(__file__).resolve().parent
ORIGEN = AQUI / "respaldo-imagenes"
DESTINO = AQUI / "sureconomics-imagenes-para-R2.zip"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    if not ORIGEN.exists():
        print("No encuentro %s. Corre antes respaldo_imagenes.py." % ORIGEN)
        return 1

    assets = sorted(p for p in ORIGEN.glob("*.*") if p.suffix != ".md"
                    and p.name != "registro.json" and p.name != "mapa-portadas.json")
    sueltas = sorted((ORIGEN / "sin-asset").glob("*.*"))
    sueltas = [p for p in sueltas if p.name != "registro.json"]

    print("empaquetando: %d assets + %d sin-asset" % (len(assets), len(sueltas)))

    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_STORED) as z:
        z.write(ORIGEN / "LEEME.md", "LEEME.md")
        z.write(ORIGEN / "mapa-portadas.json", "mapa-portadas.json")
        z.write(ORIGEN / "registro.json", "assets/registro.json")
        z.write(ORIGEN / "sin-asset" / "registro.json", "sin-asset/registro.json")
        for p in assets:
            z.write(p, "assets/" + p.name)
        for p in sueltas:
            z.write(p, "sin-asset/" + p.name)

    # Comprobar contra los inventarios, no contra lo que yo creo que meti.
    with zipfile.ZipFile(DESTINO) as z:
        dentro = set(z.namelist())
        malos = z.testzip()

    reg = json.loads((ORIGEN / "registro.json").read_text(encoding="utf-8"))
    reg2 = json.loads((ORIGEN / "sin-asset" / "registro.json").read_text(encoding="utf-8"))
    faltan = [r["archivo"] for r in reg if "assets/" + r["archivo"] not in dentro]
    faltan += [r["archivo"] for r in reg2 if "sin-asset/" + r["archivo"] not in dentro]

    mapa = json.loads((ORIGEN / "mapa-portadas.json").read_text(encoding="utf-8"))
    porArchivo = {r["asset"]: r["archivo"] for r in reg}
    sinRespaldo = [a for a in set(mapa["post_a_asset"].values())
                   if "assets/" + porArchivo.get(a, "?") not in dentro]

    mb = DESTINO.stat().st_size / 1048576
    print()
    print("=" * 62)
    print("%s" % DESTINO.name)
    print("  %.1f MB, %d archivos dentro" % (mb, len(dentro)))
    print("  zip integro          : %s" % ("si" if malos is None else "NO: " + str(malos)))
    print("  del inventario faltan: %s" % (faltan or "ninguno"))
    print("  portadas en uso sin respaldo dentro: %s" % (sinRespaldo or "ninguna"))
    print("=" * 62)
    if mb > 25:
        print("\nMas de 25 MB: no cabe en un correo. Va por WeTransfer, Drive")
        print("o un enlace de descarga.")
    return 0 if (malos is None and not faltan and not sinRespaldo) else 1


if __name__ == "__main__":
    sys.exit(main())
