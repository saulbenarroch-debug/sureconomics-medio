r"""Comprueba si la clave de Gemini puede generar imagenes, y con que modelo.

    .pyruntime\python.exe probar_imagen.py

Se escribio antes de construir nada que dependa de generar imagenes. Un plan B
sin probar no es un plan B: el respaldo de Groq llevaba meses declarado y daba
403 porque nadie lo habia llamado nunca. Aqui se comprueba primero y se decide
despues.
"""

import io
import os
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

# Los modelos de imagen de Gemini NO se llaman con generate_images (esa es la
# via de Imagen, que esta cuenta no tiene). Se llaman con generate_content y
# devuelven la imagen como una parte binaria de la respuesta.
CANDIDATOS = [
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
]


def main():
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        print("No hay GEMINI_API_KEY")
        return 1

    from google import genai
    cliente = genai.Client(api_key=clave)

    print("--- modelos que la cuenta declara para imagen ---")
    try:
        vistos = 0
        for m in cliente.models.list():
            nombre = getattr(m, "name", "")
            acciones = getattr(m, "supported_actions", None) or []
            if "image" in nombre.lower() or "imagen" in nombre.lower():
                print("  %-52s %s" % (nombre, ",".join(acciones)))
                vistos += 1
        if not vistos:
            print("  (ninguno con 'image' en el nombre)")
    except Exception as exc:  # noqa: BLE001
        print("  no pude listar: %s" % str(exc)[:110])

    print("\n--- prueba real de generacion ---")
    aviso = ("Ilustracion editorial abstracta sobre regulacion financiera "
             "internacional. Sin texto, sin logotipos, sin personas "
             "reconocibles. Formato apaisado.")
    for modelo in CANDIDATOS:
        try:
            r = cliente.models.generate_content(model=modelo, contents=aviso)
            partes = r.candidates[0].content.parts
            datos = [p.inline_data for p in partes if getattr(p, "inline_data", None)]
            if not datos:
                print("  fallo %-32s respondio sin imagen" % modelo)
                continue
            crudo = datos[0].data
            destino = AQUI / "prueba_ilustracion.png"
            destino.write_bytes(crudo)
            print("  OK    %-32s %d KB en %s" % (modelo, len(crudo) // 1024, destino.name))
            print("        tipo: %s" % datos[0].mime_type)
            return 0
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            corto = ("404 no existe" if "404" in msg or "NOT_FOUND" in msg else
                     "403 sin permiso" if "403" in msg or "PERMISSION" in msg else
                     "429 sin cuota" if "429" in msg else msg[:70])
            print("  fallo %-32s %s" % (modelo, corto))
    return 1


if __name__ == "__main__":
    sys.exit(main())
