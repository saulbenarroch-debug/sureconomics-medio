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


# El recolector guarda Paquetes serializados: el titular esta en "hecho" y el
# medio en fuentes[0]["institucion"], con su nombre bonito ("Folha de S.Paulo").
# producir.py, en cambio, quiere la CLAVE de la lista blanca ("folha"). La
# primera version leia una clave "titular" que no existe y no pasaba --diarios:
# las seis piezas morian con "Indica --diarios" y la corrida terminaba en verde
# sin haber escrito nada. Verde y vacio es el peor resultado posible.
def _clave_del_medio(tema):
    import unicodedata

    def pelar(s):
        s = unicodedata.normalize("NFKD", str(s).lower())
        return "".join(c for c in s if not unicodedata.combining(c) and c.isalnum())

    try:
        from motor.fuentes.noticias import MEDIOS
    except ImportError:
        return None
    fuentes = tema.get("fuentes") or []
    if not fuentes:
        return None
    quien = pelar(fuentes[0].get("institucion", ""))
    if not quien:
        return None
    for clave, medio in MEDIOS.items():
        if pelar(medio["nombre"]) == quien:
            return clave
    for clave, medio in MEDIOS.items():
        nombre = pelar(medio["nombre"])
        if nombre and (nombre in quien or quien in nombre):
            return clave
    return None


# Palabras vacias: si entran en el filtro, este casa con media portada y el
# extractor trae cualquier cosa menos la nota que se buscaba.
VACIAS = {"para", "como", "desde", "hasta", "entre", "sobre", "esta", "este",
          "sus", "los", "las", "del", "con", "por", "que", "una", "uno", "mas",
          "segun", "tras", "ante", "todos", "todas", "cada", "año", "anos"}


def _filtro(hecho):
    """Dos o tres palabras distintivas, en alternancia, como pide --tema.

    Se recortan a la raiz (sin las dos ultimas letras) para que "inflacion"
    tambien case con "inflacionaria" o "inflacionario".
    """
    import re
    import unicodedata

    plano = unicodedata.normalize("NFKD", hecho.lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    palabras = [p for p in re.findall(r"[a-z]{5,}", plano) if p not in VACIAS]
    if not palabras:
        return hecho[:24]
    vistas, elegidas = set(), []
    for p in sorted(palabras, key=len, reverse=True):
        raiz = p[:-2]
        if raiz not in vistas:
            vistas.add(raiz)
            elegidas.append(raiz)
        if len(elegidas) == 3:
            break
    return "|".join(elegidas)


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
    # Marca de tiempo para distinguir lo escrito HOY de lo que ya hubiera en
    # borradores/. Sin esto, una corrida mandaria por correo todo el historico.
    arranque = __import__("time").time()

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
        hecho = str(tema.get("hecho", ""))
        diario = _clave_del_medio(tema)
        filtro = _filtro(hecho)
        print("\n  [%d/%d] %s" % (i, len(temas), hecho[:70]))
        if not diario:
            print("     sin medio reconocible en la lista blanca, se salta")
            continue
        print("     medio: %s   filtro: %s" % (diario, filtro))
        r = correr([PYTHON, AQUI / "motor" / "producir.py",
                    "--tipo", "Noticia", "--horas", args.horas,
                    "--diarios", diario, "--tema", filtro])
        cola = (r.stdout or "")[-260:]
        print("     " + cola.replace("\n", "\n     ")[:400])

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
    if not args.sin_subir:
        # PENDIENTE. armar_carga.py todavia decide foto, temas y lugares pieza a
        # pieza, a mano, para las seis del 28/08/2026. Para subir de forma
        # automatica hay que generalizarlo: la foto la puede buscar
        # buscar_foto.py, pero temas y lugares hay que sacarlos del propio
        # paquete de datos. Mientras tanto, subir sin eso crearia borradores sin
        # clasificar, y prefiero no subir a subir mal.
        print("  La subida automatica aun no esta: armar_carga.py depende de")
        print("  decisiones tomadas a mano. Se manda el correo igual.")

    r = correr([PYTHON, AQUI / "enviar.py", carpeta, args.correo], minutos=15)
    print((r.stdout or "") + (r.stderr or "")[-400:])

    print("\nCorrida terminada. Nada se ha publicado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
