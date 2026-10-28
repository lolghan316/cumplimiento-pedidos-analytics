import csv
import getpass
import hashlib
import json
import runpy
import sys

from datetime import date
from pathlib import Path

import pyodbc


PROYECTO = Path(__file__).resolve().parent.parent

CONFIG = runpy.run_path(
    str(PROYECTO / "python" / "02_validar_tipos.py")
)

COLUMNAS = CONFIG["COLUMNAS"]
cargar_archivo = CONFIG["cargar_archivo"]

SERVIDOR = "localhost"
BASE = "PortfolioPedidos"

DDL = [
    """
    CREATE TABLE core.Territorio (
        TerritoryID int NOT NULL PRIMARY KEY,
        TerritoryName nvarchar(100) NOT NULL,
        CountryRegionCode nvarchar(10) NOT NULL,
        TerritoryGroup nvarchar(100) NOT NULL
    );
    """,
    """
    CREATE TABLE core.Cliente (
        CustomerID int NOT NULL PRIMARY KEY,
        TerritoryID int NOT NULL,
        FOREIGN KEY (TerritoryID)
            REFERENCES core.Territorio(TerritoryID)
    );
    """,
    """
    CREATE TABLE core.Producto (
        ProductID int NOT NULL PRIMARY KEY,
        ProductNumber nvarchar(50) NOT NULL,
        ProductName nvarchar(200) NOT NULL,
        ProductSubcategoryID int NULL,
        SubcategoryName nvarchar(100) NULL,
        ProductCategoryID int NULL,
        CategoryName nvarchar(100) NULL,
        SizeUnitMeasureCode nvarchar(20) NULL,
        WeightUnitMeasureCode nvarchar(20) NULL
    );
    """,
    """
    CREATE TABLE core.Pedido (
        SalesOrderID int NOT NULL PRIMARY KEY,
        OrderDate datetime2(3) NOT NULL,
        DueDate datetime2(3) NOT NULL,
        ShipDate datetime2(3) NOT NULL,
        Status int NOT NULL,
        OnlineOrderFlag bit NOT NULL,
        CustomerID int NOT NULL,
        TerritoryID int NOT NULL,
        ShipMethodID int NOT NULL,
        CurrencyRateID int NULL,
        SubTotal decimal(19,4) NOT NULL,
        TaxAmt decimal(19,4) NOT NULL,
        Freight decimal(19,4) NOT NULL,
        TotalDue decimal(19,4) NOT NULL,
        FOREIGN KEY (CustomerID)
            REFERENCES core.Cliente(CustomerID),
        FOREIGN KEY (TerritoryID)
            REFERENCES core.Territorio(TerritoryID)
    );
    """,
    """
    CREATE TABLE core.LineaPedido (
        SalesOrderID int NOT NULL,
        SalesOrderDetailID int NOT NULL,
        ProductID int NOT NULL,
        OrderQty int NOT NULL CHECK (OrderQty > 0),
        UnitPrice decimal(19,4) NOT NULL
            CHECK (UnitPrice >= 0),
        UnitPriceDiscount decimal(10,6) NOT NULL
            CHECK (UnitPriceDiscount BETWEEN 0 AND 1),
        LineTotal decimal(24,6) NOT NULL,
        PRIMARY KEY (SalesOrderID, SalesOrderDetailID),
        UNIQUE (SalesOrderID, SalesOrderDetailID, ProductID),
        FOREIGN KEY (SalesOrderID)
            REFERENCES core.Pedido(SalesOrderID),
        FOREIGN KEY (ProductID)
            REFERENCES core.Producto(ProductID)
    );
    """,
    """
    CREATE TABLE core.PromesaEntrega (
        SalesOrderID int NOT NULL PRIMARY KEY,
        PromisedDeliveryDate date NOT NULL,
        CommitmentDays int NOT NULL
            CHECK (CommitmentDays >= 0),
        DayType nvarchar(30) NOT NULL,
        RuleID nvarchar(100) NOT NULL,
        IsSynthetic bit NOT NULL CHECK (IsSynthetic = 1),
        FOREIGN KEY (SalesOrderID)
            REFERENCES core.Pedido(SalesOrderID)
    );
    """,
    """
    CREATE TABLE core.Entrega (
        EventID nvarchar(100) NOT NULL PRIMARY KEY,
        SalesOrderID int NOT NULL,
        SalesOrderDetailID int NOT NULL,
        ProductID int NOT NULL,
        DeliveryDate date NOT NULL,
        DeliveredQty int NOT NULL CHECK (DeliveredQty > 0),
        IsSynthetic bit NOT NULL CHECK (IsSynthetic = 1),
        SourceRow int NOT NULL,
        FOREIGN KEY (
            SalesOrderID, SalesOrderDetailID, ProductID
        )
        REFERENCES core.LineaPedido (
            SalesOrderID, SalesOrderDetailID, ProductID
        )
    );
    """,
    """
    CREATE TABLE core.PedidoRevision (
        SalesOrderID int NOT NULL PRIMARY KEY,
        Reason nvarchar(200) NOT NULL,
        FOREIGN KEY (SalesOrderID)
            REFERENCES core.Pedido(SalesOrderID)
    );
    """,
    """
    CREATE TABLE audit.Carga (
        LoadID bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        LoadedAtUTC datetime2(3) NOT NULL
            DEFAULT SYSUTCDATETIME(),
        CutoffDate date NOT NULL,
        SourceManifest nvarchar(max) NOT NULL,
        RowCounts nvarchar(max) NOT NULL
    );
    """,
]


