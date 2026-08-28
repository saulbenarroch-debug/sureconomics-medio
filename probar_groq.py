r"""Comprueba contra la API de Groq lo que de verdad sigue funcionando.

    .pyruntime\python.exe probar_groq.py

La documentacion de Groq bloquea la lectura automatica, asi que se pregunta al
propio servicio: que modelos existen hoy, si nuestro modelo sigue vivo, si el
endpoint de siempre responde y si el nuevo de "responses" existe.

CONTEXTO. Groq es el respaldo del motor: solo entra cuando Gemini falla. Por eso
mismo es donde un cambio pasa desapercibido durante meses. Ya ocurrio: llevaba
tiempo declarado como plan B y devolvia 403 sin que nadie lo supiera, porque
nadie lo habia llamado nunca.

OJO CON EL 403. Groq bloquea las IP de centros de datos y de VPN. En la maquina
del dueño, que trabaja con VPN, un 403 de red NO significa que la clave o el
modelo esten mal. Aqui se distingue una cosa de la otra.
"""

import io
import json
import os
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

BASE = "https://api.groq.com/openai/v1"


def _cabeceras():
    clave = os.environ.get("GROQ_API_KEY", "").strip()
    if not clave:
        raise SystemExit("No hay GROQ_API_KEY en el .env")
    return {"Authorization": "Bearer " + clave, "Content-Type": "application/json"}


def _diagnostico(r):
    """Traduce el codigo a lo que significa para nosotros."""
    if r.status_code == 403 and "network" in r.text.lower():
        return "403 POR RED (VPN o centro de datos). No es la clave."
    if r.status_code == 401:
        return "401: la clave no vale, hay que rotarla."
    if r.status_code == 404:
        return "404: esta ruta ya no existe."
    if r.status_code == 400:
        return "400: la ruta existe pero no le gusta lo que enviamos."
    return "HTTP %s" % r.status_code


def main():
    import requests
    from motor.ia import MODELO_GROQ

    print("modelo que usa el motor: %s\n" % MODELO_GROQ)

    print("--- 1. Que modelos existen hoy ---")
    r = requests.get(BASE + "/models", headers=_cabeceras(), timeout=40)
    if not r.ok:
        print("  " + _diagnostico(r))
        print("\n  Sin esto no se puede comprobar nada mas desde aqui.")
        print("  Donde SI se puede es en GitHub Actions, que no sale por VPN.")
        return 1

    modelos = [m["id"] for m in r.json().get("data", [])]
    print("  %d modelos" % len(modelos))
    vivo = MODELO_GROQ in modelos
    print("  %s sigue publicado: %s" % (MODELO_GROQ, "SI" if vivo else "NO, HAY QUE CAMBIARLO"))
    for m in sorted(modelos):
        if "oss" in m or "llama" in m or "kimi" in m:
            print("     " + m)

    print("\n--- 2. El endpoint de siempre, con nuestra llamada exacta ---")
    r = requests.post(BASE + "/chat/completions", headers=_cabeceras(), timeout=60,
                      json={"model": MODELO_GROQ,
                            "messages": [{"role": "user", "content": "di OK"}],
                            "temperature": 0.4})
    print("  /chat/completions -> %s" % _diagnostico(r))
    if r.ok:
        print("  respondio: %r" % r.json()["choices"][0]["message"]["content"][:40])

    print("\n--- 3. El endpoint nuevo de responses ---")
    r = requests.post(BASE + "/responses", headers=_cabeceras(), timeout=60,
                      json={"model": MODELO_GROQ, "input": "di OK"})
    print("  /responses -> %s" % _diagnostico(r))
    if r.ok:
        print("  existe. No hace falta migrar, pero esta ahi.")
    elif r.status_code == 404:
        print("  no disponible para esta cuenta.")

    print("\n--- 4. Formato JSON, que es lo que nos importa ---")
    # El motor NO usa response_format porque daba 400. Se comprueba si eso
    # cambio: si ahora funciona, el respaldo puede dejar de pedir el JSON a mano.
    r = requests.post(BASE + "/chat/completions", headers=_cabeceras(), timeout=60,
                      json={"model": MODELO_GROQ,
                            "messages": [{"role": "user",
                                          "content": "Devuelve {\"ok\": true} en JSON"}],
                            "response_format": {"type": "json_object"}})
    print("  response_format json_object -> %s" % _diagnostico(r))
    if not r.ok:
        print("     %s" % r.text[:160])
    else:
        print("     YA FUNCIONA. El comentario de motor/ia.py esta desactualizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
