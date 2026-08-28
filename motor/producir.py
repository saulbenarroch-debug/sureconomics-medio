"""La cadena completa: extraer -> redactar -> auditar -> borrador.

    python motor/producir.py --pais VEN --indicador inflacion --tipo Educación

No publica nada. Deja el borrador en borradores/ para que lo apruebe Edicion.
"""

import argparse
import json
import pathlib
import re
import sys

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(_RAIZ / ".libs"))  # openpyxl, para Damodaran

from dotenv import load_dotenv  # noqa: E402

from motor import auditor, documentalista, economista, redactor  # noqa: E402
from motor import biblioteca  # noqa: E402
from motor.paquete import componer  # noqa: E402
from motor.fuentes import banco_mundial, manual, noticias  # noqa: E402

# Las claves viven en el .env del bot: es la misma maquina y no tiene sentido
# duplicar secretos en dos sitios. Si algun dia se separan los despliegues, esto
# pasa a un .env propio.
load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")


def texto_legible(pieza):
    """La pieza como la leeria un editor, no como JSON."""
    e = pieza.get("etiquetas", {}) or {}
    etiquetas = " ".join(f"[{v}]" for v in
                         [pieza.get("tipo"), e.get("region"), e.get("subregion"),
                          e.get("pais"), e.get("topico")] if v)
    lineas = [etiquetas, "", (pieza.get("titulo") or "").upper(), ""]
    if pieza.get("autor"):
        lineas.append(f"[Autor] {pieza['autor']}")
    if pieza.get("fecha_publicacion"):
        lineas.append(f"[Fecha] {pieza['fecha_publicacion']}")
    lineas += ["", pieza.get("cuerpo", "")]
    bloque = (pieza.get("bloque_sureconomics") or "").strip()
    if bloque:
        # El modelo a veces repite la etiqueta dentro del propio campo.
        for etiqueta in ("SurEconomics:", "SURECONOMICS:"):
            if bloque.startswith(etiqueta):
                bloque = bloque[len(etiqueta):].lstrip()
        lineas += ["", "SurEconomics:", bloque]
    if pieza.get("sacado_de"):
        lineas += ["", pieza["sacado_de"]]
    extra = [f"{e.get('vigencia', '?')} · {e.get('idioma', '?')}"]
    # Sin guion largo al frente: norma del medio (ver redactor.py).
    lineas += ["", " · ".join(extra)]
    return "\n".join(lineas)


