# SurEconomics — el medio

Contexto para Claude Code y para cualquiera del equipo que trabaje en este repo.
Si cambias algo estructural (una fuente, un umbral, un horario, un secreto),
**actualízalo aquí en el mismo commit**.

El bot de Telegram vive en otro repo (`C:\Users\saulb\telegram-finance-bot`) y
tiene su propio CLAUDE.md. Ese es la **puerta**; este es el **motor**.

## Qué es

Un medio digital latinoamericano de economía, finanzas y economía política. Línea
editorial progresista sin extremos, decisión del dueño. Publica en
sureconomics.com a través de un panel propio.

**El motor no publica.** Todo lo que produce entra como BORRADOR y lo aprueba una
persona. No hay excepción, y varias decisiones de este repo solo se entienden
desde ahí.

## La regla que explica el resto

> **El código trae las cifras y audita. La IA solo redacta prosa.**

Todo lo verificable —cifras, fechas, atribuciones, formato— lo decide código
determinista. El modelo escribe el texto y propone; nunca decide si algo es
cierto. Cuando algo de esto se relaja, se rompe en producción: está documentado
más abajo, caso por caso.

**Los duplicados son la excepción que confirma la regla, y la solución no fue
más inteligencia sino una salida.** Decidir si dos titulares cuentan el mismo
hecho no es verificar un dato, es un juicio, y contar palabras no lo sabe hacer:
medido el 09/09/2026 contra el catálogo real, un duplicado auténtico puntuaba
0.238 y una noticia legítima 0.643 — **cruzados**, así que ningún umbral los
separa.

Se probó a que lo juzgara el modelo y acertaba (de 8 fallos a 2 en
`pruebas_memoria.py`), pero **se descartó por decisión del dueño**: mete una
llamada de IA y una dependencia de cuota en una decisión que no lo necesita. La
salida elegida es más simple y más robusta: **el umbral se queda como está y
todo veredicto de "repetida" es contradecible de un toque.** Si un falso
positivo cuesta un botón en vez de una noticia perdida, la precisión del
detector deja de ser crítica.

La diferencia con las cifras sigue siendo la que manda: una cifra mal decidida
se publica y es falsa; un duplicado mal decidido no publica nada, avisa a quien
lo pidió y se deshace en un toque.

## Cómo va una pieza de la nada al panel

```
  recolectar / captura / nota          ¿de qué se escribe?
        ↓
  motor/documentalista.py              arma el EXPEDIENTE (paquete.py)
        ↓
  motor/redactor.py                    prompts/ + perfiles/  → prosa
        ↓
  motor/economista.py                  critica el razonamiento; si dice
                                       "revisar", el redactor da otra pasada
        ↓
  motor/auditor.py                     bloquea lo que no cuadre
        ↓
  armar_carga.py                       clasifica, busca foto, arma carga.json
        ↓
  subir.py                             POST al panel, siempre como borrador
```

## Los tres caminos de entrada

| Camino | Qué lo dispara | Archivo |
|---|---|---|
| **Tandas diarias** | cron del Worker, 8:00 y 14:00 VET | `orquestar.py` → `.github/workflows/diario.yml` |
| **A petición** | `/nota` en Telegram | `nota.py` → `nota.yml` |
| **Vigilancia** | enlaces sueltos que alguien deja | `vigilar.py` → `vigilancia.yml` |

`/nota` acepta cuatro cosas y las distingue solo:

- un **enlace** de un medio → escribe desde esa fuente
- un **tema escrito a mano** → lo busca en la lista blanca y cruza hasta
  `MAX_FUENTES = 3` medios
- una **captura de pantalla** → la lee, deduce el medio y busca el original
- un **enlace de X o de Instagram** → lee la publicación y busca el original

Un tuit o una captura dicen QUÉ buscar; se escribe desde el artículo del medio,
que es lo auditable. **Con una excepción, y tiene dos condiciones.**

### Cuando la publicación SÍ es la fuente

Si no aparece el artículo original, la publicación puede serlo, pero solo si se
sabe **de quién es la cuenta** (`fuente_de_la_publicacion` en `nota.py`):

1. **La cuenta es de un medio de la lista.** Lo que Bloomberg Línea publica en su
   Instagram lo publica Bloomberg Línea. Fuente secundaria, se cita igual que su
   web: *«según informó Bloomberg Línea en su cuenta de Instagram»*.
2. **La cuenta es de una figura pública.** Que un jefe de Estado diga algo en su
   cuenta ES la noticia, y es fuente **primaria**: no se cuenta que ocurrió algo,
   se cuenta que lo dijo.

**La diferencia entre las dos viaja en la instrucción y no es cosmética.** En la
primera los datos son reportería del medio; en la segunda son **afirmaciones de
quien habla**, y el prompt exige atribuirle cada una («según dijo», «afirmó»).
Publicar como hecho comprobado lo que solo dice un post es el error que este
sistema existe para impedir.

**Nada de esto lo decide un modelo.** El medio se comprueba contra la lista
blanca; la persona, contra **Wikidata**, que guarda la cuenta oficial de cada
figura pública (P2003 Instagram, P2002 X). De cualquiera de ellas hay cuentas de
parodia y de suplantación: escribir «Trump dijo» desde una que no es la suya
sería el peor fallo posible del motor. Comprobado que `realdonaldtrump`,
`delcyrodriguezven` y `nicolasmaduro` resuelven a su persona, y que
`beycocapital`, `espacio.media` y `bloomberglinea` no resuelven a nadie.

## La lámina de Instagram

Se pide en el **pie de foto**, junto con la imagen y el enlace:

    haz esta noticia con esta imagen y hazme el post

Detecta «post», «instagram», «lámina», «placa», «plantilla» o «para redes»
(`motor/lamina.la_piden`). Sin esa palabra, la imagen se usa solo como portada
del sitio, que es como funcionaba antes.

