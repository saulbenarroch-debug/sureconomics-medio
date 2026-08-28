r"""Comprueba que la carga se puede pegar en el navegador sin romperse.

    .pyruntime\python.exe revisar_carga.py

El texto viaja al panel dentro de una plantilla de JavaScript. Tres caracteres
la parten por la mitad: el acento invertido, la apertura de interpolacion y la
barra invertida. Si alguno aparece en una pieza, hay que escaparlo ANTES, no
descubrirlo cuando el formulario se queda a medias.
"""

import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PELIGROSOS = {"acento invertido": chr(96),
              "interpolacion": "$" + "{",
              "barra invertida": chr(92)}


def main():
    with open("carga-28.json", encoding="utf-8") as f:
        carga = json.load(f)

    conflictos = 0
    for pieza in carga:
        texto = pieza["cuerpo_html"] + pieza["titulo"] + pieza["resumen_html"]
        for nombre, token in PELIGROSOS.items():
            if token in texto:
                print("OJO  %s lleva %s" % (pieza["origen"], nombre))
                conflictos += 1

    total = sum(len(p["cuerpo_html"]) + len(p["resumen_html"]) for p in carga)
    print("conflictos de sintaxis: %d" % conflictos)
    print("a transferir: %d caracteres en %d piezas" % (total, len(carga)))
    return 1 if conflictos else 0


if __name__ == "__main__":
    sys.exit(main())
