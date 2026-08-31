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
    SURECONOMICS_TOKEN    token de la cuenta de servicio

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

BASE = os.environ.get("SURECONOMICS_API",
                      "https://sureconomics-backend.onrender.com").rstrip("/")


class Panel:
    def __init__(self, token):
        if not token:
            raise SystemExit(
                "Falta SURECONOMICS_TOKEN. No lo escribas en el codigo ni lo "
                "pegues en un chat: va como secreto del entorno.")
        self.token = token
        self._temas = None
        self._lugares = None

    def _llamar(self, ruta, metodo="GET", cuerpo=None):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        peticion = urllib.request.Request(
            BASE + ruta, data=datos, method=metodo,
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=60) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            detalle = e.read().decode()[:300]
            if e.code == 401:
                raise SystemExit(
                    "401: el token no vale o caduco. Los tokens de sesion del "
                    "panel duran horas; para un robot hace falta una cuenta de "
                    "servicio con credencial larga.")
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
        """
        r = self._llamar("/admin/assets", "POST", {"kind": "image", "url": url})
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
            "byline": pieza.get("firma") or "",
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
    panel = Panel(os.environ.get("SURECONOMICS_TOKEN", "").strip())

    subidas, fallos = 0, []
    for pieza in carga:
        if pieza.get("bloqueada"):
            fallos.append((pieza["titulo"][:50], "bloqueada por el auditor, no se sube"))
            continue
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
