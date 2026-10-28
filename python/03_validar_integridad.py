import runpy
import sys

from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


# Recuperamos las funciones y columnas del segundo script.
RUTA_CARGADOR = (
    Path(__file__).resolve().parent / "02_validar_tipos.py"
)

CONFIGURACION = runpy.run_path(str(RUTA_CARGADOR))

COLUMNAS = CONFIGURACION["COLUMNAS"]
cargar_archivo = CONFIGURACION["cargar_archivo"]

# Tolerancias explícitas para comparar importes.
TOLERANCIA_LINEA = Decimal("0.000001")
TOLERANCIA_SUBTOTAL = Decimal("0.01")
TOLERANCIA_TOTAL = Decimal("0.0001")


def informar(nombre, problemas):
    """Muestra un resumen y hasta cinco ejemplos."""
    if problemas:
        print(f"[REVISAR] {nombre}: {len(problemas):,} casos")
        print(f"          Ejemplos: {problemas[:5]}")
        return False

    print(f"[OK] {nombre}")
    return True


def validar_clave(registros, campos, nombre):
    claves = [
        tuple(registro[campo] for campo in campos)
        for registro in registros
    ]

    filas_sin_clave = [
        numero
        for numero, clave in enumerate(claves, start=1)
        if any(valor is None for valor in clave)
    ]

    conteos = Counter(claves)

    claves_duplicadas = [
        clave
        for clave, cantidad in conteos.items()
        if cantidad > 1
    ]

    obligatoria = informar(
        f"{nombre}: clave obligatoria",
        filas_sin_clave,
    )

    unica = informar(
        f"{nombre}: clave única",
        claves_duplicadas,
    )

    return obligatoria and unica


