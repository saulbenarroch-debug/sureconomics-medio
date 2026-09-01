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

La foto, y por eso NO se pone sola salvo que se pida con --con-foto.

Las reglas de motor/foto.py si saben comprobar el LUGAR: descartan Melbourne
para una nota sobre España y Boston para una sobre Brasil. Lo que no saben es si
la foto ilustra el ASUNTO. Probadas contra las cinco piezas de la corrida del
28/08/2026, dos recibieron imagen y una era el Museu do Ipiranga encabezando una
nota sobre morosidad bancaria.

Todo lo demas si va solo: que temas y que lugares del sitio le corresponden a
cada pieza lo decide motor/clasificar.py, con una tabla que se lee y se corrige.

Por eso las piezas quedan en BORRADOR y el correo llega igual: para que alguien
las mire antes de publicarlas.
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

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
    # Ver el comentario largo de armar_carga.py sobre por que no va por defecto.
    ap.add_argument("--con-foto", action="store_true",
                    help="deja que el codigo elija foto. Acierta con el lugar y "
                         "falla con el asunto: leer armar_carga.py antes")
    # Las dos tandas del dia escriben en carpetas distintas. Si compartieran
    # carpeta, la segunda numeraria encima de la primera y el correo saldria con
    # el mismo asunto dos veces, sin forma de saber cual es cual en la bandeja.
    ap.add_argument("--tanda", default="", help="etiqueta: manana, tarde...")
    args = ap.parse_args()

    hoy = datetime.date.today().isoformat()
    nombre = "corrida-" + hoy + ("-" + args.tanda if args.tanda else "")
    carpeta = AQUI / nombre
    carpeta.mkdir(exist_ok=True)
    # Marca de tiempo para distinguir lo escrito HOY de lo que ya hubiera en
    # borradores/. Sin esto, una corrida mandaria por correo todo el historico.
    arranque = __import__("time").time()

    print("=" * 70)
    print("CORRIDA %s  %s   %d piezas"
          % ((args.tanda or "diaria").upper(), hoy, args.piezas))
    print("=" * 70)

    if not hay_con_que():
        return 1

    # 1. Que hay hoy. El orden lo pone criterio.py, que ya puntua y diversifica
    #    por pais para que un solo asunto no cope la jornada.
    #
    #    SE PIDEN MAS CANDIDATOS DE LOS QUE HACEN FALTA. Con dos tandas al dia,
    #    buena parte de lo que trae la segunda ya se conto en la primera. Si se
    #    pidieran seis justos y cuatro fueran repetidos, la tanda saldria con
    #    dos piezas. Se pide el triple y se recorta despues de filtrar.
    print("\n--- 1. RECOLECTAR ---")
    candidatos = carpeta / "candidatos.json"
    r = correr([PYTHON, AQUI / "recolectar.py", "--horas", args.horas,
                "--limite", args.piezas * 3, "--guardar", candidatos])
    print((r.stdout or "")[-900:])
    if not candidatos.exists():
        print("Sin candidatos. Nada que hacer hoy.")
        return 1

    crudos = json.loads(candidatos.read_text(encoding="utf-8"))

    # 1b. Quitar lo que ya esta publicado. Ver motor/memoria.py: la fuente de
    #     verdad es el propio sitio, asi que tambien se ve lo que subio una
    #     persona a mano.
    print("\n--- 1b. DESCARTAR LO YA PUBLICADO ---")
    try:
        from motor import memoria
        temas, repetidos = memoria.filtrar(crudos, clave="hecho")
        for c, ya in repetidos:
            print("   ya publicado: %s" % str(c.get("hecho", ""))[:60])
            print("       coincide con: %s" % ya["titulo"][:60])
        print("   %d nuevos, %d repetidos" % (len(temas), len(repetidos)))
    except Exception as exc:  # noqa: BLE001
        # Si la memoria falla NO se para la corrida: se avisa y se sigue con
        # todo. Publicar una repetida es un incordio; no publicar nada porque
        # no se pudo comprobar es peor.
        print("   [aviso] la memoria fallo (%s). Se sigue SIN filtrar."
              % str(exc)[:70])
        temas = crudos

    temas = temas[:args.piezas]
    if not temas:
        print("\nTodo lo que hay hoy ya se publico. No se escribe nada.")
        # Se manda el correo igual, aunque vaya vacio: es el unico aviso de que
        # la corrida ocurrio y de que no habia nada nuevo.
        correr([PYTHON, AQUI / "enviar.py", carpeta, args.correo], minutos=15)
        return 0

    print("\n%d temas elegidos:" % len(temas))
    for t in temas:
        print("   - " + str(t.get("hecho", "?"))[:88])

    # producir.py entra por posicion en el archivo, asi que hay que reescribirlo
    # con la lista ya filtrada o los indices apuntarian a los candidatos viejos.
    candidatos.write_text(json.dumps(temas, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    # 2. Escribir y auditar, una por una. Si una revienta, las demas siguen: una
    #    corrida que se cae entera por un tema es una corrida que no sirve.
    print("\n--- 2. PRODUCIR ---")
    for i, tema in enumerate(temas, 1):
        hecho = str(tema.get("hecho", ""))
        print("\n  [%d/%d] %s" % (i, len(temas), hecho[:70]))
        # Se le pasa EL candidato, por su posicion en el archivo. Antes se le
        # daba el medio y unas palabras y volvia a buscar: en tres de seis
        # piezas encontraba otra nota del mismo diario y escribia sobre otra
        # cosa, sin que nada fallara. Ver el comentario de --paquete en
        # motor/producir.py.
        r = correr([PYTHON, AQUI / "motor" / "producir.py",
                    "--tipo", "Noticia",
                    "--paquete", candidatos, "--indice", i - 1])
        cola = (r.stdout or "")[-260:]
        print("     " + cola.replace("\n", "\n     ")[:400])
        # STDERR SOLO CUANDO FALLA, PERO ENTONCES SIEMPRE. La corrida anterior
        # murio con un AttributeError en las seis piezas y aqui no se vio nada:
        # se imprimia solo el final de stdout, la traza iba por stderr y el
        # resumen decia "0 piezas" sin decir por que. Un fallo invisible cuesta
        # una corrida entera de averiguar.
        if r.returncode != 0 and (r.stderr or "").strip():
            print("     FALLO:")
            for linea in (r.stderr or "").strip().splitlines()[-6:]:
                print("       " + linea[:150])

    # 3. Recoger lo escrito. producir.py deja cada pieza en borradores/ con el
    #    nombre de sus fuentes; enviar.py espera una carpeta con archivos
    #    numerados. Sin este paso el correo salia vacio aunque las piezas
    #    existieran, que es el peor fallo posible: parece que no hubo noticias.
    print("\n--- 3. RECOGER ---")
    nuevos = sorted(p for p in (AQUI / "borradores").glob("*.txt")
                    if p.stat().st_mtime > arranque)
    for i, origen in enumerate(nuevos, 1):
        for sufijo in (".txt", ".json"):
            fuente = origen.with_suffix(sufijo)
            if fuente.exists():
                (carpeta / ("%d-%s%s" % (i, origen.stem[:26], sufijo))).write_bytes(
                    fuente.read_bytes())
    print("  %d pieza(s) recogidas en %s" % (len(nuevos), carpeta.name))
    if not nuevos:
        print("  No se produjo nada. Revisa el paso anterior.")

    # 4. Correo y panel. El correo va SIEMPRE, aunque el panel falle: es el
    #    unico aviso de que la corrida ocurrio.
    print("\n--- 4. ENTREGA ---")
    if not args.sin_subir and nuevos:
        orden = [PYTHON, AQUI / "armar_carga.py", carpeta]
        if args.con_foto:
            orden.append("--con-foto")
        r = correr(orden, minutos=20)
        print((r.stdout or "")[-1400:])
        carga = carpeta / "carga.json"
        if carga.exists():
            r = correr([PYTHON, AQUI / "subir.py", carga], minutos=20)
            print((r.stdout or "") + (r.stderr or "")[-400:])
        else:
            print("  No se armo la carga. No se sube nada.")

    r = correr([PYTHON, AQUI / "enviar.py", carpeta, args.correo], minutos=15)
    print((r.stdout or "") + (r.stderr or "")[-400:])

    print("\nCorrida terminada. Nada se ha publicado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
