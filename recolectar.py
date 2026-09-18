"""Agente A1 Recolector de Noticias y Candidatos.

Consolida la información de las 4 fuentes diseñadas (RSS, Tavily News,
Scrapers de Gobierno, Redes Sociales), deduplica titulares y URLs, puntúa con
criterio.py y genera un reporte estructurado y un archivo JSON de candidatos.
"""

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

from dotenv import load_dotenv  # noqa: E402
from motor import criterio  # noqa: E402
from motor import buscador  # noqa: E402
from motor.fuentes import noticias, oficiales  # noqa: E402
from motor.paquete import Fuente, Paquete  # noqa: E402

# Cargamos el .env desde el repositorio del bot de Telegram
load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")


def _a_paquete(c):
    """Convierte un resultado del buscador en Paquete, para poder mezclarlos.

    Es un candidato, no una fuente todavia: hay que abrir la nota y verificarla
    antes de escribir nada con ella. Por eso lleva su advertencia.
    """
    url = c.get("url", "")
    return Paquete(
        hecho=c.get("titular", ""),
        fecha_hecho=c.get("fecha", "") or "",
        citas=[{"texto": c.get("extracto", "") or "", "autor": c.get("medio", ""),
                "fuente_id": "web1"}] if c.get("extracto") else [],
        entidades=[c.get("medio", "")],
        fuentes=[Fuente(id="web1", institucion=c.get("medio", "") or "desconocido",
                        documento=c.get("titular", ""), url=url)],
        advertencias=["CANDIDATO DE BUSCADOR: no es fuente todavia. Hay que abrir "
                      "la nota, verificarla y registrarla con agregar_fuente.py."],
    )


def _parecidas(a, b):
    """Compara si dos titulares comparten más del 65% de sus palabras clave."""
    pa = set(re.findall(r"\w{5,}", a.lower()))
    pb = set(re.findall(r"\w{5,}", b.lower()))
    if not pa or not pb:
        return False
    return len(pa & pb) / min(len(pa), len(pb)) > 0.65


