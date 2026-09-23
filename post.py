r"""Dibuja la lamina de Instagram de una pieza YA PUBLICADA.

    python post.py https://www.sureconomics.com/<slug> --chat 123
    python post.py <slug> --titular "Trump aprieta a Mexico" --chat 123

POR QUE ESTO NO ES nota.py CON UNA BANDERA

Porque la lamina no necesita el motor. Para dibujarla hacen falta cuatro cosas
-titular corto, bajada, categoria e imagen- y para una pieza publicada las
cuatro EXISTEN YA en el panel: /posts/<slug> devuelve title, excerpt y places.

Asi que esto es leer, una llamada pequeña al modelo para acortar el titular, y
dibujar. Sin redactar, sin auditar, sin crear borrador y sin gastar cuota de
redactor. Meterlo dentro de nota.py obligaria a atravesar toda la cadena para
saltarsela entera al final.

EL CASO QUE LO PIDIO. Edicion pide /nota de algo que ya esta publicado, el
motor contesta «esa ya esta publicada» -que es lo correcto- y ahi se acababa:
el unico boton era «Escribirla igual», que rehace la pieza entera y deja un
borrador duplicado que nadie queria. Solo para conseguir la lamina.

LO QUE SE PUEDE IMPONER A MANO, y es la otra mitad de por que existe: titular,
bajada, categoria e imagen. Acortar un titular es criterio de redes, no un dato
que haya que auditar, y quien usa la lamina a diario quiere decidirlo. Aqui
cada intento cuesta segundos; por /nota costaba reescribir la nota entera.
"""

import argparse
import os
import pathlib
import re
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))


def _sin_etiquetas(html):
    """El excerpt viene en HTML y la lamina quiere texto."""
    texto = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", texto).strip()


def slug_de(peticion):
    """Acepta la direccion completa, el slug pelado o el id numerico.

    Se parte por '/' y se coge el ultimo trozo con contenido: asi da igual que
    llegue con https, con www, con barra final o con ?utm_source pegado, que es
    como salen los enlaces cuando alguien los copia del movil.

    EL ID NUMERICO ES POR EL BOTON. «Solo el post» manda el id y no el slug
    porque en callback_data de Telegram caben 64 bytes y los slugs del sitio
    llegan a 89 caracteres. Ver nota._botones_ya_publicada().
    """
    limpio = (peticion or "").strip().split("?")[0].split("#")[0]
    trozos = [t for t in limpio.split("/") if t.strip()]
    if not trozos:
        return ""
    ultimo = trozos[-1]
    # Un dominio suelto no es un slug: "sureconomics.com" tiene punto y los
    # slugs del sitio no. Sin esto, pegar la portada del medio "encontraba" una
    # pieza inexistente y el mensaje de error hablaba de otra cosa.
    return "" if "." in ultimo else ultimo


def pieza_publicada(referencia):
    """Trae del panel la pieza publicada por slug o por id, o None.

    POR QUE DOS RUTAS Y NO UNA. /posts/<slug> es la publica y devuelve la pieza
    tal y como la ve el sitio; /admin/posts/<id> es la de edicion. El boton
    manda el id, y una persona que pega un enlace manda el slug: se atienden
    las dos porque son las dos formas en que esto llega de verdad.
    """
    import subir

    panel = subir.Panel()
    panel.entrar()
    ruta = ("/admin/posts/%s" % referencia if str(referencia).isdigit()
            else "/posts/%s" % referencia)
    try:
        d = panel._crudo(ruta, "GET")
    except Exception as exc:  # noqa: BLE001
        print("  no pude leerla del panel (%s)" % str(exc)[:80])
        return None
    d = d.get("data", d)
    return d if isinstance(d, dict) and d.get("title") else None


