# Migrar las credenciales a cuentas de la empresa

Estado: pendiente. Escrito el 24 de agosto de 2026, antes de activar facturación
en Gemini.

---

## Por qué, en una frase

SurEconomics es un activo de RendiGroup que se piensa vender en 5–7 años. Hoy la
infraestructura que lo sostiene está a nombre de una persona. Eso hay que
arreglarlo **antes** de meter una tarjeta, no después.

Tres riesgos concretos, ninguno hipotético:

1. **Facturación.** Activar el plan de pago de Gemini en una cuenta personal
   carga el gasto de la empresa a una tarjeta personal.
2. **Continuidad.** Si la persona no está —vacaciones, salida, lo que sea— nadie
   más puede rotar una clave, y cuando una caduca el sistema se para sin que
   nadie sepa entrar a arreglarlo.
3. **Venta.** En una compra se revisa de quién son los activos. "La API está en
   el Gmail de alguien" y "el repositorio está en su cuenta personal" son cosas
   que se piden corregir antes de firmar, con prisa y mal.

Ya hay precedente de hacerlo bien: **La Campana envía desde el correo de trabajo
de rendigroup.com** (Google Workspace), no desde un Gmail personal. Esa es la
cuenta a la que hay que llevar el resto.

---

## Dónde vive cada credencial hoy

`GEMINI_API_KEY` es la más repartida: está en **cinco sitios**, y si se revoca la
vieja antes de actualizar los cinco, algo se rompe a las 10 de la mañana.

| Credencial | Dónde vive | ¿Migrar? |
|---|---|---|
| `GEMINI_API_KEY` | Secrets de `telegram-finance-bot`, Secrets de `wallstreet-bot`, `.env` local, binding del Worker de Cloudflare, y `scripts/deploy_worker.py` que lo empuja | **Sí, primero.** Es la que va a llevar facturación |
| `GROQ_API_KEY` | Secrets de los dos repos, `.env` local | **Sí.** Gratis, pero mismo problema de propiedad |
| `TELEGRAM_TOKEN` | Secrets de `telegram-finance-bot`, `.env` | **Sí, y es la más incómoda** (ver abajo) |
| `CLOUDFLARE_API_TOKEN` y `ACCOUNT_ID` | `.env` local | **Sí.** La cuenta de Cloudflare debería ser de la empresa |
| `GITHUB_PAT` | `.env`, y otro en cron-job.org | **Sí**, y ver lo del repositorio |
| `FRED_API_KEY` | Secrets de `wallstreet-bot` | Sí, pero es gratis y se saca en dos minutos |
| `SMTP_USUARIO` / `SMTP_CLAVE` | Secrets de `wallstreet-bot` | **Ya está bien**: es la cuenta de rendigroup.com |
| `TAVILY_API_KEY`, `WEBHOOK_SECRET`, `CHAT_ID`, `DESTINATARIOS` | `.env`, Secrets | Menores, van de arrastre |

---

## El orden importa: verificar antes de revocar

**La regla: la clave vieja se revoca ÚLTIMA, y solo después de ver funcionar la
nueva en todos los sitios.** Al revés, el fallo es silencioso — no salta un
error, simplemente no llega el mensaje de las 10.

Para `GEMINI_API_KEY`:

1. Crear la clave nueva desde la cuenta de **rendigroup.com** (puede requerir que
   el administrador del Workspace habilite el acceso a AI Studio).
2. Activar facturación ahí, con medio de pago de la empresa.
3. Actualizar los cinco sitios, **sin tocar todavía la vieja**:
   - Secret `GEMINI_API_KEY` en `telegram-finance-bot`
   - Secret `GEMINI_API_KEY` en `wallstreet-bot`
   - `.env` local — con `[System.IO.File]::WriteAllText` y `UTF8Encoding($false)`,
     **nunca** con `Set-Content -Encoding utf8`: mete BOM y `python-dotenv` deja
     de leer la primera clave (trampa ya documentada)
   - Binding del Worker de Cloudflare
   - Volver a desplegar el Worker (`python scripts/deploy_worker.py`) y **esperar
     10–20 segundos**: si se prueba de inmediato responde la versión anterior y
     parece que el cambio no funcionó
