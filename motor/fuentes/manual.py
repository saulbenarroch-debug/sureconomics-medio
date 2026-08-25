"""Fuentes verificadas a mano por la redaccion.

Existe porque hay medios que no se pueden leer por RSS —ultimasnoticias.com.ve
devuelve 403 a cualquier lector automatico— y porque a veces un periodista
encuentra algo que ningun feed trae. Sin esta via, la unica alternativa era
escribir la cita "porque me lo dijeron", que es justo lo que el sistema existe
para impedir.

El trato es este: la redaccion pega el texto y el enlace de la nota REAL, y a
partir de ahi todo funciona igual que con cualquier otra fuente — el auditor
comprueba las citas textuales contra este material y bloquea lo que no cuadre.
Lo que NO se admite es un resumen de memoria: hay que traer el texto.

    fuentes_manuales/<nombre>.json

    {
      "hecho": "...",
      "fecha": "2026-08-21",
      "medio": "Últimas Noticias",
      "autor": "Aura Torrealba",
      "url": "https://...",
      "texto": "el cuerpo de la nota, o los parrafos que importan",
      "citas": ["frase textual 1", "frase textual 2"]
    }
"""

import json
import pathlib

from motor.paquete import Cifra, Fuente, Paquete

CARPETA = pathlib.Path(__file__).resolve().parent.parent.parent / "fuentes_manuales"


def disponibles():
    if not CARPETA.exists():
        return []
    return sorted(p.stem for p in CARPETA.glob("*.json"))


def extraer(nombre):
    """Devuelve el paquete de una fuente registrada a mano. None si no existe."""
    ruta = CARPETA / f"{nombre}.json"
    if not ruta.exists():
        print(f"[aviso] no hay fuente manual '{nombre}'. Disponibles: "
              f"{', '.join(disponibles()) or 'ninguna'}")
        return None

    d = json.loads(ruta.read_text(encoding="utf-8"))
    fuente = Fuente(
        id="man1",
        institucion=d["medio"],
        documento=d.get("titulo") or d["hecho"],
        url=d["url"],
    )

    # Las cifras que trae la nota se registran, pero como cualquier dato de
    # prensa: son de quien las publico, no nuestras.
    from motor.fuentes.noticias import cifras_del_texto
    cifras = cifras_del_texto(d.get("texto", ""), "man1", d["medio"])

    citas = [{"texto": c, "autor": d.get("declarante") or d["medio"],
              "fuente_id": "man1"} for c in d.get("citas", [])]
    # El texto completo tambien entra como cita: es contra esto que el auditor
    # comprueba que una frase entrecomillada exista de verdad.
    if d.get("texto"):
        citas.append({"texto": d["texto"], "autor": d["medio"], "fuente_id": "man1"})

    avisos = [
        f"FUENTE VERIFICADA A MANO por la redacción: {d['medio']}"
        + (f", por {d['autor']}" if d.get("autor") else "")
        + f", {d['fecha']}. Cítala por su nombre.",
        "Es fuente SECUNDARIA como cualquier diario: el hecho se cuenta citando "
        "al medio, y sus cifras no se publican como propias.",
        # Sin esta frase exacta el redactor no escribe la linea «Sacado de» al
        # pie, porque es la que dispara ese paso. Faltaba, y la primera pieza
        # hecha con fuente manual salio sin acreditar el enlace: la nota citaba
        # a Bloomberg Linea en el cuerpo, pero el lector no tenia como ir a
        # comprobarlo. Una fuente verificada a mano se acredita igual que
        # cualquier otra, o el trabajo de verificarla no se ve.
        f"ATRIBUCIÓN OBLIGATORIA: la pieza cierra con el enlace a la nota de "
        f"{d['medio']}.",
    ]
    avisos += d.get("advertencias", [])

    return Paquete(
        hecho=d["hecho"],
        fecha_hecho=d["fecha"],
        cifras=cifras,
        citas=citas,
        entidades=[d["medio"]] + d.get("entidades", []),
        fuentes=[fuente],
        advertencias=avisos,
    )
