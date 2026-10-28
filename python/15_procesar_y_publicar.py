import json
import os
import subprocess
import sys
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent.parent


def ejecutar_script(nombre, argumentos=None, timeout=240):
    ruta = PROYECTO / "python" / nombre

    if not ruta.is_file():
        raise ValueError(f"No se encuentra {nombre}")

    proceso = subprocess.run(
        [
            sys.executable,
            str(ruta),
            *(argumentos or []),
        ],
        cwd=PROYECTO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env={
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
        },
    )

    try:
        respuesta = json.loads(proceso.stdout)
    except json.JSONDecodeError:
        raise ValueError(
            f"{nombre} no devolvió JSON válido. "
            f"Detalle: {proceso.stderr[-2000:]}"
        )

    if proceso.returncode != 0 or respuesta.get("success") is not True:
        raise ValueError(
            f"{nombre} falló: "
            f"{respuesta.get('error', 'Revisar el registro de ejecución')}"
        )

    return respuesta


def main():
    inicio = time.monotonic()
    carpeta_lote = None

    resultado = {
        "pipeline_execution_id": uuid.uuid4().hex,
        "started_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "success": False,
        "status": "INICIADO",
        "sql_updated": False,
        "publication_confirmed": False,
    }

    try:
        # Comprobar credenciales antes de procesar.
        if not os.environ.get("PORTFOLIO_SQL_USER"):
            raise ValueError("Falta PORTFOLIO_SQL_USER.")

        if not os.environ.get("PORTFOLIO_SQL_PASSWORD"):
            raise ValueError("Falta PORTFOLIO_SQL_PASSWORD.")

        procesamiento = ejecutar_script(
            "13_procesar_lote.py",
            timeout=180,
        )

        batch_id = procesamiento["batch_id"]

        # El identificador se utilizará como nombre de carpeta.
        if (
            len(batch_id) != 32
            or any(c not in "0123456789abcdef" for c in batch_id)
        ):
            raise ValueError("Identificador de lote inválido.")

        carpeta_lote = (
            PROYECTO / "data" / "runs" / batch_id
        )

        resultado.update({
            "batch_id": batch_id,
            "output_directory": procesamiento["output_directory"],
            "summary": procesamiento["summary"],
            "processing_success": True,
        })

        publicacion = ejecutar_script(
            "14_publicar_lote_sql.py",
            argumentos=["--batch", batch_id],
            timeout=240,
        )

        if publicacion["status"] not in {
            "PUBLICADO", "YA_PUBLICADO"
        }:
            raise ValueError(
                "El publicador devolvió un estado desconocido."
            )

        resultado.update({
            "success": True,
            "status": publicacion["status"],
            "sql_updated": publicacion["sql_updated"],
            "publication_confirmed": True,
            "load_id": publicacion["load_id"],
            "content_sha256": publicacion["content_sha256"],
            "publication": publicacion,
        })

    except subprocess.TimeoutExpired:
        resultado["status"] = "TIEMPO_AGOTADO"
        resultado["error"] = (
            "Una etapa superó el tiempo máximo. "
            "Consultar audit.Publicacion antes de concluir "
            "si SQL llegó a confirmar la publicación."
        )

    except Exception as error:
        resultado["status"] = "FALLIDO"
        resultado["error"] = str(error)

    resultado["duration_seconds"] = round(
        time.monotonic() - inicio, 3
    )

    # Conservar el resultado integrado sin modificar
    # resultado_lote.json, que describe la preparación.
    if carpeta_lote is not None:
        try:
            ruta_resultado = (
                carpeta_lote / "resultado_pipeline.json"
            )

            ruta_resultado.write_text(
                json.dumps(
                    resultado,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        except OSError as error:
            # Un fallo al guardar el archivo no revierte
            # una publicación SQL que ya fue confirmada.
            resultado["local_log_warning"] = str(error)

    print(json.dumps(
        resultado,
        ensure_ascii=False,
        indent=2,
    ))

    return 0 if resultado["success"] else 1


if __name__ == "__main__":
    sys.exit(main())