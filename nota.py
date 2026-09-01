r"""Escribe UNA pieza a peticion, desde un enlace o un tema.

    .pyruntime\python.exe nota.py "https://elpais.com/economia/..."
    .pyruntime\python.exe nota.py "Petrobras sube el precio del queroseno"

Es lo que dispara el comando /nota del bot de Telegram. Cuando alguien de la
redaccion ve algo que el robot no ha cogido, lo pega en el chat y esto corre la
cadena completa: fuente, expediente, cifras, redaccion, auditoria y correo.

DOS ENTRADAS, UNA SALIDA

Con un ENLACE se lee la nota, se registra como fuente verificada y se escribe
sobre ella. Es el caso bueno: hay un documento concreto detras.

Con un TEMA suelto se busca en la lista blanca de medios. Si no aparece nada,
NO se inventa: se dice que no se encontro y se termina. Un motor que escribe
sobre un tema sin fuente es exactamente lo que este proyecto evita.

COMPRUEBA SI YA ESTA PUBLICADO ANTES DE ESCRIBIR. Alguien puede pedir algo que
salio en la tanda de la mañana, y de hecho paso el 31/08/2026 con una captura
que llego por el chat. Si ya esta, lo dice y no gasta nada.
"""

import argparse
import pathlib
import re
import subprocess
import sys
import unicodedata
import urllib.request
from datetime import date

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _plano(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _apodo(texto):
    """Nombre de archivo corto y sin sorpresas."""
    s = re.sub(r"[^a-z0-9]+", "-", _plano(texto)).strip("-")
    return (s[:38] or "peticion")


def leer_enlace(url):
    """Trae titular y texto de una nota. Sin IA: solo limpieza de etiquetas."""
    peticion = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(peticion, timeout=45) as r:
        crudo = r.read().decode("utf-8", "replace")

    titulo = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", crudo, re.S | re.I)
    if m:
        titulo = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                  crudo, re.I)
    if m:
        titulo = re.sub(r"\s+", " ", m.group(1)).strip()

    # Fuera lo que no es texto de la nota antes de recoger parrafos.
    cuerpo = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form)[^>]*>.*?</\1>",
                    " ", crudo)
    parrafos = []
    for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", cuerpo):
        t = re.sub(r"(?s)<[^>]+>", " ", p)
        t = re.sub(r"&nbsp;", " ", t)
        t = re.sub(r"&amp;", "&", t)
        t = re.sub(r"\s+", " ", t).strip()
        # Los parrafos cortos de una web son pies, menus y avisos de cookies.
        if len(t) > 90:
            parrafos.append(t)
    return titulo, parrafos[:14]


def medio_de(url):
    d = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return d.split(".")[0].replace("-", " ").title()


def _escapar(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _trozos(texto, tope=3900):
    """Parte por parrafos, nunca a mitad de frase.

    Telegram corta en 4096 caracteres. Partir por el numero pelado deja una nota
    cortada en mitad de una cifra, que es justo donde no se puede cortar en un
    medio que publica cifras.
    """
    partes, actual = [], ""
    for parrafo in texto.split("\n\n"):
        if len(actual) + len(parrafo) + 2 > tope and actual:
            partes.append(actual.rstrip())
            actual = ""
        # Un parrafo mas largo que el tope entero: se parte por lineas.
        while len(parrafo) > tope:
            corte = parrafo.rfind(" ", 0, tope)
            corte = corte if corte > tope // 2 else tope
            partes.append(parrafo[:corte])
            parrafo = parrafo[corte:].lstrip()
        actual += parrafo + "\n\n"
    if actual.strip():
        partes.append(actual.rstrip())
    return partes


def mandar_al_chat(borrador, chat, quien=""):
    """Manda el borrador al chat que lo pidio. Devuelve True si salio.

    EL CORREO SIGUE SIENDO EL CANAL PRINCIPAL y esto no lo sustituye: si
    Telegram falla, la pieza ya se envio por correo y no se pierde. Por eso los
    fallos aqui se avisan y no cortan nada.
    """
    import json as _json
    import urllib.error

    ficha = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not ficha or not chat:
        print("  [chat] sin TELEGRAM_TOKEN o sin chat: no se manda.")
        return False

    lineas = [l for l in borrador.read_text(encoding="utf-8").split("\n")]
    # El archivo trae [Noticia] [tags], titulo, [Fecha] y luego el cuerpo.
    utiles = [l.strip() for l in lineas if l.strip()]
    titulo = next((l for l in utiles[:4] if l.isupper() and len(l) > 25), "(sin titulo)")
    desde = utiles.index(titulo) + 1
    cuerpo = [l for l in utiles[desde:]
              if not l.startswith(("[Fecha]", "Perecedero", "[Autor]"))]

    # Si el auditor la bloqueo hay que decirlo ARRIBA. Un borrador que llega al
    # chat sin esa marca invita a publicarlo tal cual.
    estado = ""
    ruta_json = borrador.with_suffix(".json")
    if ruta_json.exists():
        try:
            if _json.loads(ruta_json.read_text(encoding="utf-8")).get("bloqueada"):
                estado = "⛔ <b>BLOQUEADA POR EL AUDITOR.</b> No publicar sin revisar.\n\n"
        except Exception:  # noqa: BLE001
            pass

    cabecera = "📝 <b>Borrador listo</b>%s\n\n" % (" · pedido por " + _escapar(quien) if quien else "")
    texto = (cabecera + estado + "<b>" + _escapar(titulo) + "</b>\n\n"
             + "\n\n".join(_escapar(l) for l in cuerpo)
             + "\n\n<i>Queda en borrador. No se publica solo.</i>")

    enviados = 0
    for i, trozo in enumerate(_trozos(texto)):
        cuerpo_pet = _json.dumps({"chat_id": chat, "text": trozo,
                                  "parse_mode": "HTML",
                                  "disable_web_page_preview": True}).encode()
        pet = urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % ficha,
            data=cuerpo_pet, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pet, timeout=30):
                enviados += 1
        except urllib.error.HTTPError as exc:
            print("  [chat] trozo %d rechazado: %s" % (i + 1, exc.read().decode()[:130]))
        except Exception as exc:  # noqa: BLE001
            print("  [chat] trozo %d fallo: %s" % (i + 1, str(exc)[:90]))
    print("  [chat] %d mensaje(s) enviados a %s" % (enviados, chat))
    return enviados > 0


