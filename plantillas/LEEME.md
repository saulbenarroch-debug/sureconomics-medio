# Plantillas de redes

## Los recursos de marca

    plantillas/assets/logo.png              el logo de SurE, blanco con transparencia
    plantillas/assets/fuentes/*.woff2       Host Grotesk
    plantillas/assets/fuentes/hostgrotesk.json  qué peso y qué rango cubre cada archivo

**Host Grotesk es una fuente VARIABLE.** Google la sirve como dos archivos —uno
para `latin` y otro para `latin-ext`— y cada uno cubre todos los pesos. Por eso
no hay un archivo por peso: bajarlos «uno por peso» devuelve tres copias
idénticas del mismo fichero. El `hostgrotesk.json` guarda el `unicode-range` de
cada uno tal como lo declara Google; sin él, el navegador usa el archivo que no
toca para las tildes.

Se incrustan en el HTML y **no se enlazan a Google**: si la fuente se pide por
red y la red falla, Chrome dibuja con la de reserva y la lámina sale con otra
tipografía sin que nada avise. Se publica y se ve.

El logo lleva su transparencia en un trozo `tRNS` (es PNG de paleta, no RGBA).
Se ve en blanco sobre fondo blanco, que es lo correcto: va sobre foto.

Si falta el logo, la lámina sale con un hueco marcado y el script avisa. Es a
propósito: mejor una lámina que dice «aquí va el logo» que una publicada con el
logo equivocado.

## Uso

    .pyruntime\python.exe plantillas/post.py foto.jpg ^
        --categoria MUNDO ^
        --titular "Apple va por su iPhone más caro" ^
        --bajada "el primer plegable superaría los US$2.000" ^
        --link-en-bio ^
        --salida post.png

Sale 1080x1350, que es el formato de publicación de Instagram. Las historias
(1080x1920) van cuando llegue esa plantilla.

## Por qué HTML y Chrome

Porque el diseño ya existe y lo que hay que reproducir es tipografía apretada,
tarjeta translúcida con desenfoque y texto que se ajusta solo. En CSS son cuatro
líneas; con una librería de imagen es una tarde calculando píxeles. Es la misma
vía que usan `entorno/render.py` y `al-cierre` en el repo del bot.

## Lo que este archivo NO decide

Ni la foto, ni el titular, ni la categoría. Eso lo trae quien lo llama.
