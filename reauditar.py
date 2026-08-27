r"""Vuelve a auditar un borrador despues de editarlo a mano.

    .pyruntime\python.exe reauditar.py ofac-licencias_noticia --manual ofac-licencias

EXISTE PORQUE FALTABA. El auditor solo corria dentro de producir.py, o sea una
sola vez, justo despues de que el modelo escribiera. En cuanto un editor tocaba
el texto -o lo tocaba yo, que es lo que paso el 27/08/2026 con la nota de la
OFAC- la pieza salia a publicar sin que nadie volviera a comprobar las cifras,
las citas ni los guiones largos. La edicion humana es justo el momento en el que
se introducen errores con toda la confianza del mundo.

Lee el borrador de borradores/, reconstruye el paquete de datos de su fuente y
vuelve a pasar las mismas reglas. Reescribe el .json con el veredicto nuevo.
"""

import argparse
import json
import pathlib
import re
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

from dotenv import load_dotenv  # noqa: E402
from motor import auditor  # noqa: E402
from motor.fuentes import banco_mundial, manual  # noqa: E402
from motor.paquete import Cifra, Fuente, Paquete  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

CARPETA = AQUI / "borradores"


def _pieza_desde_texto(ruta_txt, pieza):
    """Relee el texto editado a mano y lo mete de vuelta en los campos.

    El editor trabaja sobre el .txt, no sobre el .json. Si solo se reauditara el
    json, se estaria comprobando la version vieja: exactamente el error que este
    archivo viene a evitar.
    """
    lineas = ruta_txt.read_text(encoding="utf-8").split("\n")
    cuerpo, bloque, sacado, donde = [], [], [], "cuerpo"
    for linea in lineas[1:]:
        s = linea.strip()
        if s.startswith("[Autor]") or s.startswith("[Fecha]"):
            continue
        if s.isupper() and len(s) > 25 and not cuerpo:
            pieza["titulo"] = s
            continue
        if s.startswith("SurEconomics:"):
            donde = "bloque"
            continue
        if s.startswith("Sacado de:"):
            sacado.append(s)
            donde = "pie"
            continue
        if donde == "cuerpo":
            cuerpo.append(linea)
        elif donde == "bloque":
            bloque.append(linea)
    pieza["cuerpo"] = re.sub(r"\n{3,}", "\n\n", "\n".join(cuerpo)).strip()
    pieza["bloque_sureconomics"] = "\n".join(bloque).strip()
    if sacado:
        pieza["sacado_de"] = "\n".join(sacado)
    return pieza


def main():
    ap = argparse.ArgumentParser(description="Reaudita un borrador editado")
    ap.add_argument("borrador", help="nombre sin extension, ej. ofac-licencias_noticia")
    ap.add_argument("--manual", help="fuente registrada a mano que lo origino")
    ap.add_argument("--ranking", help="si venia de un ranking del Banco Mundial")
    ap.add_argument("--encargo", default="")
    args = ap.parse_args()

    ruta_json = CARPETA / f"{args.borrador}.json"
    ruta_txt = CARPETA / f"{args.borrador}.txt"
    if not ruta_json.exists():
        print(f"No encuentro {ruta_json}")
        return 1

    datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    pieza = datos["pieza"]
    if ruta_txt.exists():
        pieza = _pieza_desde_texto(ruta_txt, pieza)

    # PRIMERO el paquete que se guardo con la pieza: es el de verdad, con el
    # expediente incluido. Reconstruirlo desde la fuente pierde las notas
    # relacionadas y hace saltar falsos positivos de cifra inventada.
    if datos.get("paquete"):
        paquete = Paquete(**{k: v for k, v in datos["paquete"].items()
                             if k in Paquete.__dataclass_fields__})
        paquete.cifras = [Cifra(**c) for c in datos["paquete"].get("cifras", [])]
        paquete.fuentes = [Fuente(**f) for f in datos["paquete"].get("fuentes", [])]
    elif args.manual:
        paquete = manual.extraer(args.manual)
    elif args.ranking:
        paquete = banco_mundial.ranking(args.ranking)
    else:
        print("Indica --manual o --ranking: sin el paquete no hay contra que auditar.")
        return 1
    if not paquete:
        return 1

    hallazgos = auditor.auditar(pieza, paquete, args.encargo)
    print(auditor.informe(hallazgos))

    datos["pieza"] = pieza
    datos["bloqueada"] = auditor.bloqueada(hallazgos)
    datos["hallazgos"] = [str(h) for h in hallazgos]
    datos["reauditada"] = True
    ruta_json.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    return 1 if auditor.bloqueada(hallazgos) else 0


if __name__ == "__main__":
    sys.exit(main())
