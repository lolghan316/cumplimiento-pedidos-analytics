# Evidencias del autor

Estas capturas proceden del ZIP original. No fueron regeneradas ni alteradas para simular resultados.
Los registros JSON seleccionados omiten stdout/stderr y sustituyen la raíz personal de rutas por
<RAIZ_PROYECTO>; sus estados de ejecución se conservan.

| Evidencia | Qué permite comprobar |
|---|---|
| [Resumen ejecutivo](evidencias/resumen-ejecutivo.png) | OTIF, cobertura y rango conservador |
| [Seguimiento](evidencias/seguimiento-pedidos.png) | Vencidos confirmados separados de información en revisión |
| [Calidad](evidencias/calidad-datos.png) | 700 alertas, 600 filas y conciliación del lote |
| [Modelo](evidencias/modelo-powerbi.png) | Dimensiones compartidas; controles desconectados |
| [Excel](evidencias/conciliacion-excel.png) | Diez comparaciones COINCIDE |
| [n8n](evidencias/workflow-n8n.png) | Tres nodos de la coordinación |
| [Publicación SQL](evidencias/publicacion-sql.png) | Registro de publicación, LoadID 2 |
| [Reproceso n8n](evidencias/reproceso-n8n.png) | YA_PUBLICADO sin actualización SQL |
| [Registro de reproceso](evidencias/registros/reproceso-confirmado.json) | Respuesta conservada del servicio |
| [Registro de rechazo](evidencias/registros/rechazo-fuente-ausente.json) | Fallo de procesamiento por entrada ausente |

La primera publicación se prueba con la auditoría SQL; no se dispone de una captura de n8n
mostrando PUBLICADO por primera vez. No es necesario recrear ese evento.
La captura histórica de /health muestra validation_only: el texto estaba desactualizado;
la versión preparada corrige ese rótulo sin cambiar el procesamiento.
