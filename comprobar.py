r"""Centinela (A12): comprueba que todo lo de fuera responde.

    .pyruntime\python.exe comprobar.py

Existe por una razon concreta. El respaldo de IA (Groq) llevaba meses declarado
como plan B de tres sistemas y nunca se habia probado: devuelve 403 porque
bloquea las IP de centro de datos, y como solo se activa cuando Gemini falla,
nadie se entero. Un respaldo sin probar no es un respaldo.

Se corre a mano antes de una tanda, o en un workflow. Devuelve codigo 1 si algo
critico esta caido, para que un cron pueda avisar.
"""

import os
import json
import pathlib
import socket
import sys
import urllib.error
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

socket.setdefaulttimeout(25)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

fallos = []


def linea(estado, nombre, detalle="", critico=False):
    marca = {"ok": "  OK  ", "mal": "FALLA ", "aviso": " aviso"}[estado]
    print(f"{marca} {nombre:34} {detalle}")
    if estado == "mal" and critico:
        fallos.append(nombre)


def huella(clave):
    """Identifica una clave sin revelarla: 8 caracteres del hash.

    Sirve para responder "que clave esta usando este sistema" sin exponerla. Se
    puede imprimir en un log de GitHub Actions sin riesgo y comparar con la de
    aqui: si coinciden, ese sistema ya usa la clave nueva; si no, se quedo con la
    vieja y la migracion no esta completa.

    Sin esto, una migracion a medias es invisible: el sistema que no se actualizo
    sigue funcionando con la clave antigua y nadie se entera hasta que esa clave
    muere.
    """
    import hashlib
    return hashlib.sha256(clave.encode()).hexdigest()[:8] if clave else "-"


def modelos_de_ia():
    print("\n--- MODELOS DE IA ---")
    import requests

    # SE COMPRUEBAN TODAS LAS CUENTAS, NO SOLO LA PRIMERA. orquestar.py no
    # arranca la tanda si ve "CUOTA AGOTADA" en esta salida, asi que mirando
    # solo la principal se quedaria el motor parado con la reserva intacta, que
    # es justo lo contrario de para lo que se puso la reserva.
    #
    # Por eso esa frase solo se escribe cuando NO QUEDA NINGUNA. Si una tiene
    # cuota, la corrida sale.
    from motor.ia import MODELOS_GEMINI, claves_gemini

    cuentas = claves_gemini()
    if not cuentas:
        linea("mal", "Gemini", "no hay GEMINI_API_KEY", critico=True)
    else:
        from google import genai
        # El modelo se lee de motor/ia.py, no se escribe otra vez aqui: con el
        # nombre duplicado, el centinela daba 404 mientras el motor ya estaba
        # corregido, y parecia una caida de Gemini que no existia.
        modelo = MODELOS_GEMINI[-1]  # el mas barato de la cadena
        con_cuota, fallos = [], []
        for nombre, clave in cuentas:
            print(f"        huella de la clave '{nombre}': {huella(clave)}")
            try:
                # El cliente se guarda en una variable: creado en linea, se
                # cierra antes de que termine la llamada y da "client has been
                # closed", que parece una caida de Gemini y no lo es.
                cliente = genai.Client(api_key=clave)
                cliente.models.generate_content(model=modelo, contents="di OK")
                linea("ok", f"Gemini ({nombre})", f"responde ({modelo})")
                con_cuota.append(nombre)
            except Exception as exc:
                msg = str(exc)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    linea("aviso", f"Gemini ({nombre})", "sin cuota")
                else:
                    linea("aviso", f"Gemini ({nombre})", msg[:60])
                    fallos.append(nombre)
        if not con_cuota:
            # La frase que lee orquestar.py. Solo aqui, y solo si no queda nada.
            linea("mal", "Gemini", "CUOTA AGOTADA hoy en todas las cuentas",
                  critico=len(fallos) == len(cuentas))

    clave = os.environ.get("GROQ_API_KEY", "").strip()
    if not clave:
        linea("aviso", "Groq (respaldo)", "no hay GROQ_API_KEY")
        return
    try:
        r = requests.get("https://api.groq.com/openai/v1/models",
                         headers={"Authorization": f"Bearer {clave}"}, timeout=30)
        if r.ok:
            linea("ok", "Groq (respaldo)", f"{len(r.json().get('data', []))} modelos")
        elif r.status_code == 403 and "network" in r.text.lower():
            # No es la clave: con una clave inventada da el mismo 403. Groq
            # bloquea IP de centro de datos y de VPN.
            #
            # En la maquina del dueño esto es NORMAL y no se puede arreglar: hace
            # falta VPN para trabajar, y la VPN es justo lo que Groq bloquea. Va
            # como aviso, no como fallo: un centinela que da una alarma inevitable
            # cada vez que se corre acaba ignorandose, y entonces no avisa de nada.
            #
            # Donde SI hay que comprobarlo es en GitHub Actions, que es donde corre
            # la produccion: ver .github/workflows/comprobar-groq.yml
            linea("aviso", "Groq (respaldo)",
                  "403 por RED (esperado tras la VPN). Comprobar en Actions")
        elif r.status_code == 401:
            linea("mal", "Groq (respaldo)", "401: la clave no vale, hay que rotarla")
        else:
            linea("mal", "Groq (respaldo)", f"{r.status_code}: {r.text[:50]}")
    except Exception as exc:
        linea("mal", "Groq (respaldo)", type(exc).__name__)


