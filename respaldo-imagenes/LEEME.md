# Imágenes de SurEconomics para migrar a Cloudflare R2

Respaldo hecho el **1 de septiembre de 2026**, antes de activar R2. Contiene
**todas** las imágenes que el sitio usa hoy, con el mapa de qué imagen
corresponde a cada pieza.

**206 archivos, 340 MB.**

---

## Por qué hace falta esto

El almacén actual es **Cloudinary**. Al migrar a R2 se pierde lo alojado ahí, y
las piezas se quedarían sin portada. Aquí están los originales descargados y,
sobre todo, **el mapa que dice dónde iba cada uno**: los nombres originales se
repiten (hay una docena de `ChatGPT Image…` y otra de `Gemini_Generated_Image…`),
así que sin el mapa son archivos indistinguibles.

## Qué hay dentro

### `assets/` — 178 archivos

Las imágenes registradas en `/admin/media`. **El nombre del archivo es el id del
asset**, con cuatro dígitos: `0181.jpg` es el asset `181`.

`registro.json` trae, por cada una: `asset`, `archivo`, `bytes`, `sha256`,
`storage` (de dónde venía), `mime`, `ancho`, `alto`, `nombre_original`,
`credito` y `url_vieja`.

El `sha256` está para que puedan verificar que lo subido es idéntico al original.

### `sin-asset/` — 28 archivos

**Estas son el caso raro y conviene leerlo.** Treinta piezas antiguas no usan el
almacén de medios: guardan la dirección directamente en el campo de texto
`featured_image_url`. Por eso **no aparecen en `/admin/media`** y es fácil que se
queden fuera de la migración. 28 de ellas apuntan a Cloudinary, o sea que se
caen igual que las demás.

Aquí **el nombre del archivo es el id de la pieza**: `post0105.png` es la portada
del post `105`. Su `registro.json` incluye la `url_vieja` de cada una.

### `mapa-portadas.json`

Lo importante. `post_a_asset` es `{id de la pieza: id del asset}`, 137 entradas.

---

## Qué habría que hacer al migrar

1. Subir los 178 archivos de `assets/` a R2 y **conservar el id de asset** si es
   posible. Si se conservan, las piezas siguen apuntando bien y no hay que tocar
   ninguna. Si se generan ids nuevos, hace falta un `PATCH` a
   `/admin/posts/<id>` con el `image_asset_id` nuevo, usando `mapa-portadas.json`
   para saber cuál va con cuál.

2. Subir los 28 de `sin-asset/` y actualizar el `featured_image_url` de cada
   pieza con la dirección nueva de R2. O, mejor, convertirlas en assets de
   verdad y pasarlas a `image_asset_id`, que dejaría el sitio con un solo
   mecanismo en vez de dos.

3. **Los 19 assets con `storage: external`** apuntan a Wikimedia Commons y no
   hace falta migrarlos: siguen funcionando. Van en el respaldo por si se
   quieren alojar propios, que sería más robusto, porque hoy el sitio depende de
   que Wikimedia no mueva una ruta. Si se suben, **hay que conservar el crédito
   de autor y licencia**: son CC BY y CC BY-SA, y publicarlas sin atribuir
   incumple la licencia. El crédito de cada una está en `registro.json`.

---

## Tres cosas que encontramos y conviene que sepan

**Ninguna afecta a lo publicado**, pero son suciedad en la base de datos:

- **Asset 7 no es una imagen.** Es la dirección de un artículo del *New York
  Times* (`nytimes.com/es/2025/09/02/…`) registrada como asset. Da 403. Ninguna
  pieza lo usa.
- **Assets 148 y 149** son enlaces a Wikimedia que dan **404**. Ninguna pieza los
  usa. Se pueden borrar.
- **Los posts 101 y 102** tienen portadas servidas desde **semana.com** y desde
  un WordPress ajeno (`estaticos.sfo2.digitaloceanspaces.com`). No están en este
  respaldo a propósito: la migración no las toca, pero son imágenes de otros
  medios servidas desde los servidores de ellos. Se caen cuando el otro quiera y
  no hay derecho de uso. Habría que sustituirlas.

---

## Dos preguntas para ustedes

1. **¿Se conservan los ids de asset al migrar?** Si sí, la restauración es solo
   subir archivos y no hay que tocar ninguna pieza.
2. **¿Qué endpoint hay que llamar para subir un archivo a R2?** Hoy existe
   `POST /admin/media/external` con `{kind, url}`, que **enlaza** sin descargar.
   Para R2 hará falta una subida real, y si nos dicen la ruta automatizamos la
   restauración desde nuestro lado.

Contacto: Saúl Benarroch — saul@rendigroup.com
