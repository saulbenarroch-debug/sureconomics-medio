r"""Lamina de Instagram (1080x1350) con la plantilla del medio.

    .pyruntime\python.exe plantillas/post.py foto.jpg ^
        --categoria MUNDO ^
        --titular "Apple va por su iPhone más caro" ^
        --bajada "el primer plegable superaría los US$2.000" ^
        --salida post.png

POR QUE HTML Y CHROME Y NO UNA LIBRERIA DE IMAGEN

Porque el diseño ya existe en Canva y lo que hay que reproducir es tipografia
apretada, tarjeta translucida con desenfoque y texto que se ajusta solo. Eso en
CSS son cuatro lineas y con Pillow es una tarde de calcular pixeles a mano. Es
la misma via que usan entorno/render.py y al-cierre: HTML, Chrome, captura.

LOS RECURSOS DE MARCA VIVEN EN plantillas/assets/ Y NO SE INVENTAN

  assets/logo.png       el logotipo blanco de SurE, con transparencia
  assets/fuentes/*.woff2  la tipografia de los titulares

Si falta el logo, se dibuja un hueco marcado y se avisa: mejor una lamina que
dice "aqui va el logo" que una lamina publicada con el logo equivocado.

LO QUE NO HACE ESTE ARCHIVO: elegir la foto, escribir el titular ni decidir la
categoria. Eso lo trae quien lo llama.
"""

import argparse
import base64
import html
import mimetypes
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
ASSETS = AQUI / "assets"

ANCHO, ALTO = 1080, 1350

# DONDE ESTA CHROME, Y HAY QUE MIRAR EN LINUX PRIMERO. Esto solo miraba rutas de
# Windows y en el runner de Actions -que es Ubuntu- decia "No encuentro Chrome ni
# Edge": la lamina se decidia entera y moria en el ultimo paso. Paso el
# 08/09/2026, la primera vez que Edicion la pidio de verdad.
#
# El runner de ubuntu YA trae google-chrome; no hay que instalar nada, solo
# buscarlo en el PATH. Es lo que hace entorno/render.py desde siempre.
CHROME = (
    os.environ.get("CHROME_BIN")
    or shutil.which("google-chrome")
    or shutil.which("google-chrome-stable")
    or shutil.which("chromium-browser")
    or shutil.which("chromium")
    or next((p for p in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        if pathlib.Path(p).exists()), None))

# El rojo de la etiqueta de seccion. Se saca de las laminas que ya publica el
# medio; si Edicion lo cambia, se cambia aqui y en ningun otro sitio.
ROJO = "#F5333F"


def _incrustar(ruta):
    """La imagen como data: URI.

    Chrome en headless carga file:// desde una pagina file:// sin problema, pero
    el HTML se escribe en una carpeta temporal y la foto puede estar en
    cualquier sitio: incrustarla evita rutas relativas y permisos.
    """
    ruta = pathlib.Path(ruta)
    if not ruta.exists():
        return ""
    mime = mimetypes.guess_type(ruta.name)[0] or "image/jpeg"
    return "data:%s;base64,%s" % (
        mime, base64.b64encode(ruta.read_bytes()).decode())


def _fuentes():
    """Las @font-face de Host Grotesk, incrustadas.

    SE INCRUSTAN Y NO SE ENLAZAN A GOOGLE a proposito. Si la fuente se pide por
    red y la red falla, Chrome dibuja con la de reserva y la lamina sale con otra
    tipografia sin que nada avise: se publica y se ve. Incrustada, o esta o no
    esta, y aqui esta.
    """
    carpeta = ASSETS / "fuentes"
    ficha = carpeta / "hostgrotesk.json"
    if not ficha.exists():
        return ""
    import json

    reglas = []
    for r in json.loads(ficha.read_text(encoding="utf-8")):
        archivo = carpeta / r["archivo"]
        if not archivo.exists():
            continue
        # El unicode-range se conserva tal cual lo sirve Google: son dos
        # archivos, latin y latin-ext, y sin el rango el navegador baja los dos
        # y usa el que no toca para las tildes.
        rango = ("unicode-range:%s;" % r["rango"]) if r.get("rango") else ""
        reglas.append(
            "@font-face{font-family:'Host Grotesk';font-weight:%s;"
            "font-style:normal;src:url('%s') format('woff2');%s}"
            % (r["peso"], _incrustar(archivo), rango))
    return "\n".join(reglas)


def componer(foto, categoria, titular, bajada="", enlace_en_bio=False):
    """El HTML de la lamina. Sin efectos: devuelve una cadena."""
    logo = _incrustar(ASSETS / "logo.png")
    fondo = _incrustar(foto)
    return PAGINA % {
        "ancho": ANCHO, "alto": ALTO, "rojo": ROJO,
        "fuentes": _fuentes(),
        "fondo": fondo,
        "logo": ("<img class='logo' src='%s'>" % logo if logo
                 else "<div class='logo falta'>falta assets/logo.png</div>"),
        "categoria": html.escape(categoria.upper()),
        "titular": html.escape(titular),
        "bajada": ("<p class='bajada'>%s</p>" % html.escape(bajada)
                   if bajada else ""),
        "boton": ("<div class='bio'>link en bio</div>" if enlace_en_bio else ""),
    }


