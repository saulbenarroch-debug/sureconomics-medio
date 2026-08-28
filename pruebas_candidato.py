r"""Comprueba que un Paquete sobrevive el viaje de ida y vuelta por disco.

    .pyruntime\python.exe pruebas_candidato.py

recolectar.py guarda los candidatos como JSON y producir.py --paquete los vuelve
a levantar. Si en ese viaje las cifras o las fuentes quedan como diccionarios en
vez de objetos, la cadena revienta mas adelante con AttributeError, ya con la
llamada a la IA gastada. Aqui se comprueba antes y sin gastar nada.
"""

import io
import json
import pathlib
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from motor.paquete import Cifra, Fuente, Paquete  # noqa: E402
from motor.producir import _leer_candidato  # noqa: E402

fallos = []


def revisar(condicion, texto):
    print(("  OK  " if condicion else "FALLA ") + texto)
    if not condicion:
        fallos.append(texto)


def main():
    fuente = Fuente(id="F1", institucion="Folha de S.Paulo",
                    documento="Orçamento de 2027",
                    url="https://www1.folha.uol.com.br/mercado/2026/08/nota.shtml")
    original = Paquete(
        hecho="Governo vai prever superavit efetivo de R$ 18 bi no Orcamento de 2027",
        fecha_hecho="2026-08-28",
        cifras=[Cifra(clave="superavit_2027", valor="18", valor_crudo=18.0,
                      unidad="mil millones de reales", periodo="2027",
                      fuente_id="F1")],
        fuentes=[fuente])

    with tempfile.TemporaryDirectory() as tmp:
        ruta = pathlib.Path(tmp) / "candidatos.json"
        ruta.write_text(json.dumps([json.loads(original.a_json())],
                                   ensure_ascii=False), encoding="utf-8")
        vuelto = _leer_candidato(ruta, 0)

        revisar(vuelto is not None, "se lee el candidato")
        if vuelto is None:
            return 1
        revisar(vuelto.hecho == original.hecho, "el hecho llega intacto")
        revisar(len(vuelto.cifras) == 1, "llega la cifra")
        revisar(isinstance(vuelto.cifras[0], Cifra),
                "la cifra es un objeto Cifra, no un diccionario")
        revisar(vuelto.cifras[0].valor_crudo == 18.0, "el valor de la cifra se conserva")
        revisar(isinstance(vuelto.fuentes[0], Fuente),
                "la fuente es un objeto Fuente, no un diccionario")
        revisar(vuelto.fuentes[0].url == fuente.url, "la url llega intacta")
        # Acceso por atributo: es lo que hacen auditor y redactor mas adelante.
        revisar(vuelto.fuentes[0].institucion == "Folha de S.Paulo",
                "se puede acceder por atributo, como hace el resto de la cadena")
        # Pedir un indice que no existe no puede reventar: en una corrida
        # automatica significa que el recolector trajo menos de lo pedido.
        revisar(_leer_candidato(ruta, 9) is None,
                "un indice fuera de rango devuelve None en vez de reventar")

    print("\n" + ("TODO EN VERDE" if not fallos else "%d FALLO(S)" % len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
