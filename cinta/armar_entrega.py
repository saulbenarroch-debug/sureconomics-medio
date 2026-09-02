r"""Arma el archivo unico que se les manda a los desarrolladores.

    .pyruntime\python.exe cinta/armar_entrega.py

Junta en un solo HTML el componente funcionando, la documentacion y el codigo
listo para copiar. Se genera A PARTIR de cinta.html, no a mano: asi el codigo
que copian los desarrolladores es siempre el que de verdad se probo, y no una
copia que se quedo vieja.

Se regenera cada vez que cambie cinta.html.
"""

import html
import pathlib
import sys
from datetime import date

AQUI = pathlib.Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMPONENTE = AQUI / "cinta.html"
DESTINO = AQUI / "cintillo-sureconomics.html"

PAGINA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cintillo de mercados · SurEconomics</title>
<style>
  :root {{ --tinta:#1a1d23; --suave:#5b6472; --linea:#e2e6ec; --fondo:#f7f8fa;
          --acento:#1f6feb; --aviso:#b45309; --papel:#fff; }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; background:var(--fondo); color:var(--tinta);
         font:16px/1.65 -apple-system,"Segoe UI",Roboto,sans-serif }}
  .demo {{ position:sticky; top:0; z-index:9; box-shadow:0 2px 14px rgba(0,0,0,.28) }}
  main {{ max-width:860px; margin:0 auto; padding:38px 22px 90px }}
  h1 {{ font-size:31px; margin:.2em 0 .1em; letter-spacing:-.4px }}
  .sub {{ color:var(--suave); margin:0 0 34px; font-size:15px }}
  h2 {{ font-size:21px; margin:44px 0 12px; padding-bottom:7px;
       border-bottom:2px solid var(--linea) }}
  h3 {{ font-size:16px; margin:26px 0 8px }}
  p, li {{ margin:.6em 0 }}
  code {{ background:#eef1f5; padding:1px 5px; border-radius:4px;
         font:13px ui-monospace,Consolas,monospace }}
  pre {{ background:#0d1117; color:#e6edf3; padding:16px 18px; border-radius:9px;
        overflow:auto; font:12.5px/1.55 ui-monospace,Consolas,monospace;
        max-height:520px }}
  .caja {{ background:var(--papel); border:1px solid var(--linea);
          border-left:4px solid var(--acento); padding:14px 18px;
          border-radius:0 8px 8px 0; margin:18px 0 }}
  .caja.ojo {{ border-left-color:var(--aviso); background:#fffbf4 }}
  .caja p:first-child {{ margin-top:0 }} .caja p:last-child {{ margin-bottom:0 }}
  table {{ border-collapse:collapse; width:100%; margin:16px 0; font-size:14.5px }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--linea) }}
  th {{ background:var(--papel) }}
  .pie {{ margin-top:56px; padding-top:18px; border-top:1px solid var(--linea);
         color:var(--suave); font-size:14px }}
  button {{ font:inherit; font-size:14px; padding:7px 14px; border-radius:7px;
           border:1px solid var(--linea); background:var(--papel); cursor:pointer }}
  button:hover {{ border-color:var(--acento); color:var(--acento) }}
</style>
</head>
<body>

<!-- ===== EL COMPONENTE, FUNCIONANDO ===== -->
<div class="demo">
{componente}
</div>

<main>
<h1>Cintillo de mercados</h1>
<p class="sub">Componente para la cabecera de sureconomics.com · generado el {fecha}
 · contacto: Saúl Benarroch, saul@rendigroup.com</p>

<p>Lo de arriba <strong>es el componente real</strong>, no una imagen. Si esta
página está abierta, está funcionando: los valores son de verdad y la tira
desfila. Todo lo que hay que integrar está en el bloque de código del final.</p>

