"""El paquete de datos: el contrato entre el extractor y todo lo demas.

Es la "caja cerrada de ingredientes". El redactor (A5) solo puede usar cifras
que esten aqui, y el auditor (A8) compara el texto final contra este paquete.
Si un numero aparece en la prosa y no esta en la caja, la pieza se bloquea.

Por eso el formato de las cifras se decide AQUI y no en el prompt: un modelo
cumple las normas de formato casi siempre, y "casi" no sirve. La cifra sale de
esta capa ya escrita como se publica.
"""

import json
from dataclasses import dataclass, field, asdict, replace
from urllib.parse import urlparse


def formato_es(valor, decimales=1):
    """Formatea un numero con la norma del medio: coma decimal, punto de miles.

    1234567.89 -> '1.234.567,9'
    """
    crudo = f"{valor:,.{decimales}f}"  # formato ingles: 1,234,567.9
    # Intercambio en tres pasos usando un caracter puente, porque hacerlo en dos
    # convierte las comas recien puestas en puntos otra vez.
    return crudo.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def magnitud_es(valor, moneda="USD"):
    """Expresa una magnitud grande con la escala correcta EN ESPAÑOL.

    Existe para hacer imposible el error mas caro de todos: escribir "trillones"
    traduciendo 'trillion'. En español billon = 10^12 y trillon = 10^18, asi que
    ese calco equivoca la cifra por un factor de un millon. Aparecio en el
    editorial del 24 de agosto ("35 trillones de deuda"), y de ahi esta funcion.
    """
    nombre = {"USD": "dólares", "EUR": "euros"}.get(moneda, moneda)
    v = abs(valor)
    if v >= 1e12:
        return f"{formato_es(valor / 1e12, 2)} billones de {nombre}"
    # Entre mil millones y un billon NO se escribe "miles de millones": la prensa
    # en español dice "21.600 millones de dolares", que es como lo lee cualquiera.
    # La primera version decia "21,6 miles de millones de USD" y sonaba a traduccion.
    if v >= 1e6:
        return f"{formato_es(valor / 1e6, 0)} millones de {nombre}"
    return f"{formato_es(valor, 2)} {nombre}"


@dataclass
class Fuente:
    """Un documento concreto y comprobable. Nunca la portada de una institucion."""

    id: str
    institucion: str
    documento: str
    url: str
    url_datos: str = ""  # llamada exacta que produjo la cifra, para reauditar
    # Excepcion consciente para instituciones que publican EN su portada y no
    # tienen enlace permanente. El caso real es el BCV: la tasa oficial del dia
    # vive en bcv.org.ve y en ningun otro sitio. Se marca a mano, fuente por
    # fuente, para que siga siendo una excepcion y no un agujero.
    portada_es_la_fuente: bool = False

    def problemas(self):
        p = []
        partes = urlparse(self.url)
        if partes.scheme not in ("http", "https"):
            p.append(f"fuente {self.id}: url invalida")
        # Una portada no verifica nada. De 256 enlaces del plan semanal del jefe,
        # 233 eran la raiz del dominio: cumplian la letra de la norma sin cumplir
        # su proposito. Aqui se rechaza por construccion.
        elif (partes.path.strip("/") == "" and not partes.query
              and not self.portada_es_la_fuente):
            p.append(f"fuente {self.id}: es la portada de {partes.netloc}, "
                     "no un documento")
        if "sureconomics" in partes.netloc:
            p.append(f"fuente {self.id}: SurEconomics no puede citarse a si mismo")
        return p


@dataclass
class Cifra:
    """Un numero con todo lo que hace falta para publicarlo sin mentir."""

    clave: str        # como la llama el redactor: 'inflacion_2016'
    valor: str        # ya formateado en español: '254,9'
    unidad: str       # '%', 'USD', 'personas'
    periodo: str      # '2016', 'julio 2026', 'al cierre del 12/08/2026'
    fuente_id: str
    valor_crudo: float = None  # el numero sin formatear, para que A8 recalcule
    nota: str = ""
    # 'hecho' = la cifra de la noticia. 'contexto' = la que aporta el medio para
    # dar fondo. La distincion importa: el hecho se atribuye a quien lo publico,
    # el contexto es trabajo nuestro y va con su propia fuente.
    rol: str = "hecho"


