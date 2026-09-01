r"""Ronda de vigilancia: mira si ha pasado algo gordo y AVISA. No escribe.

    .pyruntime\python.exe vigilar.py
    .pyruntime\python.exe vigilar.py --ensayo    (no manda nada, solo imprime)

Corre cada hora en GitHub Actions. Decision del dueño el 01/09/2026: cuando
detecta algo, manda el titular al grupo de Telegram y espera. NO produce la
pieza sola.

POR QUE AVISAR Y NO ESCRIBIR

Porque una ronda que escribe cada hora produce piezas que nadie pidio, gasta
cuota en cada falso positivo y llena el panel de borradores sin dueño. Avisando,
las horas tranquilas no cuestan casi nada y ninguna pieza se escribe sin que una
persona la haya querido. El coste asumido es que si nadie mira el grupo, la
noticia espera a la tanda siguiente.

TRES FILTROS, DEL MAS BARATO AL MAS CARO

1. **Enlaces ya avisados**, de un archivo local. Gratis.
2. **Palabras de alto impacto**, una lista. Gratis. Si ninguna aparece, la ronda
   termina aqui sin gastar nada: son la mayoria de las horas.
3. **Ya publicado**, consultando el sitio (motor/memoria.py). Una llamada.

Solo lo que pasa los tres llega al aviso. El orden importa: comprobar lo
publicado es la parte cara y va la ultima.

NO LLAMA A LA IA EN NINGUN MOMENTO. La puntuacion la hace criterio.py, que es
codigo. Una ronda horaria que llamara al modelo veinticuatro veces al dia se
comeria la cuota que necesitan las tandas.
"""

import argparse
import json
import os
import pathlib
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")

ESTADO = AQUI / "vigilancia_estado.json"
MAX_RECORDADOS = 500

# Señales de que algo se sale de lo normal. En minusculas y sin tildes: el
# texto se normaliza antes de comparar, asi "devaluacion" caza con "devaluación".
SEÑALES = [
    "desplome", "desploma", "se hunde", "se hunden", "colapso", "colapsa",
    "quiebra", "bancarrota", "insolvencia", "default", "cesacion de pagos",
    "impago", "moratoria", "corralito", "congela", "sanciones", "sancion",
    "embargo", "expropia", "expropiacion", "nacionaliza", "estatiza",
    "devaluacion", "devalua", "maxidevaluacion", "hiperinflacion", "recesion",
    "rescate", "rebaja de calificacion", "degrada la nota", "sube las tasas",
    "recorta las tasas", "sube tasas", "recorta tasas", "tasa de interes",
    "renuncia", "destituye", "estado de emergencia", "cierra la frontera",
    "acuerdo con el fmi", "paquete de ayuda", "record historico", "maximo historico",
    "minimo historico", "suspende", "intervencion", "golpe", "paro nacional",
]

UMBRAL_PUNTOS = 8  # lo que criterio.py considera relevante de verdad