def recolectar(horas=24, limite=10):
    """Consolida candidatos de todas las fuentes y devuelve una lista de Paquetes."""
    print("=" * 70)
    print(f"Buscando noticias de las últimas {horas} horas...")
    print("=" * 70)

    paquetes_crudos = []

    # 1. RSS Feeds
    print("\n[1/3] Extrayendo de feeds RSS (noticias.py)...")
    try:
        # 400 Y NO 50. Este numero no era un tope de seguridad, era QUIEN GANABA
        # LA TANDA: extraer() hace 'return' al llegar y con 50 se llenaba con
        # los cuatro primeros medios de la lista. Ahora, con el tope por medio
        # (POR_MEDIO) ningun diario puede aportar mas de cuatro, asi que 400 da
        # de sobra para leer los 59 y que decida la puntuacion, que es lo que
        # tiene que decidir. Lo que sobre lo recorta criterio.ordenar() por
        # importancia, y luego --limite.
        rss_cands = noticias.extraer(medios=None, horas=horas, limite=400)
        print(f"      -> {len(rss_cands)} candidatos de RSS")
        paquetes_crudos.extend(rss_cands)
    except Exception as e:
        print(f"      [error] Falló la extracción RSS: {e}")

    # 2. Barrido temático en la web
    print("\n[2/3] Barrido temático en la web (buscador.py)...")
    try:
        api_cands = buscador.barrido_tematico(dias=max(1, horas // 24))
        print(f"      -> {len(api_cands)} candidatos de Tavily News")
        # El buscador devuelve diccionarios y los otros dos extractores
        # devuelven Paquetes. Mezclarlos rompia el consolidador en la primera
        # linea: 'dict' object has no attribute 'fuentes'. Se convierten aqui,
        # que es donde se juntan las tres vias.
        paquetes_crudos.extend(_a_paquete(c) for c in api_cands)
    except Exception as e:
        print(f"      [error] Falló la API de Noticias: {e}")

    # 3. Comunicados oficiales (fuente primaria)
    print("\n[3/3] Comunicados oficiales (fuentes/oficiales.py)...")
    try:
        oficial_cands = oficiales.extraer(dias=max(1, horas // 24), limite_por_entidad=2)
        print(f"      -> {len(oficial_cands)} comunicados")
        paquetes_crudos.extend(oficial_cands)
    except Exception as e:
        print(f"      [error] Falló extracción de comunicados oficiales: {e}")

    # NO HAY CUARTO PASO. La revision externa del 25/08/2026 incluia un extractor
    # de Reddit y X que se retiro por decision editorial del dueño: un medio de
    # economia no cita foros ni tuits como fuente. La prueba lo confirmo — de
    # cuatro subreddits tres devolvian 429, y lo que entraba eran estudiantes
    # preguntando por su carrera universitaria.
    #
    # Si algun dia se quieren las redes como TERMOMETRO de lo que preocupa a la
    # gente, ese es un uso distinto del de fuente y hay que decidirlo aparte.

    # Consolidador: Deduplicación y puntuación
    print("\n" + "-" * 70)
    print("Consolidando, deduplicando y puntuando candidatos...")
    print("-" * 70)

    urls_vistas = set()
    titulares_vistos = []
    candidatos_finales = []

    for p in paquetes_crudos:
        # Deduplicar por URL
        url_primaria = p.fuentes[0].url if p.fuentes else ""
        if url_primaria in urls_vistas:
            continue

        # Deduplicar por similitud de titulares
        titular = p.hecho
        if any(_parecidas(titular, t) for t in titulares_vistos):
            continue

        urls_vistas.add(url_primaria)
        titulares_vistos.append(titular)

        # Calculamos la puntuación de calidad con criterio.py
        resumen = p.citas[0]["texto"] if p.citas else ""
        # EL MOMENTO MANDA SOBRE LA FECHA para puntuar: trae la hora y permite
        # distinguir lo de hace diez minutos de lo de ayer. fecha_hecho es la
        # reserva para las fuentes que solo dan el dia (capturas, posts).
        cuando = getattr(p, "momento", "") or p.fecha_hecho
        puntos = criterio.puntuar(titular, resumen=resumen, url=url_primaria, fecha=cuando)

        # Guardamos la puntuación en el paquete (usamos un atributo dinámico o nota)
        p.advertencias.append(f"CALIDAD CANDIDATO: {puntos} puntos de relevancia.")
        # Guardamos como metadato
        candidatos_finales.append((puntos, p))

    # Ordenar por puntos (relevancia) descendente
    candidatos_finales.sort(key=lambda x: x[0], reverse=True)

    # Retornar solo el límite
    resultado = [p for puntos, p in candidatos_finales[:limite]]
    print(f"Recolección completada. De {len(paquetes_crudos)} candidatos crudos, quedarán {len(resultado)} filtrados.")
    return resultado


def imprimir_reporte(candidatos):
    """Imprime por pantalla el reporte legible del recolector."""
    if not candidatos:
        print("\nNo se encontraron candidatos válidos para procesar.")
        return

    print("\n" + "=" * 70)
    print("REPORTE DEL AGENTE RECOLECTOR A1 — MEJORES CANDIDATOS")
    print("=" * 70)

    for i, p in enumerate(candidatos, start=1):
        f = p.fuentes[0] if p.fuentes else None
        medio = f.institucion if f else "Desconocido"
        url = f.url if f else ""
        tipo_fuente = "Primaria" if any("FUENTE PRIMARIA" in a for a in p.advertencias) else "Secundaria"

        print(f"\n{i}. [{medio.upper()}] ({tipo_fuente}) — {p.fecha_hecho or 's/f'}")
        print(f"   Titular: {p.hecho}")
        print(f"   Enlace : {url}")
        cifras_claves = [f"{c.valor} {c.unidad}" for c in p.cifras]
        if cifras_claves:
            print(f"   Cifras encontradas: {', '.join(cifras_claves[:5])}")
        puntos_match = re.search(r"(\d+) puntos de relevancia", "".join(p.advertencias))
        puntos_str = puntos_match.group(1) if puntos_match else "N/A"
        print(f"   Puntuación de Relevancia: {puntos_str} pts")
    print("\n" + "=" * 70)


def main():
    ap = argparse.ArgumentParser(description="Agente A1 Recolector")
    ap.add_argument("--horas", type=int, default=24, help="Ventana de horas hacia atrás")
    ap.add_argument("--limite", type=int, default=10, help="Límite máximo de candidatos en el JSON")
    ap.add_argument("--guardar", default="hoy/candidatos.json", help="Destino del archivo de candidatos")
    args = ap.parse_args()

    candidatos = recolectar(horas=args.horas, limite=args.limite)
    imprimir_reporte(candidatos)

    if args.guardar and candidatos:
        ruta = pathlib.Path(args.guardar)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        
        # Convertimos los paquetes de datos a formato JSON
        datos = []
        for p in candidatos:
            datos.append(json.loads(p.a_json()))

        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Candidatos consolidados guardados en: {ruta}")


if __name__ == "__main__":
    main()