**El titular del panel NO sirve para la lámina.** En el sitio va en mayúsculas y
largo; en la lámina caben ocho o nueve palabras en caja mixta. Así que la lámina
lleva su propio par —titular corto y bajada— que escribe el modelo a partir del
titular y la entradilla **ya auditados**: acorta, no inventa. Si no responde, se
recorta por código y la lámina sale igual.

**La categoría** (la etiqueta roja) sale del país que el motor ya clasificó:
`VENEZUELA`, `ESTADOS UNIDOS`, `LATINOAMÉRICA` si son varios, `MUNDO` si no hay
ninguno. Se puede imponer escribiendo `categoría: LO QUE SEA` en el pie.

Dos archivos, dos trabajos: `plantillas/post.py` **dibuja** y `motor/lamina.py`
**decide**. Mezclarlos es como se llega a que la lámina diga un país y el sitio
diga otro.

**No hace falta adjuntar imagen, y hasta el 21/09/2026 sí hacía falta sin
decirlo.** La condición que dibuja exigía `foto_local`, que solo se rellena con
una foto mandada por Telegram. Con `/nota <enlace> hazme el post` el motor
anunciaba «se pidió también la lámina», redactaba, subía el borrador **y no
dibujaba nada**: desde el chat parecía roto estando bien.

Ahora el fondo sale, por este orden, de:

1. **la imagen que adjuntó la persona**, si la hay: si alguien se molestó en
   mandar una foto concreta, manda ella;
2. **la portada que el motor ya eligió** para la pieza, que se baja con
   `lamina.bajar()` porque la carga solo guarda la dirección y Chrome necesita
   el archivo.

Y si no hay ninguna de las dos, **se dice por el chat** en vez de callar.

**LA LÁMINA LLEVA CRÉDITO DESDE ENTONCES, Y NO ES DECORACIÓN.** Mientras el
fondo solo podía ser una foto mandada por el chat —generadas con IA, sin autor
a quien citar— no había nada que atribuir, y por eso `post.componer()` no tenía
ranura para ello. Las portadas del buscador salen de Commons y muchas son CC BY
o CC BY-SA, que exigen nombrar al autor **donde se ve la imagen**: el pie del
sitio no sirve, porque la lámina viaja sola a Instagram. Va en la franja de
56 px que la tarjeta deja libre abajo; si se mueve la tarjeta, hay que mirar
`.credito`.

**Y el techo de todo esto es el buscador de portadas, no la lámina.** Probado el
21/09/2026 con una nota del BCV, la foto elegida fue el Tribunal Supremo de
Guyana. En el sitio una portada floja se nota; en Instagram la imagen **es** la
pieza. Antes de confiar en el camino 2 para publicar sin mirar, ver «De las
portadas» en las trampas.

## La portada de `/nota` se enseña antes de publicarse

`armar_carga.py` **no busca foto por defecto**, y su comentario explica por qué:
las reglas comprueban país y licencia, pero no si la foto *ilustra* el asunto.
El argumento que cerró aquello fue: *«una pieza sin foto la resuelve Edición en
un minuto; una con la foto equivocada la resuelve después de que la lea alguien,
y a veces después de que la lea un lector»*.

**Eso era cierto mientras la foto no se viera hasta abrir el panel.** Desde el
21/09/2026 `/nota` pasa `--con-foto` y la portada elegida **se manda al chat**
en cuanto se arma la carga, con su crédito y avisando de que la eligió el motor.
Una foto equivocada se caza en segundos, así que desaparece el motivo de dejar
las piezas sin portada.

**En las tandas sigue haciendo falta pedirla a mano** (`orquestar.py` pasa
`--con-foto`): allí no hay a quien enseñársela, que es la misma razón por la que
un bloqueo por repetida se trata distinto en la tanda y en `/nota`.

Si la persona mandó su propia portada, no se busca: se pisaría igualmente unas
líneas más abajo.

## Tipos de pieza

Seis, cada uno con su prompt en `prompts/`. `armar_carga.FORMATOS` los traduce a
los cinco formatos que tiene el sitio.

| Tipo | Prompt | Formato en el panel | Firma |
|---|---|---|---|
| Noticia | `10-noticia.md` | `noticia` | Redacción |
| **Análisis** | `60-analisis.md` | `articulo` | Redacción |
| Opinión | `20-opinion.md` | `articulo` | **persona, obligatoria** |
| Editorial | `30-editorial.md` | `editorial` | Redacción |
| Investigación | `40-investigacion.md` | `informe` | **persona, obligatoria** |
| Educación | `50-educacion.md` | `articulo` | opcional |

**La frontera entre Noticia, Análisis y Opinión es lo único difícil de esto.** La
noticia cuenta el hecho. La opinión defiende una tesis y la firma una persona. El
análisis explica el mecanismo sin defender nada: *el lector tiene que poder
discrepar de la conclusión y quedarse con la explicación*. Está escrito en
`60-analisis.md` y es el criterio con el que se corrige.

Nadie escribe el nombre interno del tipo: se pide "un artículo", "una columna",
"un reportaje". `nota.SINONIMOS` los traduce. **Artículo = Análisis**, porque en
el sitio ese formato se llama `articulo`.

## Quién entra en el pozo, que no es lo mismo que quién gana

**Son dos preguntas distintas y durante semanas se confundieron.** Puntuar bien
no sirve de nada si el candidato nunca llegó a la lista.

`noticias.extraer()` recorre los medios y hace `return` en cuanto junta
`limite` candidatas. Con los medios en el orden en que estaban escritos en
`MEDIOS` —El País el 1º, Clarín el 2º, los brasileños 3º y 4º— **los cuatro
primeros llenaban el cupo de 50 y los otros 55 no se abrían nunca.**

Medido el 09/09/2026 sobre un pozo real de 50 candidatas: **27 de Brasil, 21 de
España, 2 de Argentina y CERO de Venezuela**, con trece medios venezolanos en la
lista. No era el huso horario ni la puntuación: era el orden de un diccionario.
Y era también la causa de lo de Brasil de la víspera, que se había tapado con un
tope por país.

