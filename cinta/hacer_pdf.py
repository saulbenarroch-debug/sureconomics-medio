r"""Imprime una guia HTML a PDF con el navegador, sin depender de librerias.

    .pyruntime\python.exe cinta/hacer_pdf.py entrada.html salida.pdf

POR QUE EL NAVEGADOR Y NO UNA LIBRERIA DE PDF

Porque la guia ya esta maquetada en CSS y el navegador la imprime tal cual. Una
libreria obligaria a rehacer el diseño y el resultado no se pareceria.

EL CUELGUE DE CHROME, QUE YA COSTO UNA TARDE

`chrome --headless --print-to-pdf` se queda colgado si el usuario tiene una
ventana abierta con su perfil. Hay que darle un perfil temporal propio y usar
`--headless=new`. Con Edge pasa lo mismo y se arregla igual. Esto viene del
build del Mapa de Activos Petroleros, donde se descubrio.

Y SE ENVUELVE EL HTML. Las guias se escriben como fragmento para publicarse
online, sin <html> ni <head>. Para imprimir hace falta el documento entero, y
ademas hay que FORZAR EL MODO CLARO: el CSS tiene un bloque para pantallas
oscuras y en papel eso saldria negro.
"""

import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

# Lo que hace falta solo en papel. Va aparte del CSS de la guia para no
# ensuciarlo: en pantalla estas reglas no pintan nada.
IMPRENTA = """
<style>
  @page { size: A4; margin: 15mm 14mm 16mm; }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-size: 11.5pt; }
  .hoja { max-width: none; padding: 0; }
  /* Que no se parta por la mitad lo que se lee de un vistazo. */
  .chat, .ficha, .regla, .tabla, .pasos li { break-inside: avoid; }
  h2 { break-after: avoid; break-before: page; }
  h2:first-of-type { break-before: auto; }
  h3 { break-after: avoid; }
  /* El ancho de lectura lo fija @page; en papel sobra el tope en caracteres. */
  p, ul, .pasos li { max-width: none; }
  a { color: inherit; text-decoration: none; }
</style>
"""


def envolver(fragmento, titulo):
    """El fragmento, dentro de un documento completo y en modo claro."""
    return (
        '<!doctype html>\n<html lang="es" data-theme="light">\n<head>\n'
        '<meta charset="utf-8">\n'
        "<title>%s</title>\n%s\n</head>\n<body>\n%s\n</body>\n</html>"
        % (titulo, IMPRENTA, fragmento))


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip().splitlines()[2])
        return 1
    entrada = pathlib.Path(sys.argv[1])
    salida = pathlib.Path(sys.argv[2])

    navegador = next((n for n in NAVEGADORES if pathlib.Path(n).exists()), None)
    if not navegador:
        print("No encuentro ni Chrome ni Edge.")
        return 1

    crudo = entrada.read_text(encoding="utf-8")
    titulo = "Guía"
    if "<title>" in crudo:
        titulo = crudo.split("<title>")[1].split("</title>")[0]
    # El <title> del fragmento se reaprovecha y se quita del cuerpo.
    cuerpo = crudo.replace("<title>%s</title>" % titulo, "", 1)

    temporal = pathlib.Path(tempfile.mkdtemp(prefix="pdf-"))
    try:
        pagina = temporal / "para-imprimir.html"
        pagina.write_text(envolver(cuerpo, titulo), encoding="utf-8")
        perfil = temporal / "perfil"

        r = subprocess.run(
            [navegador, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--user-data-dir=%s" % perfil,
             "--print-to-pdf=%s" % salida,
             # Los dos: "--print-to-pdf-no-header" quedo obsoleto en las
             # versiones nuevas y Chrome lo ignora en silencio. Sin esto se
             # imprime la RUTA DEL ARCHIVO TEMPORAL al pie de cada pagina.
             "--no-pdf-header-footer", "--print-to-pdf-no-header",
             "--virtual-time-budget=12000",  # que le de tiempo a las tipografias
             pagina.as_uri()],
            capture_output=True, text=True, timeout=180)
        if not salida.exists():
            print("No se genero el PDF.")
            print((r.stderr or "")[-400:])
            return 1
        print("%s  ·  %.1f MB  ·  con %s"
              % (salida.name, salida.stat().st_size / 1048576,
                 pathlib.Path(navegador).stem))
        return 0
    finally:
        shutil.rmtree(temporal, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
