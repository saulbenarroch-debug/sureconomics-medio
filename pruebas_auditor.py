"""Pruebas del auditor (A8). Se corre y se lee la salida."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from motor.auditor import auditar, bloqueada, informe
from motor.fuentes import banco_mundial

ETIQUETAS_OK = {"region": "Latinoamérica", "subregion": "Región Andina",
                "pais": "Venezuela", "topico": "Economía",
                "vigencia": "Permanente", "idioma": "ES"}

fallos = 0
def caso(nombre, ok, detalle=""):
    global fallos
    print(("  OK  " if ok else "FALLA ") + nombre + ("" if ok else f"  -> {detalle}"))
    if not ok: fallos += 1

print("Trayendo un paquete real del Banco Mundial...\n")
paq = banco_mundial.extraer("VEN", "inflacion", 3)
assert paq, "no hubo paquete"
url = paq.fuentes[0].url

base = {"tipo": "Noticia", "autor": None, "etiquetas": dict(ETIQUETAS_OK),
        "bloque_sureconomics": "La cifra retrata el agotamiento del modelo.",
        "cifras_usadas": ["inflacion_2016"], "fuentes_usadas": ["bm1"]}

print("-- 1. Pieza correcta --")
buena = dict(base, titulo="La inflación de Venezuela llegó a 254,9 % en 2016",
             cuerpo=f"En 2016 la inflación anual de Venezuela fue de 254,9 %, "
                    f"según el Banco Mundial. En 2015 había sido de 121,7 %. {url}")
r = auditar(buena, paq)
caso("aprueba una pieza bien hecha", not bloqueada(r), informe(r))

print("\n-- 2. Cifra que no está en el paquete --")
mala = dict(buena, cuerpo=f"La inflación fue de 254,9 % en 2016 y el PIB cayó 18,6 %. {url}")
r = auditar(mala, paq)
caso("bloquea la cifra inventada (18,6)",
     any(x.codigo == "cifra-inventada" for x in r), informe(r))

print("\n-- 3. Dato viejo presentado como actual --")
vieja = dict(buena, titulo="La inflación de Venezuela es de 254,9 %",
             cuerpo=f"La inflación anual de Venezuela es de 254,9 %. {url}")
r = auditar(vieja, paq)
caso("bloquea si el texto no dice el año del dato",
     any(x.codigo == "dato-viejo" for x in r), informe(r))

print("\n-- 4. El editorial real del lunes 24 --")
real = {"tipo": "Editorial", "autor": "Redacción SurEconomics",
        "etiquetas": dict(ETIQUETAS_OK, region="Mundo", subregion="América", pais="EE. UU."),
        "titulo": "¡EL SUR GLOBAL SE AHOGA POR LA AUSTERIDAD MONETARIA!",
        "cuerpo": ("Estados Unidos acaba de rebasar la astronómica cifra de 35 trillones "
                   "de dólares en deuda pública, es decir, el 124 % de su PIB. El Tesoro "
                   "gasta más de 890.000 millones únicamente en intereses. Mientras la "
                   "Fed mantiene el costo del dinero en 5,25 %, a nosotros nos exigen "
                   "recortes a través del Fondo Monetario Internacional (MFI). "
                   "Fuente: https://www.sureconomics.com"),
        "bloque_sureconomics": "", "cifras_usadas": [], "fuentes_usadas": []}
r = auditar(real, paq)
print(informe(r))
codigos = {x.codigo for x in r}
caso("detecta 'trillones'", "trillon" in codigos)
caso("detecta 'MFI' por FMI", "sigla" in codigos)
caso("detecta la autocita a sureconomics.com", "autocita" in codigos)
caso("detecta cifras sin respaldo", "cifra-inventada" in codigos)

print("\n-- 5. Opinión sin autor --")
sin_autor = dict(buena, tipo="Opinión", autor="XXX", bloque_sureconomics="")
r = auditar(sin_autor, paq)
caso("bloquea la opinión firmada XXX", any(x.codigo == "sin-autor" for x in r))

print("\n-- 6. Etiqueta fuera de la taxonomía --")
mal_tag = dict(buena, etiquetas=dict(ETIQUETAS_OK, topico="Energía"))
r = auditar(mal_tag, paq)
caso("bloquea un tópico que no existe", any(x.codigo == "etiqueta-invalida" for x in r))

print("\n-- 7. Redondeos --")
r = auditar(dict(buena, titulo="La inflación de Venezuela en 2016",
                 cuerpo=f"En 2016 la inflación anual fue de 255 %. {url}"), paq)
caso("acepta 255 como redondeo de 254,9",
     not any(x.codigo == "cifra-inventada" for x in r), informe(r))
caso("y se lo avisa al editor", any(x.codigo == "redondeo" for x in r))

r = auditar(dict(buena, titulo="La inflación de Venezuela en 2016",
                 cuerpo=f"En 2016 la inflación anual superó el 200 %. {url}"), paq)
caso("bloquea 200: no es un redondeo de 254,9, es otra cifra",
     any(x.codigo == "cifra-inventada" for x in r), informe(r))

print(f"\n{'TODO EN VERDE' if not fallos else str(fallos) + ' FALLO(S)'}")
sys.exit(1 if fallos else 0)
