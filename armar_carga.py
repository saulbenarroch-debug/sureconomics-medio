r"""Convierte los borradores de una corrida en la carga que pide el panel.

    .pyruntime\python.exe armar_carga.py corrida-2026-08-28
    .pyruntime\python.exe armar_carga.py corrida-2026-08-28 --sin-foto

Deja carga.json dentro de esa carpeta. NO sube nada: subir es cosa de subir.py.

POR QUE ESTE ARCHIVO Y NO PEGAR A MANO

El 26/08/2026 se cargaron nueve piezas con el cuerpo vacio y nadie lo vio hasta
que el dueño abrio el sitio. La causa fue rellenar el editor del navegador antes
de que terminara de montarse. La leccion no fue "esperar mas", fue: lo que se
sube tiene que estar escrito antes, en un archivo que se pueda revisar.

La primera version de este archivo tenia la foto, los temas y los lugares de
cada pieza escritos a mano, uno por uno, para las seis del 28 de agosto. Servia
para esa tanda y para ninguna otra: la corrida automatica lo llamaba y no
encontraba nada. Ahora todo eso lo deciden motor/clasificar.py y motor/foto.py.

EL CREDITO DE LA FOTO VA EN EL PIE DEL CUERPO A PROPOSITO. El panel tiene un
campo de credito que no persiste: se rellena, se guarda, se recarga y vuelve
vacio (comprobado el 28/08/2026). Una foto CC BY o CC BY-SA sin atribucion no es
un descuido de estilo, es una infraccion de la licencia. Mientras el campo no
guarde, el credito viaja dentro del texto, que si se guarda.

LO MISMO VALE PARA LAS IMAGENES GENERADAS CON IA, Y ES MAS GRAVE. El 31/08/2026
se publicaron seis piezas con imagen generada con ChatGPT. La declaracion se
habia escrito en el campo de credito del panel y desaparecio ahi, igual que los
creditos de Commons: la ficha del asset que devuelve la API ni siquiera tiene
campo de credito, solo id, kind, storage, url y original_filename. O sea que ese
texto no se guarda en ninguna parte.

Una foto sin atribuir incumple una licencia. Una imagen generada sin declarar le
dice al lector que esta viendo una fotografia de algo que no ocurrio. La linea
es esta, al pie del cuerpo, y no se negocia:

    <p><em>Imagen generada con inteligencia artificial.</em></p>

Y NO se le pone a las imagenes que no lo son. Ponersela a una foto real de
Commons seria mentir en la direccion contraria.

LO QUE SE APRENDIO DEL PANEL, Y ES LA RAZON DE QUE ESTE ARCHIVO EXISTA

1. **La sesion vive en sessionStorage, o sea en UNA pestaña.** No hay cookie ni
   nada en localStorage. Abrir la nota en pestaña nueva deja al editor fuera sin
   avisar.
2. **Los dos editores son tiptap (ProseMirror) y NO leen innerHTML.** Solo
   aceptan un evento de pegado. Asignar innerHTML deja el texto a la vista y el
   estado vacio: se guarda una pieza en blanco.
3. **Cambiar el formato remonta el formulario entero.** Va lo primero, siempre.
4. **Verificar es recargar.** Leer los campos justo despues de rellenarlos no
   prueba nada.

Nada de eso afecta ya a la subida, que va por la API (ver subir.py), pero sigue
valiendo para quien edite a mano.
"""

import argparse
import glob
import io
import json
import os
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

# reconfigure y NO io.TextIOWrapper: envolver el buffer crea un objeto
# nuevo, y si dos archivos del proyecto lo envuelven (uno al importar al
# otro), el primero que se recoge cierra el buffer y todo lo que imprima
# despues revienta con "I/O operation on closed file", sin tocar ningun
# archivo. Paso tres veces el 28/08/2026. reconfigure cambia el que ya hay.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from motor import clasificar, foto as buscador, memoria  # noqa: E402

