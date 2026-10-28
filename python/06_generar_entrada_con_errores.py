import csv
import hashlib
import json
import random

from collections import Counter
from datetime import date
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent.parent

ORIGEN = (
    PROYECTO
    / "data"
    / "synthetic"
    / "entregas_observadas_al_corte_v1.csv"
)

ENTRADA = PROYECTO / "data" / "incoming"
EVALUACION = PROYECTO / "evaluation" / "ground_truth"

SEMILLA = 2026
CASOS_POR_TIPO = 100

TIPOS = [
    "DUPLICADO_EXACTO",
    "FECHA_VACIA",
    "CANTIDAD_NEGATIVA",
    "PRODUCTO_INEXISTENTE",
    "FECHA_FORMATO_ALTERNATIVO",
    "ESPACIOS_EN_IDENTIFICADOR",
]

COLUMNAS_ESPERADAS = [
    "EventID",
    "SalesOrderID",
    "SalesOrderDetailID",
    "ProductID",
    "DeliveryDate",
    "DeliveredQty",
    "IsSynthetic",
]


def leer_csv(ruta):
    with ruta.open(
        encoding="utf-8-sig",
        newline="",
    ) as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames
        registros = list(lector)

    return columnas, registros


def guardar_csv(ruta, registros, columnas):
    with ruta.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:
        escritor = csv.DictWriter(
            archivo,
            fieldnames=columnas,
        )
        escritor.writeheader()
        escritor.writerows(registros)


def guardar_json(ruta, contenido):
    with ruta.open(
        "w",
        encoding="utf-8",
    ) as archivo:
        json.dump(
            contenido,
            archivo,
            ensure_ascii=False,
            indent=2,
        )
        archivo.write("\n")


