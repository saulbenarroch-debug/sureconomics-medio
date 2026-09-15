r"""Copia los secretos que ya existen en local a los Secrets del repositorio.

    .pyruntime\python.exe poner_secretos.py --ver
    .pyruntime\python.exe poner_secretos.py --poner

NUNCA imprime un valor. Solo el nombre, la longitud y una huella de 8 caracteres,
que es lo justo para saber si el secreto de GitHub y el de tu maquina son el
mismo sin que ninguno de los dos aparezca en un registro.

GitHub exige cifrar cada valor con la clave publica del repositorio (caja
sellada de libsodium) antes de enviarlo. No hay forma de mandarlo en claro, y
esta bien que sea asi.

DE DONDE SALE CADA UNO

  GEMINI_API_KEY, GROQ_API_KEY, TAVILY_API_KEY  ->  .env del bot de Telegram
  SMTP_USUARIO, SMTP_CLAVE                      ->  .env de La Campana

DESTINATARIOS se fija aparte y a proposito: el .env de La Campana tiene CINCO
personas de rendigroup.com, y los borradores del medio no van para ellas.
enviar.py ya lo pisa al enviar, pero si el secreto llevara la lista de La
Campana, cualquier descuido futuro se los mandaria.
"""

import argparse
import base64
import hashlib
import os
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

from crear_repo import _llamar  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

REPO = "saulbenarroch-debug/sureconomics-medio"

ORIGENES = {
    r"C:\Users\saulb\telegram-finance-bot\.env":
        # GEMINI_API_KEY_RESERVA es la SEGUNDA cuenta de Gemini, y es opcional:
        # si no esta en el .env, este script la salta y el motor sigue con una
        # sola (ver motor.claves_gemini). Tienen que ser de PROYECTOS distintos
        # o comparten cuota y el embudo no sirve de nada.
        ["GEMINI_API_KEY", "GEMINI_API_KEY_RESERVA",
         "GROQ_API_KEY", "TAVILY_API_KEY",
         "TELEGRAM_TOKEN", "CHAT_ID",
         # Cuenta de servicio del panel. Sin esto, las tandas escriben y mandan
         # el correo pero no suben nada: subir.py corta con un mensaje claro.
         "SURECONOMICS_USUARIO", "SURECONOMICS_CLAVE"],
    r"C:\Users\saulb\wallstreet-bot\.env":
        ["SMTP_USUARIO", "SMTP_CLAVE"],
}

# Ver la cabecera. Un solo destinatario, el del dueño.
FIJOS = {"DESTINATARIOS": "saul@rendigroup.com",
         "REMITENTE_NOMBRE": "SurEconomics"}


def _huella(v):
    return hashlib.sha256(v.encode()).hexdigest()[:8]


def reunir():
    """Lee los .env SIN tocar os.environ.

    Antes usaba load_dotenv(override=True) y el segundo archivo pisaba el
    GITHUB_PAT que este mismo script necesita para hablar con GitHub: se quedaba
    sin token a mitad de camino, con un error que apuntaba al sitio equivocado.
    dotenv_values devuelve un diccionario y no toca nada.
    """
    valores = {}
    for ruta, nombres in ORIGENES.items():
        if not pathlib.Path(ruta).exists():
            print("  falta %s" % ruta)
            continue
        archivo = dotenv_values(ruta)
        for n in nombres:
            v = (archivo.get(n) or "").strip()
            if v:
                valores[n] = v
            else:
                print("  %s no esta en %s" % (n, pathlib.Path(ruta).name))
    valores.update(FIJOS)

    # LA VIGILANCIA AVISA SOLO AL DUEÑO. CHAT_ID lleva tres personas y son los
    # destinatarios del boletin, no un grupo de guardia: una alerta cada hora a
    # gente que no la pidio se vuelve ruido, y el ruido se ignora. Se sube el
    # primero de la lista, que es el suyo, y ampliarlo es decision suya.
    #
    # CHAT_ID entero NO se sube: desde el repo del medio no tiene que poder
    # salir un mensaje a los tres por un descuido.
    lista = [x.strip() for x in valores.pop("CHAT_ID", "").split(",") if x.strip()]
    if lista:
        valores["VIGILANCIA_CHAT_ID"] = lista[0]
    return valores


def ver():
    valores = reunir()
    print("\nlo que se copiaria (valores ocultos):")
    for n, v in valores.items():
        print("  %-18s %3d caracteres   huella %s" % (n, len(v), _huella(v)))

    actuales, _ = _llamar("/repos/%s/actions/secrets" % REPO)
    if "_error" in actuales:
        print("\nNo puedo leer los secretos del repo: HTTP %s" % actuales["_error"])
        print("Al token le falta el permiso 'Secrets' (Read and write).")
        return 1
    print("\nya en el repositorio: %s" % (
        ", ".join(s["name"] for s in actuales.get("secrets", [])) or "(ninguno)"))
    return 0


def poner():
    import nacl.encoding
    import nacl.public

    llave, _ = _llamar("/repos/%s/actions/secrets/public-key" % REPO)
    if "_error" in llave:
        print("No puedo pedir la clave publica: HTTP %s" % llave["_error"])
        print("Al token le falta el permiso 'Secrets' (Read and write).")
        return 1

    publica = nacl.public.PublicKey(llave["key"].encode(),
                                    nacl.encoding.Base64Encoder)
    caja = nacl.public.SealedBox(publica)

    fallos = 0
    for nombre, valor in reunir().items():
        cifrado = base64.b64encode(caja.encrypt(valor.encode())).decode()
        r, _ = _llamar("/repos/%s/actions/secrets/%s" % (REPO, nombre), "PUT",
                       {"encrypted_value": cifrado, "key_id": llave["key_id"]})
        malo = isinstance(r, dict) and r.get("_error") not in (None, 201, 204)
        print("  %-18s %s   huella %s" % (
            nombre, "MAL: HTTP %s" % r["_error"] if malo else "puesto", _huella(valor)))
        fallos += 1 if malo else 0

    actuales, _ = _llamar("/repos/%s/actions/secrets" % REPO)
    print("\nel repositorio tiene ahora: %s" %
          ", ".join(sorted(s["name"] for s in actuales.get("secrets", []))))
    return 1 if fallos else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--poner", action="store_true")
    a = ap.parse_args()
    sys.exit(poner() if a.poner else ver())
