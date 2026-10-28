import hmac
import json
import os
import subprocess
import sys
import threading
import time
import uuid

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent.parent
SCRIPT_VALIDACION = (
    PROYECTO / "python" / "03_validar_integridad.py"
)

SCRIPT_PROCESAMIENTO = (
    PROYECTO / "python" / "15_procesar_y_publicar.py"
)

CARPETA_EJECUCIONES = PROYECTO / "logs" / "executions"

TOKEN = os.environ.get("PORTFOLIO_API_TOKEN", "")

# Escucha en las interfaces del equipo para permitir
# la conexión desde Docker Desktop.
HOST = "0.0.0.0"
PUERTO = 8765

BLOQUEO = threading.Lock()


class Servicio(BaseHTTPRequestHandler):
    def responder(self, codigo, contenido):
        datos = json.dumps(
            contenido, ensure_ascii=False
        ).encode("utf-8")

        self.send_response(codigo)
        self.send_header(
            "Content-Type", "application/json; charset=utf-8"
        )
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def autorizado(self):
        recibido = self.headers.get("X-Portfolio-Token", "")

        if not hmac.compare_digest(
            recibido.encode("utf-8"),
            TOKEN.encode("utf-8"),
        ):
            self.responder(
                401,
                {"success": False, "error": "No autorizado"},
            )
            return False

        return True

    def do_GET(self):
        if not self.autorizado():
            return

        if self.path != "/health":
            self.responder(404, {"error": "Ruta inexistente"})
            return

        self.responder(200, {
            "success": True,
            "service": "PortfolioPedidos",
            "mode": "process_and_publish",
            "busy": BLOQUEO.locked(),
        })

    def do_POST(self):
        if not self.autorizado():
            return

        if self.path not in {"/validate", "/process"}:
            self.responder(404, {"error": "Ruta inexistente"})
            return

        # No acepta scripts, rutas ni comandos enviados
        # por el cliente. Solo ejecuta la operación fija.
        try:
            longitud = int(
                self.headers.get("Content-Length", "0")
            )

            if longitud < 0 or longitud > 1024:
                raise ValueError("Tamaño de solicitud inválido")

            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Transferencia no admitida")

            contenido = self.rfile.read(longitud)

            if contenido and json.loads(contenido) != {}:
                raise ValueError(
                    "Esta operación solo admite un objeto vacío"
                )

        except (ValueError, json.JSONDecodeError):
            self.responder(
                400,
                {"error": "Enviar sin cuerpo o con JSON {}"},
            )
            return

        if not BLOQUEO.acquire(blocking=False):
            self.responder(
                409,
                {"error": "Ya hay una operación en curso"},
            )
            return

        ejecucion_id = uuid.uuid4().hex
        inicio = time.monotonic()

        resultado = {
            "execution_id": ejecucion_id,
            "operation": (
            "process" if self.path == "/process" else "validate"
            ),
            "started_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "success": False,
        }

        codigo_http = 500

        try:

            script = (
                SCRIPT_PROCESAMIENTO
                if self.path == "/process"
                else SCRIPT_VALIDACION
            )

            proceso = subprocess.run(
                [sys.executable, str(script)],
                cwd=PROYECTO,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8",
                },
            )

            if self.path == "/process":
                try:
                    resultado["pipeline"] = json.loads(
                        proceso.stdout
                    )
                except json.JSONDecodeError:
                    resultado["pipeline"] = {
                        "error": (
                            "El coordinador no devolvió "
                            "un JSON válido"
                        )
                    }

            resultado.update({
                "success": proceso.returncode == 0,
                "return_code": proceso.returncode,
                "stdout": proceso.stdout,
                "stderr": proceso.stderr,
            })

            codigo_http = (
                200 if proceso.returncode == 0 else 422
            )

        except subprocess.TimeoutExpired:
            resultado["error"] = (
                "La operación superó los 600 segundos"
            )
            codigo_http = 504

        except Exception as error:
            resultado["error"] = str(error)

        finally:
            resultado["duration_seconds"] = round(
                time.monotonic() - inicio, 3
            )

            try:
                ruta = (
                    CARPETA_EJECUCIONES
                    / f"{ejecucion_id}.json"
                )

                ruta.write_text(
                    json.dumps(
                        resultado,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            except OSError:
                resultado["success"] = False
                resultado["error"] = (
                    "No se pudo guardar el registro de ejecución"
                )
                codigo_http = 500

            BLOQUEO.release()

        # La respuesta contiene el resumen.
        # El detalle queda en el registro local.
        self.responder(codigo_http, {
            clave: valor
            for clave, valor in resultado.items()
            if clave not in {"stdout", "stderr"}
        })


def main():
    if len(TOKEN) < 32:
        raise SystemExit(
            "Falta PORTFOLIO_API_TOKEN o es demasiado corto."
        )

    for script in [
        SCRIPT_VALIDACION,
        SCRIPT_PROCESAMIENTO,
    ]:
        if not script.is_file():
            raise SystemExit(
                f"No se encuentra el archivo: {script.name}"
            )

    CARPETA_EJECUCIONES.mkdir(
        parents=True, exist_ok=True
    )

    servidor = ThreadingHTTPServer(
        (HOST, PUERTO), Servicio
    )

    print(f"Servicio disponible en el puerto {PUERTO}")
    print("Modo: validación y procesamiento con publicación SQL")
    print("Mantén esta terminal abierta.")
    print("Para detenerlo: Ctrl + C")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServicio detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()