# Nuestro formato -> el del sitio. No son equivalentes uno a uno: nuestra
# 'Investigacion' entra como 'informe', que no lleva bloque de opinion al pie
# porque un informe lleva su posicion dentro del texto.
# El sitio tiene CINCO formatos y ninguno se llama "opinión": comprobado contra
# /admin/formats el 05/09/2026. Son noticia, articulo, editorial, entrevista e
# informe. Una columna va como 'articulo', que es el que muestra firma.
#
# Faltaban 'opinión' y 'educación', y el .get() de abajo las mandaba a 'noticia':
# una columna con postura y firma personal se publicaba como si fuera una
# noticia del medio. No es un detalle de catalogo, es atribuirle al medio la
# opinion de una persona.
FORMATOS = {"noticia": "noticia", "investigación": "informe",
            "investigacion": "informe", "análisis": "articulo",
            "analisis": "articulo", "editorial": "editorial",
            "entrevista": "entrevista",
            "opinión": "articulo", "opinion": "articulo",
            "educación": "articulo", "educacion": "articulo"}


def es_intertitulo(linea):
    """Linea corta, sin punto final: separa secciones, no es un parrafo."""
    s = linea.strip()
    return 0 < len(s) < 95 and not s.endswith(".") and not s.isupper()


def desmontar(ruta, con_intertitulos):
    texto = ruta.read_text(encoding="utf-8")
    cabecera = texto.split("\n", 1)[0]
    titulo, firma, resumen = "", "", ""
    crudo, fuentes = [], []

    for linea in texto.split("\n"):
        s = linea.strip()
        if not s:
            continue
        if s.startswith("[Autor]"):
            firma = s.replace("[Autor]", "").strip()
            continue
        if s.startswith("[") or s.startswith("Perecedero") or s.startswith("Permanente"):
            continue
        if s.isupper() and len(s) > 25 and not titulo:
            titulo = s
            continue
        if s.startswith("Sacado de:"):
            resto = s.replace("Sacado de:", "").strip()
            trozos = [t.strip() for t in resto.split("·")]
            fuentes.append({
                "nombre": trozos[0].split(",")[0].strip(),
                "url": next((t for t in trozos if t.startswith("http")), ""),
            })
            continue
        if s == "Resumen":
            crudo.append(("__RESUMEN__", ""))
            continue
        crudo.append(("h2" if con_intertitulos and es_intertitulo(s) else "p", s))

    # El rotulo «Resumen» pertenece al formato, no al texto: lo que va debajo es
    # la entradilla y sube al campo RESUMEN, no al cuerpo.
    partes, esperando = [], False
    for clase, s in crudo:
        if clase == "__RESUMEN__":
            esperando = True
            continue
        if esperando and not resumen:
            resumen, esperando = s, False
            continue
        esperando = False
        partes.append((clase, s))

    if not resumen and partes:
        # En una noticia la entradilla es la primera frase, que ya esta escrita.
        # No se inventa nada.
        primera = partes[0][1]
        corte = primera.find(". ")
        resumen = primera[:corte + 1] if corte > 60 else primera
    return cabecera, titulo, resumen, partes, fuentes, firma


def formato_de(cabecera):
    etiqueta = cabecera.split("]")[0].replace("[", "").strip().lower()
    return FORMATOS.get(etiqueta, "noticia")


