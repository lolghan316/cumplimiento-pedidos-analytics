import csv
import json

from collections import Counter
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent.parent
PROCESADOS = PROYECTO / "data" / "processed"
EVALUACION = PROYECTO / "evaluation"
VERDAD = EVALUACION / "ground_truth"

CAMPOS = [
    "EventID", "SalesOrderID", "SalesOrderDetailID",
    "ProductID", "DeliveryDate", "DeliveredQty",
    "IsSynthetic",
]

# Cada caso tiene una alerta principal esperada.
REGLAS = {
    "DUPLICADO_EXACTO": (
        "DUPLICADO_EXACTO", "RETIRAR_COPIA"
    ),
    "FECHA_VACIA": (
        "FECHA_VACIA", "CUARENTENA"
    ),
    "CANTIDAD_NEGATIVA": (
        "CANTIDAD_NO_POSITIVA", "CUARENTENA"
    ),
    "PRODUCTO_INEXISTENTE": (
        "PRODUCTO_INEXISTENTE", "CUARENTENA"
    ),
    "FECHA_FORMATO_ALTERNATIVO": (
        "FORMATO_FECHA", "NORMALIZAR"
    ),
    "ESPACIOS_EN_IDENTIFICADOR": (
        "ESPACIOS_EventID", "NORMALIZAR"
    ),
}