Tres cosas lo arreglan, y las tres hacen falta:

| Qué | Dónde | Para qué |
|---|---|---|
| `_en_orden_de_prioridad()` | `motor/fuentes/noticias.py` | Venezuela primero, luego la región, luego el resto |
| `POR_MEDIO = 4` | `motor/fuentes/noticias.py` | que un diario no se lleve el pozo (El País aportó 21 de 50) |
| `limite=400` | `recolectar.py` | que dé tiempo a leer los 59 antes de cortar |
| `piezas × 10` | `orquestar.py` | que lleguen bastantes para poder repartir |

Tras el cambio, el mismo día y a la misma hora: **183 candidatas de 18 países**,
Venezuela la que más aporta con 31 y España en 8.

**El orden decide quién ENTRA; la puntuación decide quién GANA.** No se le puso
ninguna bonificación por país al puntuar: si el mejor titular del día es
colombiano, gana el colombiano. Decisión del dueño el 09/09/2026, con la
medición delante (Venezuela aportaba más candidatas que nadie y a la vez tenía
la media más baja, 3.0, porque con trece medios entran también los flojos).

## Quién gana una tanda

`criterio.puntuar()` ordena los candidatos. Suma por vocabulario macro, por
cifras, por frescura, y **+3 si el medio está en `_MEDIOS_OK`**.

**La frescura se mide en HORAS desde el 18/09/2026, y antes no.** Se medía en
días, con la primera franja en «≤ 2 días → +3»: una noticia de hace diez minutos
y otra de hace dos días valían lo mismo. Medido sobre 106 candidatas reales de
22 medios, 18 tenían menos de una hora y 21 más de doce, **y las 106 puntuaban
igual**.

La hora venía en el feed —cero de las 106 sin ella— y `recolectar` la tiraba al
quedarse con el día. Ahora viaja en `Paquete.momento`; `fecha_hecho` sigue
siendo el día, que es lo que se escribe en la pieza y lo que mira el auditor.

| antigüedad | puntos |
|---|---|
| ≤ 2 h | +5 |
| ≤ 6 h | +4 |
| ≤ 12 h | +3 |
| ≤ 24 h | +2 |
| ≤ 48 h | +1 |
| ≤ 8 días | 0 |
| más | −1 |

**Llega a +5 a propósito.** Los otros premios son +3, +3 y +2: con la frescura
también en 3 empataba con ellos. En 5 pesa más que cualquiera por separado y
menos que dos juntos — una recién salida gana a una de ayer parecida, pero una
floja de hace seis minutos no gana a una buena de hace seis horas (comprobado:
9 contra 13).

**Sin hora se puntúa por días, como siempre.** Una captura o un post sin fecha
solo dan el día, y castigarlos por eso sería penalizar a la fuente por cómo
llegó, no por cuándo ocurrió.

**Ese +3 se comparaba contra el titular Y LA URL, y ahí vivió mucho tiempo un
fallo que torcía tandas enteras:** los nombres con espacio no casan con su
dominio. «el país» no encuentra `elpais.com`. Así que los medios de UNA palabra
cobraban —clarin, folha, infobae, semana— y los de dos no: ni El País, ni El
Nacional, ni La República, ni Efecto Cocuyo.

El +3 se repartía por la longitud del nombre. Y como casi toda la prensa
venezolana tiene nombre de dos palabras, **el país del medio competía con tres
puntos de desventaja**: el 08/09/2026 el pozo traía 67 candidatos venezolanos y
no entró ninguno en las seis piezas.

Ahora el separador entre palabras es opcional y la lista se escribe como lista,
no como regex a mano. Cobran 43 de los 59 medios; los 16 que no, es porque nunca
estuvieron en la lista de prestigio (BBC Mundo, DW, NYT, El Tiempo…) y eso es
una decisión editorial, no un fallo.

**Meter un medio en `MEDIOS` y no en `_MEDIOS_OK` es meterlo a medias:** puede
ser fuente cuando alguien la pide, pero no compite por entrar en la tanda.

## El piso de Venezuela

`orquestar.PISO_VENEZUELA = 3` **reserva tres de las seis plazas de cada tanda**
para Venezuela. Es lo contrario del tope de abajo y hace falta por separado: el
medio se llama SurEconomics y su tesis es Venezuela, pero la puntuación no sabe
eso. El 10/09/2026 la tanda salió con dos de Colombia, dos de Bloomberg Línea y
una de México.

**No es una bonificación al puntuar.** La puntuación sigue decidiendo *cuáles*
son las tres venezolanas, y las otras tres plazas se compiten como siempre. Si
un día no hay tres, entran las que haya y el resto se rellena: no se publica un
hueco por cumplir una cuota.

**«De Venezuela» es de lo que HABLA, no quién la publica** (`de_venezuela()`).
Telesur está fichado como venezolano y cubre toda la región: la única pieza que
el motor contaba como venezolana ese día era suya y hablaba de Argentina. Solo
cuando el titular no nombra ningún país se cae al medio, que es la mejor pista
que queda. Y dentro del piso van **primero las que nombran Venezuela**: con solo
el respaldo por medio, las plazas se las llevaban «Quién es el líder político
mejor pagado del mundo» y «El brent supera los 102 dólares» —una curiosidad y un
precio global— publicadas por diarios de Caracas.

**El recorte de candidatas es x10 por esto.** Ver «Quién entra en el pozo»: con
x3 llegaban 18 y solo una era venezolana, así que reservar tres plazas sobre
esas 18 no podía dar tres.

## El tope por país

`orquestar.tope_de()` limita cuántas piezas de un mismo país entran en una
tanda: **2 por defecto, Brasil 1, y Venezuela sin tope.**

