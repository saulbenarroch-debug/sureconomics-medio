r"""Manda los borradores de hoy por correo, para no buscarlos entre archivos.

    .pyruntime\python.exe enviar.py hoy/ saul@rendigroup.com

Reutiliza el envio de La Campana (`wallstreet-bot/correo.py`), que ya usa la
cuenta de rendigroup.com con contraseña de aplicacion. No se duplica la logica
SMTP: se importa la que lleva meses funcionando.

HTML de CORREO, no de web: tablas en vez de flex, estilos en linea, 640 px de
ancho. Gmail borra el <style> del <head> — leccion ya pagada en La Campana.
"""

import html as _html
import json
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))
sys.path.insert(0, r"C:\Users\saulb\wallstreet-bot")

from dotenv import load_dotenv  # noqa: E402

# Las credenciales SMTP viven en el .env de La Campana, que es donde estan
# configuradas y probadas. No se copian aqui. En GitHub Actions ese archivo no
# existe y load_dotenv no hace nada: las variables llegan del entorno.
load_dotenv(r"C:\Users\saulb\wallstreet-bot\.env")

try:
    import correo  # noqa: E402
except ImportError:
    # En Actions no existe C:\Users\saulb\wallstreet-bot, asi que no hay de
    # donde importar el envio. Antes esto tumbaba la corrida entera en el ultimo
    # paso, con las piezas ya escritas y sin forma de que llegaran a nadie.
    #
    # Se replica aqui lo minimo, con la MISMA interfaz, para no tener que tocar
    # nada mas abajo. No es duplicar por gusto: en la maquina del dueño se sigue
    # usando el correo.py de La Campana, que es el que lleva meses probado, y
    # esto solo entra cuando aquel no esta.
    import os
    import smtplib
    from email.message import EmailMessage
    from email.utils import formataddr

    class correo:  # noqa: N801
        @staticmethod
        def enviar(asunto, html, texto_plano=""):
            usuario = os.environ.get("SMTP_USUARIO", "").strip()
            clave = os.environ.get("SMTP_CLAVE", "").replace(" ", "").strip()
            if not usuario or not clave:
                raise RuntimeError(
                    "Faltan SMTP_USUARIO / SMTP_CLAVE. Con Gmail hace falta una "
                    "'contrasena de aplicacion', no la contrasena de la cuenta.")
            servidor = os.environ.get("SMTP_SERVIDOR", "smtp.gmail.com").strip()
            puerto = int(os.environ.get("SMTP_PUERTO", "587"))
            nombre = os.environ.get("REMITENTE_NOMBRE", "SurEconomics").strip()
            lista = [d.strip() for d in
                     os.environ.get("DESTINATARIOS", "").split(",") if d.strip()]
            if not lista:
                raise RuntimeError("DESTINATARIOS esta vacio.")

            enviados = 0
            with smtplib.SMTP(servidor, puerto, timeout=45) as s:
                s.starttls()
                s.login(usuario, clave)
                for quien in lista:
                    msg = EmailMessage()
                    msg["Subject"] = asunto
                    msg["From"] = formataddr((nombre, usuario))
                    msg["To"] = quien
                    msg.set_content(texto_plano or "Se ve mejor en HTML.")
                    msg.add_alternative(html, subtype="html")
                    try:
                        s.send_message(msg)
                        enviados += 1
                        print(f"  [correo] enviado a {quien}")
                    except Exception as e:  # noqa: BLE001
                        print(f"  [correo] fallo con {quien}: {e}")
            return enviados

TINTA, GRIS, VERDE, ROJO = "#1a2331", "#5a636e", "#2c6a4e", "#b22f26"


