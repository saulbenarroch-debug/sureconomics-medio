r"""Traduce una pieza a la taxonomia real del sitio: temas y lugares.

    from motor import clasificar
    temas = clasificar.temas("EL PETROLEO...", cuerpo)      # -> ['Energía y Minería', ...]
    lugares = clasificar.lugares("[Noticia] [Venezuela]...")  # -> ['Venezuela']

POR QUE ESTO ES CODIGO Y NO UN MODELO

Porque tiene que dar siempre lo mismo y tiene que poder discutirse. Un modelo
clasificando temas acierta casi siempre y falla de formas que nadie puede
prever ni reproducir; una tabla de palabras se lee, se corrige y da igual
resultado el martes que el jueves. Cuando se equivoque, se ve por que y se
arregla la linea concreta, que es lo que no se puede hacer con un modelo.

La taxonomia del sitio tiene DIECISEIS temas y la nuestra cuatro genericos
(Economia, Finanzas, Politica, Sociedad). La correspondencia no es automatica:
por eso hay tabla.

LOS TEMAS SE ORDENAN POR CUANTAS VECES PEGA CADA UNO, y el primero es el
principal, que es el unico que sale en las tarjetas de portada. Si empatan, gana
el que aparece antes en la tabla, que esta puesta de lo mas especifico a lo mas
general: "Energia y Mineria" antes que "Macroeconomia", porque casi cualquier
nota de energia menciona el PIB pero no al reves.
"""

import re
import unicodedata

# De lo mas especifico a lo mas general. El orden decide los empates.
TABLA = [
    ("Energía y Minería", "petrole|crudo|barril|refiner|gas |gasolin|combustible|"
                          "electric|energet|mineri|oro|litio|carbon|pdvsa|opep|"
                          "yacimiento|pozo|glp|licuado"),
    ("Agro y Alimentos", "agro|agricol|cosecha|granos|soja|maiz|trigo|ganader|"
                         "alimento|pesca|cafe|azucar|siembra"),
    ("Transporte", "aerolinea|aeropuerto|vuelo|puerto|maritim|naviera|carretera|"
                   "ferrocarril|tren|transporte|flete|buque"),
    ("Infraestructura", "infraestructura|obra publica|carreter|puente|represa|"
                        "construccion|vivienda|acueducto"),
    ("Tecnología y Pagos", "tecnolog|digital|fintech|criptomoneda|bitcoin|"
                           "inteligencia artificial|ciberseg|ciberata|software|"
                           "pago movil|telecomunicacion|internet|satelit"),
    ("Clima y Sostenibilidad", "clima|climatic|emision|carbono|renovable|solar|"
                               "eolic|sostenib|ambiental|deforest|glaciar|sequia"),
    ("Trabajo y Migración", "empleo|desemplea|desocupa|salario|sueldo|sindicat|"
                            "trabajador|migra|remesa|refugiad|jubilac|pension"),
    ("Banca y Política Monetaria", "banco central|tasa de interes|tipo de cambio|"
                                   "devaluac|encaje|reserva internacional|"
                                   "politica monetaria|credito|prestamo|"
                                   "morosidad|inadimplen|bcv|bcra"),
    ("Política Fiscal y Deuda", "deuda|deficit|superavit|presupuesto|orcamento|"
                                "impuesto|tributar|fiscal|bono soberano|"
                                "default|acreedor|tesoro"),
    ("Mercados e Inversión", "bolsa|accion|indice|wall street|inversion|"
                             "inversor|fondo|rendimiento|cotiza|mercado bursatil"),
    ("Comercio Exterior", "exporta|importa|arancel|aduana|balanza comercial|"
                          "comercio exterior|tratado comercial|mercosur"),
    ("Geoeconomía", "sancion|ofac|geopolit|bloqueo|embargo|licencia general|"
                    "diplomat|acuerdo bilateral|relacion bilateral"),
    ("Empresas y Negocios", "empresa|corporacion|filial|fusion|adquisicion|"
                            "facturacion|ganancia|balance trimestral|multinacional"),
    ("Sociedad y Bienestar", "pobreza|desigualdad|salud|educacion|escolar|"
                             "hospital|social|canasta basica"),
    ("Política", "gobierno|presidente|ministro|congreso|parlamento|eleccion|"
                 "oposicion|asamblea|decreto|corte suprema"),
    ("Macroeconomía", "inflacion|pib|producto interno|crecimiento economico|"
                      "actividad economica|recesion|indice de precios|ipc"),
]

