# SurEconomics — Diseño de agentes y automatización

Borrador 0.1 · para discusión. Si cambia una decisión estructural (la frontera
n8n/Python, la taxonomía, quién audita), se actualiza este archivo.

---

## 0. La idea que sostiene todo

El KPI del rol es **cero errores publicados por automatización**. Eso obliga a
una decisión que define la arquitectura entera:

> **El auditor no puede ser un agente de IA.**

Si quien revisa el borrador es un modelo, tenemos un modelo revisando a otro
modelo y el KPI pasa a ser una esperanza. El auditor tiene que ser **código
determinista**: saca cada número del texto redactado y verifica que ese número
exista en el paquete de datos verificado. Si aparece una cifra que no está en el
paquete, el borrador se **bloquea** — no se advierte, se bloquea, y no llega a
la cola de Edición.

De ahí sale la regla de reparto de todo el sistema:

| Naturaleza | Quién | Qué le toca |
|---|---|---|
| **Código** | Python (probado, versionado) | traer fuentes, calcular cifras, auditar, cargar al panel |
| **IA** | modelo de lenguaje | **solo prosa, clasificación y traducción** — nunca una cifra |
| **Orquestación** | n8n | horarios, orden, reintentos, credenciales, aprobaciones, fan-out |

La IA no calcula porque no puede. No porque el prompt se lo pida.

---

## 1. Los agentes

Diez agentes. La columna **naturaleza** es la más importante del documento: es
lo que hace auditable el sistema.

| ID | Agente | Naturaleza | Entrada | Salida |
|---|---|---|---|---|
| **A1** | **Recolector** | Código | catálogo de fuentes | candidatos crudos con URL, fecha, medio |
| **A2** | **Verificador** | Código + IA mínima | candidato | candidato validado o descartado, con motivo |
| **A3** | **Selector** | Código (reglas) + IA | candidatos validados | los que merecen nota, con prioridad |
| **A4** | **Extractor** | **Código, siempre** | fuente | **paquete de datos**: cifras, entidades, fechas, citas literales |
| **A5** | **Redactor** | IA | paquete de datos | bloque *hecho* + bloque *lectura*, separados |
| **A6** | **Clasificador dual** | IA (salida cerrada) | borrador | tema principal/secundario + país principal/alcance |
| **A7** | **Titulador y SEO** | IA | borrador | titular, sumario, slug, meta description, enlaces internos |
| **A8** | **Auditor** | **Código, sin IA** | borrador completo | aprobado para cola, o **bloqueado** con causa |
| **A9** | **Traductor** | IA + glosario (lookup en código) | borrador aprobado | versión en el otro idioma |
| **A10** | **Cargador** | Código | borrador auditado | borrador dentro del panel de administración |

Más dos que vigilan, no producen:

| ID | Agente | Naturaleza | Qué hace |
|---|---|---|---|
| **A11** | **Vigía de alto impacto** | Código (filtro) + IA | detecta el hecho que no puede esperar el siguiente ciclo y lo eleva de inmediato |
| **A12** | **Centinela** | Código | verifica que cada flujo corrió a su hora. Si no corrió, avisa |

### Detalle de los tres agentes que no existen hoy

**A4 Extractor** — la pieza nueva más importante y la menos vistosa. Hoy el
código calcula cifras y se las pasa a la IA en el mismo paso. Separarlo en un
agente con salida propia es lo que permite que A8 audite: sin un paquete de
datos explícito, no hay nada contra qué comparar el texto.

Para los bloques de más riesgo (cierre de mercados, cifras macro) se propone la
variante estricta: **la IA escribe marcadores, no números.** Redacta
`el IPC de junio fue de {{ipc_jun}}` y el código sustituye. Ahí inventar una
cifra es estructuralmente imposible, no improbable. Para prosa narrativa se usa
la variante normal, con A8 rechazando toda cifra ausente del paquete.

**A6 Clasificador dual** — dos ejes independientes, cada uno con principal y
secundario, y **salida restringida a la taxonomía cerrada** (no texto libre: el
modelo elige de una lista o falla). Sin taxonomía cerrada no hay corte por país
confiable, y el corte por país es cómo se mide el medio entero.

**A8 Auditor** — seis chequeos, todos deterministas:

1. cada número del texto existe en el paquete de datos de A4,
2. cada afirmación atribuida tiene URL de fuente y la URL responde,
3. tema y país están presentes y pertenecen a la taxonomía,
4. los bloques *hecho* y *lectura* están separados y etiquetados,
5. los términos del glosario se usan en su forma aprobada,
6. el titular no afirma más de lo que dice el cuerpo.

Cualquiera que falle, bloquea. La causa se registra: **la tasa de bloqueo por
causa es la métrica de calidad de cada agente** y la señal temprana del KPI.
Si suben los bloqueos por cifra, hay problema de fuente. Si suben por registro,
hay problema de prompt.

---

## 2. El flujo

