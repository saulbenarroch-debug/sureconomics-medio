r"""Sube borradores al panel por la API, sin navegador.

    .pyruntime\python.exe subir.py carga-28.json

POR QUE NO POR EL NAVEGADOR

Porque el navegador es la parte fragil. Los dias 26 y 28 de agosto de 2026 se
perdieron cuerpos enteros por lo mismo: rellenar el formulario antes de que el
editor terminara de montarse. El 28, ademas, un guardado disparado a los 2,2
segundos de cargar la pagina vacio el resumen y borro el primer parrafo de un
articulo YA PUBLICADO, incluida la linea que declaraba que lo habia redactado
una IA. Se reparo, pero el fallo no fue del operador: fue de la via.

La API no tiene ese problema. No hay editor que montar ni carrera contra el
reloj: es un POST con un JSON y una respuesta que dice si entro o no.

LO QUE ESTE ARCHIVO NO HACE, A PROPOSITO

No publica. `status` va fijo en "draft" y no hay bandera para cambiarlo. Un
robot que puede publicar solo es un robot que un dia publica algo que nadie
leyo. Publicar es un acto editorial y lo hace una persona, desde el panel.

Tampoco sube piezas que el auditor bloqueo. Esas van al correo para que las
mire alguien.

CREDENCIALES

Se leen del entorno, nunca de aqui:

    SURECONOMICS_API      base de la API
    SURECONOMICS_USUARIO  correo de la cuenta de servicio del panel
    SURECONOMICS_CLAVE    su contraseña

La cuenta debe ser PROPIA DEL ROBOT, no la de una persona. El servidor atribuye
cada pieza a la cuenta que la crea: con la cuenta de un humano, el registro
miente sobre quien escribio que, y no se le puede cortar el acceso al robot sin
cortarselo tambien a esa persona.
"""

import io
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Se carga el .env aunque llamado desde orquestar.py o nota.py las variables ya
# vengan heredadas: la cabecera de este archivo documenta ejecutarlo suelto, y
# suelto no las tenia. En Actions el archivo no existe y load_dotenv no hace
# nada, que es justo lo que se quiere: alli llegan del entorno.
try:
    from dotenv import load_dotenv

    load_dotenv(r"C:\Users\saulb\telegram-finance-bot\.env")
except Exception:  # noqa: BLE001
    pass

BASE = os.environ.get("SURECONOMICS_API",
                      "https://sureconomics-backend.onrender.com").rstrip("/")

# Con la E alta, que es la grafia de la marca. Ver crear_borrador().
FIRMA_REDACCION = "Redacción SurEconomics"


