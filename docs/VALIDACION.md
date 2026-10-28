# Validación y alcance de la revisión

Fecha: 28/10/2026. Se distingue lo ejecutado en revisión de lo aportado por el autor.

| Control | Evidencia / alcance |
|---|---|
| Sintaxis de los 15 scripts | Comprobada mediante análisis sintáctico |
| Limpieza y conciliación | 13 ejecutado sobre los CSV aportados en un entorno separado |
| Determinismo | Dos ejecuciones con huellas de salidas iguales en el mismo entorno |
| Comparación contra entrega original | Cuatro CSV de salida iguales byte a byte; resumen JSON igual en contenido |
| Error de encabezados | Rechazado en copia aislada; entrada restaurada |
| Errores controlados | 08 ejecutado: 600 casos, 700 alertas esperadas y observadas, sin diferencias |
| Métricas de negocio | Recalculadas desde CSV por pedido y línea; coinciden con capturas |
| Primera publicación SQL | Captura del registro audit.Publicacion, LoadID 2 |
| Reproceso | Registro aportado con YA_PUBLICADO, sql_updated false y LoadID 2 |
| Fuente ausente | Registro aportado de fallo y posterior recuperación; no prueba rollback dentro de SQL |
| Excel | Fórmulas y consultas inspeccionadas; diez COINCIDE almacenados; sin recálculo con Excel aquí |
| Power BI | Capturas y estructura del archivo inspeccionadas; no se ejecutó el modelo binario aquí |
| Power Automate | Capturas revisadas y pruebas declaradas por el autor; sin acceso a su entorno |

Ver evidencias/registros/revision-tecnica.json.
Los resultados perfectos de detección describen solamente este experimento con errores conocidos.

## Hallazgos y correcciones de preparación

- README y documentos iniciales estaban desactualizados: se sustituyeron por alcance implementado.
- Los CSV originales no tienen encabezados, aunque el README inicial sugería exportarlos con encabezados.
- El servicio 12 mantenía el rótulo validation_only: se corrigió el texto de /health y consola.
- Se retiraron identificadores de credencial/instancia del JSON de n8n. Importar requiere configurar credenciales.
- Se excluyeron entornos virtuales, cachés y copias repetidas de ejecuciones.
- Se conservaron los archivos PBIX/XLSX sin modificaciones; no se exportó ni reconstruyó su modelo.
- Se omitieron tres capturas de SharePoint/Power Automate por nombres y URL del entorno.
- Los cuatro CSV de resultados reproducidos coinciden exactamente con los aportados.
  El JSON resumen coincide semánticamente, pero sus bytes pueden cambiar por saltos de línea.
  La huella actual de publicación depende de bytes, no de equivalencia semántica.

## Límites técnicos a conocer

La publicación 14 sustituye core.Entrega y core.PedidoRevision y conserva auditoría por carga;
no conserva instantáneas históricas completas de esas tablas.
Exige mismo corte, maestros y promesas. No es un cargador de nuevos pedidos.

Los registros con identificador de pedido no numérico pueden bloquear la publicación de incidencias
por su conversión a int. Es una mejora pendiente fuera de los casos introducidos.
Los timeouts de subprocess no constituyen una garantía de cancelación de toda la cadena de procesos.
Consultar auditoría SQL si el resultado es incierto.

Se revisó texto accesible para detectar credenciales incrustadas y se inspeccionaron las capturas
seleccionadas. No se encontraron valores de contraseña/token en ese material.
Esto no equivale a una auditoría exhaustiva del modelo binario PBIX o de todas las aplicaciones.