<h2>Qué lleva</h2>
<table>
  <tr><th>Mitad</th><th>Qué muestra</th><th>De dónde sale</th></tr>
  <tr><td><strong>Izquierda, fija</strong></td>
      <td>BCV USD, BCV EUR, IBC</td>
      <td>Nuestro JSON, escrito por Al Cierre a las 5:30 pm hora de Venezuela</td></tr>
  <tr><td><strong>Derecha, girando</strong></td>
      <td>19 índices, EUR/USD, oro, Brent y bitcoin</td>
      <td>Widget de TradingView, directo al navegador del lector</td></tr>
</table>

<h2>Por qué está partido en dos</h2>
<p><strong>No es una decisión de diseño, es de licencia.</strong> Los datos
globales no pueden salir de nuestro servidor.</p>
<p>Nuestro proceso interno obtiene 23 datos, y 20 los toma de una fuente cuyos
términos no permiten republicarlos. Mandarlos a un chat interno del equipo es
uso interno; publicarlos en un medio comercial es redistribución, y eso no lo
permite ninguna licencia de datos de mercado en plan individual, ni siquiera de
pago. <strong>Que sean datos de cierre y no en tiempo real no cambia nada:</strong>
lo que se paga es el derecho de mostrarlos, no la latencia.</p>
<p>El widget de TradingView <strong>no es redistribución</strong>: los datos van
del proveedor al navegador del lector bajo la licencia de TradingView. Es la vía
legal y gratuita.</p>
<p>Los tres venezolanos sí son publicables porque vienen del emisor: el BCV
publica su propia tasa, que es un acto administrativo público, y el IBC lo
publica la Bolsa de Caracas. Son además los que ningún proveedor internacional
cubre.</p>
<div class="caja ojo">
<p><strong>La atribución «Mercados por TradingView» es obligatoria y no se
quita.</strong> Es la condición de poder mostrar estos datos sin contratar
derechos de display. Si se elimina, se cae la base legal de la mitad derecha.</p>
</div>

<h2>Nuestros tres datos</h2>
<p>Se leen de:</p>
<pre>{fuente_json}</pre>
<p>Responde con <code>access-control-allow-origin: *</code> y caché de 5
minutos. Lo reescribe nuestro proceso cada tarde. Formato:</p>
<pre>{ejemplo_json}</pre>
<div class="caja">
<p><strong>Lo que os pedimos:</strong> servirlo desde vuestro backend en vez de
desde GitHub. Un endpoint tipo <code>GET /cinta</code> que haga de proxy con
caché de unos minutos. GitHub raw funciona y es lo que usa el componente hoy,
pero no está pensado como CDN de producción y puede limitar por volumen. Cuando
exista, se cambia la constante <code>FUENTE</code> y ya.</p>
</div>

<h2>Cómo gira, y las trampas</h2>
<p>El widget de TradingView <strong>no desfila solo</strong>: de fábrica es una
tira que se arrastra con el ratón. Para que gire se anima el contenedor, no los
datos, que siguen dentro de los iframes de TradingView.</p>
<p>Son <strong>dos instancias idénticas</strong> de 3200 px en una pista de 6400
que se desplaza exactamente 3200. Al llegar al final, la segunda mitad está
donde estaba la primera y el bucle cierra sin costura.</p>
<h3>Tres cosas que costaron encontrar</h3>
<ul>
<li><strong>No vale duplicar la lista de símbolos</strong> dentro de un solo
widget: descarta los que no caben. A 6400 px cada símbolo ocupa unos 388, así
que de 38 solo pintaba 16 y el punto de repetición no caía en la mitad.</li>
<li><strong>La pista se crea por JavaScript, no en el HTML.</strong> El script
del widget elimina cualquier envoltorio que encuentre por fuera.</li>
<li><strong>Los anchos llevan <code>!important</code>.</strong> El widget se
escribe <code>width: 100%</code> en línea al cargar, y eso gana a la hoja.</li>
</ul>
<p><strong>Velocidad:</strong> los <code>40s</code> del <code>animation</code>.
Son 3200 px en 40 segundos, o sea 80 px/s. Es el único número que hay que tocar.
Se para al pasar el ratón por encima, para poder leer un valor.</p>