def main():
    ap = argparse.ArgumentParser(description="Una pieza a peticion")
    ap.add_argument("peticion", help="un enlace, o un tema en palabras")
    ap.add_argument("--tipo", default="Noticia")
    ap.add_argument("--correo", default="saul@rendigroup.com")
    ap.add_argument("--quien", default="", help="quien la pidio, para el correo")
    ap.add_argument("--chat", default="", help="chat de Telegram al que devolverla")
    args = ap.parse_args()

    peticion = args.peticion.strip()
    es_enlace = peticion.startswith("http://") or peticion.startswith("https://")
    print("=" * 70)
    print("NOTA A PETICION%s" % (" · pedida por " + args.quien if args.quien else ""))
    print(peticion[:100])
    print("=" * 70)

    if not es_enlace:
        # Sin enlace no hay documento que verificar. Se podria buscar en los
        # feeds, pero eso es justo lo que hace la tanda: si el tema esta ahi,
        # saldra sola. Se pide el enlace, que es barato para quien lo manda.
        print("\nEsto no es un enlace. Manda la direccion de la nota:")
        print("  /nota https://medio.com/la-noticia")
        print("\nCon el enlace hay un documento concreto que verificar. Con un")
        print("tema suelto habria que fiarse de lo que el modelo recuerde, y")
        print("eso es exactamente lo que este motor no hace.")
        return 1

    # Lo barato primero: ¿ya lo contamos?
    print("\n--- 1. ¿YA ESTA PUBLICADO? ---")
    try:
        from motor import memoria
        titulo_previo, _ = leer_enlace(peticion)
        ya = memoria.ya_cubierto(titulo_previo) if titulo_previo else None
        if ya:
            print("  SI. Coincide con: %s" % ya["titulo"])
            print("  https://www.sureconomics.com/%s" % ya["slug"])
            print("\nNo se escribe nada. Si aun asi la quieres, dilo y se fuerza.")
            return 0
        print("  no, es nueva")
    except Exception as exc:  # noqa: BLE001
        print("  [aviso] no pude comprobarlo (%s). Se sigue." % str(exc)[:60])

    print("\n--- 2. LEER LA FUENTE ---")
    try:
        titulo, parrafos = leer_enlace(peticion)
    except Exception as exc:  # noqa: BLE001
        print("  No pude leer ese enlace: %s" % str(exc)[:90])
        print("  Algunos medios bloquean la lectura automatica. Pega el texto")
        print("  a mano con agregar_fuente.py y vuelve a intentarlo.")
        return 1
    if not parrafos:
        print("  El enlace responde pero no encuentro texto de nota.")
        print("  Puede ser un video, una galeria o un muro de pago.")
        return 1
    print("  %s" % titulo[:90])
    print("  %d parrafos, %d caracteres" % (len(parrafos), sum(len(p) for p in parrafos)))

    nombre = _apodo(titulo or peticion)
    archivo = AQUI / "fuentes_manuales" / (nombre + ".txt")
    archivo.parent.mkdir(exist_ok=True)
    archivo.write_text(
        "url: %s\nmedio: %s\nfecha: %s\n\n%s\n" % (
            peticion, medio_de(peticion), date.today().isoformat(),
            "\n\n".join(parrafos)),
        encoding="utf-8")

    r = subprocess.run([sys.executable, str(AQUI / "agregar_fuente.py"), str(archivo)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("  No se pudo registrar la fuente:")
        print((r.stdout or "") + (r.stderr or "")[-300:])
        return 1
    print("  fuente registrada como '%s'" % nombre)

    print("\n--- 3. ESCRIBIR Y AUDITAR ---")
    r = subprocess.run(
        [sys.executable, str(AQUI / "motor" / "producir.py"),
         "--tipo", args.tipo, "--manual", nombre],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=25 * 60)
    print((r.stdout or "")[-1500:])
    if r.returncode != 0 and (r.stderr or "").strip():
        print("  FALLO:")
        for l in (r.stderr or "").strip().splitlines()[-6:]:
            print("    " + l[:150])

    borrador = AQUI / "borradores" / ("%s_%s.txt" % (nombre, args.tipo.lower()))
    if not borrador.exists():
        print("\nNo se genero el borrador. Revisa el fallo de arriba.")
        return 1

    print("\n--- 4. ENTREGA ---")
    carpeta = AQUI / ("peticion-" + date.today().isoformat() + "-" + nombre[:18])
    carpeta.mkdir(exist_ok=True)
    for sufijo in (".txt", ".json"):
        origen = borrador.with_suffix(sufijo)
        if origen.exists():
            (carpeta / ("1-" + nombre[:26] + sufijo)).write_bytes(origen.read_bytes())
    r = subprocess.run([sys.executable, str(AQUI / "enviar.py"), str(carpeta), args.correo],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "")[-300:])

    # El correo va primero y siempre. Esto es un extra: quien la pidio por el
    # chat la recibe por el chat, sin cambiar de aplicacion para leerla.
    if args.chat:
        mandar_al_chat(borrador, args.chat, args.quien)

    print("\nListo. Queda en borrador, como todo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