**Empezó siendo solo `{"Brasil": 1}` y esa fue la lección.** Lo que no estuviera
en la tabla no tenía tope, y cada país que faltaba hizo por turnos lo que hacía
Brasil: Brasil el 08/09, España el 09/09 por la mañana y **México el 09/09 por
la tarde, con tres piezas de seis**. Añadir países de uno en uno según van
fallando es ir siempre un día por detrás.

Venezuela sigue sin tope, que era lo único que había que proteger: es el país
del medio y una tanda entera suya es una decisión editorial legítima.

Sale de una tanda real: el 08/09/2026 tres de cinco piezas fueron de Brasil. No
es que Brasil fuera más noticia ese día; es que Folha publica mucho y muy
seguido, y el recolector ordena por calidad sin mirar de dónde viene cada una.
Un medio latinoamericano que abre tres de cinco con Brasil deja de parecerlo.

**OJO: ESTE TOPE ESTABA TAPANDO OTRA COSA.** Al día siguiente pasó lo mismo con
España y, al medirlo, la causa no era que Brasil ni España publicaran mejor: era
que estaban arriba en `MEDIOS` y `extraer()` cortaba antes de llegar a los
demás. Ver «Quién entra en el pozo». Arreglado eso, Brasil aporta 8 candidatas
de 183 en vez de 27 de 50, así que **el tope ya casi no debería morder**. Se
deja puesto como red, pero si algún día vuelve a hacer falta de verdad, mira
antes la composición del pozo: puede que el problema esté otra vez antes.

**Lo que no está en la tabla no tiene tope, y eso también es deliberado.**
Venezuela es el país del medio y una tanda entera de Venezuela es una decisión
editorial legítima, no un accidente del recolector. Un tope general habría
cambiado eso de paso, sin que nadie lo pidiera.

El tope se aplica sobre la lista **entera** y antes de cortar a `--piezas`, así
que lo que se descarta se reemplaza solo por el siguiente candidato. Va después
del filtro de duplicados: al revés, una pieza de Brasil podría gastar el cupo y
caerse luego por repetida.

## Umbrales, y de dónde sale cada número

Ninguno se elige a ojo. Todos salen de medir contra casos reales y todos tienen
su historia escrita al lado del código.

| Constante | Valor | Dónde | Qué decide |
|---|---|---|---|
| `memoria.UMBRAL` | 0.40 | `motor/memoria.py` | si algo ya se publicó |
| `noticias.POR_MEDIO` | 4 | `motor/fuentes/noticias.py` | cuántas aporta un mismo diario |
| `orquestar.PISO_VENEZUELA` | 3 | `orquestar.py` | plazas reservadas para Venezuela |
| `orquestar.TOPE_GENERAL` | 2 | `orquestar.py` | máximo por país (Venezuela exenta) |
| `captura.PARECIDO_MINIMO` | 0.45 | `motor/captura.py` | si un candidato es la nota |
| `captura.PARECIDO_AUTOMATICO` | 0.75 | `motor/captura.py` | si lo es sin preguntar |
| `nota.MAX_FUENTES` | 3 | `nota.py` | cuántos medios se cruzan |
| `foto.ANCHO_MINIMO` | 1000 | `motor/foto.py` | portada demasiado pequeña |
| `auditor.TILDES_MINIMAS` | 5,0 por mil | `motor/auditor.py` | si la pieza salió sin tildes |

`memoria.UMBRAL` lleva su propia bitácora en el docstring (0.40 → 0.31 → 0.36) y
un aviso que decía: **el hueco entre duplicados reales y falsos positivos se ha
estrechado de 0.144 a 0.035. Cuando se cierre habrá que cambiar de método, no de
número.**

**Se cerró el 09/09/2026, y del revés: el hueco es negativo.** Contra el
catálogo real, un duplicado auténtico puntuaba 0.238 y una noticia legítima
0.643. O sea que **mover el 0.36 ya no arregla nada**: subirlo deja pasar
repetidos, bajarlo tapa noticias nuevas. Si vienes a ajustar ese número, ese es
el motivo por el que no va a funcionar.

Lo primero que se hizo no fue afinar el detector sino **quitarle poder**: toda
pieza que dé por repetida se avisa al chat con dos botones, «Subirla igual» y
«Escribirla otra vez».

**Pero eso solo vale para `/nota`, y el 10/09/2026 se vio el hueco.** La tanda
automática no tiene a quien preguntar: ahí un bloqueo de más tira una noticia
buena en silencio. Pasó con «UCAB proyecta 6,5 % de crecimiento en Venezuela»
—la mejor pieza del pozo ese día y del país del medio—, descartada contra
«Datanálisis proyecta hasta 10 %»: dos institutos, dos previsiones, dos
noticias. Perdió por catorce milésimas.

Así que **el umbral subió de 0.36 a 0.40**, decisión del dueño con la medición
delante. Mismo número de fallos, distinto tipo: a 0.36 eran 2 bloqueos de más y
0 escapes; a 0.40 son 0 y 2. Un duplicado que se cuela se ve en la portada y se
borra; una noticia tirada en silencio no la echa nadie de menos, que es
justamente lo que la hace cara.

## Reglas de oro (no negociables)

1. **Ninguna cifra que no esté en el expediente.** Ni redondeada, ni estimada. El
   auditor lo comprueba y bloquea.
2. **Toda fuente usada se nombra en el texto**, no solo al pie. La lista de
   fuentes del final no es una atribución.
3. **Secretos solo en `.env` y en GitHub Secrets.** Nunca en el código ni pegados
   en un chat. Si uno se expone, se revoca antes de rotarlo.
