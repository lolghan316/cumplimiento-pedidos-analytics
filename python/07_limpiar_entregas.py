import csv
import json
import runpy

from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent.parent
ENTRADA = (
    PROYECTO / "data" / "incoming"
    / "entregas_recibidas_v1.csv"
)
SALIDA = PROYECTO / "data" / "processed"
CORTE = date(2025, 6, 29)

CONFIG = runpy.run_path(
    str(PROYECTO / "python" / "02_validar_tipos.py")
)

cargar = CONFIG["cargar_archivo"]
COLUMNAS = CONFIG["COLUMNAS"]

CAMPOS = [
    "EventID", "SalesOrderID", "SalesOrderDetailID",
    "ProductID", "DeliveryDate", "DeliveredQty",
    "IsSynthetic",
]


def guardar(nombre, registros, columnas):
    with (SALIDA / nombre).open(
        "w", encoding="utf-8-sig", newline=""
    ) as archivo:
        escritor = csv.DictWriter(
            archivo, fieldnames=columnas
        )
        escritor.writeheader()
        escritor.writerows(registros)


def main(carpeta_salida=None):
    global SALIDA

    if carpeta_salida is not None:
        SALIDA = Path(carpeta_salida)
        
    pedidos, _, _ = cargar(
        "pedidos.csv", COLUMNAS["pedidos.csv"]
    )
    lineas, _, _ = cargar(
        "lineas_pedido.csv", COLUMNAS["lineas_pedido.csv"]
    )
    productos, _, _ = cargar(
        "productos.csv", COLUMNAS["productos.csv"]
    )

    pedidos_id = {p["SalesOrderID"]: p for p in pedidos}
    lineas_id = {
        (l["SalesOrderID"], l["SalesOrderDetailID"]): l
        for l in lineas
    }
    productos_id = {p["ProductID"] for p in productos}

    with ENTRADA.open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        lector = csv.DictReader(archivo)

        if lector.fieldnames != CAMPOS:
            raise ValueError("Encabezados de entrada incorrectos.")

        originales = list(lector)

    # Revisar estructura antes de procesar.
    for numero, fila in enumerate(originales, start=1):
        if None in fila or any(v is None for v in fila.values()):
            raise ValueError(
                f"Fila {numero}: número incorrecto de campos."
            )

    bitacora = []
    cuarentena = []
    candidatos = []

    def registrar(numero, evento, regla, accion, antes="", despues=""):
        bitacora.append({
            "SourceRow": numero,
            "EventID": evento,
            "Rule": regla,
            "Action": accion,
            "Before": antes,
            "After": despues,
        })

    def rechazar(numero, original, reglas):
        cuarentena.append({
            "SourceRow": numero,
            **original,
            "Reasons": "|".join(reglas),
        })

        for regla in reglas:
            registrar(
                numero,
                original["EventID"].strip(),
                regla,
                "CUARENTENA",
            )

    # Primera pasada: normalización y validación individual.
    for numero, original in enumerate(originales, start=1):
        fila = original.copy()
        errores = []

        for campo in [
            "EventID", "SalesOrderID",
            "SalesOrderDetailID", "ProductID",
        ]:
            normalizado = fila[campo].strip()

            if normalizado != fila[campo]:
                registrar(
                    numero, fila["EventID"].strip(),
                    f"ESPACIOS_{campo}", "NORMALIZAR",
                    fila[campo], normalizado,
                )

            fila[campo] = normalizado

        if not fila["EventID"]:
            errores.append("EVENT_ID_VACIO")

        for campo in [
            "SalesOrderID", "SalesOrderDetailID",
            "ProductID", "DeliveredQty", "IsSynthetic",
        ]:
            try:
                fila[campo] = int(fila[campo])
            except ValueError:
                errores.append(f"ENTERO_INVALIDO_{campo}")

        texto_fecha = fila["DeliveryDate"]
        fecha = None

        if not texto_fecha:
            errores.append("FECHA_VACIA")
        else:
            for formato in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    fecha = datetime.strptime(
                        texto_fecha, formato
                    ).date()
                    break
                except ValueError:
                    continue

            if fecha is None:
                errores.append("FECHA_INVALIDA")
            else:
                fila["DeliveryDate"] = fecha.isoformat()

                if texto_fecha != fila["DeliveryDate"]:
                    registrar(
                        numero, fila["EventID"],
                        "FORMATO_FECHA", "NORMALIZAR",
                        texto_fecha, fila["DeliveryDate"],
                    )

                if fecha > CORTE:
                    errores.append("FECHA_POSTERIOR_AL_CORTE")

        if isinstance(fila["DeliveredQty"], int):
            if fila["DeliveredQty"] <= 0:
                errores.append("CANTIDAD_NO_POSITIVA")

        if isinstance(fila["ProductID"], int):
            if fila["ProductID"] not in productos_id:
                errores.append("PRODUCTO_INEXISTENTE")

        pedido = pedidos_id.get(fila["SalesOrderID"])
        clave = (
            fila["SalesOrderID"],
            fila["SalesOrderDetailID"],
        )
        linea = lineas_id.get(clave)

        if pedido is None:
            errores.append("PEDIDO_INEXISTENTE")
        elif fecha is not None:
            if fecha <= pedido["ShipDate"].date():
                errores.append("ENTREGA_NO_POSTERIOR_A_DESPACHO")

        if linea is None:
            errores.append("LINEA_INEXISTENTE")
        else:
            if fila["ProductID"] != linea["ProductID"]:
                errores.append("PRODUCTO_NO_COINCIDE_CON_LINEA")

        if fila["IsSynthetic"] != 1:
            errores.append("MARCA_SINTETICA_INVALIDA")

        if errores:
            rechazar(numero, original, errores)
        else:
            candidatos.append((numero, original, fila))

    # Segunda pasada: duplicados y conflictos de EventID.
    grupos = defaultdict(list)

    for elemento in candidatos:
        grupos[elemento[2]["EventID"]].append(elemento)

    unicos = []

    for evento_id, grupo in grupos.items():
        firmas = {
            tuple(elemento[2][c] for c in CAMPOS)
            for elemento in grupo
        }

        if len(firmas) > 1:
            for numero, original, fila in grupo:
                rechazar(
                    numero, original,
                    ["EVENT_ID_CONTRADICTORIO"],
                )
            continue

        unicos.append(grupo[0])

        for numero, original, fila in grupo[1:]:
            registrar(
                numero, evento_id,
                "DUPLICADO_EXACTO", "RETIRAR_COPIA",
            )

    # Tercera pasada: acumulados de cantidad por línea.
    por_linea = defaultdict(list)

    for elemento in unicos:
        fila = elemento[2]
        clave = (
            fila["SalesOrderID"],
            fila["SalesOrderDetailID"],
        )
        por_linea[clave].append(elemento)

    aceptadas = []

    for clave, grupo in por_linea.items():
        entregado = sum(
            elemento[2]["DeliveredQty"]
            for elemento in grupo
        )

        if entregado > lineas_id[clave]["OrderQty"]:
            for numero, original, fila in grupo:
                rechazar(
                    numero, original,
                    ["ACUMULADO_SUPERA_CANTIDAD_PEDIDA"],
                )
        else:
            for numero, original, fila in grupo:
                aceptadas.append({
                    "SourceRow": numero,
                    **fila,
                })

    acciones = Counter(
        r["Action"] for r in bitacora
    )

    retiradas = acciones["RETIRAR_COPIA"]

    if (
        len(aceptadas) + len(cuarentena) + retiradas
        != len(originales)
    ):
        raise ValueError("No concilian las disposiciones de filas.")

    SALIDA.mkdir(parents=True, exist_ok=True)

    guardar(
        "entregas_aceptadas_v1.csv",
        sorted(
            aceptadas,
            key=lambda r: (
                r["SalesOrderID"],
                r["SalesOrderDetailID"],
                r["DeliveryDate"],
                r["EventID"],
            ),
        ),
        ["SourceRow"] + CAMPOS,
    )

    guardar(
        "entregas_cuarentena_v1.csv",
        cuarentena,
        ["SourceRow"] + CAMPOS + ["Reasons"],
    )

    guardar(
        "bitacora_calidad_v1.csv",
        bitacora,
        [
            "SourceRow", "EventID", "Rule",
            "Action", "Before", "After",
        ],
    )

    pedidos_revision = sorted({
        int(r["SalesOrderID"])
        for r in cuarentena
        if r["SalesOrderID"].strip().isdigit()
        and int(r["SalesOrderID"]) in pedidos_id
    })

    guardar(
        "pedidos_con_revision_v1.csv",
        [{"SalesOrderID": p} for p in pedidos_revision],
        ["SalesOrderID"],
    )

    resumen = {
        "filas_entrada": len(originales),
        "filas_aceptadas": len(aceptadas),
        "filas_cuarentena": len(cuarentena),
        "copias_retiradas": retiradas,
        "normalizaciones": acciones["NORMALIZAR"],
        "pedidos_con_revision": len(pedidos_revision),
        "incidencias_por_regla": dict(Counter(
            r["Rule"] for r in bitacora
        )),
        "conciliacion_filas": True,
        "fecha_corte": CORTE.isoformat(),
        "nota": (
            "Las incidencias pueden superar las filas afectadas. "
            "No se consultó la verdad de evaluación. "
            "Los pedidos con cuarentena requieren evaluar "
            "la incertidumbre antes de publicar su OTIF."
        ),
    }

    with (SALIDA / "resumen_limpieza_v1.json").open(
        "w", encoding="utf-8"
    ) as archivo:
        json.dump(
            resumen, archivo,
            ensure_ascii=False, indent=2,
        )
        archivo.write("\n")

    print(json.dumps(
        resumen, ensure_ascii=False, indent=2
    ))
    print("\nProceso terminado. Revisar cuarentena y bitácora.")


if __name__ == "__main__":
    main()