def desde_donde_nos_ven():
    print("\n--- RED ---")
    try:
        import json
        d = json.load(urllib.request.urlopen("https://ipinfo.io/json", timeout=20))
        org = d.get("org", "")
        detalle = f"{d.get('country')} · {d.get('city', '')} · {org[:36]}"
        # Una IP de centro de datos o VPN la bloquean varios proveedores.
        sospechoso = any(p in org.lower() for p in
                         ("datacamp", "vpn", "hosting", "cloud", "digitalocean",
                          "ovh", "hetzner", "linode", "m247"))
        linea("aviso" if sospechoso else "ok", "Salimos a internet como", detalle)
        if sospechoso:
            print("        ^ es un rango de centro de datos o VPN. Varios "
                  "proveedores de IA los bloquean.")
    except Exception:
        linea("aviso", "Salimos a internet como", "no pude comprobarlo")


def bases_de_datos():
    print("\n--- BASES DE DATOS ---")
    pruebas = [
        ("Banco Mundial", "https://api.worldbank.org/v2/country/VEN/indicator/"
                          "FP.CPI.TOTL.ZG?format=json&mrnev=1", True),
        ("Damodaran (NYU Stern)", "https://pages.stern.nyu.edu/~adamodar/pc/"
                                  "datasets/ctryprem.xlsx", False),
        ("EMBI vía BCRP", "https://estadisticas.bcrp.gob.pe/estadisticas/series/"
                          "api/PN01129XM/json/2026-07/2026-08", False),
    ]
    for nombre, url, critico in pruebas:
        try:
            p = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
            with urllib.request.urlopen(p) as r:
                linea("ok", nombre, f"HTTP {r.status}")
        except urllib.error.HTTPError as e:
            linea("mal", nombre, f"HTTP {e.code}", critico=critico)
        except Exception as e:
            linea("mal", nombre, type(e).__name__, critico=critico)


def diarios():
    print("\n--- DIARIOS (lista blanca) ---")
    import feedparser
    from motor.fuentes.noticias import MEDIOS

    caidos = []
    for clave, medio in MEDIOS.items():
        try:
            f = feedparser.parse(medio["url"], agent=NAVEGADOR)
            n = len(f.entries)
            if n:
                linea("ok", f"{medio['nombre']} ({clave})", f"{n} notas")
            else:
                linea("mal", f"{medio['nombre']} ({clave})",
                      f"0 notas [HTTP {getattr(f, 'status', '?')}]")
                caidos.append(clave)
        except Exception as e:
            linea("mal", f"{medio['nombre']} ({clave})", type(e).__name__)
            caidos.append(clave)

    if caidos:
        print(f"\n        {len(caidos)} feed(s) sin responder: {', '.join(caidos)}")
        print("        Un feed caido no tumba una corrida, pero si son varios se "
              "estrecha la cobertura sin que se note.")



def cuota_de_busqueda():
    """Cuanto queda del plan de Tavily.

    Se añadio el 28/08/2026 porque el plan gratuito se agoto sin que nadie lo
    viera venir: 886 de 1.000 creditos consumidos, y el aviso llego cuando
    quedaban 114. Un limite que solo se descubre al chocar con el no es un
    limite, es una sorpresa. Aqui se ve todos los dias, junto al resto.
    """
    print("\n--- CUOTA DE BÚSQUEDA ---")
    clave = os.environ.get("TAVILY_API_KEY", "").strip()
    if not clave:
        linea("mal", "Tavily", "sin clave en el .env", critico=True)
        return
    try:
        peticion = urllib.request.Request(
            "https://api.tavily.com/usage",
            headers={"Authorization": "Bearer " + clave})
        with urllib.request.urlopen(peticion, timeout=20) as r:
            datos = json.load(r)
    except Exception as exc:  # noqa: BLE001
        linea("mal", "Tavily", f"no responde: {str(exc)[:60]}", critico=True)
        return

    cuenta = datos.get("account", {}) or {}
    usados = cuenta.get("plan_usage")
    limite = cuenta.get("plan_limit")
    plan = cuenta.get("current_plan", "?")
    if not limite:
        linea("ok", "Tavily", f"plan {plan}, sin límite declarado")
        return
    quedan = limite - usados
    porcentaje = 100.0 * usados / limite
    # Por debajo del 20 % restante se avisa, pero no se considera caido: el
    # sistema sigue funcionando y lo que hace falta es tiempo para reaccionar.
    detalle = f"plan {plan}: {usados} de {limite} ({porcentaje:.0f} %), quedan {quedan}"
    linea("ok" if quedan > limite * 0.2 else "aviso", "Tavily", detalle)
    if quedan <= limite * 0.2:
        print(f"   OJO: al ritmo de esta semana, eso son pocos días. "
              f"Renovar o subir de plan antes de quedarse sin búsqueda.")


if __name__ == "__main__":
    print("=" * 72)
    print("CENTINELA — comprobación de todo lo que depende de fuera")
    print("=" * 72)
    desde_donde_nos_ven()
    modelos_de_ia()
    bases_de_datos()
    cuota_de_busqueda()
    diarios()
    print("\n" + "=" * 72)
    if fallos:
        print(f"HAY {len(fallos)} FALLO(S) CRÍTICO(S): {', '.join(fallos)}")
        sys.exit(1)
    print("Nada crítico caído.")
    sys.exit(0)