4. **Degradación suave.** Si Tavily cae, quedan los feeds. Si el panel falla, el
   correo sale igual. Mantener ese patrón.

   **PERO «si Gemini se agota, está Groq» ERA MENTIRA PARA EL REDACTOR, y
   conviene saberlo antes de confiar en ello.** El 14/09/2026 se agotó el
   crédito de Gemini, Groq devolvió 413 y el motor no escribió ni una pieza:
   cinco peticiones perdidas y la tanda del día siguiente caída.

   Medido después desde Actions, con el plan `on_demand` de Groq:

   | prompt | respuesta |
   |---|---|
   | 1, 10, 20 KB | 200 |
   | 30 KB | 429 · cuota por minuto |
   | 45 KB | 413 · *Request too large* |

   **El prompt del redactor son ~30 KB** (`00-base.md` 12,5 + el del tipo 5 + el
   perfil 5,4 + el expediente), así que está en el filo y con un expediente de
   tres fuentes se pasa. No es que el respaldo fallara ese día: es que **nunca
   pudo escribir una pieza**. Para las llamadas pequeñas —la entidad de la
   portada, los textos de la lámina— sí sirve.

   Quien quiera que el respaldo sea real tiene dos caminos: **adelgazar el
   prompt** (que además es donde se va el crédito de Gemini) o **pagar un plan
   de Groq**. Mientras tanto, si Gemini se queda sin crédito el motor se para,
   y eso hay que saberlo, no descubrirlo.
5. **Nada se publica solo.** Todo entra como borrador.
6. **El `schedule:` de GitHub no es el reloj.** Llega con horas de retraso
   (medido: 12:00 UTC → 16:22). Lo dispara el cron del Worker. El `schedule` de
   `diario.yml` se queda como red: la `guardia` salta el del reloj si esa tanda
   ya salió.

## Trampas conocidas (leer antes de depurar)

Cada una costó al menos una tarde.

### Del expediente y el auditor

1. **Las cifras vienen con la norma del medio que las publicó.** El Economista es
   mexicano y escribe `2.61%`; el extractor entendía solo la norma española y
   guardaba `61 %`. No era un fallo de formato: el expediente afirmaba que Apple
   subió 61 % citando a un medio que dijo 2,61 %. Se aceptan las dos normas, con
   los millares antes que los decimales para que `1.500` siga siendo mil
   quinientos.
2. **Una fecha no es una cifra.** Ni «2 de septiembre», ni `2026-08-31` en una
   línea de referencia. Las dos formas se quitan antes de buscar números.
3. **Si dos medios publican la misma cifra, basta nombrar a uno.** Con el
   multi-fuente, la cifra del titular la publica todo el que cubre la historia:
   exigir la lista entera bloqueaba piezas que citaban correctamente y empujaba a
   atribuirle a un medio algo leído en otro.
4. **Un aviso por hueco, no por cifra.** La comprobación de atribución vivía
   dentro del bucle de advertencias y salían nueve hallazgos idénticos.

### De la memoria de duplicados

5. **El filtro previo no atraviesa el idioma.** Corre antes de escribir, cuando
   el titular todavía es el de la fuente: «Por que a Holanda retirou toneladas de
   ouro» puntúa 0.336 y pasa; ya en español, la misma pieza puntúa 0.620. Por eso
   se comprueba **otra vez en `armar_carga.py`**, con el titular final.
6. **Se compara contra piezas del MISMO formato.** Una columna sobre lo que ya se
   reportó no es un duplicado: es lo que hace un medio todos los días.
7. **Un tuit se lee como tuit también en la comprobación de duplicados.** Pasarle
   la URL de x.com a `leer_enlace()` devuelve su muro de acceso, y se comparaba
   esa basura contra lo publicado: un bloqueo correcto señalando la pieza
   equivocada. Un motivo equivocado hace que una decisión buena parezca un fallo.
8. **El catálogo se pedía con `limit=60` y el sitio tenía 270 piezas.** La
   memoria estaba ciega al 78 % de lo publicado: a doce piezas diarias entre las
   dos tandas, todo lo de más de cinco días atrás se podía republicar sin que
   nada lo notara. Y de paso envenenaba los pesos, porque con 60 titulares
   «acuerdo» y «petrolero» aparecen en uno solo y el sistema los tomaba por
   rarísimos. **La API tope las respuestas en 100 aunque le pidas más**: hay que
   paginar con `page` y mirar `meta.pages`.
9. **El bloqueo por repetida ocurre DESPUÉS de escribir y entregar.** La pieza ya
   se anunció como «Borrador listo», ya se mandó entera por el chat y ya salió
   por correo. Si esa última puerta se cierra en silencio, la persona se queda
   con un borrador que no existe en ninguna otra parte. Pasó dos veces en media
   hora el 09/09/2026 y se describió como que el bot se había vuelto loco.
   `armar_carga.py` deja `descartadas.json` y `nota._avisar_descartadas()` lo
   cuenta con el botón de subirla igual. **Si añades otro motivo de descarte,
   apúntalo ahí también**: el log de Actions no lo lee nadie desde Telegram.
10. **Los dos botones hacen cosas distintas y no son intercambiables.**
    «Subirla igual» (`subir:<corrida>`) lanza `subir_borrador.yml`, que se baja
    el artefacto de aquella corrida y sube **el texto exacto** que la persona ya
    leyó. «Escribirla otra vez» (`forzar:1`) redacta desde cero: tarda minutos y
    devuelve un texto parecido pero distinto del que aprobó. Por eso el primero
    va primero.
    **Y solo el segundo necesita enlace:** el Worker lo recupera del texto del
    mensaje con `/\/nota\s+(https?:\/\/\S+)/` porque no cabe en `callback_data`
    (64 bytes), así que con un tema escrito a mano no aparece. El número de
    corrida sí cabe —once dígitos— y por eso «Subirla igual» sale siempre.
11. **El artefacto de una corrida trae MÁS carpetas `peticion-*` de las que esa
    corrida escribió.** Hay una commiteada en el repo
    (`peticion-2026-09-01-bank-of-america-vi/`) que el checkout deja en el
    workspace y que `upload-artifact` recoge con el patrón `peticion-*/`. Elegir
    «la primera» por orden alfabético subía **esa**, o sea una pieza de otro día
    que nadie pidió. `subir_borrador.yml` elige por contenido: la única carpeta
    cuyo `carga.json` tiene una pieza marcada `duplicada`. Si algún día borráis
    esas carpetas del repo, la regla sigue siendo correcta; al revés no.
