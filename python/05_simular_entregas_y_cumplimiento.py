import csv
import json
import random
import runpy

from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent.parent
SALIDA = PROYECTO / "data" / "synthetic"

CONFIG = runpy.run_path(
    str(PROYECTO / "python" / "02_validar_tipos.py")
)

COLUMNAS = CONFIG["COLUMNAS"]
cargar_archivo = CONFIG["cargar_archivo"]

SEMILLA = 42
FECHA_CORTE = date(2025, 6, 29)


def guardar_csv(nombre, registros, columnas):
    ruta = SALIDA / nombre

    with ruta.open(
        "w", encoding="utf-8-sig", newline=""
    ) as archivo:
        escritor = csv.DictWriter(
            archivo, fieldnames=columnas
        )
        escritor.writeheader()
        escritor.writerows(registros)

    return ruta


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def main():
    print("SIMULACIÓN DE ENTREGAS Y CUMPLIMIENTO\n")

    pedidos, _, _ = cargar_archivo(
        "pedidos.csv", COLUMNAS["pedidos.csv"]
    )
    lineas, _, _ = cargar_archivo(
        "lineas_pedido.csv", COLUMNAS["lineas_pedido.csv"]
    )

    # Leer compromisos generados por el script 04.
    ruta_promesas = SALIDA / "promesas_entrega_v1.csv"

    with ruta_promesas.open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        filas_promesas = list(csv.DictReader(archivo))

    promesas = {
        int(fila["SalesOrderID"]): date.fromisoformat(
            fila["PromisedDeliveryDate"]
        )
        for fila in filas_promesas
    }

    pedidos_por_id = {
        p["SalesOrderID"]: p for p in pedidos
    }

    exigir(
        len(pedidos_por_id) == len(pedidos),
        "Hay pedidos duplicados.",
    )
    exigir(
        len(promesas) == len(filas_promesas),
        "Hay promesas duplicadas.",
    )
    exigir(
        set(promesas) == set(pedidos_por_id),
        "Las promesas no corresponden exactamente a los pedidos.",
    )

    lineas_por_pedido = defaultdict(list)
    cantidades_pedidas = {}

    for linea in lineas:
        pedido_id = linea["SalesOrderID"]
        clave = (
            pedido_id,
            linea["SalesOrderDetailID"],
        )

        exigir(
            pedido_id in pedidos_por_id,
            f"Línea sin pedido: {clave}",
        )
        exigir(
            clave not in cantidades_pedidas,
            f"Línea duplicada: {clave}",
        )
        exigir(
            linea["OrderQty"] is not None
            and linea["OrderQty"] > 0,
            f"Cantidad inválida: {clave}",
        )

        cantidades_pedidas[clave] = linea["OrderQty"]
        lineas_por_pedido[pedido_id].append(linea)

    exigir(
        set(lineas_por_pedido) == set(pedidos_por_id),
        "Hay pedidos sin líneas.",
    )

    eventos = []
    escenarios = {}
    contadores = Counter()

    for pedido_id in sorted(pedidos_por_id):
        pedido = pedidos_por_id[pedido_id]

        exigir(
            pedido["OrderDate"] is not None
            and pedido["ShipDate"] is not None,
            f"Faltan fechas en el pedido {pedido_id}",
        )

        fecha_pedido = pedido["OrderDate"].date()
        fecha_despacho = pedido["ShipDate"].date()
        compromiso = promesas[pedido_id]

        exigir(
            fecha_despacho >= fecha_pedido,
            f"Despacho anterior al pedido {pedido_id}",
        )
        exigir(
            compromiso >= fecha_pedido,
            f"Compromiso anterior al pedido {pedido_id}",
        )

        # Semilla por pedido: su escenario no depende
        # del orden en que aparezca en el archivo.
        azar = random.Random(SEMILLA + pedido_id)
        seleccion = azar.random()

        if seleccion < 0.70:
            escenario = "HABITUAL"
        elif seleccion < 0.90:
            escenario = "DEMORA"
        else:
            escenario = "DIVIDIDO"

        detalle = sorted(
            lineas_por_pedido[pedido_id],
            key=lambda x: x["SalesOrderDetailID"],
        )

        unidades_pedido = sum(
            linea["OrderQty"] for linea in detalle
        )

        # Un pedido de una sola unidad no puede dividirse.
        if escenario == "DIVIDIDO" and unidades_pedido == 1:
            escenario = "DEMORA"

        fecha_base = (
            fecha_despacho
            + timedelta(days=azar.randint(1, 4))
        )

        if escenario == "DEMORA":
            fecha_primera = max(
                fecha_base,
                compromiso
                + timedelta(days=azar.randint(1, 7)),
            )
        else:
            fecha_primera = fecha_base

        fecha_segunda = max(
            fecha_primera
            + timedelta(days=azar.randint(2, 5)),
            compromiso
            + timedelta(days=azar.randint(1, 5)),
        )

        escenarios[pedido_id] = escenario
        contadores[escenario] += 1

        # En pedidos divididos, entregar aproximadamente
        # la mitad de las unidades en la primera fecha.
        restante_primera = unidades_pedido // 2

        for linea in detalle:
            cantidad = linea["OrderQty"]
            linea_id = linea["SalesOrderDetailID"]

            if escenario == "DIVIDIDO":
                primera_cantidad = min(
                    cantidad, restante_primera
                )
                restante_primera -= primera_cantidad

                entregas = [
                    (1, primera_cantidad, fecha_primera),
                    (
                        2,
                        cantidad - primera_cantidad,
                        fecha_segunda,
                    ),
                ]
            else:
                entregas = [
                    (1, cantidad, fecha_primera)
                ]

            for numero, unidades, fecha in entregas:
                if unidades == 0:
                    continue

                eventos.append({
                    "EventID": f"E-{pedido_id}-{linea_id}-{numero}",
                    "SalesOrderID": pedido_id,
                    "SalesOrderDetailID": linea_id,
                    "ProductID": linea["ProductID"],
                    "DeliveryDate": fecha.isoformat(),
                    "DeliveredQty": unidades,
                    "IsSynthetic": 1,
                })

    # Validar todo el escenario antes de guardarlo.
    cantidades_entregadas = defaultdict(int)
    cantidades_al_corte = defaultdict(int)
    ultima_entrega_al_corte = {}

    ids_eventos = set()
    eventos_observados = []

    for evento in eventos:
        evento_id = evento["EventID"]

        exigir(
            evento_id not in ids_eventos,
            f"Evento duplicado: {evento_id}",
        )
        ids_eventos.add(evento_id)

        pedido_id = evento["SalesOrderID"]
        clave = (
            pedido_id,
            evento["SalesOrderDetailID"],
        )
        fecha = date.fromisoformat(
            evento["DeliveryDate"]
        )
        unidades = evento["DeliveredQty"]

        exigir(
            clave in cantidades_pedidas,
            f"Entrega sin línea: {clave}",
        )
        exigir(
            unidades > 0,
            f"Entrega con cantidad inválida: {evento_id}",
        )
        exigir(
            fecha > pedidos_por_id[pedido_id]["ShipDate"].date(),
            f"Entrega no posterior al despacho: {evento_id}",
        )

        cantidades_entregadas[clave] += unidades

        if fecha <= FECHA_CORTE:
            eventos_observados.append(evento)
            cantidades_al_corte[clave] += unidades

            ultima_entrega_al_corte[pedido_id] = max(
                fecha,
                ultima_entrega_al_corte.get(
                    pedido_id, fecha
                ),
            )

    exigir(
        dict(cantidades_entregadas) == cantidades_pedidas,
        "Las entregas no concilian con las cantidades pedidas.",
    )

    # Construir el análisis usando solo información al corte.
    resumen = []

    for pedido_id in sorted(pedidos_por_id):
        pedido = pedidos_por_id[pedido_id]

        if pedido["OrderDate"].date() > FECHA_CORTE:
            continue

        detalle = lineas_por_pedido[pedido_id]
        compromiso = promesas[pedido_id]

        unidades_pedidas = sum(
            linea["OrderQty"] for linea in detalle
        )

        unidades_recibidas = sum(
            cantidades_al_corte[
                (pedido_id, linea["SalesOrderDetailID"])
            ]
            for linea in detalle
        )

        completo = all(
            cantidades_al_corte[
                (pedido_id, linea["SalesOrderDetailID"])
            ] == linea["OrderQty"]
            for linea in detalle
        )

        elegible = compromiso <= FECHA_CORTE

        fecha_completa = (
            ultima_entrega_al_corte[pedido_id]
            if completo else None
        )

        a_tiempo = (
            fecha_completa <= compromiso
            if completo else False
        )

        if completo:
            estado = (
                "COMPLETO_A_TIEMPO"
                if a_tiempo else "COMPLETO_TARDE"
            )
        elif elegible:
            estado = "PENDIENTE_VENCIDO"
        else:
            estado = "PENDIENTE_EN_PLAZO"

        resumen.append({
            "SalesOrderID": pedido_id,
            "TerritoryID": pedido["TerritoryID"],
            "OrderDate": pedido["OrderDate"].date().isoformat(),
            "PromisedDeliveryDate": compromiso.isoformat(),
            "CutoffDate": FECHA_CORTE.isoformat(),
            "OrderedQty": unidades_pedidas,
            "DeliveredQtyAtCutoff": unidades_recibidas,
            "PendingQtyAtCutoff": (
                unidades_pedidas - unidades_recibidas
            ),
            "CompleteDeliveryDateAtCutoff": (
                fecha_completa.isoformat()
                if fecha_completa else ""
            ),
            "StatusAtCutoff": estado,
            "EligibleOTIF": int(elegible),
            "OTIF": (
                int(completo and a_tiempo)
                if elegible else ""
            ),
            "IsSynthetic": 1,
        })

    exigir(bool(resumen), "No hay pedidos al corte.")

    elegibles = sum(
        fila["EligibleOTIF"] for fila in resumen
    )
    cumplidos = sum(
        fila["OTIF"]
        for fila in resumen
        if fila["EligibleOTIF"] == 1
    )

    estados = Counter(
        fila["StatusAtCutoff"] for fila in resumen
    )

    SALIDA.mkdir(parents=True, exist_ok=True)

    columnas_eventos = [
        "EventID",
        "SalesOrderID",
        "SalesOrderDetailID",
        "ProductID",
        "DeliveryDate",
        "DeliveredQty",
        "IsSynthetic",
    ]

    guardar_csv(
        "entregas_escenario_completo_v1.csv",
        eventos,
        columnas_eventos,
    )

    guardar_csv(
        "entregas_observadas_al_corte_v1.csv",
        eventos_observados,
        columnas_eventos,
    )

    guardar_csv(
        "cumplimiento_pedidos_al_corte_v1.csv",
        resumen,
        list(resumen[0]),
    )

    # Esta etiqueta es información del generador:
    # no debe emplearse como una causa observada.
    guardar_csv(
        "asignacion_escenarios_v1.csv",
        [
            {
                "SalesOrderID": pedido_id,
                "SimulationScenario": escenario,
            }
            for pedido_id, escenario
            in sorted(escenarios.items())
        ],
        ["SalesOrderID", "SimulationScenario"],
    )

    metadatos = {
        "naturaleza": "SIMULACION, NO RESULTADOS REALES",
        "version": 1,
        "semilla": SEMILLA,
        "fecha_corte_inclusiva": FECHA_CORTE.isoformat(),
        "precision_temporal": "DIA",
        "pesos_iniciales": {
            "habitual": 0.70,
            "demora": 0.20,
            "dividido": 0.10,
        },
        "excepcion": (
            "Pedidos divididos de una unidad pasan a demora."
        ),
        "supuestos": [
            "No hay cancelaciones ni devoluciones.",
            "Todos los pedidos se completan eventualmente.",
            "Los pendientes solo se evalúan a la fecha de corte.",
            "La recepción se registra el mismo día de entrega.",
            "No se simulan entregas dañadas o rechazadas.",
        ],
        "advertencias": [
            "No usar eventos futuros en el análisis al corte.",
            "No interpretar etiquetas del generador como causas.",
            "No se han introducido errores de calidad todavía.",
            "El CSV de cumplimiento es referencia de validación; "
            "después se reconstruirá desde eventos en SQL.",
        ],
        "pedidos_analizados": len(resumen),
        "eventos_completos": len(eventos),
        "eventos_observados": len(eventos_observados),
        "escenarios_asignados": dict(contadores),
        "estados_al_corte": dict(estados),
        "pedidos_elegibles_otif": elegibles,
        "pedidos_cumplen_otif": cumplidos,
        "otif_porcentaje": (
            round(100 * cumplidos / elegibles, 4)
            if elegibles else None
        ),
    }

    with (SALIDA / "resumen_simulacion_v1.json").open(
        "w", encoding="utf-8"
    ) as archivo:
        json.dump(
            metadatos, archivo,
            ensure_ascii=False, indent=2,
        )
        archivo.write("\n")

    print(f"Pedidos originales: {len(pedidos):,}")
    print(f"Líneas originales: {len(lineas):,}")
    print(f"Eventos generados: {len(eventos):,}")
    print(f"Eventos observados al corte: {len(eventos_observados):,}")
    print(f"Fecha de corte: {FECHA_CORTE}")

    print("\nEstados al corte:")
    for estado, cantidad in sorted(estados.items()):
        print(f"  {estado}: {cantidad:,}")

    print(f"\nPedidos elegibles para OTIF: {elegibles:,}")
    print(f"Pedidos que cumplen OTIF: {cumplidos:,}")

    if elegibles:
        print(
            f"OTIF SIMULADO: "
            f"{100 * cumplidos / elegibles:.2f}%"
        )
    else:
        print("OTIF: sin pedidos elegibles.")

    print("\nVALIDACIÓN SATISFACTORIA")
    print("Cantidades entregadas conciliadas por línea.")
    print("Identificadores de eventos únicos.")
    print("Entregas posteriores al despacho.")
    print("Análisis limitado a la fecha de corte.")
    print(f"Archivos guardados en: {SALIDA}")


if __name__ == "__main__":
    main()