def escapar(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    ap = argparse.ArgumentParser(description="Arma la carga del panel")
    ap.add_argument("carpeta")
    # LA FOTO NO VA POR DEFECTO, Y ESTO ES UNA DECISION, NO UN OLVIDO.
    #
    # Se probaron las reglas estrictas contra las cinco piezas que produjo la
    # corrida automatica del 28/08/2026. Las reglas SI saben comprobar el lugar:
    # descartaron Melbourne para una nota sobre España y el distrito financiero
    # de Boston para una sobre Brasil. Lo que no saben es si la foto ilustra el
    # asunto. Con todo apretado, dos de cinco piezas recibieron imagen, y una de
    # esas dos era el Museu do Ipiranga encabezando una nota sobre morosidad
    # bancaria: pais correcto, licencia correcta, sentido ninguno.
    #
    # Una pieza sin foto la resuelve Edicion en un minuto con buscar_foto.py.
    # Una pieza con la foto equivocada la resuelve despues de que la lea alguien,
    # y a veces despues de que la lea un lector. Por eso hay que pedirla.
    ap.add_argument("--con-foto", action="store_true",
                    help="busca imagen automaticamente. Ver el comentario de "
                         "arriba antes de usarlo en produccion")
    args = ap.parse_args()

    carpeta = pathlib.Path(args.carpeta)
    rutas = sorted(pathlib.Path(p) for p in glob.glob(str(carpeta / "[0-9]*.txt")))
    if not rutas:
        print("No hay piezas en %s/" % carpeta)
        return 1

    # Una sola consulta al sitio para todas las piezas de la corrida. Pedirlo
    # dentro del bucle serian seis llamadas identicas.
    catalogo = memoria.publicadas()
    peso = memoria.pesos(catalogo)

    carga = []
    for ruta in rutas:
        formato = formato_de(ruta.read_text(encoding="utf-8").split("\n", 1)[0])
        cabecera, titulo, resumen, partes, fuentes, firma = desmontar(
            ruta, con_intertitulos=formato != "noticia")
        if not titulo:
            print("  %s: sin titulo, se salta" % ruta.name)
            continue

        # SE VUELVE A MIRAR SI YA ESTABA PUBLICADO, AHORA CON EL TITULAR EN
        # ESPAÑOL. El filtro de duplicados corre antes de escribir, cuando el
        # titular todavia es el de la fuente, y eso NO ATRAVIESA EL IDIOMA.
        #
        # Medido el 04/09/2026: la nota del oro de Países Bajos venia de Folha,
        # "Por que a Holanda retirou toneladas de ouro dos Estados Unidos".
        # Contra lo ya publicado puntuaba 0.336 y pasaba, porque no comparte una
        # sola palabra con "PAÍSES BAJOS" ni "ORO": en portugues son "Holanda" y
        # "ouro". Ya escrita en español, la misma pieza puntua 0.620 contra
        # "BANCO CENTRAL DE LOS PAÍSES BAJOS RETIRA TONELADAS DE ORO DESDE NUEVA
        # YORK", publicada cuatro horas antes. Se subio la tercera version del
        # mismo hecho en dos dias.
        #
        # La comprobacion de antes se queda: ahorra escribir lo que ya se sabe
        # repetido. Esta es la que ve lo que la otra no puede ver.
        repetida = memoria.ya_cubierto(titulo, catalogo, peso=peso,
                                       formato=formato)
        if repetida:
            print("  %s: YA PUBLICADA como «%s». No se sube."
                  % (ruta.name[:28], repetida["titulo"][:56]))
            continue

        cuerpo_plano = " ".join(s for _, s in partes)
        temas = clasificar.temas(titulo, cuerpo_plano)
        lugares = clasificar.lugares(cabecera, titulo)

        # El veredicto del auditor viaja con la pieza. subir.py no sube lo
        # bloqueado, pero la decision se toma aqui, donde esta el expediente.
        bloqueada = False
        json_ruta = ruta.with_suffix(".json")
        if json_ruta.exists():
            bloqueada = bool(json.loads(
                json_ruta.read_text(encoding="utf-8")).get("bloqueada"))

        elegida = None
        if args.con_foto and not bloqueada:
            elegida = buscador.para(titulo, lugares, temas[0], explicar=True)

        cuerpo = "".join("<%s>%s</%s>" % (c, escapar(s), c) for c, s in partes)
        if elegida:
            cuerpo += "<p><em>" + escapar(elegida["credito"]) + "</em></p>"

        carga.append({
            "origen": ruta.name,
            "formato": formato,
            "titulo": titulo,
            "resumen": resumen,
            "resumen_html": "<p>" + escapar(resumen) + "</p>",
            "cuerpo_html": cuerpo,
            "firma": firma,
            "fuentes": fuentes,
            "temas": temas,
            "lugares": lugares,
            "foto": elegida["url"] if elegida else "",
            "credito": elegida["credito"] if elegida else "",
            "bloqueada": bloqueada,
        })

        marca = "BLOQUEADA" if bloqueada else "ok"
        print("%-30s %-9s %-9s  %s" % (ruta.name[:30], formato, marca,
                                       " · ".join(temas)))
        print("     %s" % titulo[:86])
        print("     lugares: %s" % (", ".join(lugares) or "(ninguno)"))
        if elegida:
            print("     foto: %s (%sx%s) [%s]" % (
                elegida["titulo"][:40], elegida["ancho"], elegida["alto"],
                elegida["consulta"]))
        elif args.con_foto and not bloqueada:
            print("     foto: NINGUNA paso las reglas. Sube sin imagen.")

    destino = carpeta / "carga.json"
    destino.write_text(json.dumps(carga, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    con_foto = sum(1 for p in carga if p["foto"])
    bloqueadas = sum(1 for p in carga if p["bloqueada"])
    print("\n%s: %d piezas, %d con foto, %d bloqueadas (no se subiran)" % (
        destino.name, len(carga), con_foto, bloqueadas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
