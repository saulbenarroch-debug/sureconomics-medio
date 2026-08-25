r"""Rota la clave de Gemini en el .env, con red de seguridad.

    .pyruntime\python.exe rotar_gemini.py

Lo que hace, en este orden y no en otro:

  1. Te pide la clave nueva SIN mostrarla en pantalla.
  2. La PRUEBA contra Gemini. Si no funciona, no toca nada y se acaba aqui.
  3. Copia el .env actual a .env.bak por si acaso.
  4. Escribe la clave nueva conservando el resto del archivo.
  5. Te recuerda los tres sitios que faltan y en que orden.

Probar antes de escribir es el punto entero del script: si se escribe primero y
la clave tenia un dedazo, el .env queda roto y el fallo aparece a las 10 de la
mañana sin decir por que.

La clave no se imprime, no se registra en ningun sitio y no sale de tu maquina
salvo a Google para la prueba.
"""

import getpass
import os
import pathlib
import shutil
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI / ".libs"))

ENV = pathlib.Path(r"C:\Users\saulb\telegram-finance-bot\.env")
CLAVE = "GEMINI_API_KEY"


def probar(clave):
    """Devuelve (sirve, mensaje). No imprime la clave nunca."""
    try:
        from google import genai
    except ImportError:
        return False, "no encuentro la libreria google-genai"
    try:
        cliente = genai.Client(api_key=clave)
        r = cliente.models.generate_content(
            model="gemini-2.5-flash-lite", contents="Responde solo: OK")
        return True, (r.text or "").strip()[:20]
    except Exception as exc:
        # El mensaje de error de Gemini puede traer la clave (va en la URL).
        # Se limpia antes de enseñarlo, o la filtramos en pantalla.
        msg = str(exc).replace(clave, "<CLAVE>")
        return False, msg[:150]


def escribir_env(clave_nueva):
    """Sustituye la linea de GEMINI_API_KEY conservando todo lo demas.

    Se escribe en UTF-8 SIN BOM a proposito: `Set-Content -Encoding utf8` de
    PowerShell 5.1 mete BOM y python-dotenv deja de leer la primera clave del
    archivo. Es una trampa ya documentada en los dos repos.
    """
    lineas = ENV.read_text(encoding="utf-8-sig").splitlines()
    salida, encontrada = [], False
    for linea in lineas:
        if linea.startswith(f"{CLAVE}="):
            salida.append(f"{CLAVE}={clave_nueva}")
            encontrada = True
        else:
            salida.append(linea)
    if not encontrada:
        salida.append(f"{CLAVE}={clave_nueva}")
    ENV.write_text("\n".join(salida) + "\n", encoding="utf-8")
    return encontrada


def main():
    print("=" * 68)
    print("ROTACIÓN DE LA CLAVE DE GEMINI")
    print("=" * 68)

    if not ENV.exists():
        print(f"No encuentro {ENV}")
        return 1

    print(f"\nArchivo: {ENV}")
    actual = ""
    for linea in ENV.read_text(encoding="utf-8-sig").splitlines():
        if linea.startswith(f"{CLAVE}="):
            actual = linea.split("=", 1)[1].strip()
    print(f"Clave actual: {'presente, ' + str(len(actual)) + ' caracteres' if actual else 'NO HAY'}")

    print("\nPega la clave NUEVA (no se va a ver mientras escribes) y pulsa Enter.")
    print("Para cancelar, pulsa Enter sin escribir nada.")
    nueva = getpass.getpass("Clave nueva: ").strip()

    if not nueva:
        print("\nCancelado. No toqué nada.")
        return 0
    if nueva == actual:
        print("\nEsa es la misma clave que ya estaba. No toqué nada.")
        return 0
    # Sin comprobacion de prefijo a proposito: conviven al menos dos formatos
    # ('AIza...' el clasico y 'AQ.A...' el nuevo de AI Studio), y avisar por un
    # prefijo desconocido daria falsas alarmas con claves perfectamente buenas.
    # La unica comprobacion que vale es la de verdad: llamar a Gemini.

    print("\n1. Probando la clave nueva contra Gemini...")
    sirve, detalle = probar(nueva)
    if not sirve:
        print(f"   NO FUNCIONA: {detalle}")
        print("\n   No escribí nada. El .env sigue como estaba.")
        print("   Revisa que la clave sea correcta y que la facturación esté")
        print("   activada en la cuenta nueva.")
        return 1
    print(f'   Funciona. Gemini respondió: "{detalle}"')

    print("\n2. Copia de seguridad...")
    respaldo = ENV.with_suffix(".env.bak")
    shutil.copy2(ENV, respaldo)
    print(f"   {respaldo}")

    print("\n3. Escribiendo el .env (UTF-8 sin BOM)...")
    sustituida = escribir_env(nueva)
    print("   línea sustituida" if sustituida else "   línea añadida al final")

    print("\n4. Comprobando que python-dotenv lo lee bien...")
    from dotenv import load_dotenv
    os.environ.pop(CLAVE, None)
    load_dotenv(ENV, override=True)
    leida = os.environ.get(CLAVE, "")
    if leida == nueva:
        print("   Correcto: se lee igual que se escribió.")
    else:
        print("   PROBLEMA: no se lee igual. Restaura con:")
        print(f"      copy {respaldo} {ENV}")
        return 1

    print("\n" + "=" * 68)
    print("HECHO EN TU MÁQUINA. Faltan tres sitios, EN ESTE ORDEN:")
    print("=" * 68)
    print("""
  a) El Worker de Cloudflare — lee la clave del .env que acabas de actualizar:
         cd C:\\Users\\saulb\\telegram-finance-bot
         .pyruntime\\python.exe scripts\\deploy_worker.py
     Espera 10-20 segundos antes de probarlo: si lo pruebas de inmediato
     responde la versión anterior y parece que no funcionó.

  b) Secret GEMINI_API_KEY en el repo telegram-finance-bot
  c) Secret GEMINI_API_KEY en el repo wallstreet-bot
     (Settings -> Secrets and variables -> Actions -> GEMINI_API_KEY -> Update)

  Después, COMPROBAR antes de revocar la vieja:
     .pyruntime\\python.exe comprobar.py          (aquí, Gemini en verde)
     Actions -> news.yml -> Run workflow          (llega el mensaje de Telegram)
     Actions -> boletin.yml -> Run workflow       (llega el correo)
     Pregúntale algo al bot conversacional        (responde)

  Y SOLO ENTONCES revocar la clave vieja en la cuenta personal.
  Si revocas antes, el fallo es silencioso: no salta ningún error, simplemente
  no llega el mensaje de las 10.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
