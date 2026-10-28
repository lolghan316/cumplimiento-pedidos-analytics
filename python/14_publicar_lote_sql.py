import argparse
import csv
import hashlib
import json
import os
import re
import runpy
import sys

from datetime import date
from pathlib import Path

import pyodbc


PROYECTO = Path(__file__).resolve().parent.parent

CONFIG = runpy.run_path(
    str(PROYECTO / "python" / "09_probar_conexion_sql.py")
)
valor_odbc = CONFIG["valor_odbc"]

ARCHIVOS_SALIDA = {
    "entregas_aceptadas_v1.csv",
    "entregas_cuarentena_v1.csv",
    "bitacora_calidad_v1.csv",
    "pedidos_con_revision_v1.csv",
    "resumen_limpieza_v1.json",
}

FUENTES = {
    "data/raw/pedidos.csv",
    "data/raw/lineas_pedido.csv",
    "data/raw/productos.csv",
    "data/raw/clientes.csv",
    "data/raw/territorios.csv",
    "data/incoming/entregas_recibidas_v1.csv",
}

RUTA_PROMESAS = "data/synthetic/promesas_entrega_v1.csv"


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def huella(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def leer_csv(ruta):
    with ruta.open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        return list(csv.DictReader(archivo))


def insertar_bloques(cursor, sql, filas):
    for inicio in range(0, len(filas), 1000):
        cursor.executemany(sql, filas[inicio:inicio + 1000])


def publicar(batch_id):
    exigir(
        re.fullmatch(r"[0-9a-f]{32}", batch_id) is not None,
        "El identificador de lote no tiene el formato esperado.",
    )

    carpeta = PROYECTO / "data" / "runs" / batch_id

    reporte = json.loads(
        (carpeta / "resultado_lote.json")
        .read_text(encoding="utf-8")
    )

    exigir(
        reporte["success"]
        and reporte["status"] == "LISTO_PARA_CARGA_SQL"
        and reporte["batch_id"] == batch_id,
        "El paquete no está preparado para publicación.",
    )

    exigir(
        set(reporte["source_hashes"]) == FUENTES,
        "El inventario de fuentes no coincide.",
    )
    exigir(
        set(reporte["output_hashes"]) == ARCHIVOS_SALIDA,
        "El inventario de salidas no coincide.",
    )

    for nombre, esperado in reporte["source_hashes"].items():
        exigir(
            huella(PROYECTO / nombre) == esperado,
            f"La fuente cambió: {nombre}. Procesa un lote nuevo.",
        )

    for nombre, esperado in reporte["output_hashes"].items():
        exigir(
            huella(carpeta / nombre) == esperado,
            f"La salida del paquete cambió: {nombre}",
        )

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
    revisiones = leer_csv(
        carpeta / "pedidos_con_revision_v1.csv"
    )
    bitacora = leer_csv(
        carpeta / "bitacora_calidad_v1.csv"
    )
    entrada = leer_csv(
        PROYECTO / "data" / "incoming"
        / "entregas_recibidas_v1.csv"
    )

    exigir(
        len(aceptadas) == resumen["filas_aceptadas"]
        and len(cuarentena) == resumen["filas_cuarentena"]
        and len(revisiones) == resumen["pedidos_con_revision"]
        and len(entrada) == resumen["filas_entrada"],
        "Los conteos del paquete no concilian.",
    )

    retiradas = [
        r for r in bitacora
        if r["Action"] == "RETIRAR_COPIA"
    ]

    disposiciones = [
        int(r["SourceRow"])
        for grupo in [aceptadas, cuarentena, retiradas]
        for r in grupo
    ]

    exigir(
        len(disposiciones) == len(entrada)
        and set(disposiciones)
        == set(range(1, len(entrada) + 1)),
        "Las disposiciones de filas no concilian.",
    )

    corte = date.fromisoformat(resumen["fecha_corte"])

    exigir(
        all(
            date.fromisoformat(r["DeliveryDate"]) <= corte
            for r in aceptadas
        ),
        "El paquete incluye entregas posteriores al corte.",
    )

    incidencias = []

    for r in bitacora:
        numero = int(r["SourceRow"])

        exigir(
            1 <= numero <= len(entrada),
            "Hay una referencia de fila inválida.",
        )

        fuente = entrada[numero - 1]

        exigir(
            fuente["EventID"].strip() == r["EventID"],
            f"No coincide el evento de la fila {numero}.",
        )

        incidencias.append((
            numero,
            r["EventID"],
            int(fuente["SalesOrderID"].strip()),
            r["Rule"],
            r["Action"],
            r["Before"],
            r["After"],
        ))

    huella_promesas = huella(PROYECTO / RUTA_PROMESAS)

    contenido = {
        "publisher_version": 1,
        "sources": reporte["source_hashes"],
        "outputs": reporte["output_hashes"],
        "promises": huella_promesas,
        "cutoff": corte.isoformat(),
    }

    firma = hashlib.sha256(
        json.dumps(
            contenido, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    usuario = os.environ.get("PORTFOLIO_SQL_USER")
    clave = os.environ.get("PORTFOLIO_SQL_PASSWORD")

    exigir(
        bool(usuario) and bool(clave),
        "Faltan las variables de credenciales de SQL.",
    )

    controlador = next(
        (
            d for d in [
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
            ]
            if d in pyodbc.drivers()
        ),
        None,
    )
    exigir(controlador is not None, "Falta controlador ODBC.")

    cadena = (
        f"DRIVER={valor_odbc(controlador)};"
        "SERVER=localhost;"
        "DATABASE=PortfolioPedidos;"
        f"UID={valor_odbc(usuario)};"
        f"PWD={valor_odbc(clave)};"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )

    conexion = pyodbc.connect(
        cadena, autocommit=False, timeout=10
    )

    try:
        cursor = conexion.cursor()
        cursor.execute("SET XACT_ABORT ON;")

        # Impedir dos publicaciones simultáneas.
        cursor.execute("""
            DECLARE @resultado int;
            EXEC @resultado = sys.sp_getapplock
                @Resource = N'PortfolioPedidos_Publicacion',
                @LockMode = 'Exclusive',
                @LockOwner = 'Transaction',
                @LockTimeout = 10000;
            SELECT @resultado;
        """)

        exigir(
            cursor.fetchone()[0] >= 0,
            "No se pudo obtener el bloqueo de publicación.",
        )

        cursor.execute("""
            SELECT TOP (1)
                LoadID, CutoffDate, SourceManifest, RowCounts
            FROM audit.Carga
            ORDER BY LoadID DESC;
        """)
        anterior = cursor.fetchone()
        exigir(anterior is not None, "Falta la carga inicial.")

        load_anterior, corte_anterior, fuentes_json, conteos_json = anterior

        exigir(
            corte_anterior == corte,
            "Esta versión solo publica sobre el mismo corte.",
        )

        fuentes_sql = {
            r["archivo"]: r["sha256"]
            for r in json.loads(fuentes_json)
        }

        # Los maestros y compromisos deben seguir siendo
        # los que respaldan las tablas ya cargadas.
        for nombre in sorted(FUENTES):
            if nombre.startswith("data/raw/"):
                exigir(
                    fuentes_sql.get(nombre)
                    == reporte["source_hashes"][nombre],
                    f"Cambió un maestro: {nombre}",
                )

        exigir(
            fuentes_sql.get(RUTA_PROMESAS) == huella_promesas,
            "Los compromisos cambiaron desde la carga inicial.",
        )

        cursor.execute("""
            SELECT LoadID
            FROM audit.Publicacion
            WHERE ContentSHA256 = ?;
        """, firma)
        existente = cursor.fetchone()

        if existente is not None:
            exigir(
                existente[0] == load_anterior,
                "Este contenido fue publicado antes, pero ya "
                "no es el vigente. No se restaurará automáticamente.",
            )

            conexion.rollback()

            return {
                "success": True,
                "status": "YA_PUBLICADO",
                "sql_updated": False,
                "load_id": existente[0],
                "batch_id": batch_id,
                "content_sha256": firma,
            }

        conteos = json.loads(conteos_json)
        conteos["core.Entrega"] = len(aceptadas)
        conteos["core.PedidoRevision"] = len(revisiones)

        manifiesto = [
            {"archivo": nombre, "sha256": valor}
            for nombre, valor
            in sorted(reporte["source_hashes"].items())
        ]
        manifiesto.append({
            "archivo": RUTA_PROMESAS,
            "sha256": huella_promesas,
        })
        manifiesto.extend([
            {
                "archivo": (
                    carpeta / nombre
                ).relative_to(PROYECTO).as_posix(),
                "sha256": valor,
            }
            for nombre, valor
            in sorted(reporte["output_hashes"].items())
        ])

        cursor.execute("""
            INSERT INTO audit.Carga (
                CutoffDate, SourceManifest, RowCounts
            )
            OUTPUT INSERTED.LoadID
            VALUES (?, ?, ?);
        """,
            corte,
            json.dumps(manifiesto, ensure_ascii=False),
            json.dumps(conteos, ensure_ascii=False),
        )
        load_id = cursor.fetchone()[0]

        # Sustitución del estado logístico actual.
        # Solo será visible al confirmar toda la transacción.
        cursor.execute("DELETE FROM core.Entrega;")
        cursor.execute("DELETE FROM core.PedidoRevision;")

        insertar_bloques(cursor, """
            INSERT INTO core.Entrega (
                EventID, SalesOrderID, SalesOrderDetailID,
                ProductID, DeliveryDate, DeliveredQty,
                IsSynthetic, SourceRow
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, [
            (
                r["EventID"],
                int(r["SalesOrderID"]),
                int(r["SalesOrderDetailID"]),
                int(r["ProductID"]),
                date.fromisoformat(r["DeliveryDate"]),
                int(r["DeliveredQty"]),
                int(r["IsSynthetic"]),
                int(r["SourceRow"]),
            )
            for r in aceptadas
        ])

        insertar_bloques(cursor, """
            INSERT INTO core.PedidoRevision (
                SalesOrderID, Reason
            )
            VALUES (?, ?);
        """, [
            (
                int(r["SalesOrderID"]),
                "Eventos en cuarentena: revisar calidad",
            )
            for r in revisiones
        ])

        cursor.execute("""
            INSERT INTO audit.CalidadCarga (
                LoadID, InputRows, AcceptedRows,
                QuarantineRows, RemovedCopies, Normalizations,
                InputSHA256, LogSHA256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
            load_id,
            len(entrada),
            len(aceptadas),
            len(cuarentena),
            resumen["copias_retiradas"],
            resumen["normalizaciones"],
            reporte["source_hashes"][
                "data/incoming/entregas_recibidas_v1.csv"
            ],
            reporte["output_hashes"]["bitacora_calidad_v1.csv"],
        )

        insertar_bloques(cursor, """
            INSERT INTO audit.IncidenciaCalidad (
                LoadID, SourceRow, EventID, SalesOrderID,
                [Rule], [Action], BeforeValue, AfterValue
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, [
            (load_id,) + r for r in incidencias
        ])

        cursor.execute("SELECT COUNT_BIG(*) FROM core.Entrega;")
        exigir(
            cursor.fetchone()[0] == len(aceptadas),
            "No concilian las entregas cargadas.",
        )

        cursor.execute("""
            SELECT COUNT_BIG(*)
            FROM core.PedidoRevision;
        """)
        exigir(
            cursor.fetchone()[0] == len(revisiones),
            "No concilian los pedidos con revisión.",
        )

        cursor.execute("""
            SELECT COUNT_BIG(*)
            FROM audit.IncidenciaCalidad
            WHERE LoadID = ?;
        """, load_id)
        exigir(
            cursor.fetchone()[0] == len(bitacora),
            "No concilian las incidencias cargadas.",
        )

        cursor.execute("""
            INSERT INTO audit.Publicacion (
                LoadID, BatchID, ContentSHA256
            )
            VALUES (?, ?, ?);
        """, load_id, batch_id, firma)

        conexion.commit()

        return {
            "success": True,
            "status": "PUBLICADO",
            "sql_updated": True,
            "load_id": load_id,
            "batch_id": batch_id,
            "content_sha256": firma,
            "deliveries": len(aceptadas),
            "orders_under_review": len(revisiones),
            "quality_incidents": len(bitacora),
        }

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    argumentos = parser.parse_args()

    try:
        resultado = publicar(argumentos.batch)
        print(json.dumps(
            resultado, ensure_ascii=False, indent=2
        ))
        return 0

    except Exception as error:
        print(json.dumps({
            "success": False,
            "status": "ERROR_PUBLICACION",
            "error": str(error),
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())