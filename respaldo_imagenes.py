r"""Baja a disco todas las imagenes del sitio, antes de que se apague Cloudinary.

    .pyruntime\python.exe respaldo_imagenes.py inventario.json

POR QUE

Van a activar Cloudflare R2 y, al migrar, se pierde lo que hay subido. De los
181 assets del sitio, 75 estan alojados en CLOUDINARY: esos mueren. Los otros
enlazan a Wikimedia, que no se cae con la migracion, pero se bajan igual porque
un enlace externo desaparece el dia que Wikimedia cambia una ruta, y eso ya
estaba apuntado como fragilidad del CMS.

QUE NO HACE ESTE ARCHIVO. No vuelve a subir nada. Subir necesita el sitio ya
migrado y una cuenta de servicio; esto solo pone a salvo los originales y deja
escrito que imagen era de cada pieza. Lo primero es no perder los bytes.

CADA IMAGEN SE GUARDA CON EL ID DEL ASSET EN EL NOMBRE. Ese id es la unica
forma de volver a atar cada imagen a su pieza despues de la migracion: los
nombres originales se repiten y varios son "ChatGPT Image ... .png".
"""

import argparse
import hashlib
import json
import pathlib
import sys
import time
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
# Wikimedia rechaza los agentes genericos y pide uno con contacto.
WIKIMEDIA = "SurEconomics/1.0 (respaldo del medio; saul@rendigroup.com)"


def extension(mime, url):
    for m, e in (("jpeg", ".jpg"), ("png", ".png"), ("webp", ".webp"),
                 ("gif", ".gif"), ("svg", ".svg"), ("pdf", ".pdf")):
        if m in (mime or "").lower():
            return e
    cola = url.split("?")[0].rsplit(".", 1)
    return ("." + cola[-1][:4]) if len(cola) == 2 and len(cola[-1]) <= 4 else ".bin"


def main():
    ap = argparse.ArgumentParser(description="Respaldo de las imagenes del sitio")
    ap.add_argument("inventario", help="el JSON que exporta el panel")
    ap.add_argument("--destino", default=str(AQUI / "respaldo-imagenes"))
    args = ap.parse_args()

    datos = json.loads(pathlib.Path(args.inventario).read_text(encoding="utf-8"))
    assets = datos["assets"]
    destino = pathlib.Path(args.destino)
    destino.mkdir(exist_ok=True)

    print("=" * 68)
    print("RESPALDO DE IMAGENES  ·  %d assets" % len(assets))
    print("destino: %s" % destino)
    print("=" * 68)

    registro, fallos, saltados = [], [], 0
    for i, a in enumerate(assets, 1):
        url = (a.get("url") or "").strip()
        if not url:
            fallos.append((a["id"], "sin url"))
            continue
        nombre = "%04d%s" % (a["id"], extension(a.get("mime"), url))
        ruta = destino / nombre

        if ruta.exists() and ruta.stat().st_size > 0:
            saltados += 1
            continue

        agente = WIKIMEDIA if "wikimedia" in url or "wikipedia" in url else NAVEGADOR
        try:
            pet = urllib.request.Request(url, headers={"User-Agent": agente})
            with urllib.request.urlopen(pet, timeout=60) as r:
                crudo = r.read()
        except Exception as exc:  # noqa: BLE001
            fallos.append((a["id"], str(exc)[:70]))
            print("  [%3d/%d] FALLA  %s  %s" % (i, len(assets), nombre, str(exc)[:50]))
            continue

        ruta.write_bytes(crudo)
        registro.append({
            "asset": a["id"], "archivo": nombre, "bytes": len(crudo),
            "sha256": hashlib.sha256(crudo).hexdigest(),
            "storage": a.get("storage"), "mime": a.get("mime"),
            "ancho": a.get("width"), "alto": a.get("height"),
            "nombre_original": a.get("original_filename") or "",
            "credito": a.get("credit") or "", "url_vieja": url})
        if i % 20 == 0 or i == len(assets):
            print("  [%3d/%d] %d bajadas, %d saltadas, %d fallos"
                  % (i, len(assets), len(registro), saltados, len(fallos)))
        time.sleep(0.15)   # no castigar a Wikimedia ni a Cloudinary

    # El registro se escribe SIEMPRE, aunque haya fallos: lo que se bajo bien
    # tiene que quedar anotado aunque una imagen concreta no responda.
    ficha = destino / "registro.json"
    previo = json.loads(ficha.read_text(encoding="utf-8")) if ficha.exists() else []
    porId = {r["asset"]: r for r in previo}
    porId.update({r["asset"]: r for r in registro})
    ficha.write_text(json.dumps(sorted(porId.values(), key=lambda r: r["asset"]),
                                ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(r["bytes"] for r in porId.values())
    print("\n" + "=" * 68)
    print("a salvo: %d imagenes, %.1f MB" % (len(porId), total / 1048576))
    print("registro: %s" % ficha)
    if fallos:
        print("\nNO SE PUDIERON BAJAR (%d). Estas se pierden si nadie las rescata:" % len(fallos))
        for ident, motivo in fallos:
            print("  asset %s: %s" % (ident, motivo))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
