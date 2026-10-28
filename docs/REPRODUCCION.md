# Reproducir y operar

## Entorno de referencia

Windows, Python 3.13, SQL Server local, ODBC Driver 18, Power BI Desktop,
Excel con Power Query, Docker Desktop con n8n y una cuenta organizacional con SharePoint/Power Automate.
pyodbc 5.3.0 es la versión identificada en el entorno entregado.
SQL y aplicaciones Microsoft requieren instalación y configuración propias.
Los CSV permiten comprobar la limpieza sin instalar SQL Server.

Trabajar en una copia nueva; conservar intacto el proyecto original y su base.
Todos los comandos siguientes se ejecutan en PowerShell desde la carpeta del README.

~~~powershell
py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
~~~

## 1. Comprobar los datos incluidos

~~~powershell
./.venv/Scripts/python.exe python/01_inspeccionar_archivos.py
./.venv/Scripts/python.exe python/02_validar_tipos.py
./.venv/Scripts/python.exe python/03_validar_integridad.py
./.venv/Scripts/python.exe python/13_procesar_lote.py
./.venv/Scripts/python.exe python/08_evaluar_limpieza.py
~~~

13 crea una carpeta nueva en data/runs y no escribe en SQL. 08 evalúa los archivos de
data/processed incluidos, no la última carpeta de runs. Para evaluar una regeneración, ejecutar
07 antes de 08 en esta copia de trabajo.

No volver a exportar los CSV para la demostración incluida: ya tienen el formato esperado.
Para construir desde cero, usar SQL 01/02 sobre AdventureWorks2025 y exportar los cinco resultados
**sin encabezados**, UTF-8, coma separadora y punto decimal. 01 declara el orden de columnas.
Ejecutar Python 01, 02 y 03; luego 04, 05, 06, 07 y 08, en ese orden.
04–06 regeneran archivos sintéticos; no forman parte del botón rutinario de n8n.

## 2. Crear una base nueva para reproducir

No ejecutar la carga inicial 10 sobre una base ya poblada: el script la rechaza.
Si PortfolioPedidos ya es la base de trabajo del autor, conservarla y omitir esta instalación.

Alternar SSMS y PowerShell en este orden:

1. SSMS: sql/03_crear_base.sql.
2. PowerShell: python/09_probar_conexion_sql.py.
3. PowerShell: python/10_cargar_sql.py (crea tablas y carga inicial).
4. SSMS: sql/04_verificar_carga.sql.
5. SSMS: sql/05_crear_vistas_analiticas.sql y sql/06_validar_vistas.sql.
6. PowerShell: python/11_cargar_calidad_sql.py.
7. SSMS: sql/07_vistas_calidad.sql y sql/08_registro_publicaciones.sql.

Para ejecutar cada .py utilizar ./.venv/Scripts/python.exe seguido de su ruta.
Los scripts interactivos solicitan usuario y contraseña. localhost es el servidor, no el usuario.
Usar una cuenta de laboratorio; no guardar contraseñas en archivos.

## 3. Servicio y n8n

En una misma terminal PowerShell, configurar las variables y arrancar el servicio:

~~~powershell
$credencialSQL = Get-Credential -Message "Credenciales de SQL Server del laboratorio"
$env:PORTFOLIO_SQL_USER = $credencialSQL.UserName
$env:PORTFOLIO_SQL_PASSWORD = $credencialSQL.GetNetworkCredential().Password
$env:PORTFOLIO_API_TOKEN = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
Set-Clipboard -Value $env:PORTFOLIO_API_TOKEN
~~~

Antes de copiar otro texto, pegar ese token en una credencial Header Auth de n8n:
nombre del encabezado X-Portfolio-Token, valor el token. No pegarlo en GitHub ni en capturas.

Importar automation/n8n/procesamiento_entregas_v1.json y seleccionar esa credencial en ambos nodos HTTP.
El JSON público no contiene una credencial asignada. Mantener n8n inactivo para ejecución manual.

~~~powershell
./.venv/Scripts/python.exe python/12_servicio_pipeline.py
~~~

Mantener esa terminal abierta. El servicio usa el puerto 8765 y escucha en 0.0.0.0 para Docker Desktop.
Está diseñado para laboratorio local, sin HTTPS; no exponerlo a Internet.
Ejecutar el workflow: GET /health, luego POST /process sin cuerpo.
host.docker.internal es la dirección de acceso desde Docker Desktop al equipo anfitrión.

PUBLICADO: confirmó en SQL una nueva versión del contenido.
YA_PUBLICADO: encontró el mismo contenido ya vigente; no lo volvió a cargar.
Un batch_id distinto puede devolver YA_PUBLICADO si sus archivos son iguales.
Error 422: revisar el resultado y logs; no asumir que cualquier error de transporte prueba rollback.
Tras un timeout, consultar audit.Publicacion antes de reintentar.

En esta versión la huella incluye bytes de archivos, incluso JSON: saltos de línea o cambios de
serialización pueden cambiar la huella sin cambiar los registros. Mantener los mismos archivos y entorno;
no editar los paquetes generados. .gitattributes preserva los bytes de datos al clonar.

## 4. Power BI y Excel

Abrir powerbi/Cumplimiento_Pedidos_v1.pbix. Configurar acceso propio a localhost / PortfolioPedidos.
Pulsar Actualizar manualmente. Repetir en Excel con Datos > Actualizar todo cuando corresponda.
Las credenciales deben gestionarse en cada aplicación, nunca en el repositorio.

Las capturas son evidencia del entorno del autor. El modelo binario PBIX no fue ejecutado en
Power BI durante la revisión remota; verificar actualización e interacciones en Windows.
En Excel se conservaron fórmulas y consultas; consultas_power_query.m es una extracción legible del libro.

## 5. Gestión de casos

Seguir automation/power-automate/README.md. Es un piloto separado con alta manual de casos.
Cerrar un caso en SharePoint no carga datos corregidos en SQL.
