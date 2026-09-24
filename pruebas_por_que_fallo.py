"""Pruebas de nota._por_que_fallo(). Se corre y se lee la salida.

ESTA FUNCION SE HA EQUIVOCADO DOS VECES, Y LAS DOS EN LA MISMA DIRECCION:
diciendo «se agotó la cuota» cuando no era eso. El 19/09/2026 porque buscaba
«cuota agotada» en toda la salida, y esa linea sale tambien en corridas buenas.
El 24/09/2026 porque la seguia buscando en toda la salida aunque exigiera que
no hubiera IA, y un primer modelo sin cuota tapaba tres saturados.

Las salidas de aqui son LITERALES de los logs de Actions, no inventadas. Un
texto escrito a mano da un caso plausible; el que rompe es el que produce el
motor de verdad.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / ".libs"))
from nota import _por_que_fallo  # noqa: E402

fallos = 0


def caso(nombre, salida, debe_contener, no_debe=None):
    global fallos
    r = _por_que_fallo(salida)
    ok = debe_contener.lower() in r.lower()
    if no_debe and no_debe.lower() in r.lower():
        ok = False
    print(("  OK  " if ok else "FALLA ") + nombre)
    if not ok:
        print("        dijo: %s" % r)
        fallos += 1


print("-- 1. El 24/09/2026 13:56 UTC: saturado, NO cuota --")
# Corrida 36009218286. La reserva tenia cuota: estaba Google saturado.
hoy = """[aviso] gemini-3.5-flash (principal): cuota agotada, paso al siguiente
[aviso] gemini-3.5-flash-lite (principal) caido, reintento en 5s
[aviso] gemini-3.5-flash (reserva) caido, reintento en 5s
[aviso] gemini-3.5-flash-lite (reserva) caido, reintento en 5s
[aviso] Gemini no disponible (503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}); uso Groq
[error] tampoco Groq (Groq respondio 413: Request too large for model `openai/gpt-oss-120b` in organization `org_x` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 11900, please reduce your )."""
caso("dice que esta saturado", hoy, "saturado")
caso("y NO manda a volver mañana", hoy, "saturado", no_debe="mañana")

print("\n-- 2. Todo sin cuota de verdad --")
todo_cuota = """[aviso] gemini-3.5-flash (principal): cuota agotada, paso al siguiente
[aviso] gemini-3.5-flash-lite (principal): cuota agotada, paso al siguiente
[aviso] gemini-3.5-flash (reserva): cuota agotada, paso al siguiente
[aviso] gemini-3.5-flash-lite (reserva): cuota agotada, paso al siguiente
[aviso] Gemini no disponible (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota'}}); uso Groq
[error] tampoco Groq (Groq respondio 413: Request too large)."""
caso("dice que es la cuota", todo_cuota, "cuota")

print("\n-- 3. El 19/09/2026: 'cuota agotada' en una corrida que SI escribio --")
# flash sin cuota, flash-lite responde, y el fallo es otro: no hubo rendicion.
el_19 = """[aviso] gemini-3.5-flash (principal): cuota agotada, paso al siguiente
[redactor] gemini-3.5-flash-lite (principal)
[economista] gemini-3.5-flash-lite (principal)
Traceback (most recent call last):
KeyError: 'cuerpo'"""
caso("no culpa a la cuota", el_19, "redacción falló", no_debe="cuota")

print("\n-- 4. Sin credito de prepago --")
credito = """[aviso] Gemini no disponible (429 RESOURCE_EXHAUSTED. Your prepayment credits are depleted.); uso Groq
[error] tampoco Groq (Groq respondio 413: Request too large)."""
caso("pide recargar", credito, "recargar")

print("\n-- 5. Una llamada anterior se rindio y se salvo; la que mato fue saturacion --")
# producir.py hace varias llamadas. Se mira la ULTIMA rendicion.
dos_llamadas = """[aviso] Gemini no disponible (429 RESOURCE_EXHAUSTED quota); uso Groq
[entidad] groq openai/gpt-oss-120b
[aviso] Gemini no disponible (503 UNAVAILABLE high demand); uso Groq
[error] tampoco Groq (Groq respondio 413: Request too large)."""
caso("manda la ultima razon", dos_llamadas, "saturado")

print("\n%s" % ("TODO EN VERDE" if not fallos else "%d FALLO(S)" % fallos))
sys.exit(1 if fallos else 0)
