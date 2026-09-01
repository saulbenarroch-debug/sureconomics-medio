# Firmas puestas el 01/09/2026

Registro para poder deshacerlo. El dueño pidió que todo lo que estuviera sin
autor saliera firmado como **Redacción SurEconomics**.

## Qué se tocó, en tres tandas

**1. Catorce piezas del motor** (cruzadas contra `borradores/`, `corrida-*/` y
`peticion-*/`, que es el único registro de qué escribió el motor):

    338, 339, 340, 341, 342, 356, 380, 382, 384, 385, 386, 387, 390, 399

**2. Veinticinco con otra grafía**, unificadas a la E alta. Convivían
`Redacción Sureconomics` (24) y `Equipo de Redacción Sureconomics` (1).

**3. Ciento treinta y seis sin firma**, el resto del sitio. Ids del 101 al 371:

    101-146 (sin el 104)
    147-230, 249, 255, 273, 279
    301, 312, 325, 326, 332, 357, 358, 371

De estas, 122 son `articulo`, 7 `editorial` y 7 `noticia`; 94 estaban en
borrador y 42 publicadas.

## Lo que NO se tocó

Ninguna pieza que ya tuviera un autor. Solo se rellenó el campo cuando estaba
vacío, así que **no se borró el crédito de nadie**:

- Pablo Quintero (7)
- Saul Benarroch (3)
- Óscar Doval (1), el artículo #389
- Equipo de Investigación Rendigroup Advisors (1)

## Estado final

298 piezas: 286 con `Redacción SurEconomics` y 12 con autor propio.

## Cómo deshacerlo

Con la sesión del panel abierta, un PATCH a `/admin/posts/<id>` con
`{"byline": ""}` por cada id de la lista de arriba. La tanda de 136 seguidas
agota el tiempo de la consola del navegador: hay que partirla en grupos de
unas 40, o esperar el token de cuenta de servicio y hacerlo con `subir.py`.

## Por qué existe este archivo

El registro se iba a devolver desde el navegador y la llamada agotó el tiempo
al devolver el resultado, no al escribir: las 136 se habían hecho ya. Sin este
archivo no habría forma de saber cuáles eran, porque después del cambio son
indistinguibles de las que siempre estuvieron firmadas.
