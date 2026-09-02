# Cintillo de mercados

Para el equipo de Alalza. Componente suelto, listo para pegar en la plantilla.

## Qué es

Una franja de cotizaciones para la cabecera de sureconomics.com, en dos mitades:

- **Izquierda, fija:** BCV USD, BCV EUR e IBC. Son nuestros, salen de Al Cierre
  a las 5:30 pm hora de Venezuela.
- **Derecha, rotando:** 19 índices, divisas, oro, Brent y bitcoin, servidos por
  el widget de TradingView.

`cinta.html` es autocontenido: estilos, marcado y script. Todo cuelga de
`.se-cinta` para no pisar los estilos del sitio.

## Por qué está partido en dos

**No es una decisión de diseño, es de licencia.** Los datos globales no pueden
salir de nuestro servidor.

Al Cierre obtiene 23 datos, y 20 los saca raspando un endpoint interno de Yahoo
Finance. Mandarlos al Telegram del equipo es uso interno; publicarlos en un
medio comercial es redistribución, y eso no lo permite ninguna licencia de datos
de mercado en plan individual, ni siquiera de pago. **Que sean datos de cierre y
no en tiempo real no cambia nada:** lo que se paga es el derecho de display, no
la latencia.

El widget de TradingView **no es redistribución**: los datos viajan del
proveedor al navegador del lector bajo la licencia de TradingView. Es la vía
legal y gratuita.

Los tres venezolanos sí son publicables porque vienen del emisor: el BCV publica
su propia tasa, que es un acto administrativo público, y el IBC lo publica la
Bolsa de Caracas. Son además los que ningún proveedor internacional cubre.

> **La atribución «Mercados por TradingView» es obligatoria y no se quita.**
> Es el precio de mostrar estos datos sin contratar derechos de display.

## De dónde salen nuestros tres datos

    https://raw.githubusercontent.com/saulbenarroch-debug/telegram-finance-bot/main/al-cierre/cinta.json

Responde con `access-control-allow-origin: *` y caché de 5 minutos. Lo reescribe
el workflow de Al Cierre cada tarde.

Formato:

```json
{
  "actualizado": "2026-09-02T14:44:08+00:00",
  "fecha_cierre": "2026-07-21",
  "valores": [
    {"clave": "ves_usd", "etiqueta": "BCV USD", "valor": 737.23,
     "variacion": 0.04, "unidad": "Bs",
     "fuente": "Banco Central de Venezuela", "url_fuente": "https://www.bcv.org.ve/"}
  ],
  "faltan": []
}
```

**Lo que os pedimos:** servirlo desde vuestro backend en vez de desde GitHub.
Un endpoint tipo `GET /cinta` que haga de proxy con caché de unos minutos.
GitHub raw funciona y es lo que usa el componente hoy, pero no está pensado como
CDN de producción y puede limitar por volumen. Cuando exista el endpoint, se
cambia una constante en `cinta.html` y ya.

## Cómo gira

**El widget de TradingView no desfila solo.** De fábrica es una tira que se
arrastra con el ratón, no una marquesina. Comprobado el 02/09/2026.

Para que gire se anima **el contenedor entero**, no los datos: los valores
siguen dentro del iframe de TradingView y bajo su licencia, que es la condición
de todo esto. Lo único que se mueve es la caja.

Tres cosas que hay que saber si tocáis esto:

1. **La lista de símbolos va duplicada** dentro del mismo widget (19 x 2 = 38).
   Así la segunda mitad del iframe es idéntica a la primera y desplazar un 50 %
   vuelve al inicio sin costura. Con un solo widget a propósito: dos instancias
   serían dos conexiones.
2. **Se anima `.tradingview-widget-container`, no un div propio.** El script del
   widget elimina cualquier envoltorio que se le ponga por fuera.
3. **El ancho lleva `!important`.** El widget se escribe `width: 100%` en línea
   sobre su contenedor al cargar, y un estilo en línea gana a la hoja.

Con `prefers-reduced-motion: reduce` la animación se apaga y la tira queda
quieta y arrastrable, como viene de fábrica.

## Comportamiento ante fallos

- **Si el JSON no responde**, reintenta 3 veces (a los 4 y 8 segundos). Si aun
  así falla, la mitad venezolana se retira y queda solo TradingView. Nunca se
  muestra un hueco ni un mensaje de error.
- **Se pinta primero lo que haya en `sessionStorage`** y luego se refresca, para
  que la cinta no parpadee en cada navegación.
- Si TradingView no carga, queda la mitad venezolana.

## Símbolos

Los 19 símbolos están **verificados uno por uno en el widget**. Ojo con esto si
añadís alguno: la mayoría de los símbolos `TVC:` de índices existen en
TradingView pero **están bloqueados en widgets embebidos** y muestran «Este
símbolo solo está disponible en TradingView». Lo mismo `NASDAQ:IXIC`, `SP:SPX`,
`DJ:DJI`, `BMV:ME`. Los que funcionan son los CFD (`FOREXCOM:`, `CAPITALCOM:`) y
algunos índices de bolsa (`XETR:DAX`, `BME:IBC`, `INDEX:MXX`, `BVC:COLCAP`,
`BMFBOVESPA:IBOV`, `BCBA:IMV`, `SSE:000001`).

**Antes de añadir un símbolo, probadlo en un widget.** El buscador de TradingView
y su API de cotización dicen que existen símbolos que el widget luego no sirve.

**Falta el IPSA de Chile:** no encontramos ningún símbolo que el widget acepte.

## Responsive

Por encima de 860 px, las dos mitades van en línea. Por debajo se apilan y la
parte venezolana se desliza en horizontal.

## Contacto

Saúl Benarroch, saul@rendigroup.com