@dataclass
class Paquete:
    """Todo lo que el redactor puede usar. Nada mas."""

    hecho: str
    fecha_hecho: str
    # LA HORA, APARTE DE LA FECHA, Y SOLO PARA ORDENAR POR FRESCURA.
    #
    # fecha_hecho se queda en AAAA-MM-DD porque es lo que se escribe en la pieza
    # ("Sacado de: El Nacional, 2026-09-18") y lo que mira el auditor; meterle
    # una hora cambiaria las dos cosas de paso.
    #
    # Pero la hora hace falta y se estaba tirando: los feeds la traen SIEMPRE
    # -comprobado el 18/09/2026 sobre 106 candidatas de 22 medios, cero sin
    # hora- y el recolector se quedaba solo con el dia. Con eso, una noticia de
    # hace diez minutos y otra de hace veintitres horas puntuaban IGUAL, porque
    # criterio.puntuar medía la frescura en dias. Un medio no puede dar
    # inmediatez si descarta la hora antes de decidir.
    #
    # Va vacio cuando la fuente no la da (una captura, un post sin fecha): ahi
    # se sigue puntuando por dias, como siempre.
    momento: str = ""
    cifras: list = field(default_factory=list)
    citas: list = field(default_factory=list)
    entidades: list = field(default_factory=list)
    fuentes: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)

    def validar(self):
        """Devuelve la lista de problemas. Vacia = el paquete puede usarse.

        Se valida ANTES de gastar una llamada a la IA: redactar sobre un paquete
        roto es tirar cuota y tiempo.
        """
        problemas = []
        ids = {f.id for f in self.fuentes}

        if not self.hecho.strip():
            problemas.append("el paquete no dice que paso")
        if not self.fuentes:
            problemas.append("no hay ninguna fuente")

        for f in self.fuentes:
            problemas.extend(f.problemas())

        for c in self.cifras:
            if c.fuente_id not in ids:
                problemas.append(f"cifra '{c.clave}': la fuente "
                                 f"'{c.fuente_id}' no existe en el paquete")
            if not c.periodo:
                problemas.append(f"cifra '{c.clave}': sin periodo. Una cifra sin "
                                 "periodo no se puede publicar")
            if not c.unidad:
                problemas.append(f"cifra '{c.clave}': sin unidad")

        claves = [c.clave for c in self.cifras]
        for k in set(claves):
            if claves.count(k) > 1:
                problemas.append(f"clave repetida: '{k}'")

        return problemas

    def avisos_de_formato(self):
        """Detecta cifras que SE VEN iguales pero no lo son.

        Al redondear para publicar (1.832.641 millones y 1.830.489 millones dan
        los dos '1,83 billones'), dos años distintos pueden quedar identicos en
        pantalla. Un redactor que lo lea asi escribe "se mantuvo igual", que es
        una afirmacion que el dato crudo no sostiene. Se avisa en vez de callar.
        """
        avisos = []
        por_valor = {}
        for c in self.cifras:
            por_valor.setdefault(c.valor, []).append(c)
        for valor, grupo in por_valor.items():
            if len(grupo) < 2:
                continue
            crudos = {c.valor_crudo for c in grupo if c.valor_crudo is not None}
            if len(crudos) > 1:
                claves = ", ".join(c.clave for c in grupo)
                avisos.append(
                    f"{claves} se muestran igual ('{valor}') pero los valores "
                    f"reales difieren. No escribas que son iguales: usa "
                    f"'valor_crudo' si necesitas compararlos."
                )
        return avisos

    def a_json(self, indent=2):
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent)


def componer(principal, *contextos):
    """Funde un paquete de noticia con paquetes de contexto en uno solo.

    Es la respuesta a "la nota queda muy pelada". Un RSS entrega un titular y dos
    frases; con eso no hay pieza que valga. El fondo lo pone el medio: la serie
    de inflacion, el PIB, la comparacion con la region. Eso es lo que el diario
    original NO trae, y es la razon por la que alguien nos leeria a nosotros.

    El primero es la noticia y da el 'hecho'. Los demas entran como contexto, con
    sus cifras marcadas rol='contexto' y su propia fuente: el contexto tambien se
    cita, no se afirma porque si.
    """
    if principal is None:
        return None
    vivos = [c for c in contextos if c is not None]

    cifras = list(principal.cifras)
    fuentes = list(principal.fuentes)
    citas = list(principal.citas)
    entidades = list(principal.entidades)
    advertencias = list(principal.advertencias)
    ids = {f.id for f in fuentes}

    for i, ctx in enumerate(vivos, start=1):
        # Los ids de fuente pueden chocar (dos extractores usando 'bm1'), y una
        # cifra apuntando a la fuente equivocada es una atribucion falsa.
        mapa = {}
        for f in ctx.fuentes:
            nuevo, n = f.id, 1
            while nuevo in ids:
                n += 1
                nuevo = f"{f.id}_{n}"
            ids.add(nuevo)
            mapa[f.id] = nuevo
            fuentes.append(replace(f, id=nuevo))

        claves = {c.clave for c in cifras}
        for c in ctx.cifras:
            # Se busca un nombre libre de verdad, no solo se pone el prefijo. El
            # contador `i` se reinicia en cada llamada a componer(), y como la
            # cadena compone dos veces -el expediente del documentalista primero
            # y el contexto del economista despues- la segunda vuelta generaba
            # otra vez 'ctx1_cifra_1' y el paquete quedaba invalido.
            clave = c.clave
            sufijo = i
            while clave in claves:
                clave = f"ctx{sufijo}_{c.clave}"
                sufijo += 1
            claves.add(clave)
            cifras.append(replace(
                c, clave=clave, rol="contexto",
                fuente_id=mapa.get(c.fuente_id, c.fuente_id),
                nota=(c.nota + " " if c.nota else "") + "(contexto que aporta el medio)"))

        citas += ctx.citas
        entidades += [e for e in ctx.entidades if e not in entidades]
        advertencias += [a for a in ctx.advertencias if a not in advertencias]

    return Paquete(
        hecho=principal.hecho,
        fecha_hecho=principal.fecha_hecho,
        cifras=cifras,
        citas=citas,
        entidades=entidades,
        fuentes=fuentes,
        advertencias=advertencias,
    )