def _leer_candidato(ruta, indice):
    """Rehidrata un Paquete guardado por recolectar.py.

    Se reconstruyen Cifra y Fuente como objetos, no como diccionarios: el
    auditor y el redactor acceden por atributo (c.valor, f.institucion) y con
    diccionarios crudos fallarian con AttributeError a mitad de la cadena.
    """
    import json
    import pathlib

    from motor.paquete import Cifra, Fuente, Paquete

    datos = json.loads(pathlib.Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(datos, list):
        datos = [datos]
    if indice >= len(datos):
        print("El archivo tiene %d candidatos y se pidio el %d." % (len(datos), indice))
        return None

    crudo = datos[indice]
    paquete = Paquete(**{k: v for k, v in crudo.items()
                         if k in Paquete.__dataclass_fields__
                         and k not in ("cifras", "fuentes")})
    paquete.cifras = [Cifra(**{k: v for k, v in c.items()
                               if k in Cifra.__dataclass_fields__})
                      for c in crudo.get("cifras", [])]
    paquete.fuentes = [Fuente(**{k: v for k, v in f.items()
                                 if k in Fuente.__dataclass_fields__})
                       for f in crudo.get("fuentes", [])]
    print("   del recolector, sin volver a buscar:")
    print("   %s" % paquete.hecho[:90])
    if paquete.fuentes:
        print("   %s" % paquete.fuentes[0].url[:90])
    return paquete


def main():
    ap = argparse.ArgumentParser(description="Cadena completa de produccion")
    ap.add_argument("--diarios", help="claves de la lista blanca separadas por coma, "
                                      "o 'todos'. Ej: elnacional,clarin")
    ap.add_argument("--tema", help="filtro adicional por palabra, ej. 'inflaci|dolar'")
    ap.add_argument("--manual", help="nombre de una nota registrada a mano en "
                    "fuentes_manuales/. Es la via para los medios que no se "
                    "dejan leer por maquina y para lo que solo aparece en la web")
    ap.add_argument("--paquete", help="ruta a un candidatos.json de recolectar.py")
    ap.add_argument("--indice", type=int, default=0,
                    help="cual de los candidatos de ese archivo, empezando en 0")
    ap.add_argument("--horas", type=int, default=24)
    ap.add_argument("--pais", help="ISO3, para el Banco Mundial")
    ap.add_argument("--indicador", help="indicador del Banco Mundial")
    ap.add_argument("--ranking", help="ordena a los paises de America Latina por un indicador del Banco Mundial, ej. pib. El puesto lo calcula el codigo")
    ap.add_argument("--top", type=int, default=12,
                    help="cuantos paises entran en el ranking. Doce, porque con "
                         "diez Venezuela se queda fuera por un puesto y es el "
                         "pais del que escribimos")
    ap.add_argument("--contexto", default="",
                    help="fuerza el contexto a mano y salta al economista. "
                         "Ej: VEN:inflacion,dam:Venezuela,embi:Argentina")
    ap.add_argument("--tipo", required=True, choices=list(redactor.PROMPTS))
    ap.add_argument("--autor")
    ap.add_argument("--encargo", default="", help="instruccion puntual de edicion")
    ap.add_argument("--observaciones", type=int, default=3)
    ap.add_argument("--sin-economista", action="store_true",
                    help="salta la revision del economista (para comparar)")
    ap.add_argument("--sin-expediente", action="store_true",
                    help="salta al documentalista (mas rapido, menos fundamentado)")
    ap.add_argument("--sin-contexto", action="store_true",
                    help="no anadir contexto de datos, ni a mano ni por economista")
    args = ap.parse_args()

    print("=" * 70)
    print("1. EXTRACTOR — voy a la fuente")
    if args.paquete:
        # BUSCAR DOS VECES ERA EL FALLO. La corrida automatica del 28/08/2026
        # elegia bien el tema y luego le pedia a este archivo que lo volviera a
        # encontrar dando el medio y unas palabras. En tres de seis piezas el
        # filtro casaba antes con otra nota del mismo diario y se escribia sobre
        # otra cosa: se pidio el superavit del Orcamento brasileño y salio una
        # nota de vacantes de empleo. El texto estaba bien hecho y bien
        # auditado, pero no era la noticia elegida, que es un fallo que no deja
        # rastro de error en ningun sitio.
        #
        # El recolector ya tiene el paquete entero, con su url y sus cifras
        # verificadas. Aqui se lee tal cual y no se busca nada.
        paquete = _leer_candidato(args.paquete, args.indice)
    elif args.ranking:
        paquete = banco_mundial.ranking(args.ranking, top=args.top)
        # Un ranking no es un hecho noticioso: es una tabla. No hay «que mas se
        # sabe de esto» que buscar en la prensa, ni contexto que pedirle al
        # economista, porque el contexto ES la tabla entera. Cuando se dejaron
        # correr los dos pasos, el expediente devolvio NADA en cuatro de las
        # cinco busquedas y el economista pidio la inversion extranjera en
        # manufactura brasileña. Se apagan por defecto; --sin-expediente y
        # --sin-contexto siguen ahi por si algun dia se quiere lo contrario.
        args.sin_expediente = True
        args.sin_contexto = True
    elif args.manual:
        # Una nota verificada a mano puede ser la noticia, no solo el contexto.
        # Es el unico camino para los temas que no estan en ningun feed: el 25 de
        # agosto, siete de trece noticias del dia no aparecian en las 44 fuentes
        # y solo se llegaba a ellas buscando y abriendo la nota.
        paquete = manual.extraer(args.manual)
    elif args.diarios:
        medios = None if args.diarios == "todos" else args.diarios.split(",")
        lote = noticias.extraer(medios, horas=args.horas, limite=1, tema=args.tema)
        paquete = lote[0] if lote else None
    elif args.pais and args.indicador:
        paquete = banco_mundial.extraer(args.pais, args.indicador, args.observaciones)
    else:
        print("Indica --diarios, o bien --pais y --indicador.")
        return 1
    if not paquete:
        return 1

    # EL DOCUMENTALISTA VA PRIMERO. Antes de decidir que datos hacen falta hay
    # que saber que ya publico la prensa: sin este paso el sistema escribia con
    # una sola nota y se le escapaban cosas que llevaban dias publicadas en el
    # mismo diario que estabamos leyendo.
    if not args.sin_expediente:
        print("\n1b. DOCUMENTALISTA — ¿qué más se sabe de esto?")
        expediente, informe = documentalista.armar_expediente(paquete)
        for linea in informe:
            print(f"   {linea}")
        if expediente:
            paquete = componer(paquete, *expediente)
            print(f"   -> expediente de {len(expediente)} nota(s) añadido")

    # El economista elige el contexto POR DEFECTO. Elegirlo a mano reproduce el
    # error de pegarle el riesgo pais de Venezuela a una noticia de aranceles
    # entre EE.UU. y Canada: con tres fuentes equivocarse es facil, con quince es
    # lo mas probable. --contexto sigue existiendo para forzarlo a mano.
    contexto = args.contexto
    if args.sin_contexto:
        contexto = ""
    elif not contexto:
        print("\n1b. ECONOMISTA — ¿qué contexto pide esta noticia?")
        resumen = paquete.citas[0]["texto"] if paquete.citas else ""
        fallo = economista.pertinencia(paquete.hecho, resumen)
        if fallo:
            print(f"   {fallo.get('razon', '')}")
            for f in fallo.get("faltan", []) or []:
                print(f"   [falta] {f}")
            if fallo.get("sin_contexto"):
                print("   -> esta noticia se cuenta sola: sin contexto")
            else:
                contexto = ",".join(fallo.get("peticiones", []) or [])
                print(f"   -> {contexto or 'ninguno'}")
        else:
            print("   [aviso] el economista no respondió: sigo sin contexto")

    if contexto:
        extras = []
        for peticion in contexto.split(","):
            try:
                print(f"   + contexto: {biblioteca.describir(peticion)}")
                extras.append(biblioteca.traer(peticion, args.observaciones))
            except ValueError as exc:
                print(f"[aviso] {exc}")
        paquete = componer(paquete, *extras)

    del_hecho = sum(1 for c in paquete.cifras if c.rol == "hecho")
    del_ctx = len(paquete.cifras) - del_hecho
    print(f"   {del_hecho} cifras del hecho + {del_ctx} de contexto, "
          f"{len(paquete.fuentes)} fuente(s)")
    for a in paquete.advertencias:
        print(f"   ! {a}")

    print("\n2. REDACTOR — escribo la prosa")
    pieza = redactor.redactar(args.tipo, paquete, args.autor, args.encargo)
    if not pieza:
        return 1

    critica = None
    if not args.sin_economista:
        print("\n2b. ECONOMISTA — reviso el razonamiento")
        critica = economista.criticar(pieza, paquete)
        print(economista.resumen_critica(critica))
        if critica and critica.get("veredicto") == "revisar":
            print("\n2c. REDACTOR — segunda pasada, aplico la crítica")
            revisada = redactor.redactar(args.tipo, paquete, args.autor,
                                         args.encargo, critica=critica)
            # Si la segunda pasada falla, se conserva la primera: una pieza
            # revisable es mejor que ninguna pieza.
            if revisada:
                pieza = revisada
            else:
                print("[aviso] la segunda pasada falló; me quedo con el borrador")
        else:
            print("   el economista no pide cambios")

    print("\n3. AUDITOR — verifico contra el paquete")
    hallazgos = auditor.auditar(pieza, paquete, args.encargo)
    print(auditor.informe(hallazgos))

    print("\n" + "=" * 70)
    print(texto_legible(pieza))
    print("=" * 70)

    carpeta = pathlib.Path(__file__).resolve().parent.parent / "borradores"
    carpeta.mkdir(exist_ok=True)
    if args.paquete:
        # Sin esta rama, --paquete caia en el `else` del Banco Mundial y moria
        # con AttributeError sobre args.pais, que es None. La pieza ya estaba
        # escrita y auditada: se perdia entera en el ultimo paso, despues de
        # gastar las llamadas a la IA. Y como el fallo iba por stderr, la corrida
        # decia "0 piezas" sin explicar por que.
        institucion = paquete.fuentes[0].institucion if paquete.fuentes else "fuente"
        base = re.sub(r"[^a-z0-9]+", "-", institucion.lower()).strip("-")[:16]
        corto = re.sub(r"[^a-z0-9]+", "-", paquete.hecho.lower()).strip("-")[:30]
        if corto:
            base += "_" + corto
    elif args.ranking:
        base = f"ranking_{args.ranking}"
    elif args.manual:
        base = args.manual
    elif args.diarios:
        base = args.diarios.replace(",", "-")
        # EL TEMA ENTRA EN EL NOMBRE. Dos piezas del mismo diario en el mismo dia
        # se pisaban: el 27/08/2026 la de los activos expropiados y la del comite
        # de acreedores salian las dos de Bitacora Economica y la segunda borro a
        # la primera sin avisar. Un borrador que desaparece en silencio es peor
        # que uno que falla.
        if args.tema:
            corto = re.sub(r"[^a-z0-9]+", "-", args.tema.lower()).strip("-")[:24]
            if corto:
                base += "_" + corto
    else:
        base = f"{args.pais.lower()}_{args.indicador}"
    nombre = f"{base}_{args.tipo.lower()}"
    (carpeta / f"{nombre}.json").write_text(
        json.dumps({"pieza": pieza,
                    "bloqueada": auditor.bloqueada(hallazgos),
                    "hallazgos": [str(h) for h in hallazgos],
                    "critica_economista": critica,
                    # EL PAQUETE SE GUARDA CON LA PIEZA. Sin esto no se puede
                    # volver a auditar despues de una edicion a mano: reauditar.py
                    # tenia que reconstruirlo desde la fuente y perdia el
                    # expediente del documentalista, asi que marcaba como
                    # inventada cualquier cifra que viniera de una nota
                    # relacionada. Le paso el 27/08/2026 con el reclamo de Gold
                    # Reserve en la pieza de la OFAC.
                    "paquete": json.loads(paquete.a_json())},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (carpeta / f"{nombre}.txt").write_text(texto_legible(pieza), encoding="utf-8")
    estado = "BLOQUEADO" if auditor.bloqueada(hallazgos) else "listo para Edicion"
    print(f"\nBorrador guardado en borradores/{nombre}.txt — {estado}")
    return 1 if auditor.bloqueada(hallazgos) else 0


if __name__ == "__main__":
    sys.exit(main())