<h2>Los símbolos</h2>
<p>Los 19 están <strong>verificados uno por uno pintándolos</strong>. Si añadís
alguno, probadlo antes.</p>
<div class="caja ojo">
<p>La mayoría de los símbolos <code>TVC:</code> de índices existen en TradingView
pero <strong>están bloqueados en widgets embebidos</strong> y muestran «Este
símbolo solo está disponible en TradingView». Lo mismo <code>NASDAQ:IXIC</code>,
<code>SP:SPX</code>, <code>DJ:DJI</code> y <code>BMV:ME</code>.</p>
<p>Y el buscador de TradingView y su API de cotización <strong>se contradicen con
el widget</strong>: dicen que <code>NASDAQ:IXIC</code> funciona y que
<code>FOREXCOM:SPXUSD</code> no, y en pantalla es al revés. La única prueba
válida es pintarlo.</p>
</div>
<p><strong>Falta el IPSA de Chile:</strong> no encontramos ningún símbolo que el
widget acepte.</p>

<h2>Si algo falla</h2>
<ul>
<li><strong>Si el JSON no responde</strong>, reintenta 3 veces. Si aun así falla,
la mitad venezolana se retira y queda solo TradingView. Nunca se muestra un
hueco ni un mensaje de error.</li>
<li><strong>Se pinta primero lo que haya en <code>sessionStorage</code></strong>
y luego se refresca, para que no parpadee al navegar.</li>
<li>Si TradingView no carga, queda la mitad venezolana.</li>
<li>Con <code>prefers-reduced-motion: reduce</code> se muestra una sola
instancia, quieta y arrastrable.</li>
</ul>

<h2>Responsive</h2>
<p>Por encima de 860 px las dos mitades van en línea. Por debajo se apilan y la
parte venezolana se desliza en horizontal.</p>

<h2>El código</h2>
<p>Esto es exactamente lo que está corriendo arriba. Todo cuelga de
<code>.se-cinta</code>, así que no pisa estilos del sitio.</p>
<p><button onclick="copiar(this)">Copiar el código</button></p>
<pre id="codigo">{codigo}</pre>

<p class="pie">Generado desde <code>cinta/cinta.html</code> del repositorio
sureconomics-medio. Si hay que cambiar algo, se cambia allí y se regenera este
archivo, para que el código de aquí no se quede viejo.</p>
</main>

<script>
function copiar(b) {{
  navigator.clipboard.writeText(document.getElementById("codigo").textContent)
    .then(function () {{ b.textContent = "Copiado"; setTimeout(function () {{ b.textContent = "Copiar el código"; }}, 2000); }})
    .catch(function () {{ b.textContent = "No pude copiar; selecciónalo a mano"; }});
}}
</script>
</body>
</html>
"""

EJEMPLO = """{
  "actualizado": "2026-09-02T14:44:08+00:00",
  "fecha_cierre": "2026-09-02",
  "valores": [
    {"clave": "ves_usd", "etiqueta": "BCV USD", "valor": 737.23,
     "variacion": 0.04, "unidad": "Bs",
     "fuente": "Banco Central de Venezuela",
     "url_fuente": "https://www.bcv.org.ve/"}
  ],
  "faltan": []
}"""

FUENTE = ("https://raw.githubusercontent.com/saulbenarroch-debug/"
          "telegram-finance-bot/main/al-cierre/cinta.json")


def main():
    if not COMPONENTE.exists():
        print("No encuentro cinta.html")
        return 1
    codigo = COMPONENTE.read_text(encoding="utf-8")
    DESTINO.write_text(PAGINA.format(
        componente=codigo,
        codigo=html.escape(codigo),
        ejemplo_json=html.escape(EJEMPLO),
        fuente_json=html.escape(FUENTE),
        fecha=date.today().strftime("%d/%m/%Y")), encoding="utf-8")
    print("%s  (%d KB)" % (DESTINO.name, DESTINO.stat().st_size // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