12. **Una repetida y una bloqueada por el auditor son dos cosas distintas y
    tienen banderas distintas** (`--subir-duplicadas` y `--subir-bloqueadas`).
    Una repetida no tiene ningún problema de contenido, solo se parece a algo ya
    publicado; una bloqueada tiene una cifra que no se pudo rastrear. Juntarlas
    en una sola bandera obligaría a aceptar las dos cosas para conseguir una.

### De la ortografía

**Cuando una pieza sale sin tildes, no le falta una: le faltan todas, y eso es
lo que la hace detectable.** Edición reportó «errores ortográficos» el
21/09/2026 y lo primero que se buscó fue lo difícil: `«según informo»` por
`«informó»`, que ningún corrector marca porque sin tilde sigue siendo una
palabra válida (*yo informo*) y solo el contexto la distingue.

Medida la densidad de tildes sobre las 290 piezas publicadas con cuerpo, el
problema real era otro y era grueso:

| | tildes por mil letras |
|---|---|
| mediana del catálogo | 20,4 |
| la más baja de las sanas (#274) | 12,0 |
| **#427**, presupuesto de Brasil (03/09) | **0,8** |
| **#578**, Trump y México (17/09) | **0,0** |

Dos de 290, con un hueco de 15x. **Al revés que con los duplicados, aquí el
umbral sí separa**: cualquier valor entre 2 y 10 da el mismo resultado sobre el
catálogo entero. Por eso esto sí se resuelve con un número y aquello no pudo.

**La ñ sobrevive y las vocales no** (`brasileño`, `señalo`, y alrededor
`Comite`, `aprobo`, `miercoles`, `oposicion`). Eso descarta un fallo de
codificación —cp1252 se habría llevado la ñ por delante— y prueba que el texto
se redactó así. Por eso la ñ **no** cuenta en la medida: contarla taparía el
síntoma justo en los casos que hay que cazar. Y por eso no hay nada que
"arreglar" en el camino del texto: se comprobó que ninguna de las
normalizaciones del repo toca `title` ni `content`; todas van con `.lower()` y
alimentan comparadores.

Se ataca por los dos lados: `prompts/00-base.md` lo pide (**## Tildes**) y
`auditor.TILDES_MINIMAS` lo bloquea cuando el prompt no basta. **Es bloqueo y no
aviso porque las dos se publicaron**: un aviso en el log de Actions no lo lee
nadie (ver trampa 9), y para el bloqueo ya existe salida con
`--subir-bloqueadas`.

### De la recolección

13. **`extraer()` corta al llegar al límite, y el orden de `MEDIOS` decidía la
    tanda.** Ver «Quién entra en el pozo». Si vuelves a tocar `limite`, mira
    antes cuántos medios da tiempo a leer: es un tope de composición, no de
    seguridad.
14. **Un medio que publica mucho se lleva el pozo si le dejas.** El País aportó
    21 de 50 candidatas él solo. `POR_MEDIO` lo limita a cuatro.
15. **España no estaba en `criterio.PAISES`**, así que `pais_de()` devolvía
    `None` para toda noticia española y `diversificar()` las metía en el saco
    «sin país» sin poder contarlas. Media tanda del 09/09/2026 fue española sin
    que ninguna regla de reparto se enterara.
16. **El tope por país mira el MEDIO; `criterio.diversificar()` miraría el
    TITULAR, y no la llama nadie.** Comprobado con un grep: es código muerto que
    parece una red puesta. Y las dos preguntas no son la misma: «las claves del
    Paquete Económico 2027» es de México y por titular sale «sin país». Si
    buscas por qué no se frenó un país, está en `orquestar.py`.
17. **Dos piezas del mismo hecho el mismo día no son «repetidas» para la
    memoria**, porque ninguna está publicada todavía: se repiten entre ellas.
    `orquestar.sin_repetirse_entre_si()` las compara con la misma vara. Salió
    de una tanda con tres notas del mismo Paquete Económico mexicano.
18. **El feed puede vivir en otro dominio que los artículos**, y entonces
    `_pais_de()` no reconoce el medio y sus piezas se saltan el tope **sin que
    nada avise**. Pasa con BBC Mundo (sindica desde `bbci.co.uk`, publica en
    `bbc.com`) y con el Expansión español (CDN `uecdn.es` → `expansion.com`).
    Para eso está la clave `dominio` en `MEDIOS`.
19. **«Hacienda» no identifica a España.** Es también el fisco de México, Chile,
    Colombia y Costa Rica: con esa palabra en el patrón, una nota mexicanísima
    sobre el ISR y el RFC salió clasificada como española y rompió el reparto de
    una tanda. En `PAISES` solo van términos que no existan fuera del país.
20. **En `criterio.PAISES` había quince bytes 0x08 literales donde el código
    debía decir `\b`.** Un límite de palabra que se perdió al escribir el
    archivo con una herramienta que interpretó el escape: `\bbcv\b`,
    `bolívar\b` y `\bfed\b` no podían casar nunca, porque exigirían un
    retroceso de carro dentro del titular. **Y al arreglarlo con un heredoc
    volvió a pasar lo mismo**, dejando la sustitución en un no-op. Para tocar
    escapes, archivo aparte; nunca heredoc ni `sed`.

### De los archivos y los procesos

21. **`producir.py` fija su salida a UTF-8, y no es cosmético.** Al llamarlo como
   subproceso, la tubería usa cp1252 y la «ó» de `opinión` se pierde: `nota.py`
   buscaba `opini?n-2.txt`, no existía, y daba por no generada una pieza escrita
   y auditada. Ni Telegram ni panel.
22. **El nombre del borrador se calcula en UN sitio.** Lo calculaban los dos y
   falló dos veces en una semana. Ahora `producir.py` lo imprime y `nota.py` lo
   lee de ahí. Además se numera (`-2`, `-3`) si ya existe: dos columnas del mismo
   tema se pisaban en silencio.

### De la búsqueda

23. **`topic:"news"` de Tavily excluye a los medios pequeños**, y además su
    relevancia es inestable: la misma consulta devolvió seis piezas correctas y,
    minutos después, resultados de otro tema. Por eso se consultan los dos modos
    y **se exige que el candidato NOMBRE el asunto**.
24. **Las páginas de etiqueta ganan una búsqueda por texto.** «Nombre: Noticias,
    Fotos y Videos», «Nombre - Diario.com», «Sección - Página 731 de 8174». Son
    donde ese nombre aparece más veces. `_es_indice()` las descarta, y se piden
    tres veces más resultados de los que se van a usar porque el filtro vacía la
    primera página.
25. **Una ficha de podcast no es una nota.** «BBC Audio | Global News Podcast» se
    deja leer y devuelve el resumen del episodio; la pieza se escribió desde ahí.
26. **El relleno de hablar arruina la consulta.** «lo que dijo X hoy» reparte el
    peso entre palabras vacías: el primer resultado era de otro tema. Se limpia
    antes de buscar (`nota._consulta_limpia`).
27. **Si la captura dice de qué medio es, se va ahí primero** —y se leen sus
    feeds a fondo (21 días, 100 por feed) en vez de por encima como los 51. Leer
    hondo en uno cuesta lo mismo que leer por encima en cuarenta.
28. **Los feeds de sección no son solo de economía.** De un medio aprobado, una
    nota fuera de su sección económica era invisible. Los feeds añadidos van con
    `economia=False`: `titulares()` (capturas) los ve enteros, `extraer()` (pozo
    de las tandas) les exige vocabulario económico.
29. **Google News encuentra lo que el RSS no ve, pero su enlace no sirve.** Es un
    redirector cifrado que desde 2024 solo salta por JavaScript (comprobado
    decodificándolo: 437 bytes, sin URL dentro). `titulares_google()` **nunca
    devuelve enlaces** a propósito, para que ninguno pueda colar un redirector en
    el expediente. Sirve para decir «esto existe, pásame el enlace».

### De las redes sociales

30. **X e Instagram son aplicaciones de JavaScript**: `leer_enlace()` encuentra
    cero párrafos. X se lee por su oEmbed. **Instagram se lee cambiando el
    User-Agent**: a un navegador le sirve la página vacía, a
    `facebookexternalhit` le sirve las etiquetas Open Graph con la cuenta, la
    fecha y el pie entero. Es la vía que Instagram publica para que se puedan
    previsualizar sus enlaces; su API oficial exige una app de Meta revisada.
31. **Los dos se atienden por la misma puerta** (`leer_publicacion`). Tener dos
    ramas paralelas es como se llega a que una se arregle y la otra no.

### De las portadas

32. **La imagen ilustra el ASUNTO, no la sección.** Buscar en Commons palabras
    del titular daba el Museu do Ipiranga encabezando una nota de morosidad. Se
    le pregunta a **Wikidata cuál es la imagen de la entidad**: P18 imagen, P154
    logo, P41 bandera.
33. **Si se sabe de quién habla y no hay imagen suya, no se pone ninguna.** Sin
    esto, una nota sobre la salida a bolsa de Shein eligió el retrato de Ali
    Mohamed Shein, expresidente de Zanzíbar.
34. **La bandera solo si el país es el ÚNICO asunto.** Si el titular nombra algo
    más, o es la imagen de eso o ninguna. Y se descarta la entidad país entera,
    no solo su bandera: quitando solo P41, el hueco lo ocupaba el mapa del país.
35. **Wikidata separa figura pública de particular sin que nadie mantenga una
    lista.** Un jefe de Estado tiene ficha y retrato libre; la víctima de un
    suceso, no. Cuando no hay ficha no hay foto, que es el resultado que se
    quería.
36. **Sin IA, el buscador de portadas se degradaba a elegir cualquier cosa, y
    en silencio.** El camino bueno —preguntarle a Wikidata por la entidad—
    necesita al modelo para saber de quién habla el titular
    (`entidad.nombres_del_titular`). Cuando Gemini se queda sin cuota ese paso
    no falla con estrépito: devolvía lista vacía, **indistinguible de «este
    titular no nombra a nadie»**, y la nota caía a la búsqueda por texto en
    Commons.

    Medido el 21/09/2026 con la IA apagada, sobre las diez peticiones guardadas
    en el repo: **siete recibieron portada y las siete estaban mal.** El bitcoin
    con servidores de la Fuerza Aérea; la deuda de EE. UU. con un gráfico de la
    deuda **húngara**; el acuerdo energético EE. UU.-Venezuela con **un derrame
    petrolero en Morrocoy**. Y repetidas: el mismo derrame en tres notas.

    Con la IA encendida, esas mismas dan el logo de Bitcoin, el de JPMorgan y
    ninguna portada. **El buscador no estaba roto: lo que estaba roto es que se
    siguiera adelante cuando no se le podía preguntar.** Ahora
    `entidad.nombres_del_titular` devuelve `None` ante una avería (y `[]` solo
    cuando el modelo sí contestó que no hay nadie), y `foto.para()` se niega a
    buscar por texto en ese caso.

    La del derrame es la que explica por qué no es cuestión de estética:
    ilustrar la firma de un acuerdo energético con un derrame **es una opinión
    editorial que no escribió nadie**.
37. **Wikimedia contesta 200 con una PÁGINA HTML cuando el thumb no existe**,
    no un 404 (comprobado el 21/09/2026: 231 KB con `Content-Type: text/html`).
    Sin comprobar el tipo, esos bytes se guardaban con nombre `.jpg`, Chrome no
    podía dibujarlos y la lámina salía con el fondo en negro **sin que nada
    dijera por qué**. `lamina.bajar()` exige `image/`.
38. **Un SVG no tiene medidas** y Commons fecha banderas y logos por cuando se
    adoptó el diseño (la del Reino Unido consta como de 1801). Las reglas de
    tamaño y antigüedad no se les aplican; a las fotografías sí, enteras.

## Comandos

```bash
python orquestar.py --tanda manana --piezas 6 --con-foto   # la tanda completa
python nota.py "<enlace o tema>" --tipo Análisis            # una pieza
python nota.py "<tema>" --tipo Opinión --autor "Nombre"     # una columna
python armar_carga.py <carpeta>                             # carga.json
python subir.py <carga.json> --subir-bloqueadas             # al panel
python reauditar.py <nombre-sin-extension>                  # volver a auditar
python comprobar.py                                         # salud de fuentes e IA
python buscar_foto.py "<consulta>"                          # portadas a mano
```

Las pruebas son scripts `pruebas_*.py`: auditor, memoria, paquete, candidato y
clasificar. **No hay framework**: se corren y se mira la salida.

Sin Python global en Windows: hay un runtime portátil en
`C:\Users\saulb\telegram-finance-bot\.pyruntime\`.

## Credenciales y cuentas

- **Panel:** `SURECONOMICS_USUARIO` / `SURECONOMICS_CLAVE`. No hay token
  estático: `subir.py` hace `POST /auth/login` y reintenta una vez ante un 401.
- **`JWT_SECRET_KEY` del backend NO se comparte jamás.** Firma los tokens: con
  ella se puede falsificar la sesión de cualquier usuario.
- **Las claves viven en el `.env` del bot**, que es la misma máquina. Si algún
  día se separan los despliegues, esto pasa a un `.env` propio.
- **Tavily** (`TAVILY_API_KEY`): plan gratuito de 1.000 créditos/mes. Cuando se
  agota devuelve **432** y la búsqueda desaparece en silencio salvo por el aviso.
  Sin ella quedan los feeds. Pago por uso a $0,008 el crédito.
- **Gemini, con DOS CUENTAS en embudo.** `motor.claves_gemini()` las lee en
  orden y `_gemini()` las recorre: si la primera se queda sin cuota, la segunda
  escribe la pieza. Cada modelo tiene además su cuota diaria propia, así que la
  cadena real es cuatro combinaciones.

  | variable | quién | papel |
  |---|---|---|
  | `GEMINI_API_KEY` | cuenta de **servicios** de la empresa | principal |
  | `GEMINI_API_KEY_RESERVA` | cuenta de trabajo personal | desahogo |

  **La institucional va primera a propósito.** El medio es un producto de la
  empresa: si la clave que lo sostiene cuelga de la cuenta personal de alguien,
  el día que esa cuenta cambie se cae la producción con ella.

  **LAS DOS CLAVES TIENEN QUE SER DE PROYECTOS DISTINTOS.** La cuota de Gemini
  va por proyecto, no por clave: dos claves del mismo proyecto comparten el
  mismo cubo y el embudo es decorativo.

  La reserva es **opcional**. Si no está, todo sigue igual con una sola: un
  secreto que no existe llega como cadena vacía y `claves_gemini()` lo descarta.

  `comprobar.py` prueba **todas** las cuentas y solo escribe `CUOTA AGOTADA`
  —la frase que lee `orquestar.hay_con_que()` para no arrancar la tanda—
  **cuando no queda ninguna**. Mirando solo la principal, el motor se quedaría
  parado con la reserva intacta.

  **El Worker NO tiene el embudo**: `worker.js` es otra implementación, en JS,
  con su propio binding de una sola clave. El newsletter y el asistente del chat
  gastan de la cuenta principal y, cuando se agota, ahí sí se caen.

- **Groq sigue de respaldo, pero no para el redactor.** Ver la regla de oro #4:
  su límite por petición no admite los ~30 KB del prompt. Sirve para las
  llamadas pequeñas.

## Convenciones

- **Español** en comentarios, docstrings y mensajes de commit.
- Los comentarios explican **por qué**, no qué. Casi la mitad de las líneas de
  este repo son explicación, y es a propósito: buena parte de lo que hay aquí son
  decisiones aprendidas a golpes. **Si borras un comentario así, se repite el
  error.**
- Sin dependencias nuevas salvo necesidad real.
- Antes de cambiar un umbral, **mídelo** contra casos reales y deja la medición
  escrita.

## Pendientes conocidos

- **Rotar la clave de `sur@bot.com`** (se pegó en un chat) y bajarle el rol de
  `admin` a `editor`.
- **Recargar Tavily: ya está bloqueando trabajo, no es un pendiente cómodo.** Se
  agotó y devuelve 432. El 09/09/2026 una petición desde un tuit murió con «no
  encuentro esta noticia en ninguna fuente verificable»: sin Tavily quedan los
  feeds, y un tuit de un medio cuyo feed no cubre esa sección no se encuentra por
  ningún otro camino. De 534 candidatos del respaldo, el más parecido puntuó
  0.000 y era de otro tema.
- No hay endpoint de subida de imágenes en el panel (`POST /admin/media` da 405):
  solo se puede adjuntar por dirección web. `motor/imagen_publica.py` es un apaño
  hasta que los desarrolladores lo añadan con la migración a R2.
- **Paraguay sigue sin ningún medio.** Se probaron ABC Color (cuatro
  direcciones), Última Hora (dos) y La Nación PY (dos): todas devuelven vacío.
  Hace falta buscar por otra vía, no insistir con esas.
- Ampliar la lista blanca con macro de EE. UU. **Ojo:** hay que probar por
  separado el host del RSS y el del artículo; `bancaynegocios.com` tiene el feed
  muerto y los artículos legibles, y por eso está en `REFERENCIA` y no en
  `MEDIOS`.
- Barrer las piezas publicadas por si hay atribuciones invertidas: el auditor
  comprueba que la fuente se nombre, no que la cita sea suya.
