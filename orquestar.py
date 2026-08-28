r"""La corrida diaria completa, sin que nadie pida nada.

    .pyruntime\python.exe orquestar.py --piezas 6

Encadena lo que ya existia y funcionaba por separado: recolectar, producir,
auditar, buscar foto, armar la carga, subir borradores y mandar el correo.
Pensado para correr en GitHub Actions a las 12:00 UTC, que son las 8 de la
mañana en Venezuela.

TRES COSAS QUE HACE Y CONVIENE ENTENDER

1. **Se para antes de empezar si no hay con que.** Comprueba la cuota de
   busqueda y la de IA primero. Una corrida que arranca sin cuota no falla: hace
   la mitad del trabajo y deja seis piezas a medio escribir que parecen
   terminadas. Es peor que no correr.

2. **No publica nada.** Todo entra como borrador. Ver la cabecera de subir.py.

3. **Lo bloqueado no se sube, se manda por correo.** Si el auditor tumba una
   pieza, subirla igualmente convierte al auditor en decoracion.

QUE SIGUE NECESITANDO A UNA PERSONA

La foto. El codigo puede exigir que sea de Wikimedia Commons, con autor y
licencia declarados, apaisada y de resolucion suficiente. Lo que no puede
comprobar es si la foto es DEL SITIO del que habla la nota. El 26/08/2026
aparecieron fotos buenisimas de migrantes venezolanos para una nota sobre
Colombia, y eran del cruce entre Ecuador y Colombia. Por eso las piezas quedan
en borrador y el correo llega igual: para que alguien las mire.
"""

import argparse
import datetime
import io
import json
import pathlib
import subprocess
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PYTHON = sys.executable


def correr(argumentos, minutos=25):
    print("  $ " + " ".join(str(a) for a in argumentos[1:]))
    r = subprocess.run([str(a) for a in argumentos], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=minutos * 60)
    return r


def hay_con_que():
    """Cuota antes de arrancar. Ver punto 1 de la cabecera."""
    r = correr([PYTHON, AQUI / "comprobar.py"], minutos=10)
    salida = (r.stdout or "") + (r.stderr or "")
    print(salida[-1200:])
    if "CUOTA AGOTADA" in salida:
        print("\nGemini sin cuota hoy. No se arranca.")
        return False
    if r.returncode != 0:
        print("\nHay algo critico caido. No se arranca.")
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Corrida diaria de SurEconomics")
    ap.add_argument("--piezas", type=int, default=6)
    ap.add_argument("--horas", type=int, default=24)
    ap.add_argument("--correo", default="saul@rendigroup.com")
    ap.add_argument("--sin-subir", action="store_true",
                    help="produce y manda el correo, pero no toca el panel")
    args = ap.parse_args()

    hoy = datetime.date.today().isoformat()
    carpeta = AQUI / ("corrida-" + hoy)
    carpeta.mkdir(exist_ok=True)

    print("=" * 70)
    print("CORRIDA DIARIA  %s   %d piezas" % (hoy, args.piezas))
    print("=" * 70)

    if not hay_con_que():
        return 1

    # 1. Que hay hoy. El orden lo pone criterio.py, que ya puntua y diversifica
    #    por pais para que un solo asunto no cope la jornada.
    print("\n--- 1. RECOLECTAR ---")
    candidatos = carpeta / "candidatos.json"
    r = correr([PYTHON, AQUI / "recolectar.py", "--horas", args.horas,
                "--limite", args.piezas, "--guardar", candidatos])
    print((r.stdout or "")[-900:])
    if not candidatos.exists():
        print("Sin candidatos. Nada que hacer hoy.")
        return 1

    temas = json.loads(candidatos.read_text(encoding="utf-8"))
    print("\n%d temas elegidos:" % len(temas))
    for t in temas:
        print("   - " + str(t.get("titular", t))[:88])

    # 2. Escribir y auditar, una por una. Si una revienta, las demas siguen: una
    #    corrida que se cae entera por un tema es una corrida que no sirve.
    print("\n--- 2. PRODUCIR ---")
    for i, tema in enumerate(temas, 1):
        titular = str(tema.get("titular", ""))[:60]
        print("\n  [%d/%d] %s" % (i, len(temas), titular))
        r = correr([PYTHON, AQUI / "motor" / "producir.py",
                    "--tipo", "Noticia", "--horas", args.horas,
                    "--tema", tema.get("filtro") or titular[:40]])
        cola = (r.stdout or "")[-260:]
        print("     " + cola.replace("\n", "\n     ")[:400])

    # 3. Correo y panel. El correo va SIEMPRE, aunque el panel falle: es el
    #    unico aviso de que la corrida ocurrio.
    print("\n--- 3. ENTREGA ---")
    correr([PYTHON, AQUI / "armar_carga.py"], minutos=10)
    carga = AQUI / "carga-28.json"

    if not args.sin_subir and carga.exists():
        r = correr([PYTHON, AQUI / "subir.py", carga], minutos=20)
        print((r.stdout or "") + (r.stderr or "")[-500:])

    r = correr([PYTHON, AQUI / "enviar.py", carpeta, args.correo], minutos=15)
    print((r.stdout or "") + (r.stderr or "")[-400:])

    print("\nCorrida terminada. Todo queda en borrador.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
