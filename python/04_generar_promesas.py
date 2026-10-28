import csv
import json
import runpy
import sys

from datetime import timedelta
from pathlib import Path


# Ubicación del proyecto.
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent

# Reutilizamos la lectura y conversión de tipos.
CONFIGURACION = runpy.run_path(
    str(
        CARPETA_PROYECTO
        / "python"
        / "02_validar_tipos.py"
    )
)

COLUMNAS = CONFIGURACION["COLUMNAS"]
cargar_archivo = CONFIGURACION["cargar_archivo"]

# Política ficticia de esta primera versión.
DIAS_COMPROMISO = 14
REGLA_ID = "ENTREGA_14_DIAS_CALENDARIO_V1"

# Los datos simulados se guardan separados de los originales.
CARPETA_SALIDA = (
    CARPETA_PROYECTO / "data" / "synthetic"
)


def main():
    print("GENERACIÓN DE COMPROMISOS DE ENTREGA SIMULADOS\n")

    pedidos, _, _ = cargar_archivo(
        "pedidos.csv",
        COLUMNAS["pedidos.csv"],
    )

    ids = [
        pedido["SalesOrderID"]
        for pedido in pedidos
    ]

    if any(pedido_id is None for pedido_id in ids):
        raise ValueError("Hay pedidos sin identificador.")

    if len(ids) != len(set(ids)):
        raise ValueError("Hay identificadores de pedido duplicados.")

    promesas = []

    for pedido in sorted(
        pedidos,
        key=lambda registro: registro["SalesOrderID"],
    ):
        fecha_pedido = pedido["OrderDate"]

        if fecha_pedido is None:
            raise ValueError(
                f"El pedido {pedido['SalesOrderID']} "
                "no tiene fecha de creación."
            )

        fecha_comprometida = (
            fecha_pedido.date()
            + timedelta(days=DIAS_COMPROMISO)
        )

        promesas.append({
            "SalesOrderID": pedido["SalesOrderID"],
            "OrderDate": fecha_pedido.date().isoformat(),
            "PromisedDeliveryDate": fecha_comprometida.isoformat(),
            "CommitmentDays": DIAS_COMPROMISO,
            "DayType": "CALENDARIO",
            "RuleID": REGLA_ID,
            "IsSynthetic": 1,
        })

    # Comprobaciones antes de guardar.
    if len(promesas) != len(pedidos):
        raise ValueError(
            "La cantidad de promesas no coincide con los pedidos."
        )

    if any(
        promesa["PromisedDeliveryDate"] < promesa["OrderDate"]
        for promesa in promesas
    ):
        raise ValueError(
            "Se encontró una promesa anterior al pedido."
        )

    CARPETA_SALIDA.mkdir(
        parents=True,
        exist_ok=True,
    )

    ruta_promesas = (
        CARPETA_SALIDA / "promesas_entrega_v1.csv"
    )

    columnas_salida = [
        "SalesOrderID",
        "OrderDate",
        "PromisedDeliveryDate",
        "CommitmentDays",
        "DayType",
        "RuleID",
        "IsSynthetic",
    ]

    with ruta_promesas.open(
        mode="w",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:
        escritor = csv.DictWriter(
            archivo,
            fieldnames=columnas_salida,
        )

        escritor.writeheader()
        escritor.writerows(promesas)

    politica = {
        "regla_id": REGLA_ID,
        "version": 1,
        "origen": "SUPUESTO_DE_SIMULACION",
        "descripcion": (
            "Entrega completa dentro de los 14 días calendario "
            "posteriores a la fecha del pedido."
        ),
        "dias_compromiso": DIAS_COMPROMISO,
        "tipo_dias": "CALENDARIO",
        "fecha_base": "OrderDate",
        "limite": "Final del día de PromisedDeliveryDate",
        "alcance": "Todos los pedidos de la extracción",
        "usa_shipdate_para_definir_promesa": False,
        "reemplaza_duedate_original": False,
        "nota": (
            "No representa una política real de AdventureWorks. "
            "No permite calcular cumplimiento hasta disponer "
            "de entregas y una fecha de corte."
        ),
    }

    ruta_politica = (
        CARPETA_SALIDA / "politica_entrega_v1.json"
    )

    with ruta_politica.open(
        mode="w",
        encoding="utf-8",
    ) as archivo:
        json.dump(
            politica,
            archivo,
            ensure_ascii=False,
            indent=2,
        )

        archivo.write("\n")

    print(f"Pedidos originales: {len(pedidos):,}")
    print(f"Promesas generadas: {len(promesas):,}")
    print(f"Plazo: {DIAS_COMPROMISO} días calendario")
    print(f"Regla: {REGLA_ID}")

    print("\nPrimeras tres promesas:")

    for promesa in promesas[:3]:
        print(
            f"Pedido {promesa['SalesOrderID']} | "
            f"Creación: {promesa['OrderDate']} | "
            f"Compromiso: {promesa['PromisedDeliveryDate']}"
        )

    print("\nArchivos generados:")
    print(ruta_promesas)
    print(ruta_politica)

    print("\nRESULTADO FINAL")
    print("Compromisos simulados generados correctamente.")
    print("Los archivos originales no fueron modificados.")

    return 0


if __name__ == "__main__":
    sys.exit(main())