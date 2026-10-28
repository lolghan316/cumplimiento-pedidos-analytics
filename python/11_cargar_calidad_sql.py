import csv
import getpass
import hashlib
import json
import runpy

from pathlib import Path

import pyodbc


PROYECTO = Path(__file__).resolve().parent.parent

CONFIG = runpy.run_path(
    str(PROYECTO / "python" / "09_probar_conexion_sql.py")
)
valor_odbc = CONFIG["valor_odbc"]

RUTA_ENTRADA = (
    PROYECTO / "data" / "incoming"
    / "entregas_recibidas_v1.csv"
)
RUTA_BITACORA = (
    PROYECTO / "data" / "processed"
    / "bitacora_calidad_v1.csv"
)
RUTA_RESUMEN = (
    PROYECTO / "data" / "processed"
    / "resumen_limpieza_v1.json"
)


def leer_csv(ruta):
    with ruta.open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        return list(csv.DictReader(archivo))


def huella(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main():
    recibidas = leer_csv(RUTA_ENTRADA)
    bitacora = leer_csv(RUTA_BITACORA)
    resumen = json.loads(
        RUTA_RESUMEN.read_text(encoding="utf-8-sig")
    )

    if len(recibidas) != resumen["filas_entrada"]:
        raise ValueError("La entrada no coincide con el resumen.")

    if (
        resumen["filas_aceptadas"]
        + resumen["filas_cuarentena"]
        + resumen["copias_retiradas"]
        != len(recibidas)
    ):
        raise ValueError("Las disposiciones no concilian.")

    incidencias = []

    for registro in bitacora:
        numero = int(registro["SourceRow"])

        if not 1 <= numero <= len(recibidas):
            raise ValueError(f"SourceRow inválido: {numero}")

        fuente = recibidas[numero - 1]
        evento = fuente["EventID"].strip()

        if evento != registro["EventID"]:
            raise ValueError(
                f"EventID no coincide en SourceRow {numero}"
            )

        if registro["Action"] not in {
            "NORMALIZAR", "CUARENTENA", "RETIRAR_COPIA"
        }:
            raise ValueError("Acción de calidad desconocida.")

        incidencias.append((
            numero,
            evento,
            int(fuente["SalesOrderID"].strip()),
            registro["Rule"],
            registro["Action"],
            registro["Before"],
            registro["After"],
        ))

    disponibles = pyodbc.drivers()
    controlador = next(
        (
            d for d in [
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
            ]
            if d in disponibles
        ),
        None,
    )

    if controlador is None:
        raise ValueError("Falta el controlador ODBC.")

    usuario = input("Usuario de SQL Server: ").strip()
    clave = getpass.getpass("Contraseña: ")

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

        cursor.execute("""
            SELECT TOP (1)
                LoadID, CutoffDate, SourceManifest
            FROM audit.Carga
            ORDER BY LoadID DESC;
        """)
        carga = cursor.fetchone()

        if carga is None:
            raise ValueError("No hay carga principal confirmada.")

        carga_id, corte, manifiesto_json = carga

        if corte.isoformat() != resumen["fecha_corte"]:
            raise ValueError("Las fechas de corte no coinciden.")

        # Vincular este procesamiento con los archivos
        # utilizados en la carga principal.
        manifiesto = {
            r["archivo"]: r["sha256"]
            for r in json.loads(manifiesto_json)
        }

        archivos_vinculados = [
            RUTA_RESUMEN,
            PROYECTO / "data" / "processed"
            / "entregas_aceptadas_v1.csv",
            PROYECTO / "data" / "processed"
            / "pedidos_con_revision_v1.csv",
        ]

        for ruta in archivos_vinculados:
            nombre = ruta.relative_to(PROYECTO).as_posix()

            if manifiesto.get(nombre) != huella(ruta):
                raise ValueError(
                    f"El archivo cambió desde la carga: {nombre}"
                )

        cursor.execute("""
            IF OBJECT_ID('audit.CalidadCarga', 'U') IS NULL
            CREATE TABLE audit.CalidadCarga (
                LoadID bigint NOT NULL PRIMARY KEY,
                InputRows int NOT NULL,
                AcceptedRows int NOT NULL,
                QuarantineRows int NOT NULL,
                RemovedCopies int NOT NULL,
                Normalizations int NOT NULL,
                InputSHA256 char(64) NOT NULL,
                LogSHA256 char(64) NOT NULL,
                FOREIGN KEY (LoadID)
                    REFERENCES audit.Carga(LoadID)
            );
        """)

        cursor.execute("""
            IF OBJECT_ID('audit.IncidenciaCalidad', 'U') IS NULL
            CREATE TABLE audit.IncidenciaCalidad (
                IncidentID bigint IDENTITY(1,1) NOT NULL
                    PRIMARY KEY,
                LoadID bigint NOT NULL,
                SourceRow int NOT NULL,
                EventID nvarchar(100) NOT NULL,
                SalesOrderID int NOT NULL,
                [Rule] nvarchar(100) NOT NULL,
                [Action] nvarchar(30) NOT NULL,
                BeforeValue nvarchar(max) NULL,
                AfterValue nvarchar(max) NULL,
                UNIQUE (LoadID, SourceRow, [Rule], [Action]),
                FOREIGN KEY (LoadID)
                    REFERENCES audit.CalidadCarga(LoadID),
                FOREIGN KEY (SalesOrderID)
                    REFERENCES core.Pedido(SalesOrderID)
            );
        """)

        cursor.execute(
            "SELECT COUNT(*) FROM audit.CalidadCarga WHERE LoadID = ?",
            carga_id,
        )

        if cursor.fetchone()[0]:
            raise ValueError(
                "La calidad de esta carga ya está registrada. "
                "No se repetirá."
            )

        cursor.execute("""
            INSERT INTO audit.CalidadCarga (
                LoadID, InputRows, AcceptedRows,
                QuarantineRows, RemovedCopies, Normalizations,
                InputSHA256, LogSHA256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
            carga_id,
            len(recibidas),
            resumen["filas_aceptadas"],
            resumen["filas_cuarentena"],
            resumen["copias_retiradas"],
            resumen["normalizaciones"],
            huella(RUTA_ENTRADA),
            huella(RUTA_BITACORA),
        )

        sql = """
            INSERT INTO audit.IncidenciaCalidad (
                LoadID, SourceRow, EventID, SalesOrderID,
                [Rule], [Action], BeforeValue, AfterValue
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """

        filas = [
            (carga_id,) + incidencia
            for incidencia in incidencias
        ]

        for inicio in range(0, len(filas), 1000):
            cursor.executemany(sql, filas[inicio:inicio + 1000])

        cursor.execute("""
            SELECT COUNT_BIG(*)
            FROM audit.IncidenciaCalidad
            WHERE LoadID = ?;
        """, carga_id)

        cantidad = cursor.fetchone()[0]

        if cantidad != len(bitacora):
            raise ValueError("No concilia la cantidad de incidencias.")

        conexion.commit()

        print("\nCALIDAD CARGADA CORRECTAMENTE")
        print(f"LoadID: {carga_id}")
        print(f"Incidencias: {cantidad}")
        print(f"Filas de entrada: {len(recibidas)}")

    except Exception:
        conexion.rollback()
        print("Se revirtieron los cambios de esta ejecución.")
        raise

    finally:
        conexion.close()


if __name__ == "__main__":
    main()