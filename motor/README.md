# El motor — A4, el extractor

El extractor va a la fuente oficial, trae los números y arma el **paquete de
datos**: la caja cerrada de ingredientes con la que después se redacta. No
escribe prosa. No opina. Solo trae cifras con su origen.

Es la primera pieza porque todo lo demás depende de ella: el redactor solo puede
usar cifras del paquete, y el auditor compara el texto final contra el paquete.
Sin paquete, no hay contra qué comparar.

## Cómo se corre

Con el Python portátil de Sureconomics (no hay Python global en esta máquina):

```bash
C:\Users\saulb\telegram-finance-bot\.pyruntime\python.exe motor/extraer.py --pais VEN --indicador inflacion
```

Otros ejemplos:

```bash
motor/extraer.py --pais MEX --indicador pib --observaciones 5
motor/extraer.py --pais COL --indicador desempleo --guardar paquetes/
```

Las pruebas de los frenos de seguridad:

```bash
C:\Users\saulb\telegram-finance-bot\.pyruntime\python.exe pruebas_paquete.py
```

## Qué hay

| Archivo | Qué hace |
|---|---|
| `paquete.py` | El contrato: qué es una cifra, qué es una fuente, y qué se rechaza |
| `fuentes/banco_mundial.py` | Extractor de cifras oficiales: Banco Mundial, gratis y sin clave |
| `fuentes/noticias.py` | Extractor de noticieros por RSS. **Fuente secundaria** |
| `auditor.py` | A8: compara la pieza redactada contra el paquete |
| `extraer.py` | Línea de comandos |

## Dos clases de fuente, y no se mezclan

| | Banco Mundial | Noticieros (RSS) |
|---|---|---|
| Qué es | fuente **primaria** | fuente **secundaria** |
| La cifra la produjo | la institución | un periodista |
| Se puede publicar como propia | sí | **no**, hay que confirmarla |
| Sirve para | contexto, educación, investigación | contar el hecho citando al medio |

El extractor de noticias marca cada cifra con `CITADA POR UN MEDIO, NO
VERIFICADA EN FUENTE PRIMARIA` y el auditor lo eleva como aviso al editor. No es
burocracia: si publicamos como nuestro un número que escribió otro y sale mal,
el error es nuestro.

## El auditor: qué bloquea y qué no

**Bloquea** (comprobable sin opinar): una cifra que no está en el paquete · un
decimal con punto · la palabra "trillón" · una sigla mal escrita · un enlace que
no viene del paquete · la autocita · una etiqueta que no existe · una noticia
sin bloque `SurEconomics:` · una opinión sin autor · un dato viejo cuyo año no
aparece en el texto · un enlace redirector de Google News.

**Avisa, no bloquea** (necesita criterio humano): que el cuerpo de una noticia
no lleve postura, y que el titular no afirme más de lo que el cuerpo sostiene.
Convertir eso en bloqueo daría falsos positivos, y un auditor que da falsos
positivos se desactiva a la semana — y entonces no audita nada.

## Los frenos que trae

- **Nunca inventa.** Si la fuente no responde, no sale paquete y no hay nada que
  redactar. No hay camino en el que se produzca un número sin origen.
- **Formato español garantizado en código**, no pedido a un modelo: coma
  decimal, punto de miles, y `billón = 10¹²`. La palabra "trillón" no puede
  salir de aquí.
- **Rechaza la portada de una institución como fuente.** `cepal.org` no
  verifica nada; el informe con su ruta sí. En el plan semanal de agosto, 233 de
  256 enlaces eran portadas.
- **Rechaza que SurEconomics se cite a sí mismo.**
- **Avisa cuando el dato es viejo.** La última inflación de Venezuela que
  publica el Banco Mundial es de 2016: el paquete obliga a decir el año.
- **Avisa cuando dos cifras distintas se ven iguales** al redondear, para que
  nadie escriba "se mantuvo igual" sin que el dato lo sostenga.

## Limitación del Banco Mundial

Publica series **anuales y con retraso**. Sirve para contexto, educación e
investigación —lo que el perfil editorial etiqueta como `Permanente`, que es
justo lo que llena el pool base—. **No sirve para una noticia de hoy.** Para eso
hacen falta extractores de bancos centrales e institutos de estadística, que es
el siguiente paso.
