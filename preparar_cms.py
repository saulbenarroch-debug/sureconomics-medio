r"""Traduce los borradores del dia al formato que pide el panel de sureconomics.

    .pyruntime\python.exe preparar_cms.py 26-agosto

Deja un carga-cms.json listo para subir. NO sube nada: la carga se hizo el
26/08/2026 a mano, con el navegador y la sesion abierta por el propio dueño,
porque no se meten contraseñas en formularios de acceso.

LO QUE SE APRENDIO DEL PANEL, Y ES LA RAZON DE QUE ESTE ARCHIVO EXISTA

1. **La taxonomia del sitio es mas fina que la nuestra.** Nosotros etiquetamos
   con cuatro topicos genericos (Economia, Finanzas, Politica...) y el sitio
   tiene dieciseis temas: Macroeconomia, Politica Fiscal y Deuda, Banca y
   Politica Monetaria, Energia y Mineria, Trabajo y Migracion, Geoeconomia... La
   correspondencia no es automatica y por ahora se decide pieza a pieza, aqui
   abajo. Lo correcto a futuro es que el motor produzca ya en la taxonomia real.

2. **Los formatos no son equivalentes uno a uno.** Nuestro 'Investigacion' entra
   como 'informe', y el formato informe NO tiene bloque «¿Que piensa
   SurEconomics?»: un informe lleva su posicion dentro del texto, no al pie.

3. **El resumen no lo produce el motor.** Para una noticia la entradilla es la
   primera frase, que ya esta escrita; no se inventa nada. Para el informe hay
   que saltarse el rotulo «Resumen» del propio formato.
"""

import sys, io, json, glob, os, re
out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Correspondencia entre nuestras etiquetas y la taxonomia real del sitio, que es
# mas fina que la nuestra. Se decide pieza a pieza, no automaticamente.
TEMAS = {
 "1-visas-eeuu":            ["Trabajo y Migración", "Política"],
 "2-rubio-velasco":         ["Geoeconomía", "Comercio Exterior"],
 "3-acuerdos-petroleros":   ["Energía y Minería", "Empresas y Negocios"],
 "4-maiquetia":             ["Transporte", "Infraestructura"],
 "5-embajada-paises-bajos": ["Geoeconomía"],
 "6-talcual":               ["Trabajo y Migración", "Política"],
 "7-freno-dolarizacion":    ["Banca y Política Monetaria", "Política"],
 "8-venezuela-colombia":    ["Comercio Exterior", "Empresas y Negocios"],
 "9-pib-ecoanalitica":      ["Macroeconomía", "Política Fiscal y Deuda"],
}
LUGARES = {
 "1-visas-eeuu": ["EE. UU."], "2-rubio-velasco": ["México", "EE. UU."],
 "3-acuerdos-petroleros": ["Venezuela"], "4-maiquetia": ["Venezuela"],
 "5-embajada-paises-bajos": ["Venezuela"], "6-talcual": ["Colombia", "Venezuela"],
 "7-freno-dolarizacion": ["Venezuela"], "8-venezuela-colombia": ["Venezuela", "Colombia"],
 "9-pib-ecoanalitica": ["Venezuela"],
}
FORMATO = {"Noticia": "noticia", "Investigación": "informe"}

salida = []
for ruta in sorted(glob.glob("26-agosto/*.json")):
    clave = os.path.basename(ruta)[:-5]
    d = json.load(open(ruta, encoding="utf-8"))
    p = d["pieza"]
    cuerpo = (p.get("cuerpo") or "").strip()
    # El resumen no lo produce el motor. Para una noticia la entradilla ES la
    # primera frase: no se inventa nada, se reutiliza lo que ya esta escrito.
    primera = re.split(r"(?<=[.!?])\s", cuerpo)[0] if cuerpo else ""
    fuentes = []
    for linea in (p.get("sacado_de") or "").split("\n"):
        m = re.match(r"Sacado de:\s*(.+?),\s*[\d-]+\s*·\s*(\S+)", linea.strip())
        if m:
            fuentes.append({"nombre": m.group(1).strip(), "url": m.group(2).strip()})
    salida.append({
        "clave": clave,
        "formato": FORMATO.get(p.get("tipo"), "noticia"),
        "titulo": (p.get("titulo") or "").strip(),
        "resumen": primera,
        "firma": "Saúl Benarroch" if p.get("tipo") == "Investigación" else "Redacción SurEconomics",
        "cuerpo": cuerpo,
        "cierre": (p.get("bloque_sureconomics") or "").strip(),
        "temas": TEMAS.get(clave, []),
        "lugares": LUGARES.get(clave, []),
        "fuentes": fuentes,
    })

json.dump(salida, open("carga-cms.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for s in salida:
    out.write("%-24s %-8s %s\n     temas: %s | lugares: %s | fuentes: %d\n"
              % (s["clave"], s["formato"], s["titulo"][:62],
                 ", ".join(s["temas"]), ", ".join(s["lugares"]), len(s["fuentes"])))
out.flush()