def main():
    ap = argparse.ArgumentParser(
        description="La lamina de Instagram de una pieza ya publicada")
    ap.add_argument("peticion", help="direccion de la pieza publicada o su slug")
    ap.add_argument("--foto", default="",
                    help="file_id de una imagen mandada al bot; manda sobre la "
                         "portada de la pieza")
    ap.add_argument("--titular", default="", help="titular corto de la lamina")
    ap.add_argument("--bajada", default="", help="bajada de la lamina")
    ap.add_argument("--categoria", default="", help="la etiqueta roja")
    ap.add_argument("--chat", default="", help="chat de Telegram al que mandarla")
    # El pie de foto entero. De aqui salen «titular:», «bajada:» y «categoria:»
    # cuando se piden escribiendo en vez de por bandera, que es como llega
    # desde Telegram. Las banderas mandan sobre el pie: son mas explicitas.
    ap.add_argument("--encargo", default="",
                    help="el pie de foto, por si trae titular:/bajada:/categoria:")
    ap.add_argument("--salida", default="", help="donde dejar el PNG")
    args = ap.parse_args()

    from motor import lamina as _lam

    slug = slug_de(args.peticion)
    if not slug:
        print("No reconozco esa dirección. Pásame el enlace de la pieza "
              "publicada, algo como https://www.sureconomics.com/<slug>")
        return 1

    print("--- 1. LA PIEZA ---")
    print("  %s: %s" % ("id" if slug.isdigit() else "slug", slug))
    pieza = pieza_publicada(slug)
    if not pieza:
        print("  no la encuentro publicada")
        if args.chat:
            _avisar(args.chat,
                    "🔍 <b>No encuentro esa pieza publicada.</b>\n\n"
                    "Comprueba el enlace: tiene que ser el de una nota que ya "
                    "esté en sureconomics.com.")
        return 1

    titulo = pieza.get("title") or ""
    resumen = _sin_etiquetas(pieza.get("excerpt"))
    lugares = [p.get("name") for p in (pieza.get("places") or []) if p.get("name")]
    print("  %s" % titulo[:78])
    print("  lugares: %s" % (", ".join(lugares) or "ninguno"))

    print("\n--- 2. LA IMAGEN ---")
    fondo, credito = None, ""
    if args.foto:
        # LA QUE MANDA UNA PERSONA GANA SIEMPRE, igual que en nota.py. Si
        # alguien se molesto en adjuntar una imagen, no se le discute.
        from motor import captura
        try:
            datos, mime = captura.bajar_de_telegram(args.foto)
            fondo = AQUI / ("post-fondo" + (".jpg" if "jpeg" in (mime or "")
                                            else ".png"))
            fondo.write_bytes(datos)
            print("  la mandó Edición: %s" % fondo.name)
        except Exception as exc:  # noqa: BLE001
            print("  no pude traer la imagen del chat (%s)" % str(exc)[:70])
            fondo = None
    if not fondo and (pieza.get("featured_image_url") or "").strip():
        fondo = _lam.bajar(pieza["featured_image_url"], AQUI / "post-fondo")
        if fondo:
            print("  la portada de la pieza: %s" % fondo.name)
            # El credito de una publicada no viaja en el JSON del panel: vive
            # dentro del cuerpo, en el <em> que le pone armar_carga.py. Se saca
            # de ahi para que la lamina lo lleve, que es lo que exige CC BY.
            credito = _credito_del_cuerpo(pieza)
    if not fondo:
        # SIN IMAGEN NO HAY LAMINA, y hay que decirlo con lo que la persona
        # puede hacer. De 379 piezas publicadas, 349 no tienen portada (medido
        # el 21/09/2026): este es el camino normal, no el raro.
        print("  ni adjunta ni portada propia: no hay fondo que dibujar")
        if args.chat:
            _avisar(args.chat,
                    "🖼️ <b>Me falta la imagen.</b>\n\n"
                    "Esa pieza no tiene portada en el sitio, así que no tengo "
                    "fondo para la lámina.\n\n"
                    "Mándame la imagen en el mismo mensaje y te la hago.")
        return 1

    print("\n--- 3. LA LÁMINA ---")
    titular = args.titular or _lam.titular_pedido(args.encargo)
    bajada = args.bajada or _lam.bajada_pedida(args.encargo)
    categoria = args.categoria or _lam.categoria_pedida(args.encargo)
    destino = pathlib.Path(args.salida or (AQUI / ("post-%s.png" % slug[:40])))
    hecha = _lam.hacer(fondo, titulo, resumen, lugares, str(destino),
                       categoria=categoria, credito=credito,
                       titular=titular, bajada=bajada)
    if not hecha:
        print("  no se pudo dibujar")
        if args.chat:
            _avisar(args.chat, "⚠️ <b>No pude dibujar la lámina.</b>")
        return 1
    print("  %s" % hecha)

    if args.chat:
        from nota import _foto_telegram
        _foto_telegram(args.chat, hecha,
                       "🖼️ <b>Lámina para Instagram</b>\n"
                       "1080×1350. Si quieres cambiar el texto, repite el "
                       "comando con <code>titular:</code> y <code>bajada:</code>.")
    return 0


def _credito_del_cuerpo(pieza):
    """El credito que armar_carga.py dejo en el <em> del final del cuerpo."""
    cuerpo = pieza.get("content") or ""
    ems = re.findall(r"<em>(.*?)</em>", cuerpo, re.S)
    for e in reversed(ems):
        texto = _sin_etiquetas(e)
        # Se reconoce por la licencia, que es lo unico que siempre lleva. Un
        # <em> cualquiera del cuerpo es enfasis, no una atribucion de foto.
        if "Commons" in texto or "CC " in texto or "Foto:" in texto:
            return texto
    return ""


def _avisar(chat, texto):
    """Un aviso al chat. Se reusa el de nota.py: dos implementaciones de esto
    es como se llega a que una se arregle y la otra no."""
    try:
        from nota import _mensaje_telegram
        _mensaje_telegram(chat, texto)
    except Exception as exc:  # noqa: BLE001
        print("  [chat] no pude avisar (%s)" % str(exc)[:70])


if __name__ == "__main__":
    sys.exit(main())
