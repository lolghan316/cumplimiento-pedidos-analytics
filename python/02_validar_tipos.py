import csv
import runpy
import sys

from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


# Recuperamos las columnas y rutas del primer script.
# Esto no ejecuta su función main.
RUTA_INSPECTOR = (
    Path(__file__).resolve().parent / "01_inspeccionar_archivos.py"
)

CONFIGURACION = runpy.run_path(str(RUTA_INSPECTOR))

COLUMNAS = CONFIGURACION["COLUMNAS"]
CARPETA_DATOS = CONFIGURACION["CARPETA_DATOS"]


CAMPOS_ENTEROS = {
    "SalesOrderID",
    "SalesOrderDetailID",
    "Status",
    "OnlineOrderFlag",
    "CustomerID",
    "TerritoryID",
    "ShipMethodID",
    "CurrencyRateID",
    "ProductID",
    "OrderQty",
    "ProductSubcategoryID",
    "ProductCategoryID",
}

CAMPOS_DECIMALES = {
    "SubTotal",
    "TaxAmt",
    "Freight",
    "TotalDue",
    "UnitPrice",
    "UnitPriceDiscount",
    "LineTotal",
}

CAMPOS_FECHA = {
    "OrderDate",
    "DueDate",
    "ShipDate",
}


def convertir_valor(columna, valor):
    """Interpreta un valor sin modificar el archivo original."""
    if valor == "NULL" or valor == "":
        return None

    if columna in CAMPOS_ENTEROS:
        return int(valor)

    if columna in CAMPOS_DECIMALES:
        numero = Decimal(valor)

        if not numero.is_finite():
            raise ValueError("El valor decimal no es finito")

        return numero

    if columna in CAMPOS_FECHA:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S.%f")

    return valor


def cargar_archivo(nombre, columnas):
    ruta = CARPETA_DATOS / nombre

    registros = []
    nulos = Counter()
    vacios = Counter()

    cantidad_errores = 0
    ejemplos_errores = []

    with ruta.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:
        lector = csv.reader(archivo, delimiter=",", strict=True)

        for numero_fila, fila in enumerate(lector, start=1):
            if len(fila) != len(columnas):
                cantidad_errores += 1

                if len(ejemplos_errores) < 5:
                    ejemplos_errores.append(
                        f"Fila {numero_fila}: cantidad incorrecta de columnas"
                    )

                continue

            registro = {}
            fila_correcta = True

            for columna, valor in zip(columnas, fila):
                if valor == "NULL":
                    nulos[columna] += 1
                elif valor == "":
                    vacios[columna] += 1

                try:
                    registro[columna] = convertir_valor(columna, valor)

                except (ValueError, InvalidOperation) as error:
                    cantidad_errores += 1
                    fila_correcta = False

                    if len(ejemplos_errores) < 5:
                        ejemplos_errores.append(
                            f"Fila {numero_fila}, columna {columna}, "
                            f"valor {valor!r}: {error}"
                        )

            if fila_correcta:
                registros.append(registro)

    # Si algo falla, no devolvemos un conjunto parcial como válido.
    if cantidad_errores > 0:
        detalle = "\n".join(ejemplos_errores)

        raise ValueError(
            f"{nombre}: {cantidad_errores} errores detectados.\n{detalle}"
        )

    if not registros:
        raise ValueError(f"{nombre}: no contiene registros")

    return registros, nulos, vacios


def main():
    print("VALIDACIÓN DE TIPOS")
    print(f"Carpeta de datos: {CARPETA_DATOS}")

    archivos_correctos = 0

    for nombre, columnas in COLUMNAS.items():
        print(f"\nArchivo: {nombre}")

        try:
            registros, nulos, vacios = cargar_archivo(nombre, columnas)

        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            print(f"ERROR: {error}")
            continue

        archivos_correctos += 1

        print(f"Registros convertidos: {len(registros):,}")
        print(f"Valores NULL por columna: {dict(nulos)}")
        print(f"Campos vacíos por columna: {dict(vacios)}")

        print("Ejemplo de valores y tipos del primer registro:")

        for columna, valor in registros[0].items():
            print(
                f"  {columna}: {valor!r} "
                f"→ {type(valor).__name__}"
            )

    print("\nRESULTADO FINAL")

    if archivos_correctos == len(COLUMNAS):
        print("Los cinco archivos superaron la conversión de tipos.")
        print("Los archivos originales no fueron modificados.")
        print("Todavía falta validar claves y reglas de negocio.")
        return 0

    print("Hay archivos con errores. Debemos revisarlos antes de avanzar.")
    return 1


if __name__ == "__main__":
    sys.exit(main())