def sha256(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main():
    print("GENERACIÓN DE DATOS IMPERFECTOS\n")

    columnas, originales = leer_csv(ORIGEN)

    if columnas != COLUMNAS_ESPERADAS:
        raise ValueError(
            "Las columnas del archivo de entregas "
            "no coinciden con las esperadas."
        )

    minimo = CASOS_POR_TIPO * len(TIPOS)

    if len(originales) < minimo:
        raise ValueError(
            f"Se necesitan al menos {minimo} eventos."
        )

    ids = [
        registro["EventID"]
        for registro in originales
    ]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "El archivo original ya tiene EventID repetidos."
        )

    # Validar que los campos a modificar parten de valores
    # adecuados para este experimento controlado.
    for registro in originales:
        date.fromisoformat(registro["DeliveryDate"])

        if int(registro["DeliveredQty"]) <= 0:
            raise ValueError(
                "El archivo original contiene "
                "cantidades no positivas."
            )

        if registro["EventID"] != registro["EventID"].strip():
            raise ValueError(
                "El archivo original ya tiene espacios "
                "en EventID."
            )

    # Leer las claves de productos originales.
    # Este CSV no tiene encabezados.
    ruta_productos = (
        PROYECTO / "data" / "raw" / "productos.csv"
    )

    with ruta_productos.open(
        encoding="utf-8-sig",
        newline="",
    ) as archivo:
        ids_productos = {
            int(fila[0])
            for fila in csv.reader(archivo)
        }

    producto_inexistente = max(ids_productos) + 1000000

    if any(
        int(registro["ProductID"]) not in ids_productos
        for registro in originales
    ):
        raise ValueError(
            "El archivo original contiene productos desconocidos."
        )

    hash_original_antes = sha256(ORIGEN)

    # Copias independientes: no modificamos los originales.
    entrada = [
        registro.copy()
        for registro in originales
    ]

    azar = random.Random(SEMILLA)

    posiciones = azar.sample(
        range(len(originales)),
        minimo,
    )

    manifiesto = []

    for indice_tipo, tipo in enumerate(TIPOS):
        inicio = indice_tipo * CASOS_POR_TIPO
        fin = inicio + CASOS_POR_TIPO

        for posicion in posiciones[inicio:fin]:
            original = originales[posicion]
            modificado = entrada[posicion]

            if tipo == "DUPLICADO_EXACTO":
                entrada.append(original.copy())

                campo = "REGISTRO_COMPLETO"
                valor_original = "1 aparición"
                valor_introducido = "2 apariciones"
                tratamiento = "ELIMINAR_COPIA_EXACTA"

            elif tipo == "FECHA_VACIA":
                campo = "DeliveryDate"
                valor_original = original[campo]
                valor_introducido = ""
                modificado[campo] = valor_introducido
                tratamiento = "CUARENTENA"

            elif tipo == "CANTIDAD_NEGATIVA":
                campo = "DeliveredQty"
                valor_original = original[campo]
                valor_introducido = str(
                    -int(valor_original)
                )
                modificado[campo] = valor_introducido
                tratamiento = "CUARENTENA"

            elif tipo == "PRODUCTO_INEXISTENTE":
                campo = "ProductID"
                valor_original = original[campo]
                valor_introducido = str(producto_inexistente)
                modificado[campo] = valor_introducido
                tratamiento = "CUARENTENA"

            elif tipo == "FECHA_FORMATO_ALTERNATIVO":
                campo = "DeliveryDate"
                valor_original = original[campo]

                valor_introducido = (
                    date.fromisoformat(valor_original)
                    .strftime("%d/%m/%Y")
                )

                modificado[campo] = valor_introducido
                tratamiento = "NORMALIZAR_FECHA"

            else:
                campo = "EventID"
                valor_original = original[campo]
                valor_introducido = f"  {valor_original}  "
                modificado[campo] = valor_introducido
                tratamiento = "QUITAR_ESPACIOS_EXTERNOS"

            manifiesto.append({
                "EventIDOriginal": original["EventID"],
                "TipoCaso": tipo,
                "Campo": campo,
                "ValorOriginal": valor_original,
                "ValorIntroducido": valor_introducido,
                "TratamientoEsperado": tratamiento,
            })

    # Desordenar evita que todas las copias estén al final.
    azar.shuffle(entrada)

    esperados = len(originales) + CASOS_POR_TIPO

    if len(entrada) != esperados:
        raise ValueError(
            "El número final de registros es incorrecto."
        )

    conteos = Counter(
        caso["TipoCaso"]
        for caso in manifiesto
    )

    if any(
        conteos[tipo] != CASOS_POR_TIPO
        for tipo in TIPOS
    ):
        raise ValueError(
            "La cantidad de casos por tipo es incorrecta."
        )

    if len({
        caso["EventIDOriginal"]
        for caso in manifiesto
    }) != minimo:
        raise ValueError(
            "Se aplicaron varios casos al mismo evento."
        )

    ENTRADA.mkdir(parents=True, exist_ok=True)
    EVALUACION.mkdir(parents=True, exist_ok=True)

    ruta_entrada = ENTRADA / "entregas_recibidas_v1.csv"

    guardar_csv(
        ruta_entrada,
        entrada,
        COLUMNAS_ESPERADAS,
    )

    guardar_csv(
        EVALUACION / "manifiesto_errores_v1.csv",
        manifiesto,
        [
            "EventIDOriginal",
            "TipoCaso",
            "Campo",
            "ValorOriginal",
            "ValorIntroducido",
            "TratamientoEsperado",
        ],
    )

    # Contrato de la fuente: no revela dónde están los errores.
    contrato = {
        "fuente": "OPERADOR_LOGISTICO_SIMULADO",
        "version": 1,
        "naturaleza": "DATOS_SINTETICOS",
        "archivo": "entregas_recibidas_v1.csv",
        "codificacion": "UTF-8 con BOM",
        "separador": ",",
        "formatos_fecha_admitidos": [
            "AAAA-MM-DD",
            "DD/MM/AAAA",
        ],
        "interpretacion_fecha_con_barras": (
            "Día/mes/año, según contrato de esta fuente."
        ),
        "reglas": [
            "EventID debe estar informado.",
            "Los espacios externos en identificadores "
            "no forman parte de la clave.",
            "Las cantidades entregadas deben ser enteros positivos.",
            "ProductID debe existir en el maestro de productos.",
            "Las fechas ausentes no se completan por estimación.",
            "Duplicados exactamente iguales permiten conservar "
            "una sola aparición con trazabilidad.",
            "Un mismo EventID con valores contradictorios "
            "requiere revisión.",
        ],
    }

    guardar_json(
        ENTRADA / "contrato_fuente_v1.json",
        contrato,
    )

    hash_original_despues = sha256(ORIGEN)

    if hash_original_antes != hash_original_despues:
        raise ValueError(
            "El archivo original cambió durante la ejecución."
        )

    resumen = {
        "naturaleza": "EXPERIMENTO_CONTROLADO",
        "semilla": SEMILLA,
        "eventos_originales": len(originales),
        "filas_entrada": len(entrada),
        "eventos_seleccionados": len(manifiesto),
        "casos_por_tipo": dict(conteos),
        "copias_adicionales": CASOS_POR_TIPO,
        "sha256_origen": hash_original_antes,
        "sha256_entrada": sha256(ruta_entrada),
        "original_sin_modificaciones": True,
        "nota": (
            "El manifiesto y este resumen son para evaluación. "
            "El proceso de limpieza no debe utilizarlos "
            "para localizar ni corregir registros."
        ),
    }

    guardar_json(
        EVALUACION / "resumen_inyeccion_v1.json",
        resumen,
    )

    print(f"Eventos originales: {len(originales):,}")
    print(f"Filas del archivo imperfecto: {len(entrada):,}")
    print(f"Eventos seleccionados: {len(manifiesto):,}")

    print("\nCasos introducidos:")
    for tipo in TIPOS:
        print(f"  {tipo}: {conteos[tipo]}")

    print("\nVALIDACIÓN SATISFACTORIA")
    print("El archivo original conserva su huella SHA-256.")
    print("El registro de evaluación está separado de la entrada.")
    print(f"Entrada generada: {ruta_entrada}")


if __name__ == "__main__":
    main()