def _plano(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def cargar_avisados():
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8")).get("avisados", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def guardar_avisados(enlaces):
    ESTADO.write_text(json.dumps({"avisados": enlaces[-MAX_RECORDADOS:]},
                                 ensure_ascii=False, indent=1), encoding="utf-8")


def hay_señal(candidatos):
    """Filtro barato. Si devuelve False, la ronda termina sin gastar nada."""
    texto = _plano(" ".join(c["titular"] + " " + c.get("extracto", "")
                            for c in candidatos))
    return [s for s in SEÑALES if s in texto]


def recoger(horas=2):
    """Titulares recientes de la lista blanca. Sin IA, sin Tavily."""
    from motor.fuentes import noticias
    from motor import criterio

    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    salida = []
    for clave, medio in noticias.MEDIOS.items():
        try:
            import feedparser
            f = feedparser.parse(medio["url"], agent=noticias.NAVEGADOR
                                 if hasattr(noticias, "NAVEGADOR") else None)
        except Exception:  # noqa: BLE001
            continue
        for e in getattr(f, "entries", [])[:20]:
            titular = (e.get("title") or "").strip()
            enlace = (e.get("link") or "").strip()
            if not titular or not enlace:
                continue
            # LA VENTANA HAY QUE APLICARLA, NO SOLO CALCULARLA. En la primera
            # prueba se colaron dos notas del 27 de agosto en una ronda de seis
            # horas: el corte estaba escrito pero no se usaba. Una ronda horaria
            # que saca noticias de hace cinco dias es ruido, y ademas las avisa
            # una sola vez y luego las da por vistas, asi que el fallo se tapa
            # solo y no se vuelve a ver.
            marca = e.get("published_parsed") or e.get("updated_parsed")
            if marca:
                import calendar
                cuando = datetime.fromtimestamp(calendar.timegm(marca), timezone.utc)
                if cuando < desde:
                    continue
            salida.append({"titular": titular, "enlace": enlace,
                           "medio": medio["nombre"],
                           "extracto": (e.get("summary") or "")[:300],
                           "puntos": criterio.puntuar(titular, e.get("summary") or "",
                                                      enlace)})
    return salida


def avisar(hallazgos, ensayo=False):
    """Manda el aviso al grupo. Formato corto: se lee en el movil."""
    import requests
    ficha = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat = os.environ.get("VIGILANCIA_CHAT_ID", "").strip() or \
        os.environ.get("CHAT_ID", "").strip()
    lineas = ["<b>SurEconomics · vigilancia</b>", ""]
    for h in hallazgos:
        lineas.append("<b>%s</b>" % h["titular"][:150])
        lineas.append("%s · %d pts · %s" % (h["medio"], h["puntos"], h["enlace"]))
        lineas.append("")
    lineas.append("<i>Para que se escriba, responde:</i> /nota &lt;enlace&gt;")
    texto = "\n".join(lineas)

    if ensayo or not ficha or not chat:
        print("\n--- AVISO QUE SE MANDARIA ---\n" + texto)
        if not ensayo and (not ficha or not chat):
            print("\n[aviso] sin TELEGRAM_TOKEN o CHAT_ID: no se mando.")
        return False
    # Una sola linea de destinatarios, separada por comas, como en el bot.
    enviados = 0
    for uno in [c.strip() for c in chat.split(",") if c.strip()]:
        r = requests.post("https://api.telegram.org/bot%s/sendMessage" % ficha,
                          json={"chat_id": uno, "text": texto,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=30)
        if r.ok:
            enviados += 1
        else:
            print("  [telegram] %s: %s" % (uno, r.text[:110]))
    print("  aviso enviado a %d destino(s)" % enviados)
    return enviados > 0


def main():
    ap = argparse.ArgumentParser(description="Ronda de vigilancia horaria")
    ap.add_argument("--horas", type=int, default=2,
                    help="ventana hacia atras. Dos, no una: si un feed tarda en "
                         "actualizar, una ventana de una hora lo pierde")
    ap.add_argument("--maximo", type=int, default=3,
                    help="cuantos hallazgos como mucho por aviso")
    ap.add_argument("--ensayo", action="store_true", help="no manda nada")
    args = ap.parse_args()

    print("RONDA DE VIGILANCIA · %s UTC" % datetime.now(timezone.utc).strftime("%H:%M"))

    avisados = cargar_avisados()
    candidatos = [c for c in recoger(args.horas) if c["enlace"] not in avisados]
    print("  %d titulares nuevos en las ultimas %d horas" % (len(candidatos), args.horas))
    if not candidatos:
        return 0

    señales = hay_señal(candidatos)
    if not señales:
        print("  ninguna señal de alto impacto. Hora tranquila, no se gasta nada.")
        return 0
    print("  señales detectadas: %s" % ", ".join(señales[:6]))

    fuertes = sorted([c for c in candidatos if c["puntos"] >= UMBRAL_PUNTOS],
                     key=lambda c: -c["puntos"])
    # Solo los que ademas llevan una señal en SU propio titular: que la haya en
    # el lote no significa que la lleve esta nota.
    fuertes = [c for c in fuertes
               if any(s in _plano(c["titular"] + " " + c.get("extracto", ""))
                      for s in SEÑALES)]
    print("  %d pasan el umbral de %d puntos" % (len(fuertes), UMBRAL_PUNTOS))
    if not fuertes:
        return 0

    # Lo caro va al final: preguntar al sitio que hay publicado ya.
    try:
        from motor import memoria
        nuevos, repetidos = memoria.filtrar(fuertes, clave="titular")
        for c, ya in repetidos:
            print("  ya publicado: %s" % c["titular"][:60])
    except Exception as exc:  # noqa: BLE001
        print("  [aviso] la memoria fallo (%s). Se avisa igual." % str(exc)[:60])
        nuevos = fuertes

    if not nuevos:
        print("  todo lo fuerte ya esta publicado. Nada que avisar.")
        return 0

    # Y quitar los repetidos ENTRE ELLOS. Varios medios de la lista blanca
    # cubren el mismo hecho, y algunos son la misma casa: Infobae e Infobae
    # America publicaron identico el desplome de los bonos. En un aviso de tres
    # huecos, eso gasta dos en lo mismo.
    from motor import memoria as _mem
    distintos = []
    for c in nuevos:
        if any(_mem.parecido(c["titular"], d["titular"]) >= 0.6 for d in distintos):
            print("  repetida de otro medio: %s" % c["titular"][:58])
            continue
        distintos.append(c)
    nuevos = distintos

    hallazgos = nuevos[:args.maximo]
    print("\n  AVISAR %d:" % len(hallazgos))
    for h in hallazgos:
        print("    %3d pts · %s · %s" % (h["puntos"], h["medio"], h["titular"][:70]))

    if avisar(hallazgos, args.ensayo) and not args.ensayo:
        guardar_avisados(avisados + [h["enlace"] for h in hallazgos])
    return 0


if __name__ == "__main__":
    sys.exit(main())