# Solo los que el sitio tiene dados de alta. España no esta: una pieza sobre
# España se sube sin lugar, que es preferible a colgarla del pais equivocado.
LUGARES = {
    "venezuela": "Venezuela", "colombia": "Colombia", "ecuador": "Ecuador",
    "peru": "Perú", "bolivia": "Bolivia", "argentina": "Argentina",
    "brasil": "Brasil", "chile": "Chile", "paraguay": "Paraguay",
    "uruguay": "Uruguay", "mexico": "México", "cuba": "Cuba",
    "haiti": "Haití", "republica dominicana": "República Dominicana",
    "panama": "Panamá", "costa rica": "Costa Rica", "guatemala": "Guatemala",
    "honduras": "Honduras", "nicaragua": "Nicaragua", "belice": "Belice",
    "el salvador": "El Salvador", "china": "China",
    "estados unidos": "EE. UU.", "ee. uu.": "EE. UU.", "eeuu": "EE. UU.",
    "ee.uu": "EE. UU.", "washington": "EE. UU.",
}


def _plano(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def temas(titulo, cuerpo, maximo=3):
    """Los temas del sitio que pegan, ordenados por cuanto pegan."""
    # El titulo pesa el triple: si algo esta en el titular, es de lo que va la
    # pieza. En el cuerpo cualquier nota de economia menciona medio diccionario.
    texto = _plano(titulo + " ") * 3 + _plano(cuerpo)
    puntuados = []
    for nombre, patron in TABLA:
        # El limite va SOLO al principio. Los patrones son raices a proposito
        # ("petrole" tiene que casar con "petroleras"), asi que cerrar por
        # detras los romperia. Abrir por delante, en cambio, es imprescindible:
        # sin esto "morosidad" casaba con "oro" y una nota sobre el credito
        # bancario en Brasil se clasificaba como mineria.
        golpes = len(re.findall(r"\b(?:" + patron + r")", texto))
        if golpes:
            puntuados.append((golpes, nombre))
    if not puntuados:
        # Nunca dejar una pieza sin tema: sin tema no sale en ninguna seccion y
        # se queda invisible aunque este publicada.
        return ["Macroeconomía"]
    orden = {n: i for i, (n, _) in enumerate(TABLA)}
    puntuados.sort(key=lambda x: (-x[0], orden[x[1]]))
    return [n for _, n in puntuados[:maximo]]


def lugares(cabecera, titulo="", cuerpo="", maximo=3):
    """Lugares del sitio, primero los que declara la propia pieza.

    La cabecera que escribe el motor ya trae el pais entre corchetes
    ("[Noticia] [Latinoamerica] [Region Andina] [Venezuela] [Economia]"). Eso es
    mas fiable que rastrear el cuerpo, donde aparecen paises de pasada.
    """
    encontrados = []
    for etiqueta in re.findall(r"\[([^\]]+)\]", cabecera or ""):
        nombre = LUGARES.get(_plano(etiqueta).strip())
        if nombre and nombre not in encontrados:
            encontrados.append(nombre)

    if not encontrados:
        # Solo si la cabecera no dijo nada. Se mira el titular, no el cuerpo: en
        # el cuerpo salen paises de contexto que no son el sitio de la noticia.
        plano = _plano(titulo)
        for clave, nombre in LUGARES.items():
            if clave in plano and nombre not in encontrados:
                encontrados.append(nombre)
    return encontrados[:maximo]