def leer_csv(ruta):
    with ruta.open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        return list(csv.DictReader(archivo))


def valor_odbc(texto):
    return "{" + texto.replace("}", "}}") + "}"


def insertar(cursor, tabla, campos, filas):
    """Carga filas en bloques dentro de la misma transacción."""
    nombres = ", ".join(f"[{campo}]" for campo in campos)
    marcas = ", ".join("?" for _ in campos)

    sql = (
        f"INSERT INTO {tabla} ({nombres}) "
        f"VALUES ({marcas})"
    )

    for inicio in range(0, len(filas), 1000):
        bloque = filas[inicio:inicio + 1000]
        cursor.executemany(sql, bloque)

    cursor.execute(f"SELECT COUNT_BIG(*) FROM {tabla}")
    cargadas = cursor.fetchone()[0]

    if cargadas != len(filas):
        raise ValueError(
            f"{tabla}: se esperaban {len(filas)} "
            f"filas y hay {cargadas}."
        )

    print(f"  {tabla}: {cargadas:,} filas verificadas")
    return cargadas


def main():
    print("PREPARACIÓN DE DATOS PARA SQL SERVER\n")

    originales = {}

    for nombre, columnas in COLUMNAS.items():
        registros, _, _ = cargar_archivo(nombre, columnas)
        originales[nombre] = registros

    promesas = leer_csv(
        PROYECTO / "data" / "synthetic"
        / "promesas_entrega_v1.csv"
    )
    entregas = leer_csv(
        PROYECTO / "data" / "processed"
        / "entregas_aceptadas_v1.csv"
    )
    revisiones = leer_csv(
        PROYECTO / "data" / "processed"
        / "pedidos_con_revision_v1.csv"
    )

    # La fecha de corte procede del procesamiento de calidad.
    ruta_resumen = (
        PROYECTO / "data" / "processed"
        / "resumen_limpieza_v1.json"
    )
    resumen_limpieza = json.loads(
        ruta_resumen.read_text(encoding="utf-8-sig")
    )
    corte = date.fromisoformat(
        resumen_limpieza["fecha_corte"]
    )

    if not resumen_limpieza["conciliacion_filas"]:
        raise ValueError(
            "La limpieza no tiene conciliación satisfactoria."
        )

    if len(entregas) != resumen_limpieza["filas_aceptadas"]:
        raise ValueError(
            "Las entregas no coinciden con el resumen de limpieza."
        )

    if len(revisiones) != resumen_limpieza["pedidos_con_revision"]:
        raise ValueError(
            "Los pedidos con revisión no coinciden con el resumen."
        )

    if any(
        date.fromisoformat(r["DeliveryDate"]) > corte
        for r in entregas
    ):
        raise ValueError("Hay entregas posteriores al corte.")

    # Cada carga especifica columnas y valores explícitamente.
    cargas = []

    for tabla, archivo, campos in [
        (
            "core.Territorio", "territorios.csv",
            COLUMNAS["territorios.csv"],
        ),
        (
            "core.Cliente", "clientes.csv",
            COLUMNAS["clientes.csv"],
        ),
        (
            "core.Producto", "productos.csv",
            COLUMNAS["productos.csv"],
        ),
        (
            "core.Pedido", "pedidos.csv",
            COLUMNAS["pedidos.csv"],
        ),
        (
            "core.LineaPedido", "lineas_pedido.csv",
            COLUMNAS["lineas_pedido.csv"],
        ),
    ]:
        filas = [
            tuple(registro[c] for c in campos)
            for registro in originales[archivo]
        ]
        cargas.append((tabla, campos, filas))

    cargas.append((
        "core.PromesaEntrega",
        [
            "SalesOrderID", "PromisedDeliveryDate",
            "CommitmentDays", "DayType", "RuleID",
            "IsSynthetic",
        ],
        [
            (
                int(r["SalesOrderID"]),
                date.fromisoformat(r["PromisedDeliveryDate"]),
                int(r["CommitmentDays"]),
                r["DayType"],
                r["RuleID"],
                int(r["IsSynthetic"]),
            )
            for r in promesas
        ],
    ))

    cargas.append((
        "core.Entrega",
        [
            "EventID", "SalesOrderID", "SalesOrderDetailID",
            "ProductID", "DeliveryDate", "DeliveredQty",
            "IsSynthetic", "SourceRow",
        ],
        [
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
            for r in entregas
        ],
    ))

    cargas.append((
        "core.PedidoRevision",
        ["SalesOrderID", "Reason"],
        [
            (
                int(r["SalesOrderID"]),
                "Eventos en cuarentena: revisar calidad",
            )
            for r in revisiones
        ],
    ))

    rutas_fuente = [
        PROYECTO / "data" / "raw" / nombre
        for nombre in COLUMNAS
    ] + [
        PROYECTO / "data" / "synthetic"
        / "promesas_entrega_v1.csv",
        PROYECTO / "data" / "processed"
        / "entregas_aceptadas_v1.csv",
        PROYECTO / "data" / "processed"
        / "pedidos_con_revision_v1.csv",
        ruta_resumen,
    ]

    manifiesto = [
        {
            "archivo": ruta.relative_to(PROYECTO).as_posix(),
            "sha256": hashlib.sha256(
                ruta.read_bytes()
            ).hexdigest(),
        }
        for ruta in rutas_fuente
    ]

    disponibles = pyodbc.drivers()

    controlador = next(
        (
            nombre
            for nombre in [
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
            ]
            if nombre in disponibles
        ),
        None,
    )

    if controlador is None:
        raise ValueError("No hay controlador ODBC compatible.")

    usuario = input("Usuario de SQL Server: ").strip()
    contrasena = getpass.getpass(
        "Contraseña de SQL Server: "
    )

    cadena = (
        f"DRIVER={valor_odbc(controlador)};"
        f"SERVER={valor_odbc(SERVIDOR)};"
        f"DATABASE={valor_odbc(BASE)};"
        f"UID={valor_odbc(usuario)};"
        f"PWD={valor_odbc(contrasena)};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )

    conexion = pyodbc.connect(
        cadena, autocommit=False, timeout=10
    )

    try:
        cursor = conexion.cursor()
        cursor.execute("SET XACT_ABORT ON;")

        cursor.execute("SELECT DB_NAME();")

        if cursor.fetchone()[0] != BASE:
            raise ValueError("La conexión apunta a otra base.")

        for esquema in ["core", "audit"]:
            cursor.execute(
                "SELECT SCHEMA_ID(?);", esquema
            )

            if cursor.fetchone()[0] is None:
                raise ValueError(
                    f"Falta el esquema {esquema}."
                )

        # Creación de tablas si no existen.
        tablas = [
            tabla for tabla, _, _ in cargas
        ] + ["audit.Carga"]

        for tabla, sentencia in zip(tablas, DDL):
            cursor.execute(
                "SELECT OBJECT_ID(?, 'U');", tabla
            )

            if cursor.fetchone()[0] is None:
                cursor.execute(sentencia)

        # Primera carga exclusivamente.
        for tabla in tablas:
            cursor.execute(
                f"SELECT COUNT_BIG(*) FROM {tabla};"
            )

            if cursor.fetchone()[0] != 0:
                raise ValueError(
                    f"{tabla} ya contiene datos. "
                    "La carga inicial no se repetirá."
                )

        conteos = {}

        print("\nCARGA EN CURSO")

        for tabla, campos, filas in cargas:
            conteos[tabla] = insertar(
                cursor, tabla, campos, filas
            )

        cursor.execute(
            """
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

        carga_id = cursor.fetchone()[0]

        conexion.commit()

        print("\nCARGA CONFIRMADA EN SQL SERVER")
        print(f"Base: {BASE}")
        print(f"Identificador de carga: {carga_id}")
        print(f"Fecha de corte: {corte}")

    except Exception:
        conexion.rollback()
        print(
            "\nCarga no confirmada: "
            "se revirtieron los cambios de esta transacción."
        )
        raise

    finally:
        conexion.close()


if __name__ == "__main__":
    main()