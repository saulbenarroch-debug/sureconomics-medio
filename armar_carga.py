r"""Convierte los borradores del dia en la carga exacta que pide el panel.

    .pyruntime\python.exe armar_carga.py

Deja carga-28.json. NO sube nada: subir es cosa del navegador, con la sesion
abierta por el propio dueño.

POR QUE ESTE ARCHIVO Y NO PEGAR A MANO

El 26/08/2026 se cargaron nueve piezas con el cuerpo vacio y nadie lo vio hasta
que el dueño abrio el sitio. La causa fue rellenar el editor antes de que
terminara de montarse. La leccion no fue "esperar mas", fue: lo que se sube
tiene que estar escrito antes, en un archivo que se pueda revisar, y el
navegador solo lo copia y lo comprueba leyendo de vuelta.

EL CREDITO DE LA FOTO VA EN EL PIE DEL CUERPO A PROPOSITO. El panel tiene un
campo de credito que no persiste (defecto conocido, pendiente de arreglo). Una
foto CC BY o CC BY-SA sin atribucion no es un descuido de estilo: es una
infraccion de la licencia. Mientras el campo no guarde, el credito viaja dentro
del texto, que si se guarda.

LO QUE SE APRENDIO DEL PANEL EL 28/08/2026, PARA NO VOLVER A DESCUBRIRLO

1. **La sesion vive en sessionStorage, o sea en UNA pestaña.** No hay cookie ni
   nada en localStorage. Abrir la nota en pestaña nueva deja al editor fuera sin
   avisar. Se arregla del lado del sitio con una cookie HttpOnly; mientras
   tanto, se trabaja en la pestaña donde se entro y en ninguna otra.

2. **Los dos editores son tiptap (ProseMirror), y NO leen innerHTML.** Lo unico
   que aceptan de fuera es un evento de pegado con text/html, que es la misma
   via que usa una persona con el portapapeles. Asignar innerHTML deja el texto
   a la vista y el estado vacio: se guarda una pieza en blanco.

3. **Los campos normales son de React.** Hay que usar el setter nativo del
   prototipo y disparar input y change. Asignar .value a secas se ve relleno y
   no llega.

4. **Las fuentes no tienen boton de «añadir»: la fila siguiente aparece sola**
   en cuanto se llena la anterior. Buscar el boton y rendirse al no encontrarlo
   dejaba fuera la segunda fuente.

5. **Cambiar el formato remonta el formulario entero.** Va lo primero, siempre,
   o borra lo que ya se hubiera escrito.

6. **Verificar es recargar.** Leer los campos justo despues de rellenarlos no
   prueba nada: el 26/08 el cargador dijo «cuerpo ok» y nueve piezas salieron
   vacias. La comprobacion buena es volver a abrir la pieza guardada y contar.
"""

import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

COMMONS = "https://upload.wikimedia.org/wikipedia/commons/"

# Foto, tema y lugar se deciden pieza a pieza. No hay automatismo que sepa que
# una nota sobre el rey de Noruega no lleva lugar: Noruega no esta en la
# taxonomia del sitio, y poner "EE. UU." porque si seria mentir en la ficha.
FICHAS = {
    "1-todos_chevron": dict(
        formato="noticia",
        temas=["Energía y Minería", "Empresas y Negocios"],
        lugares=["Venezuela", "EE. UU."],
        foto=COMMONS + "thumb/7/74/Refiner%C3%ADa_El_Palito%2C_Carabobo%2C_"
                       "Venezuela.JPG/1920px-Refiner%C3%ADa_El_Palito%2C_"
                       "Carabobo%2C_Venezuela.JPG",
        credito="Archivo, 2012. Refinería El Palito, en Carabobo, Venezuela. "
                "Foto: Marive Casimiro, CC BY-SA 3.0, vía Wikimedia Commons."),
    "2-elnacional-descifrado-bita": dict(
        formato="noticia",
        temas=["Energía y Minería", "Política Fiscal y Deuda"],
        lugares=["Venezuela", "EE. UU."],
        foto=COMMONS + "a/ae/Edificio_PDVSA_5_de_Julio.jpg",
        credito="Archivo. Sede de PDVSA en la avenida 5 de Julio, Maracaibo. "
                "Foto: Wilfredor, CC BY-SA 3.0, vía Wikimedia Commons."),
    "3-bbcmundo-france24-dw_nepal": dict(
        formato="noticia",
        temas=["Comercio Exterior", "Infraestructura"],
        lugares=["China"],
        # Se cambio el 28/08/2026: la del Puente de la Amistad era vertical
        # (1494x2056) y se recortaba mal en portada. Se descarto tambien la del
        # puesto de Gyirong, que es el sitio exacto de la nota, por ser una
        # captura de un video de YouTube de un medio estatal y de solo 996 px.
        # Esta es obra propia de un usuario de Commons, apaisada y de 1600 px.
        # El pie dice "Nepal y China" y no "Gyirong" porque la foto no acredita
        # ese paso concreto: el pie no puede afirmar mas que la foto.
        foto=COMMONS + "3/37/Nepal_China_Border.JPG",
        credito="Archivo, 2013. La frontera entre Nepal y China. Foto: Krish "
                "Dulal, CC BY-SA 3.0, vía Wikimedia Commons."),
    "4-latercera-elpais-infobae_h": dict(
        formato="noticia",
        temas=["Política"],
        lugares=[],
        foto=COMMONS + "f/fa/King_Harald_V_2021.jpg",
        credito="Archivo, 2021. El rey Harald V de Noruega. Foto: Sámediggi - "
                "Sametinget, CC BY 2.0, vía Wikimedia Commons."),
    "5-todos_ciberataque-ciberseg": dict(
        formato="noticia",
        temas=["Tecnología y Pagos", "Geoeconomía"],
        lugares=["EE. UU."],
        foto=COMMONS + "thumb/5/5d/BalticServers_data_center.jpg/1920px-"
                       "BalticServers_data_center.jpg",
        credito="Archivo, 2013. Interior de un centro de datos. Foto: "
                "BalticServers.com, CC BY-SA 3.0, vía Wikimedia Commons."),
    "6-elpais-latercera-oilprice_": dict(
        formato="noticia",
        temas=["Comercio Exterior", "Energía y Minería"],
        lugares=["EE. UU."],
        foto=COMMONS + "b/b8/Jet_refueling.jpg",
        credito="Archivo, 2023. Carga de combustible en un avión. Foto: "
                "Dayton.loyd, CC0, vía Wikimedia Commons."),
}

