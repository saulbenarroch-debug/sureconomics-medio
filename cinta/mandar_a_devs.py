r"""Manda el cintillo a los desarrolladores, con el archivo adjunto.

    .pyruntime\python.exe cinta/mandar_a_devs.py rmarquina@pidelove.com
    .pyruntime\python.exe cinta/mandar_a_devs.py --ensayo destinatario@x.com

El envio de La Campana (wallstreet-bot/correo.py) no adjunta archivos, asi que
aqui se arma el mensaje a mano. Las CREDENCIALES no se copian: se leen del mismo
.env que lleva meses funcionando.

--ensayo imprime el correo y no lo manda. Un correo sale una vez y no se puede
recoger, asi que conviene mirarlo antes.
"""

import argparse
import mimetypes
import os
import pathlib
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formataddr

AQUI = pathlib.Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(AQUI.parent / ".libs"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\wallstreet-bot\.env")

ADJUNTO = AQUI / "cintillo-sureconomics.html"
ASUNTO = "Cintillo de mercados para sureconomics.com"

CUERPO = """Hola:

Os paso el cintillo de cotizaciones para la cabecera de sureconomics.com, listo
para integrar.

Va todo en el archivo adjunto: es una página HTML que se abre con doble clic y
que hace tres cosas a la vez. Arriba se ve el componente funcionando de verdad,
con datos en vivo; debajo está la documentación; y al final, el código exacto
con un botón para copiarlo.

Tres cosas que conviene leer antes de integrarlo:

1. La atribución "Mercados por TradingView" no se puede quitar. No es un detalle
   de diseño: es la condición que permite mostrar los índices globales sin
   contratar derechos de display. Si se elimina, se cae la base legal de esa
   mitad del cintillo.

2. Los datos están partidos en dos por licencia, no por diseño. Los índices
   globales los sirve TradingView directamente al navegador del lector. Las dos
   tasas del BCV y el IBC son nuestros y salen de un JSON que actualizamos cada
   tarde. En la documentación está explicado el porqué.

3. Os pedimos una cosa: servir ese JSON desde vuestro backend en vez de desde
   GitHub. Bastaría un endpoint tipo GET /cinta que haga de proxy con caché de
   unos minutos. Hoy el componente lee de GitHub, que funciona, pero no está
   pensado como CDN de producción. Cuando exista el endpoint solo hay que
   cambiar una constante.

Si al añadir algún símbolo os aparece "Este símbolo solo está disponible en
TradingView", está explicado en la documentación: hay que probarlos pintándolos,
porque el buscador de TradingView y su API dicen cosas distintas del widget.

Cualquier duda, me decís.

Un saludo,
Saúl Benarroch
RendiGroup
saul@rendigroup.com
"""


def main():
    ap = argparse.ArgumentParser(description="Manda el cintillo a los devs")
    ap.add_argument("destinatarios", nargs="+", help="uno o varios correos")
    ap.add_argument("--ensayo", action="store_true", help="no envia, solo imprime")
    args = ap.parse_args()

    if not ADJUNTO.exists():
        print("No encuentro %s. Corre antes armar_entrega.py." % ADJUNTO.name)
        return 1

    usuario = os.environ.get("SMTP_USUARIO", "").strip()
    # Google da la contrasena de aplicacion en cuatro bloques con espacios y
    # smtplib la rechaza tal cual. Mismo criterio que correo.py.
    clave = os.environ.get("SMTP_CLAVE", "").replace(" ", "").strip()
    servidor = os.environ.get("SMTP_SERVIDOR", "").strip() or "smtp.gmail.com"
    puerto = int(os.environ.get("SMTP_PUERTO", "").strip() or "587")
    if not usuario or not clave:
        print("Faltan SMTP_USUARIO / SMTP_CLAVE.")
        return 1

    datos = ADJUNTO.read_bytes()
    tipo, _ = mimetypes.guess_type(ADJUNTO.name)
    mayor, menor = (tipo or "text/html").split("/", 1)

    print("=" * 66)
    print("De      : %s" % usuario)
    print("Para    : %s" % ", ".join(args.destinatarios))
    print("Asunto  : %s" % ASUNTO)
    print("Adjunto : %s (%d KB)" % (ADJUNTO.name, len(datos) // 1024))
    print("=" * 66)
    print(CUERPO)
    print("=" * 66)

    if args.ensayo:
        print("ENSAYO: no se ha mandado nada.")
        return 0

    enviados = []
    with smtplib.SMTP(servidor, puerto, timeout=45) as s:
        s.starttls()
        s.login(usuario, clave)
        for quien in args.destinatarios:
            msg = EmailMessage()
            msg["Subject"] = ASUNTO
            msg["From"] = formataddr(("Saúl Benarroch · RendiGroup", usuario))
            msg["To"] = quien
            msg["Reply-To"] = usuario
            msg.set_content(CUERPO)
            msg.add_attachment(datos, maintype=mayor, subtype=menor,
                               filename=ADJUNTO.name)
            try:
                s.send_message(msg)
                enviados.append(quien)
                print("  [correo] enviado a %s" % quien)
            except Exception as exc:  # noqa: BLE001
                # Un rebote no detiene a los demas, igual que en La Campana.
                print("  [correo] fallo con %s: %s" % (quien, str(exc)[:110]))

    print("\n%d de %d entregados." % (len(enviados), len(args.destinatarios)))
    return 0 if enviados else 1


if __name__ == "__main__":
    sys.exit(main())