def main():
    print("VALIDACIÓN DE INTEGRIDAD Y REGLAS DE NEGOCIO\n")

    datos = {}

    for nombre, columnas in COLUMNAS.items():
        registros, _, _ = cargar_archivo(nombre, columnas)
        datos[nombre] = registros

    pedidos = datos["pedidos.csv"]
    lineas = datos["lineas_pedido.csv"]
    productos = datos["productos.csv"]
    clientes = datos["clientes.csv"]
    territorios = datos["territorios.csv"]

    resultados = []

    print("1. CLAVES")

    definiciones_clave = [
        (pedidos, ["SalesOrderID"], "Pedidos"),
        (
            lineas,
            ["SalesOrderID", "SalesOrderDetailID"],
            "Líneas de pedido",
        ),
        (productos, ["ProductID"], "Productos"),
        (clientes, ["CustomerID"], "Clientes"),
        (territorios, ["TerritoryID"], "Territorios"),
    ]

    for registros, campos, nombre in definiciones_clave:
        resultados.append(
            validar_clave(registros, campos, nombre)
        )

    # No construiremos índices sobre claves incorrectas.
    if not all(resultados):
        print("\nDetenido: revisar las claves antes de continuar.")
        return 1

    print("\n2. CAMPOS NECESARIOS PARA LOS CÁLCULOS")

    campos_requeridos = [
        (
            pedidos,
            "SalesOrderID",
            [
                "OrderDate",
                "DueDate",
                "ShipDate",
                "CustomerID",
                "TerritoryID",
                "SubTotal",
                "TaxAmt",
                "Freight",
                "TotalDue",
            ],
            "Pedidos",
        ),
        (
            lineas,
            "SalesOrderDetailID",
            [
                "ProductID",
                "OrderQty",
                "UnitPrice",
                "UnitPriceDiscount",
                "LineTotal",
            ],
            "Líneas",
        ),
    ]

    campos_correctos = True

    for registros, campo_id, campos, nombre in campos_requeridos:
        faltantes = [
            (registro[campo_id], campo)
            for registro in registros
            for campo in campos
            if registro[campo] is None
        ]

        correcto = informar(
            f"{nombre}: campos requeridos completos",
            faltantes,
        )

        resultados.append(correcto)

        if not correcto:
            campos_correctos = False

    # ShipDate es obligatorio aquí porque estamos validando
    # esta extracción histórica. En la simulación futura,
    # un pedido pendiente sí podrá carecer de despacho.
    if not campos_correctos:
        print("\nDetenido: faltan datos necesarios para los cálculos.")
        return 1

    pedidos_por_id = {
        pedido["SalesOrderID"]: pedido
        for pedido in pedidos
    }

    ids_productos = {
        producto["ProductID"]
        for producto in productos
    }

    ids_clientes = {
        cliente["CustomerID"]
        for cliente in clientes
    }

    ids_territorios = {
        territorio["TerritoryID"]
        for territorio in territorios
    }

    print("\n3. RELACIONES")

    resultados.append(informar(
        "Todas las líneas tienen un pedido existente",
        [
            linea["SalesOrderDetailID"]
            for linea in lineas
            if linea["SalesOrderID"] not in pedidos_por_id
        ],
    ))

    resultados.append(informar(
        "Todas las líneas tienen un producto existente",
        [
            linea["SalesOrderDetailID"]
            for linea in lineas
            if linea["ProductID"] not in ids_productos
        ],
    ))

    resultados.append(informar(
        "Todos los pedidos tienen un cliente existente",
        [
            pedido["SalesOrderID"]
            for pedido in pedidos
            if pedido["CustomerID"] not in ids_clientes
        ],
    ))

    resultados.append(informar(
        "Todos los pedidos tienen un territorio existente",
        [
            pedido["SalesOrderID"]
            for pedido in pedidos
            if pedido["TerritoryID"] not in ids_territorios
        ],
    ))

    resultados.append(informar(
        "Todos los clientes tienen un territorio existente",
        [
            cliente["CustomerID"]
            for cliente in clientes
            if cliente["TerritoryID"] not in ids_territorios
        ],
    ))

    print("\n4. CANTIDADES, PRECIOS Y DESCUENTOS")

    resultados.append(informar(
        "Cantidades mayores que cero",
        [
            linea["SalesOrderDetailID"]
            for linea in lineas
            if linea["OrderQty"] <= 0
        ],
    ))

    resultados.append(informar(
        "Precios no negativos",
        [
            linea["SalesOrderDetailID"]
            for linea in lineas
            if linea["UnitPrice"] < 0
        ],
    ))

    resultados.append(informar(
        "Descuentos entre 0 y 1",
        [
            linea["SalesOrderDetailID"]
            for linea in lineas
            if not Decimal("0")
            <= linea["UnitPriceDiscount"]
            <= Decimal("1")
        ],
    ))

    print("\n5. FECHAS")

    resultados.append(informar(
        "Despachos no anteriores al pedido",
        [
            pedido["SalesOrderID"]
            for pedido in pedidos
            if pedido["ShipDate"] < pedido["OrderDate"]
        ],
    ))

    resultados.append(informar(
        "Vencimientos no anteriores al pedido",
        [
            pedido["SalesOrderID"]
            for pedido in pedidos
            if pedido["DueDate"] < pedido["OrderDate"]
        ],
    ))

    print("\n6. CONCILIACIÓN DE IMPORTES")

    errores_linea = []
    importes_por_pedido = defaultdict(lambda: Decimal("0"))

    for linea in lineas:
        importe_calculado = (
            Decimal(linea["OrderQty"])
            * linea["UnitPrice"]
            * (Decimal("1") - linea["UnitPriceDiscount"])
        )

        diferencia = abs(
            importe_calculado - linea["LineTotal"]
        )

        if diferencia > TOLERANCIA_LINEA:
            errores_linea.append(
                (linea["SalesOrderDetailID"], str(diferencia))
            )

        importes_por_pedido[linea["SalesOrderID"]] += (
            linea["LineTotal"]
        )

    resultados.append(informar(
        "Importes de línea correctos",
        errores_linea,
    ))

    resultados.append(informar(
        "Todos los pedidos tienen líneas",
        [
            pedido["SalesOrderID"]
            for pedido in pedidos
            if pedido["SalesOrderID"] not in importes_por_pedido
        ],
    ))

    errores_subtotal = []
    errores_total = []
    maxima_diferencia_subtotal = Decimal("0")

    for pedido in pedidos:
        pedido_id = pedido["SalesOrderID"]

        diferencia_subtotal = abs(
            pedido["SubTotal"]
            - importes_por_pedido.get(pedido_id, Decimal("0"))
        )

        maxima_diferencia_subtotal = max(
            maxima_diferencia_subtotal,
            diferencia_subtotal,
        )

        if diferencia_subtotal > TOLERANCIA_SUBTOTAL:
            errores_subtotal.append(
                (pedido_id, str(diferencia_subtotal))
            )

        total_calculado = (
            pedido["SubTotal"]
            + pedido["TaxAmt"]
            + pedido["Freight"]
        )

        diferencia_total = abs(
            pedido["TotalDue"] - total_calculado
        )

        if diferencia_total > TOLERANCIA_TOTAL:
            errores_total.append(
                (pedido_id, str(diferencia_total))
            )

    resultados.append(informar(
        "Subtotales conciliados con sus líneas",
        errores_subtotal,
    ))

    resultados.append(informar(
        "Totales conciliados con subtotal, impuesto y flete",
        errores_total,
    ))

    print(
        "Máxima diferencia entre subtotal y suma de líneas:",
        maxima_diferencia_subtotal,
    )

    print("\nRESULTADO FINAL")

    if all(resultados):
        print("Los datos superaron todos los controles implementados.")
        print("Los archivos originales no fueron modificados.")
        return 0

    print("Hay controles que requieren revisión.")
    print("No debemos corregirlos sin investigar su causa.")
    return 1


if __name__ == "__main__":
    sys.exit(main())