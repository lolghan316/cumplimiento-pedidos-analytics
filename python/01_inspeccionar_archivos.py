import csv
import sys
from pathlib import Path

# Localiza el proyecto a partir de la ubicación de este script.
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_DATOS = CARPETA_PROYECTO / "data" / "raw"

# Los CSV no tienen encabezados.
# Estas columnas siguen el mismo orden que nuestras consultas SQL.
COLUMNAS = {
    "pedidos.csv": [
        "SalesOrderID",
        "OrderDate",
        "DueDate",
        "ShipDate",
        "Status",
        "OnlineOrderFlag",
        "CustomerID",
        "TerritoryID",
        "ShipMethodID",
        "CurrencyRateID",
        "SubTotal",
        "TaxAmt",
        "Freight",
        "TotalDue",
    ],
    "lineas_pedido.csv": [
        "SalesOrderID",
        "SalesOrderDetailID",
        "ProductID",
        "OrderQty",
        "UnitPrice",
        "UnitPriceDiscount",
        "LineTotal",
    ],
    "productos.csv": [
        "ProductID",
        "ProductNumber",
        "ProductName",
        "ProductSubcategoryID",
        "SubcategoryName",
        "ProductCategoryID",
        "CategoryName",
        "SizeUnitMeasureCode",
        "WeightUnitMeasureCode",
    ],
    "clientes.csv": [
        "CustomerID",
        "TerritoryID",
    ],
    "territorios.csv": [
        "TerritoryID",
        "TerritoryName",
        "CountryRegionCode",
        "TerritoryGroup",
    ],
}


def inspeccionar_archivo(nombre, columnas):
    """Comprueba la estructura de un CSV sin modificarlo."""
    ruta = CARPETA_DATOS / nombre

    print(f"\nArchivo: {nombre}")

    if not ruta.is_file():
        print(f"ERROR: no se encontró el archivo en {ruta}")
        return False

    cantidad_filas = 0
    filas_invalidas = 0
    primera_fila = None
    ejemplos_invalidos = []

    # utf-8-sig reconoce la marca de codificación de estos archivos.
    with ruta.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:
        lector = csv.reader(archivo, delimiter=",", strict=True)

        for numero_fila, fila in enumerate(lector, start=1):
            cantidad_filas += 1

            if len(fila) != len(columnas):
                filas_invalidas += 1

                if len(ejemplos_invalidos) < 3:
                    ejemplos_invalidos.append(numero_fila)

                continue

            if primera_fila is None:
                primera_fila = dict(zip(columnas, fila))

    print(f"Registros: {cantidad_filas:,}")
    print(f"Columnas esperadas: {len(columnas)}")
    print(f"Filas con cantidad incorrecta de columnas: {filas_invalidas}")

    if ejemplos_invalidos:
        print(f"Ejemplos de filas incorrectas: {ejemplos_invalidos}")

    if primera_fila is not None:
        print("Primer registro con nombres de columnas:")

        for columna, valor in primera_fila.items():
            print(f"  {columna}: {valor}")

    if cantidad_filas == 0:
        print("ERROR: el archivo está vacío.")
        return False

    return filas_invalidas == 0


def main():
    print("INSPECCIÓN INICIAL DEL PROYECTO")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Intérprete utilizado: {sys.executable}")
    print(f"Carpeta de datos: {CARPETA_DATOS}")

    todo_correcto = True

    for nombre, columnas in COLUMNAS.items():
        try:
            correcto = inspeccionar_archivo(nombre, columnas)
        except (OSError, UnicodeError, csv.Error) as error:
            print(f"ERROR al leer {nombre}: {error}")
            correcto = False

        if not correcto:
            todo_correcto = False

    print("\nRESULTADO FINAL")

    if todo_correcto:
        print("Los cinco archivos superaron la revisión de estructura.")
        print("Todavía falta validar tipos de datos y reglas de negocio.")
    else:
        print("Hay problemas de lectura o estructura que debemos revisar.")

    return 0 if todo_correcto else 1


if __name__ == "__main__":
    sys.exit(main())