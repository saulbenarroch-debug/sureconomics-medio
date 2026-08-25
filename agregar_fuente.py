r"""Registra una fuente verificada a mano, sin escribir JSON.

    .pyruntime\python.exe agregar_fuente.py mi-nota.txt

El periodista abre la nota en el navegador, copia el texto y lo pega en un
archivo de texto con cuatro datos arriba. Nada mas. El script saca solo las
citas textuales, las cifras y el titular, y deja la fuente lista para usar.

FORMATO DEL ARCHIVO (crealo con el Bloc de notas):

    url: https://ultimasnoticias.com.ve/politica/jorge-rodriguez-es-falso...
    medio: Últimas Noticias
    fecha: 2026-08-21
    autor: Aura Torrealba
    declarante: Jorge Rodríguez

    El presidente de la Asamblea Nacional, Jorge Rodríguez, anunció que...
    «La noticia es tan descabellada, tan absurda...», enfatizó.

Obligatorios: url, medio, fecha. Los demas se pueden omitir.

POR QUE HACE FALTA
Las fuentes mas valiosas no se dejan leer por maquina. Comprobado el 25/08/2026
desde GitHub Actions, con IP limpia: el FMI, el DANE, el BID, El Economista y
Ultimas Noticias devuelven 403 igual. No es la VPN ni el servidor: bloquean
lectores automaticos y punto. Asi que este canal no es un parche mientras llega
algo mejor, es la unica via para esas fuentes.
"""

import json
import pathlib
import re
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

DESTINO = AQUI / "fuentes_manuales"
# Comillas de todo tipo: al copiar de un navegador vienen tipograficas.
CITA = re.compile("[«\"“]([^»\"”]{25,400})[»\"”]")


def _partes(texto):
    """Separa la cabecera (clave: valor) del cuerpo."""
    cabecera, cuerpo, en_cabecera = {}, [], True
    for linea in texto.splitlines():
        if en_cabecera:
            m = re.match(r"\s*(url|medio|fecha|autor|declarante|titulo)\s*:\s*(.+)",
                         linea, re.IGNORECASE)
            if m:
                cabecera[m.group(1).lower()] = m.group(2).strip()
                continue
            if not linea.strip():
                continue
            en_cabecera = False
        cuerpo.append(linea)
    return cabecera, "\n".join(cuerpo).strip()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    origen = pathlib.Path(sys.argv[1])
    if not origen.exists():
        print(f"No encuentro {origen}")
        return 1

    cabecera, cuerpo = _partes(origen.read_text(encoding="utf-8-sig"))

    faltan = [c for c in ("url", "medio", "fecha") if not cabecera.get(c)]
    if faltan:
        print(f"Falta en la cabecera: {', '.join(faltan)}")
        print("\nLa cabecera va arriba del todo, una por línea:")
        print("  url: https://...\n  medio: Nombre del diario\n  fecha: 2026-08-21")
        return 1
    if len(cuerpo) < 80:
        print("El cuerpo está vacío o es muy corto. Pega el texto de la nota "
              "debajo de la cabecera.\nUn resumen de memoria no vale: hay que "
              "traer el texto, que es contra lo que el auditor comprueba las citas.")
        return 1

    # Las citas textuales se sacan solas: son lo que va entre comillas.
    citas = [re.sub(r"\s+", " ", c).strip() for c in CITA.findall(cuerpo)]

    # El titular: el de la cabecera, o la primera frase del cuerpo.
    titulo = cabecera.get("titulo") or re.split(r"(?<=[.!?])\s", cuerpo)[0][:160]

    d = {
        "hecho": titulo,
        "titulo": titulo,
        "fecha": cabecera["fecha"],
        "medio": cabecera["medio"],
        "url": cabecera["url"],
        "texto": cuerpo,
        "citas": citas,
    }
    for opcional in ("autor", "declarante"):
        if cabecera.get(opcional):
            d[opcional] = cabecera[opcional]

    DESTINO.mkdir(exist_ok=True)
    nombre = re.sub(r"[^a-z0-9]+", "-", origen.stem.lower()).strip("-")
    salida = DESTINO / f"{nombre}.json"
    salida.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Registrada: {cabecera['medio']}, {cabecera['fecha']}")
    print(f"  titular : {titulo[:70]}")
    print(f"  citas   : {len(citas)} textual(es)")
    print(f"  texto   : {len(cuerpo)} caracteres")
    print(f"  guardada: {salida}")
    print(f"\nYa se puede usar:  --contexto manual:{nombre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