class Panel:
    """Sesion contra el panel. Entra con usuario y contraseña, no con un token.

    ESTE BACKEND NO DA TOKENS FIJOS. Se comprobo contra la API el 02/09/2026:
    solo existe POST /auth/login con {email, password}, que devuelve un token de
    acceso de vida corta, y POST /auth/refresh para renovarlo. Es lo mismo que
    hace el panel en el navegador, donde el token caduca en una hora.

    La version anterior esperaba un SURECONOMICS_TOKEN fijo que no existe en
    ninguna parte, asi que nunca habria funcionado.

    LO QUE HACE FALTA ES UNA CUENTA DE SERVICIO, no la de una persona: el
    servidor atribuye cada pieza a la cuenta que la crea, y con la sesion de
    alguien del equipo todo sale firmado por esa persona.

    Y NO, NO SIRVE EL JWT_SECRET_KEY del servidor. Esa es la clave con la que el
    backend FIRMA los tokens: con ella se puede fabricar un token de cualquier
    usuario sin contraseña. Es la llave maestra y no sale del servidor.
    """

    def __init__(self, usuario=None, clave=None):
        self.usuario = (usuario or os.environ.get("SURECONOMICS_USUARIO", "")).strip()
        self.clave = clave or os.environ.get("SURECONOMICS_CLAVE", "")
        if not self.usuario or not self.clave:
            raise SystemExit(
                "Faltan SURECONOMICS_USUARIO y SURECONOMICS_CLAVE, que son el "
                "correo y la contraseña de la cuenta de servicio del panel. "
                "No los escribas en el codigo ni los pegues en un chat: van "
                "como secretos del entorno.")
        self.token = None
        self.refresco = None
        self._temas = None
        self._lugares = None
        self.entrar()

    def _crudo(self, ruta, metodo="GET", cuerpo=None, con_token=True):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        cabeceras = {"Content-Type": "application/json"}
        if con_token and self.token:
            cabeceras["Authorization"] = "Bearer " + self.token
        peticion = urllib.request.Request(BASE + ruta, data=datos,
                                          method=metodo, headers=cabeceras)
        with urllib.request.urlopen(peticion, timeout=60) as r:
            return json.loads(r.read().decode() or "{}")

    def entrar(self):
        """Abre sesion. Devuelve el nombre con el que quedaran firmadas."""
        try:
            r = self._crudo("/auth/login", "POST",
                            {"email": self.usuario, "password": self.clave},
                            con_token=False)
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 422):
                raise SystemExit(
                    "El panel rechazo las credenciales de la cuenta de "
                    "servicio (%s). Revisa correo y contraseña." % e.code)
            raise SystemExit("No pude entrar al panel: HTTP %s" % e.code)
        d = r.get("data", r)
        self.token = d.get("access_token") or d.get("token")
        self.refresco = d.get("refresh_token")
        if not self.token:
            raise SystemExit("El login respondio sin token: %s" % str(r)[:200])
        quien = (d.get("user") or {}).get("email", self.usuario)
        print("  [panel] sesion abierta como %s" % quien)
        return quien

    def _llamar(self, ruta, metodo="GET", cuerpo=None, reintento=True):
        try:
            return self._crudo(ruta, metodo, cuerpo)
        except urllib.error.HTTPError as e:
            detalle = e.read().decode()[:300]
            # UN 401 A MITAD DE CORRIDA NO ES UN FALLO, ES EL TOKEN CADUCANDO.
            # Duran una hora y una tanda de seis piezas puede pasarse. Se
            # renueva y se reintenta UNA vez; si vuelve a fallar, es de verdad.
            if e.code == 401 and reintento:
                print("  [panel] el token caduco, renuevo y reintento")
                self.entrar()
                return self._llamar(ruta, metodo, cuerpo, reintento=False)
            if e.code == 401:
                raise SystemExit(
                    "401 despues de renovar la sesion. La cuenta de servicio "
                    "puede no tener permiso de edicion.")
            if e.code == 403:
                raise SystemExit(
                    "403: la cuenta de servicio entro pero no tiene permiso "
                    "para esto. Necesita rol de editor o administrador.")
            raise SystemExit("HTTP %s en %s %s: %s" % (e.code, metodo, ruta, detalle))

    @staticmethod
    def _lista(respuesta):
        """La API a veces envuelve en {'data': [...]} y a veces no."""
        if isinstance(respuesta, dict):
            return respuesta.get("data") or respuesta.get("items") or []
        return respuesta or []

    def _catalogo(self, ruta):
        return {t["name"]: t["id"] for t in self._lista(self._llamar(ruta))
                if isinstance(t, dict) and "name" in t and "id" in t}

    def temas(self):
        if self._temas is None:
            self._temas = self._catalogo("/admin/topics")
        return self._temas

    def lugares(self):
        if self._lugares is None:
            self._lugares = self._catalogo("/admin/places")
        return self._lugares

    def imagen_externa(self, url):
        """Registra una imagen por enlace y devuelve su id.

        El panel llama a esto "adjuntar por direccion" y guarda storage
        "external": el sitio NO se descarga la imagen, la enlaza. Si Wikimedia
        cambia la ruta, la foto desaparece de la pieza. Esta apuntado como
        arreglo pendiente del CMS.

        LA RUTA ES /admin/media/external, NO /admin/assets. La segunda me la
        habia inventado por deduccion a partir del campo image_asset_id que
        devuelve la ficha de una pieza, y falla de la peor manera: el navegador
        la rechaza por CORS antes de que haya codigo de respuesta, asi que no da
        404 sino "Failed to fetch", que parece un fallo de red. Se descubrio el
        31/08/2026 escuchando lo que hace el propio panel al pulsar ADJUNTAR.
        """
        r = self._llamar("/admin/media/external", "POST",
                         {"kind": "image", "url": url})
        d = r.get("data", r)
        return d.get("id")

    def crear_borrador(self, pieza):
        temas, lugares = self.temas(), self.lugares()

        faltan = [t for t in pieza["temas"] if t not in temas]
        faltan += [l for l in pieza["lugares"] if l not in lugares]
        if faltan:
            return {"ok": False, "motivo": "no existen en el panel: %s" % ", ".join(faltan)}

        cuerpo = {
            "format": pieza["formato"],
            "title": pieza["titulo"],
            "excerpt": pieza["resumen_html"],
            "content": pieza["cuerpo_html"],
            # LO QUE ESCRIBE EL MOTOR VA FIRMADO POR LA REDACCION. Decision del
            # dueño el 01/09/2026. Hasta hoy subia con la firma vacia y el sitio
            # mostraba la pieza sin autor: catorce quedaron asi y hubo que
            # firmarlas a mano una por una.
            #
            # Se respeta la firma que traiga la pieza, que es como se acredita a
            # una persona: el articulo #389 lleva la de Óscar Doval porque el
            # analisis es suyo. Solo se rellena cuando viene vacia.
            #
            # La E va alta. Convivian "Redacción SurEconomics", "Redacción
            # Sureconomics" y "Equipo de Redacción Sureconomics" en el mismo
            # sitio; se unificaron las 150 ese dia.
            "byline": pieza.get("firma") or FIRMA_REDACCION,
            # La API pide {name, url} en ingles y nuestra carga los guarda como
            # {nombre, url}. Enviarlos en español devuelve un 422 con
            # "Missing data for required field" por cada fuente. Se descubrio
            # subiendo a mano el 31/08/2026; la primera corrida automatica
            # habria fallado igual y sin nadie mirando.
            "sources": [{"name": f.get("nombre") or f.get("name") or "",
                         "url": f.get("url") or ""}
                        for f in (pieza.get("fuentes") or [])],
            "topic_ids": [temas[t] for t in pieza["temas"]],
            "place_ids": [lugares[l] for l in pieza["lugares"]],
            # Fijo. Ver la cabecera de este archivo.
            "status": "draft",
        }
        if pieza.get("foto"):
            ident = self.imagen_externa(pieza["foto"])
            if ident:
                cuerpo["image_asset_id"] = ident

        creada = self._llamar("/admin/posts", "POST", cuerpo)
        d = creada.get("data", creada)
        ident = d.get("id")
        if not ident:
            return {"ok": False, "motivo": "el servidor no devolvio id"}

        # Leer de vuelta NO es opcional. Es la comprobacion que faltaba el 26 de
        # agosto, cuando nueve piezas se dieron por subidas y estaban vacias.
        guardada = self._llamar("/admin/posts/%s" % ident)
        g = guardada.get("data", guardada)
        sin_marcas = lambda h: len(_texto(h or ""))
        return {
            "ok": (sin_marcas(g.get("content")) == sin_marcas(pieza["cuerpo_html"])
                   and g.get("title") == pieza["titulo"]
                   and g.get("status") == "draft"),
            "id": ident,
            "estado": g.get("status"),
            "cuerpo_guardado": sin_marcas(g.get("content")),
            "cuerpo_enviado": sin_marcas(pieza["cuerpo_html"]),
        }


