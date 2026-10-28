import getpass
import sys

import pyodbc


SERVIDOR = "localhost"
BASE_DATOS = "PortfolioPedidos"


def valor_odbc(texto):
    """Protege valores con caracteres especiales."""
    return "{" + texto.replace("}", "}}") + "}"


def main():
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
        print(
            "Falta Microsoft ODBC Driver 18 o 17 "
            "para SQL Server."
        )
        return 1

    print("PRUEBA DE CONEXIÓN")
    print(f"Servidor: {SERVIDOR}")
    print(f"Base: {BASE_DATOS}")
    print(f"Controlador: {controlador}")

    usuario = input("\nUsuario de SQL Server: ").strip()
    contrasena = getpass.getpass(
        "Contraseña de SQL Server: "
    )

    if not usuario or not contrasena:
        print("Debes proporcionar usuario y contraseña.")
        return 1

    conexion_texto = (
        f"DRIVER={valor_odbc(controlador)};"
        f"SERVER={valor_odbc(SERVIDOR)};"
        f"DATABASE={valor_odbc(BASE_DATOS)};"
        f"UID={valor_odbc(usuario)};"
        f"PWD={valor_odbc(contrasena)};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )

    conexion = None

    try:
        conexion = pyodbc.connect(
            conexion_texto,
            timeout=10,
        )

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT
                DB_NAME() AS BaseActual,
                ORIGINAL_LOGIN() AS UsuarioConexion;
        """)

        fila = cursor.fetchone()

        print("\nCONEXIÓN SATISFACTORIA")
        print(f"Base actual: {fila[0]}")
        print(f"Usuario conectado: {fila[1]}")

        cursor.execute("""
            SELECT name
            FROM sys.schemas
            WHERE name IN (
                'stg', 'core', 'analytics', 'audit'
            )
            ORDER BY name;
        """)

        encontrados = {
            fila[0]
            for fila in cursor.fetchall()
        }

        esperados = {
            "stg", "core", "analytics", "audit"
        }

        print(
            "Esquemas encontrados:",
            ", ".join(sorted(encontrados)),
        )

        if encontrados != esperados:
            print(
                "Faltan esquemas. Revisa la ejecución "
                "de 03_crear_base.sql."
            )
            return 1

        print("Estructura inicial confirmada.")
        return 0

    except pyodbc.Error as error:
        print("\nNO SE PUDO COMPLETAR LA PRUEBA")
        print(f"Detalle: {error}")
        return 1

    finally:
        if conexion is not None:
            conexion.close()


if __name__ == "__main__":
    sys.exit(main())