def _pieza_html(texto, veredicto, hallazgos):
    partes = []
    for linea in texto.strip().split("\n"):
        if not linea.strip():
            continue
        e = _html.escape(linea)
        if linea.startswith("["):
            partes.append(f'<p style="margin:0 0 6px;font:bold 11px Arial;'
                          f'color:{GRIS};letter-spacing:.4px">{e}</p>')
        elif linea.isupper() and len(linea) > 25:
            partes.append(f'<p style="margin:0 0 10px;font:bold 17px Georgia,serif;'
                          f'color:{TINTA};line-height:1.25">{e}</p>')
        elif linea.startswith("SurEconomics:"):
            partes.append(f'<p style="margin:14px 0 4px;font:bold 13px Arial;'
                          f'color:{VERDE}">{e}</p>')
        elif linea.startswith("Sacado de:"):
            partes.append(f'<p style="margin:2px 0;font:11px Arial;color:{GRIS};'
                          f'word-break:break-all">{e}</p>')
        # El pie de la pieza («Perecedero · ES»). Antes empezaba con un guion
        # largo y se reconocia por ahi; ya no lleva guion, asi que se reconoce
        # por lo que es: una linea corta con el separador de metadatos.
        elif " · " in linea and len(linea) < 60:
            partes.append(f'<p style="margin:8px 0 0;font:11px Arial;color:{GRIS}">{e}</p>')
        else:
            partes.append(f'<p style="margin:0 0 10px;font:14px/1.55 Georgia,serif;'
                          f'color:{TINTA}">{e}</p>')

    color = ROJO if veredicto == "BLOQUEADA" else VERDE
    avisos = "".join(
        f'<p style="margin:2px 0;font:11px Arial;color:{GRIS}">{_html.escape(h.strip())}</p>'
        for h in hallazgos)
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 26px">
      <tr><td style="background:#fbfaf8;border:1px solid #e6e3dd;padding:20px">
        {''.join(partes)}
      </td></tr>
      <tr><td style="padding:8px 4px 0">
        <p style="margin:0 0 4px;font:bold 11px Arial;color:{color}">{veredicto}</p>
        {avisos}
      </td></tr>
    </table>"""


def main():
    carpeta = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "hoy")
    destino = sys.argv[2] if len(sys.argv) > 2 else "saul@rendigroup.com"

    piezas = sorted(carpeta.glob("[0-9]*.txt"))
    if not piezas:
        print(f"No hay piezas en {carpeta}/")
        return 1

    cuerpos, planos, bloqueadas = [], [], 0
    for ruta in piezas:
        texto = ruta.read_text(encoding="utf-8")
        datos = {}
        json_ruta = ruta.with_suffix(".json")
        if json_ruta.exists():
            datos = json.loads(json_ruta.read_text(encoding="utf-8"))
        veredicto = "BLOQUEADA" if datos.get("bloqueada") else "APROBADA por el auditor"
        if datos.get("bloqueada"):
            bloqueadas += 1
        cuerpos.append(_pieza_html(texto, veredicto, datos.get("hallazgos", [])))
        planos.append(texto + "\n\n" + "-" * 60 + "\n")

    from datetime import date
    # El mes estaba escrito a mano ("de agosto") y en septiembre habria
    # fechado mal todos los correos sin que nadie lo notara.
    MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    _h = date.today()
    hoy = f"{_h.day} de {MESES[_h.month - 1]} de {_h.year}"
    resumen = (f"{len(piezas)} piezas · {len(piezas) - bloqueadas} aprobadas"
               + (f" · {bloqueadas} bloqueadas" if bloqueadas else ""))

    html = f"""<body style="margin:0;padding:20px 10px;background:#f2f1ee">
    <table width="640" align="center" cellpadding="0" cellspacing="0"
           style="background:#fff;padding:26px;border:1px solid #e6e3dd">
      <tr><td>
        <p style="margin:0 0 2px;font:bold 11px Arial;color:{GRIS};
                  letter-spacing:.6px">SURECONOMICS · BORRADORES</p>
        <p style="margin:0 0 4px;font:bold 22px Georgia,serif;color:{TINTA}">{hoy}</p>
        <p style="margin:0 0 20px;padding-bottom:14px;border-bottom:2px solid {TINTA};
                  font:12px Arial;color:{GRIS}">{resumen}</p>
        {''.join(cuerpos)}
        <p style="margin:20px 0 0;padding-top:14px;border-top:1px solid #e6e3dd;
                  font:11px Arial;color:{GRIS}">
          Ninguna está publicada. Todas entran como borrador y las aprueba Edición.
        </p>
      </td></tr>
    </table></body>"""

    # El nombre de la carpeta entra en el asunto cuando no es la del dia. Dos
    # tandas del mismo dia salian con el asunto identico ("6 borradores del 25
    # de agosto") y en la bandeja no habia forma de saber cual era cual.
    tanda = "" if carpeta.name == "hoy" else f" ({carpeta.name})"
    # Singular cuando va una sola. «1 borradores» delata que lo escribe
    # una maquina, y este correo lo abre Edicion todos los dias.
    palabra = "borrador" if len(piezas) == 1 else "borradores"
    asunto = f"SurEconomics · {len(piezas)} {palabra} del {hoy}{tanda}"

    # CUIDADO AQUI. correo.enviar() lee los destinatarios de la variable de
    # entorno DESTINATARIOS, que en el .env de La Campana tiene CINCO personas de
    # rendigroup.com. Si no se pisa, estos borradores les llegarian a todas.
    # Se fija solo el destinatario pedido, y el remitente se identifica como
    # SurEconomics para que no parezca un correo de La Campana.
    import os
    os.environ["DESTINATARIOS"] = destino
    os.environ["REMITENTE_NOMBRE"] = "SurEconomics"

    enviados = correo.enviar(asunto, html, "\n".join(planos))
    print(f"Enviado a {destino}: {enviados} destinatario(s)")
    print(f"Asunto: {asunto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
