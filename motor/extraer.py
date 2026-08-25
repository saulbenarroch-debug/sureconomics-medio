"""Linea de comandos del extractor (A4).

    python -m motor.extraer --pais VEN --indicador inflacion
    python -m motor.extraer --pais MEX --indicador pib --guardar paquetes/

Imprime el paquete de datos en JSON y su validacion. Es el unico paso que habla
con el mundo exterior: de aqui en adelante, nadie vuelve a buscar un numero.
"""

import argparse
import pathlib
import sys

# El Python portatil de .pyruntime es "embeddable": trae un ._pth que ignora
# PYTHONPATH y no agrega la carpeta del script a sys.path, asi que sin esto no
# encuentra el paquete 'motor'. Mismo arreglo que en wallstreet-bot/boletin.py.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motor.fuentes import banco_mundial  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Extractor de cifras verificadas")
    ap.add_argument("--pais", required=True, help="codigo ISO3, ej. VEN, MEX, COL")
    ap.add_argument("--indicador", required=True,
                    help=f"uno de: {', '.join(banco_mundial.INDICADORES)}")
    ap.add_argument("--observaciones", type=int, default=3,
                    help="cuantos años recientes traer (por defecto 3)")
    ap.add_argument("--guardar", help="carpeta donde escribir el paquete")
    args = ap.parse_args()

    paquete = banco_mundial.extraer(args.pais, args.indicador, args.observaciones)
    if paquete is None:
        print("\nNo se produjo paquete. No hay nada que redactar.")
        return 1

    problemas = paquete.validar()
    print(paquete.a_json())

    if paquete.advertencias:
        print("\nADVERTENCIAS (el redactor tiene que respetarlas):")
        for a in paquete.advertencias:
            print(f"  ! {a}")

    if problemas:
        print("\nPAQUETE INVALIDO:")
        for p in problemas:
            print(f"  x {p}")
        return 1

    print("\nPaquete valido: "
          f"{len(paquete.cifras)} cifras, {len(paquete.fuentes)} fuente(s).")

    if args.guardar:
        carpeta = pathlib.Path(args.guardar)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{args.pais.lower()}_{args.indicador}.json"
        destino.write_text(paquete.a_json(), encoding="utf-8")
        print(f"Guardado en {destino}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