4. Comprobar los cuatro sistemas con la clave nueva:
   - `python comprobar.py` en `sureconomics-medio` (Gemini en verde)
   - Disparar `news.yml` a mano y ver que llega el mensaje
   - Disparar `boletin.yml --edicion media` y ver que llega el correo
   - Preguntarle algo al bot conversacional
5. **Solo entonces**, revocar la clave vieja en la cuenta personal.
6. Correr `comprobar.py` otra vez. Si algo se rompió, fue el paso 3.

---

## Decidido el 24/08/2026

- **Telegram: no se migra.** El bot se queda en la cuenta que lo creó. Queda como
  deuda conocida, no como pendiente.
- **Cloudflare: en marcha.** Se está creando la cuenta con correo de la empresa
  para el sitio web. Cuando exista, ahí debería mudarse también el Worker del bot
  conversacional y del newsletter, que hoy está en cuenta personal.
- **Repositorios: se dan por resueltos con la migración a n8n.** Ojo con esto —
  ver la sección siguiente: n8n cambia la pregunta, no la responde.

## n8n no elimina la pregunta de propiedad

Lo que se va a n8n es la **orquestación**: horarios, orden, reintentos,
credenciales. Eso sí sale de GitHub Actions y es lo correcto.

Lo que NO se va son ~1.400 líneas de Python que n8n **llama**: el extractor con
sus cuatro fuentes, el auditor, el economista, el redactor, el paquete de datos y
la biblioteca, más los prompts y los perfiles editoriales. Esa frontera se fijó a
propósito: reescribir esa lógica en nodos reintroduce los errores que ya costaron
caro (el `previousClose` de Yahoo, el cruce de earnings de Nasdaq, el timeout de
feedparser).

Ese código necesita un repositorio igual. Y los flujos de n8n son archivos JSON
que también conviene versionar, o el día que alguien rompe uno no hay a qué
volver.

La pregunta, entonces, no desaparece: **¿de quién es el servidor de n8n, y de
quién es el repositorio del código que n8n invoca?** Si la respuesta a las dos es
"de la empresa", el problema está resuelto. Si es "de una persona", solo cambió
de sitio.

## Lo incómodo: Telegram y el repositorio

**El bot de Telegram lo creó BotFather desde una cuenta personal.** Telegram no
tiene una forma cómoda de traspasar la propiedad de un bot. Las opciones son
crear un bot nuevo bajo una cuenta de la empresa —lo que obliga a que todos los
suscriptores vuelvan a darle a Empezar, y ahí se pierde gente— o dejarlo como
está y anotarlo como deuda conocida. **Es decisión de Alex, no técnica.**

**Los repositorios están en una cuenta personal de GitHub** (`saulbenarroch-debug`),
y son públicos para tener Actions gratis e ilimitado. Para un activo de la
empresa, lo correcto es una organización de RendiGroup. Trasladar un repositorio
conserva el historial y las estrellas, pero **hay que volver a cargar todos los
Secrets a mano**: no viajan con el repositorio. Y los PAT que usa cron-job.org
apuntan al repositorio viejo, así que también hay que rehacerlos.

Esto último es probablemente más importante que la clave de Gemini, y es más
fácil de hacer ahora que con quince personas trabajando encima.

---

## Recomendación de orden

1. **Gemini**, porque es la que va a llevar facturación y es la que te está
   frenando hoy.
2. **Groq y FRED**, que son gratis y salen en diez minutos.
3. **Cloudflare**, cuando haya cuenta de empresa.
4. **Repositorios a una organización de RendiGroup** — la más importante a medio
   plazo, y la que conviene decidir con Alex.
5. **Telegram**, al final y como decisión de negocio: cuesta suscriptores.
