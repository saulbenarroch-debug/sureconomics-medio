r"""Busca dónde está una noticia, dentro de los medios de confianza.

    .pyruntime\python.exe buscar.py "Mexico bonos Samurai emision"

Devuelve candidatos con su enlace. No son fuente todavía: hay que abrir la nota,
comprobarla y registrarla con agregar_fuente.py.
"""
import pathlib, sys
AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(AQUI / ".libs"))
from dotenv import load_dotenv
load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")
from motor import buscador

if len(sys.argv) < 2:
    print(__doc__); sys.exit(1)
consulta = " ".join(sys.argv[1:])
print(buscador.informe(consulta, buscador.buscar(consulta)))