def leer(ruta):
    with ruta.open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        return list(csv.DictReader(archivo))


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def main():
    manifiesto = leer(
        VERDAD / "manifiesto_errores_v1.csv"
    )
    bitacora = leer(
        PROCESADOS / "bitacora_calidad_v1.csv"
    )
    aceptadas = leer(
        PROCESADOS / "entregas_aceptadas_v1.csv"
    )
    cuarentena = leer(
        PROCESADOS / "entregas_cuarentena_v1.csv"
    )
    referencia = leer(
        PROYECTO / "data" / "synthetic"
        / "entregas_observadas_al_corte_v1.csv"
    )

    alertas_principales = set()
    alertas_esperadas = set()
    ids_cuarentena_esperados = set()
    ids_duplicados_esperados = set()
    casos_por_tipo = Counter()

    for caso in manifiesto:
        evento = caso["EventIDOriginal"]
        tipo = caso["TipoCaso"]
        regla, accion = REGLAS[tipo]

        alerta = (evento, regla, accion)

        alertas_principales.add(alerta)
        alertas_esperadas.add(alerta)
        casos_por_tipo[tipo] += 1

        if accion == "CUARENTENA":
            ids_cuarentena_esperados.add(evento)

        if accion == "RETIRAR_COPIA":
            ids_duplicados_esperados.add(evento)

        # Consecuencia adicional válida del producto incorrecto.
        if tipo == "PRODUCTO_INEXISTENTE":
            alertas_esperadas.add((
                evento,
                "PRODUCTO_NO_COINCIDE_CON_LINEA",
                "CUARENTENA",
            ))

    alertas_observadas = {
        (
            fila["EventID"],
            fila["Rule"],
            fila["Action"],
        )
        for fila in bitacora
    }

    verdaderas = alertas_observadas & alertas_esperadas
    adicionales = alertas_observadas - alertas_esperadas
    omitidas = alertas_esperadas - alertas_observadas

    casos_detectados = len(
        alertas_principales & alertas_observadas
    )

    ids_cuarentena_observados = {
        fila["EventID"].strip()
        for fila in cuarentena
    }

    ids_duplicados_observados = {
        fila["EventID"]
        for fila in bitacora
        if fila["Action"] == "RETIRAR_COPIA"
    }

    referencia_por_id = {
        fila["EventID"]: fila
        for fila in referencia
    }
    aceptadas_por_id = {
        fila["EventID"]: fila
        for fila in aceptadas
    }

    exigir(
        len(referencia_por_id) == len(referencia),
        "La referencia tiene EventID repetidos.",
    )
    exigir(
        len(aceptadas_por_id) == len(aceptadas),
        "La salida aceptada tiene EventID repetidos.",
    )

    ids_aceptados_esperados = (
        set(referencia_por_id)
        - ids_cuarentena_esperados
    )

    ids_faltantes = (
        ids_aceptados_esperados
        - set(aceptadas_por_id)
    )
    ids_sobrantes = (
        set(aceptadas_por_id)
        - ids_aceptados_esperados
    )

    diferencias_valor = []

    for evento in sorted(
        ids_aceptados_esperados & set(aceptadas_por_id)
    ):
        for campo in CAMPOS:
            esperado = referencia_por_id[evento][campo]
            observado = aceptadas_por_id[evento][campo]

            if esperado != observado:
                diferencias_valor.append({
                    "EventID": evento,
                    "Campo": campo,
                    "Esperado": esperado,
                    "Observado": observado,
                })

    comprobaciones = {
        "todos_los_casos_detectados": (
            casos_detectados == len(manifiesto)
        ),
        "sin_alertas_adicionales": not adicionales,
        "sin_alertas_omitidas": not omitidas,
        "sin_alertas_repetidas": (
            len(alertas_observadas) == len(bitacora)
        ),
        "cuarentena_correcta": (
            ids_cuarentena_observados
            == ids_cuarentena_esperados
            and len(cuarentena)
            == len(ids_cuarentena_esperados)
        ),
        "duplicados_correctos": (
            ids_duplicados_observados
            == ids_duplicados_esperados
            and sum(
                fila["Action"] == "RETIRAR_COPIA"
                for fila in bitacora
            ) == len(ids_duplicados_esperados)
        ),
        "ids_aceptados_correctos": (
            not ids_faltantes and not ids_sobrantes
        ),
        "valores_aceptados_correctos": (
            not diferencias_valor
        ),
    }

    total_alertas = len(alertas_observadas)
    total_esperadas = len(alertas_esperadas)

    resumen = {
        "alcance": "Evaluación del experimento controlado v1",
        "casos_introducidos": len(manifiesto),
        "casos_detectados": casos_detectados,
        "casos_por_tipo": dict(casos_por_tipo),
        "alertas_esperadas": total_esperadas,
        "alertas_observadas": total_alertas,
        "alertas_correctas": len(verdaderas),
        "alertas_adicionales": len(adicionales),
        "alertas_omitidas": len(omitidas),
        "precision_alertas": (
            len(verdaderas) / total_alertas
            if total_alertas else None
        ),
        "recuperacion_alertas": (
            len(verdaderas) / total_esperadas
            if total_esperadas else None
        ),
        "registros_aceptados": len(aceptadas),
        "ids_aceptados_faltantes": len(ids_faltantes),
        "ids_aceptados_sobrantes": len(ids_sobrantes),
        "diferencias_en_valores": len(diferencias_valor),
        "comprobaciones": comprobaciones,
        "evaluacion_satisfactoria": all(
            comprobaciones.values()
        ),
        "limitacion": (
            "Estos resultados solo describen los errores "
            "y registros de este experimento. No demuestran "
            "detección perfecta en datos desconocidos."
        ),
    }

    EVALUACION.mkdir(parents=True, exist_ok=True)

    with (EVALUACION / "resumen_evaluacion_v1.json").open(
        "w", encoding="utf-8"
    ) as archivo:
        json.dump(
            resumen, archivo,
            ensure_ascii=False, indent=2,
        )
        archivo.write("\n")

    # Guardar ejemplos de diferencias si las hubiera.
    detalles = {
        "alertas_adicionales": sorted(adicionales)[:20],
        "alertas_omitidas": sorted(omitidas)[:20],
        "ids_faltantes": sorted(ids_faltantes)[:20],
        "ids_sobrantes": sorted(ids_sobrantes)[:20],
        "diferencias_valor": diferencias_valor[:20],
    }

    with (EVALUACION / "detalle_evaluacion_v1.json").open(
        "w", encoding="utf-8"
    ) as archivo:
        json.dump(
            detalles, archivo,
            ensure_ascii=False, indent=2,
        )
        archivo.write("\n")

    print(json.dumps(
        resumen, ensure_ascii=False, indent=2
    ))

    if not resumen["evaluacion_satisfactoria"]:
        raise SystemExit(
            "Hay diferencias. Revisar detalle_evaluacion_v1.json."
        )

    print("\nEvaluación satisfactoria.")


if __name__ == "__main__":
    main()