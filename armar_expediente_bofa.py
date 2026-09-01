r"""Arma el expediente de la noticia de Times Square y la vuelve a auditar.

    .pyruntime\python.exe armar_expediente_bofa.py

POR QUE A MANO. El extractor busca cifras economicas y en un suceso no encontro
ninguna: el paquete salio con cero cifras y una sola fuente. El auditor bloqueo,
y hacia bien, porque las edades, la hora y la calle son numeros que el texto
afirma y el expediente no respalda.

La respuesta correcta no es saltarse al auditor, es darle el expediente que le
falta. Cada numero de la nota queda aqui atado a la fuente concreta donde se
comprobo, y las tres fuentes quedan registradas.

DISCREPANCIA ANOTADA: Fortune situa el ataque en la calle 41 Oeste; Al Jazeera y
Fox Business, en la 42. Se publica la 42, que es lo que dicen dos fuentes
independientes, y queda escrito aqui para que se pueda revisar.

Se borra cuando el extractor sepa hacer esto solo.
"""

import json
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from motor import auditor  # noqa: E402
from motor.paquete import Cifra, Fuente, Paquete  # noqa: E402

BORRADOR = AQUI / "borradores" / "bank-of-america-vice-president-identif_noticia"

FUENTES = [
    Fuente(id="fortune", institucion="Fortune",
           documento="Bank of America vice president identified as victim in random Times Square stabbing",
           url="https://fortune.com/2026/09/01/bank-of-america-vice-president-identified-as-victim-in-random-times-square-stabbing/"),
    Fuente(id="aljazeera", institucion="Al Jazeera",
           documento="Bank of America vice president identified as victim in Times Square attack",
           url="https://www.aljazeera.com/news/2026/9/1/bank-of-america-vice-president-identified-as-killed-in-times-square-attack"),
    Fuente(id="foxbusiness", institucion="Fox Business",
           documento="Bank of America VP killed in Times Square stabbing",
           url="https://www.foxbusiness.com/fox-news-us/bank-america-vp-killed-times-square-stabbing-attack"),
]

CIFRAS = [
    Cifra(clave="edad_victima", valor="32", unidad="años",
          periodo="31/08/2026", fuente_id="fortune", valor_crudo=32,
          nota="Erin Piacenti, identificada por la policia de Nueva York"),
    Cifra(clave="edad_segundo_herido", valor="68", unidad="años",
          periodo="31/08/2026", fuente_id="foxbusiness", valor_crudo=68,
          nota="hospitalizado en condicion estable"),
    Cifra(clave="edad_agresora", valor="49", unidad="años",
          periodo="31/08/2026", fuente_id="foxbusiness", valor_crudo=49,
          nota="Pamela Cisneros, de Queens"),
    Cifra(clave="hora_ataque", valor="4", unidad="de la tarde",
          periodo="31/08/2026", fuente_id="aljazeera", valor_crudo=4,
          nota="Al Jazeera dice 'about 4:30pm'; Fortune precisa las 4:24 pm"),
    Cifra(clave="minuto_ataque", valor="30", unidad="minutos",
          periodo="31/08/2026", fuente_id="aljazeera", valor_crudo=30,
          nota="ver hora_ataque"),
    Cifra(clave="calle", valor="42", unidad="calle Oeste",
          periodo="31/08/2026", fuente_id="aljazeera", valor_crudo=42,
          nota="Al Jazeera y Fox Business dicen 42; Fortune dice 41"),
]


def main():
    d = json.loads((BORRADOR.with_suffix(".json")).read_text(encoding="utf-8"))

    paq = Paquete(
        hecho="Muere apuñalada en Times Square una empleada de Bank of America",
        fecha_hecho="2026-08-31", cifras=CIFRAS, fuentes=FUENTES)

    problemas = [p for f in FUENTES for p in f.problemas()]
    print("fuentes con problemas: %s" % (problemas or "ninguna"))

    lineas = [l for l in BORRADOR.with_suffix(".txt").read_text(
        encoding="utf-8").split(chr(10)) if l.strip()]
    pieza = dict(d["pieza"])
    pieza["titulo"] = lineas[1]
    pieza["cuerpo"] = (chr(10) * 2).join(
        l for l in lineas[3:] if not l.startswith(("Sacado de:", "Perecedero")))

    hallazgos = auditor.auditar(pieza, paq)
    print(auditor.informe(hallazgos))
    bloqueada = auditor.bloqueada(hallazgos)
    print(chr(10) + "BLOQUEADA: %s" % bloqueada)

    d["pieza"] = pieza
    d["paquete"] = {"hecho": paq.hecho, "fecha_hecho": paq.fecha_hecho,
                    "cifras": [c.__dict__ for c in CIFRAS],
                    "fuentes": [f.__dict__ for f in FUENTES]}
    d["bloqueada"] = bloqueada
    d["hallazgos"] = [h.__dict__ for h in hallazgos]
    BORRADOR.with_suffix(".json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if bloqueada else 0


if __name__ == "__main__":
    sys.exit(main())