PAGINA = """<!doctype html><html><head><meta charset="utf-8"><style>
%(fuentes)s
*{margin:0;padding:0;box-sizing:border-box;}
html,body{width:%(ancho)spx;height:%(alto)spx;background:#000;}
.hoja{position:relative;width:%(ancho)spx;height:%(alto)spx;overflow:hidden;
  font-family:'Host Grotesk','Segoe UI',Arial,sans-serif;color:#fff;}
.fondo{position:absolute;inset:0;width:100%%;height:100%%;object-fit:cover;}
/* El degradado hace legible el texto pase lo que pase en la foto. Sin el, una
   foto clara deja el titular ilegible y eso solo se ve al publicar. */
.velo{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(0,0,0,.62) 0%%,rgba(0,0,0,.34) 26%%,
                  rgba(0,0,0,.55) 55%%,rgba(0,0,0,.85) 100%%);}
.logo{position:absolute;top:96px;left:50%%;transform:translateX(-50%%);
  height:78px;z-index:3;}
.logo.falta{display:flex;align-items:center;justify-content:center;
  width:420px;border:2px dashed rgba(255,255,255,.5);border-radius:12px;
  font-size:22px;letter-spacing:1px;}
.tarjeta{position:absolute;left:40px;right:40px;bottom:56px;z-index:2;
  background:rgba(18,18,18,.42);backdrop-filter:blur(16px);
  border:1.5px solid rgba(255,255,255,.22);border-radius:44px;
  padding:74px 52px 52px;}
.etiqueta{position:absolute;top:-24px;left:50%%;transform:translateX(-50%%);
  background:%(rojo)s;color:#fff;border-radius:999px;padding:11px 30px;
  font-size:23px;font-weight:800;letter-spacing:2px;white-space:nowrap;}
h1{font-size:100px;font-weight:800;line-height:.92;letter-spacing:-3px;}
.bajada{margin-top:22px;font-size:47px;font-weight:400;line-height:1.12;}
.bio{margin:38px auto 4px;width:max-content;border:2px solid #fff;
  border-radius:999px;padding:13px 46px;font-size:28px;font-weight:500;}
</style></head><body><div class="hoja">
  <img class="fondo" src="%(fondo)s">
  <div class="velo"></div>
  %(logo)s
  <div class="tarjeta">
    <div class="etiqueta">%(categoria)s</div>
    <h1>%(titular)s</h1>
    %(bajada)s
    %(boton)s
  </div>
</div></body></html>"""


def dibujar(html_texto, salida):
    """Chrome en headless: HTML -> PNG."""
    if not CHROME:
        print("No encuentro Chrome ni Edge.")
        return False
    temporal = pathlib.Path(tempfile.mkdtemp(prefix="post-"))
    try:
        pagina = temporal / "post.html"
        pagina.write_text(html_texto, encoding="utf-8")
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             # Perfil propio: sin esto Chrome se cuelga si hay una ventana
             # abierta con el perfil del usuario. Costo una tarde en el mapa
             # de activos petroleros y esta apuntado en cinta/hacer_pdf.py.
             "--user-data-dir=%s" % (temporal / "perfil"),
             "--hide-scrollbars", "--force-device-scale-factor=1",
             "--window-size=%d,%d" % (ANCHO, ALTO),
             # Que le de tiempo a las tipografias incrustadas.
             "--virtual-time-budget=6000",
             "--screenshot=%s" % pathlib.Path(salida).resolve(),
             pagina.as_uri()],
            capture_output=True, text=True, timeout=180)
        return pathlib.Path(salida).exists()
    finally:
        shutil.rmtree(temporal, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Lámina de Instagram del medio")
    ap.add_argument("foto", help="la imagen de fondo")
    ap.add_argument("--categoria", default="MUNDO")
    ap.add_argument("--titular", required=True)
    ap.add_argument("--bajada", default="")
    ap.add_argument("--link-en-bio", action="store_true")
    ap.add_argument("--salida", default="post.png")
    args = ap.parse_args()

    if not (ASSETS / "logo.png").exists():
        print("[aviso] falta plantillas/assets/logo.png: la lámina sale con el "
              "hueco marcado. No la publiques así.")
    html_texto = componer(args.foto, args.categoria, args.titular,
                          args.bajada, args.link_en_bio)
    if not dibujar(html_texto, args.salida):
        print("No se generó la lámina.")
        return 1
    p = pathlib.Path(args.salida)
    print("%s · %.0f KB · %dx%d" % (p.name, p.stat().st_size / 1024, ANCHO, ALTO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
