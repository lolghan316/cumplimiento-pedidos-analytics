import contextlib
import csv
import hashlib
import io
import json
import runpy
import sys
import time
import traceback
import uuid

from datetime import datetime, timezone
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent.parent


def huella(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def leer_csv(ruta):
    with ruta.open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        return list(csv.DictReader(archivo))


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def main():
    lote_id = uuid.uuid4().hex
    carpeta = PROYECTO / "data" / "runs" / lote_id
    carpeta.mkdir(parents=True, exist_ok=False)

    inicio = time.monotonic()
    salida_consola = io.StringIO()

    reporte = {
        "batch_id": lote_id,
        "started_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "success": False,
        "status": "INICIADO",
        "sql_updated": False,
        "output_directory": carpeta.relative_to(
            PROYECTO
        ).as_posix(),
    }

    fuentes = [
        PROYECTO / "data" / "raw" / nombre
        for nombre in [
            "pedidos.csv",
            "lineas_pedido.csv",
            "productos.csv",
            "clientes.csv",
            "territorios.csv",
        ]
    ] + [
        PROYECTO / "data" / "incoming"
        / "entregas_recibidas_v1.csv"
    ]

    try:
        huellas_iniciales = {
            ruta.relative_to(PROYECTO).as_posix(): huella(ruta)
            for ruta in fuentes
        }

        # Capturamos los mensajes detallados en un archivo.
        # La respuesta final de consola será únicamente JSON.
        with contextlib.redirect_stdout(salida_consola):
            validador = runpy.run_path(
                str(
                    PROYECTO / "python"
                    / "03_validar_integridad.py"
                )
            )

            codigo = validador["main"]()

            exigir(
                codigo == 0,
                "Los originales no superaron la validación.",
            )

            limpieza = runpy.run_path(
                str(
                    PROYECTO / "python"
                    / "07_limpiar_entregas.py"
                )
            )

            limpieza["main"](carpeta_salida=carpeta)

        resumen = json.loads(
            (carpeta / "resumen_limpieza_v1.json")
            .read_text(encoding="utf-8")
        )

        aceptadas = leer_csv(
            carpeta / "entregas_aceptadas_v1.csv"
        )
        cuarentena = leer_csv(
            carpeta / "entregas_cuarentena_v1.csv"
        )
        bitacora = leer_csv(
            carpeta / "bitacora_calidad_v1.csv"
        )
        revisiones = leer_csv(
            carpeta / "pedidos_con_revision_v1.csv"
        )

        fuente_entregas = leer_csv(fuentes[-1])

        exigir(
            len(fuente_entregas) == resumen["filas_entrada"],
            "No coincide el conteo de entrada.",
        )
        exigir(
            len(aceptadas) == resumen["filas_aceptadas"],
            "No coincide el conteo de aceptadas.",
        )
        exigir(
            len(cuarentena) == resumen["filas_cuarentena"],
            "No coincide el conteo de cuarentena.",
        )
        exigir(
            len(revisiones) == resumen["pedidos_con_revision"],
            "No coincide el conteo de pedidos con revisión.",
        )

        copias = [
            fila for fila in bitacora
            if fila["Action"] == "RETIRAR_COPIA"
        ]

        exigir(
            len(copias) == resumen["copias_retiradas"],
            "No coincide el conteo de copias retiradas.",
        )

        # Cada fila recibida debe tener una disposición final:
        # aceptada, cuarentena o copia retirada.
        filas_dispuestas = [
            int(fila["SourceRow"])
            for grupo in [aceptadas, cuarentena, copias]
            for fila in grupo
        ]

        exigir(
            len(filas_dispuestas) == len(fuente_entregas)
            and set(filas_dispuestas)
            == set(range(1, len(fuente_entregas) + 1)),
            "Hay filas omitidas, repetidas o mal identificadas.",
        )

        ids_eventos = [
            fila["EventID"] for fila in aceptadas
        ]

        exigir(
            len(ids_eventos) == len(set(ids_eventos)),
            "Hay EventID duplicados entre las aceptadas.",
        )

        # Comprobar que la entrada no cambió durante el proceso.
        for ruta in fuentes:
            nombre = ruta.relative_to(PROYECTO).as_posix()

            exigir(
                huella(ruta) == huellas_iniciales[nombre],
                f"La fuente cambió durante el proceso: {nombre}",
            )

        archivos_salida = [
            "entregas_aceptadas_v1.csv",
            "entregas_cuarentena_v1.csv",
            "bitacora_calidad_v1.csv",
            "pedidos_con_revision_v1.csv",
            "resumen_limpieza_v1.json",
        ]

        reporte.update({
            "success": True,
            "status": "LISTO_PARA_CARGA_SQL",
            "source_hashes": huellas_iniciales,
            "output_hashes": {
                nombre: huella(carpeta / nombre)
                for nombre in archivos_salida
            },
            "summary": resumen,
        })

    except Exception as error:
        reporte["status"] = "FALLIDO"
        reporte["error"] = str(error)
        salida_consola.write("\n" + traceback.format_exc())

    finally:
        reporte["duration_seconds"] = round(
            time.monotonic() - inicio, 3
        )

        (carpeta / "detalle_ejecucion.txt").write_text(
            salida_consola.getvalue(),
            encoding="utf-8",
        )

        (carpeta / "resultado_lote.json").write_text(
            json.dumps(
                reporte,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(json.dumps(
        reporte, ensure_ascii=False, indent=2
    ))

    return 0 if reporte["success"] else 1


if __name__ == "__main__":
    sys.exit(main())