```
                     FUENTES (RSS · API · SEC · FRED · bolsas · bancos centrales)
                                          |
   A1 Recolector  ──────────────────────────────────────────────► candidatos
                                          |
   A2 Verificador   lista blanca · enlaces vivos · dedup contra el archivo
                                          |
   A3 Selector      ¿merece nota? ¿con qué prioridad?
                                          |
   A4 Extractor     ═══ PAQUETE DE DATOS (cifras, citas, entidades) ═══
                                          |        (código, sin IA)
                                          |
   A5 Redactor      hecho ──── lectura            (IA: solo prosa)
                                          |
   A6 Clasificador  tema + país                   (IA: salida cerrada)
   A7 Titulador     titular · sumario · SEO       (IA)
                                          |
   A8 AUDITOR  ◄──── compara texto contra paquete de datos
                     │                            (código, sin IA)
              BLOQUEA│              │APRUEBA
                     ▼              ▼
              registro de      A10 Cargador ──► PANEL (borrador)
              causa                                    |
                                              ═══ EDICIÓN aprueba ═══
                                                       |
                                              A9 Traductor ──► A8 otra vez ──► panel (EN)
```

Dos observaciones sobre el dibujo:

- **A8 aparece dos veces a propósito.** La traducción vuelve a auditarse. Una
  traducción que cambia el sentido es un error publicado igual que una cifra mala.
- **La única compuerta humana es Edición**, y recibe piezas ya verificadas y
  clasificadas. El objetivo es que el editor **apruebe o rechace**, no que
  reescriba. Si Edición se vuelve el cuello de botella, la automatización no
  aceleró el medio: lo atascó.

---

## 3. Reparto en n8n

**No un flujo gigante.** Siete flujos chicos, cada uno con una razón de ser:

| Flujo | Dispara | Qué corre | Por qué separado |
|---|---|---|---|
| **W1 Recolección** | cada hora | A1 → A2 → A3 → cola | Un ciclo de recolección no debe depender de la redacción |
| **W2 Producción de nota** | por cada candidato de la cola | A4 → A5 → A6 → A7 → A8 → A10 | **Uno por pieza**: una nota que falla no arrastra a la tanda |
| **W3 Traducción** | cuando Edición aprueba (webhook) | A9 → A8 → A10 | Solo se traduce lo aprobado. Traducir borradores es gastar por nada |
| **W4 Cierre de mercados** | hora fija, después del cierre de NY | A4 → plantilla → A8 → A10 | **Sin IA.** Dato puro, plantilla fija |
| **W5 Alto impacto** | cada hora | filtro por palabras clave → A11 | El filtro corre **antes** de llamar a la IA: no se gasta cuota en horas tranquilas |
| **W6 Agenda semanal** | semanal | A1 → A4 → A5 | Ritmo distinto, riesgo distinto |
| **W0 Centinela** | cada hora | A12 | Si W1–W6 no corrió, avisa. El fallo silencioso es el peor fallo |

Un flujo por candidato en W2 es la ventaja concreta de n8n sobre un script: el
manejo de error por ítem sale gratis, y eso es exactamente el principio de
**degradación suave** que ya rige los dos sistemas en producción.

### La frontera, escrita

n8n **nunca** calcula una cifra, ni parsea una fuente, ni renderiza una lámina.
Llama a herramientas Python que hacen eso y devuelven JSON. Motivo: el Python
actual encodea arreglos que costaron caro —que el `previousClose` de Yahoo
viene vacío y hay que sacarlo de la serie diaria, que la sorpresa de EPS exige
cruzar dos endpoints de Nasdaq, que la SEC bloquea sin User-Agent identificado,
que feedparser no trae timeout y cuelga el job 15 minutos—. Reescribir eso en
nodos reintroduce todos esos errores.

El nodo de código de n8n corre JavaScript y un Python limitado sin librerías
pip normales, así que la frontera además es técnica, no solo de criterio.

**Riesgo de esta frontera:** acabar con lógica en dos sitios y que nadie sepa
dónde vive qué. Por eso está escrita aquí y no queda como hábito.

---

## 4. Modelos: dónde vale pagar

Hoy la cadena es `gemini-2.5-flash-lite` → `gemini-2.5-flash` → `groq
llama-3.3-70b`, elegida por cuota gratuita. Para el medio conviene separar:

| Agente | Recomendación |
|---|---|
| **A5 Redactor** | Modelo capaz de pago. Es donde la calidad **es** el producto, y son pocas llamadas al día. Un texto mediocre en un medio que aspira a ser referente cuesta más que la suscripción |
| **A6 Clasificador**, **A2 dedup** | Modelo económico. La tarea es mecánica y la salida está cerrada |
| **A9 Traductor** | Modelo capaz. Una traducción que decide sentido es un error publicado |
| **A11 Alto impacto** | Económico, y solo después del filtro por palabras clave |

Se mantiene la cadena de respaldo en todos: si el modelo cae, sale el hecho con
su fuente y sin lectura. Nunca se rellena inventando.

---

## 5. Decisiones que faltan antes de construir

1. **Taxonomía de temas y países** — cerrarla antes de A6. Cambiarla después
   obliga a reclasificar el archivo.
2. **Especificación de la API de carga del panel** (Alalza, OCT-1) — se puede
   construir contra archivo y conectar después, pero hay que saber qué campos
   acepta.
3. **Umbral de alto impacto** para A11: qué justifica interrumpir el ciclo.
4. **Lista blanca de fuentes** — es una decisión editorial, no técnica.
5. **Variante estricta de marcadores en A5**: ¿en qué bloques se aplica?