def _texto(html):
    import re
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    carga = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    panel = Panel()

    # SUBIR LAS BLOQUEADAS ES UNA DECISION, NO EL COMPORTAMIENTO POR DEFECTO.
    # El dueño lo pidio el 02/09/2026: prefiere tenerlas en el panel y
    # arreglarlas ahi antes que no tener nada. Va bien, pero una pieza bloqueada
    # es una en la que alguna cifra del texto NO se pudo rastrear al expediente,
    # asi que no puede llegar al panel con el mismo aspecto que las demas: se le
    # mete un aviso al principio del cuerpo, donde lo ve quien la abra.
    forzar = "--subir-bloqueadas" in sys.argv

    subidas, fallos = 0, []
    for pieza in carga:
        if pieza.get("bloqueada"):
            if not forzar:
                fallos.append((pieza["titulo"][:50],
                               "bloqueada por el auditor, no se sube"))
                continue
            motivos = " ".join(str(m) for m in (pieza.get("hallazgos") or []))
            pieza = dict(pieza)
            pieza["cuerpo_html"] = (
                '<p><strong>⚠️ EL AUDITOR BLOQUEÓ ESTA PIEZA. No publicar sin '
                "revisarla.</strong> Alguna cifra o cita del texto no se pudo "
                "comprobar contra la fuente. Sube al panel a petición de la "
                "redacción, para editarla aquí." +
                ("<br><em>" + motivos[:400] + "</em>" if motivos else "") +
                "</p>" + pieza.get("cuerpo_html", ""))
            print("  [aviso] %s va BLOQUEADA y marcada" % pieza["titulo"][:44])
        r = panel.crear_borrador(pieza)
        if r.get("ok"):
            subidas += 1
            print("  OK   #%s  %s" % (r["id"], pieza["titulo"][:58]))
        else:
            motivo = r.get("motivo") or ("cuerpo %s de %s" % (
                r.get("cuerpo_guardado"), r.get("cuerpo_enviado")))
            fallos.append((pieza["titulo"][:50], motivo))
            print("  MAL  %s :: %s" % (pieza["titulo"][:48], motivo))

    print("\n%d subidas, %d con problema" % (subidas, len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
