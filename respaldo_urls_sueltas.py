r"""Respalda las portadas que NO son assets, sino una direccion en un campo.

    .pyruntime\python.exe respaldo_urls_sueltas.py

POR QUE EXISTE APARTE

Treinta piezas antiguas no usan el almacen de medios: guardan la direccion de la
imagen en el campo de texto featured_image_url y tiran de un servidor ajeno. Por
eso no aparecen en /admin/media y el respaldo de assets no las vio. Veintiocho
apuntan a Cloudinary, o sea que se caen con la migracion igual que las demas, y
nadie las habria echado en falta hasta que el sitio saliera con huecos.

Las otras dos NO se bajan aqui y es a proposito: una tira de semana.com y otra
de un WordPress ajeno. Esas no las afecta la migracion porque nunca estuvieron
en nuestro almacen, pero son enlaces a servidores de otros medios, que es un
problema distinto y peor: se caen cuando el otro quiera y ademas no tenemos
derecho a mostrarlas. Van anotadas para que alguien decida, no copiadas.
"""

import hashlib
import json
import pathlib
import sys
import time
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
DESTINO = AQUI / "respaldo-imagenes" / "sin-asset"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# post -> direccion. Sacadas de featured_image_url el 01/09/2026.
PORTADAS = {
    103: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785877913/sureconomics/articulos/29venezuela-quake-casualties-hmcj-videoSixteenByNine3000_yvu2lk.jpg",
    105: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785869970/sureconomics/articulos/Gemini_Generated_Image_r6amayr6amayr6am_seq2yj.png",
    106: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785871897/sureconomics/articulos/Gemini_Generated_Image_vmirm6vmirm6vmir_fxxj3j.png",
    107: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785877204/sureconomics/articulos/Gemini_Generated_Image_nu01xhnu01xhnu01_kn41ts.png",
    108: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785877353/sureconomics/articulos/Gemini_Generated_Image_h3gqufh3gqufh3gq_kselhd.png",
    109: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785939333/sureconomics/articulos/Gemini_Generated_Image_jxpphqjxpphqjxpp_uxtukb.png",
    110: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785945880/sureconomics/articulos/Gemini_Generated_Image_g6d8tog6d8tog6d8_rczchw.png",
    111: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785946333/sureconomics/articulos/Gemini_Generated_Image_52yenm52yenm52ye_uakf3y.png",
    112: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785957814/sureconomics/articulos/pexels-nataliaolivera-32082839_pfalgj.jpg",
    113: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785946749/sureconomics/articulos/Gemini_Generated_Image_w7lmfiw7lmfiw7lm_wciyti.png",
    114: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785947323/sureconomics/articulos/Gemini_Generated_Image_ir08a6ir08a6ir08_o21wwp.png",
    115: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785957129/sureconomics/articulos/pexels-franco30-3577875_shcda6.jpg",
    116: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785947787/sureconomics/articulos/Gemini_Generated_Image_59beqr59beqr59be_nyashv.png",
    117: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785957105/sureconomics/articulos/Gemini_Generated_Image_t33yzht33yzht33y_fszhrt.png",
    118: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785956564/sureconomics/articulos/pexels-hejpetrpepa-pepa-927919250-35981527_rbfiwc.jpg",
    119: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785956815/sureconomics/articulos/pexels-kampus-7854123_zkdwre.jpg",
    120: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785942838/sureconomics/articulos/Gemini_Generated_Image_dxo86kdxo86kdxo8_ngk68e.png",
    121: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1785943144/sureconomics/articulos/Gemini_Generated_Image_djef6jdjef6jdjef_qbwjdv.png",
    122: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786640227/sureconomics/articulos/Reserva_Federal_ardfjb.png",
    123: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786640626/sureconomics/articulos/UE_xwm3zm.png",
    124: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786650064/sureconomics/articulos/OPEP_cin4ch.png",
    125: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786650535/sureconomics/articulos/Organizacion_Mundial_de_la_Salud_tbz2hp.png",
    126: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786651125/sureconomics/articulos/Banco_mundial_tsaezn.png",
    127: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786651475/sureconomics/articulos/ChatGPT_Image_13_ago_2026_04_04_15_p.m._f1e9c7.png",
    128: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786652133/sureconomics/articulos/CHINA-CELAC_nor5yd.png",
    129: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1787151655/sureconomics/articulos/FMI_nhxhee.png",
    130: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1787152566/sureconomics/articulos/ChatGPT_Image_19_ago_2026_11_15_46_a.m._tpmhu4.png",
    224: "https://res.cloudinary.com/pjr7bqzt/image/upload/v1786628178/sureconomics/articulos/pexels-bryan-bravo-1331578-3535926_sk9icw.jpg",
}

# No se copian: son de otros medios. Ver la cabecera.
AJENAS = {
    101: "semana.com",
    102: "estaticos.sfo2.digitaloceanspaces.com (WordPress ajeno)",
}


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    registro, fallos = [], []
    print("PORTADAS SIN ASSET  ·  %d de Cloudinary" % len(PORTADAS))

    for post, url in sorted(PORTADAS.items()):
        ext = "." + url.split("?")[0].rsplit(".", 1)[-1][:4]
        ruta = DESTINO / ("post%04d%s" % (post, ext))
        if ruta.exists() and ruta.stat().st_size > 0:
            continue
        try:
            pet = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
            with urllib.request.urlopen(pet, timeout=60) as r:
                crudo = r.read()
        except Exception as exc:  # noqa: BLE001
            fallos.append((post, str(exc)[:70]))
            print("  post %s FALLA: %s" % (post, str(exc)[:60]))
            continue
        ruta.write_bytes(crudo)
        registro.append({"post": post, "archivo": ruta.name, "bytes": len(crudo),
                         "sha256": hashlib.sha256(crudo).hexdigest(), "url_vieja": url})
        time.sleep(0.15)

    ficha = DESTINO / "registro.json"
    previo = json.loads(ficha.read_text(encoding="utf-8")) if ficha.exists() else []
    porPost = {r["post"]: r for r in previo}
    porPost.update({r["post"]: r for r in registro})
    ficha.write_text(json.dumps(sorted(porPost.values(), key=lambda r: r["post"]),
                                ensure_ascii=False, indent=2), encoding="utf-8")

    print("\na salvo: %d de %d  (%.1f MB)"
          % (len(porPost), len(PORTADAS),
             sum(r["bytes"] for r in porPost.values()) / 1048576))
    print("\nNO se copian, son de otros medios:")
    for post, de in AJENAS.items():
        print("  post %s: %s" % (post, de))
    if fallos:
        print("\nfallos: %s" % fallos)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
