# Plantillas de redes

## Qué falta para que esto sirva

Dos archivos de marca que no se pueden deducir ni inventar:

    plantillas/assets/logo.png          el logo blanco de SurE, con transparencia
    plantillas/assets/fuentes/Titulo-800.woff2   la tipografía de los titulares

Sin el logo, la lámina sale con un hueco marcado y el script avisa. Es a
propósito: mejor una lámina que dice «aquí va el logo» que una publicada con el
logo equivocado.

**La tipografía no es Poppins.** En las láminas que ya publica el medio la «a»
es de dos pisos y la Poppins la tiene de uno. Si sale de Canva, hay que exportar
el archivo; si es de Google Fonts, basta el nombre.

El nombre del archivo manda: `Familia-peso.woff2`. `Titulo-800.woff2` se
registra como familia `Titulo` en peso 800, que es lo que pide el CSS.

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