ARTICULO = dict(
    ruta="borradores/ofac-licencias_investigación.txt",
    formato="articulo",
    temas=["Energía y Minería", "Geoeconomía", "Política Fiscal y Deuda"],
    lugares=["Venezuela", "EE. UU."],
    foto=COMMONS + "d/da/Orinoco_Oil_Belt.png",
    credito="Archivo, 2009. Mapa de la Faja Petrolífera del Orinoco. Foto: "
            "Christopher J. Schenk (USGS), dominio público, vía Wikimedia "
            "Commons.")


def es_intertitulo(linea):
    """Linea corta, sin punto final: separa secciones, no es un parrafo.

    En una noticia no hay ninguno y por eso no se busca. En el articulo son los
    que dan la estructura, y si entran como parrafo el texto se lee como un
    ladrillo sin respiracion.
    """
    s = linea.strip()
    return 0 < len(s) < 95 and not s.endswith(".") and not s.isupper()


def desmontar(ruta, con_intertitulos):
    texto = open(ruta, encoding="utf-8").read()
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
            resumen = s
            esperando = False
            continue
        esperando = False
        partes.append((clase, s))

    if not resumen and partes:
        # En una noticia la entradilla es la primera frase, que ya esta escrita.
        # No se inventa nada.
        primera = partes[0][1]
        corte = primera.find(". ")
        resumen = primera[:corte + 1] if corte > 60 else primera
    return titulo, resumen, partes, fuentes, firma


def escapar(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    carga = []
    for ruta in sorted(glob.glob("28-noticias/[0-9]*.txt")):
        ficha = FICHAS[os.path.basename(ruta)[:-4]]
        titulo, resumen, partes, fuentes, firma = desmontar(ruta, False)
        carga.append(dict(ficha, titulo=titulo, resumen=resumen, firma=firma,
                          fuentes=fuentes, partes=partes,
                          origen=os.path.basename(ruta)))

    titulo, resumen, partes, fuentes, firma = desmontar(ARTICULO["ruta"], True)
    carga.append(dict({k: v for k, v in ARTICULO.items() if k != "ruta"},
                      titulo=titulo, resumen=resumen, firma=firma,
                      fuentes=fuentes, partes=partes, origen="ofac-licencias"))

    for p in carga:
        partes = p.pop("partes")
        cuerpo = "".join("<%s>%s</%s>" % (c, escapar(s), c) for c, s in partes)
        # El credito, en cursiva, al pie del cuerpo. Ver cabecera del archivo.
        cuerpo += "<p><em>" + escapar(p["credito"]) + "</em></p>"
        p["cuerpo_html"] = cuerpo
        p["resumen_html"] = "<p>" + escapar(p["resumen"]) + "</p>"

    with open("carga-28.json", "w", encoding="utf-8") as f:
        json.dump(carga, f, ensure_ascii=False, indent=1)

    for p in carga:
        print("%-31s %-9s cuerpo %5d  h2:%d  fuentes:%d  temas:%d  lugares:%d" % (
            p["origen"][:31], p["formato"], len(p["cuerpo_html"]),
            p["cuerpo_html"].count("<h2>"), len(p["fuentes"]),
            len(p["temas"]), len(p["lugares"])))
        print("    " + p["titulo"][:88])
    print("\ncarga-28.json con %d piezas" % len(carga))


if __name__ == "__main__":
    main()
