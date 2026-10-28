# Gestión de revisión: diseño del piloto

Se implementaron y probaron dos flujos manuales en el entorno del autor.
El ZIP recibido contiene capturas, no paquetes exportados importables. Este documento permite
reconstruirlos; no es una exportación oficial de Power Automate.

Lista RevisionPedidos:
Title; CasoClave (texto único, requerido, ejemplo carga-pedido); PedidoID (número);
CargaID (número); Motivo (texto); Estado (elección); Responsable (texto);
FechaInicioRevision y FechaResolucion (fecha/hora); ComentarioResolucion (texto).
Estados: Pendiente, En revision, Requiere aclaracion, Resuelto.
CasoID corresponde al ID interno de SharePoint, no al PedidoID.

## Iniciar revisión

1. Activador manual: CasoID numérico y ResponsableRevision de texto.
2. Obtener elemento por CasoID.
3. Inicializar Responsable desde el texto del activador.
4. Condición AND: Estado Value = Pendiente; empty(trim(variables('Responsable'))) = false.
5. Sí: actualizar el mismo ID, preservar campos del caso, Estado = En revision,
   Responsable = trim(variables('Responsable')), FechaInicioRevision = utcNow().
6. No: terminar con CASO_NO_INICIABLE.

## Cerrar revisión

1. Activador manual: CasoID y ComentarioCierre.
2. Obtener elemento; inicializar Comentario desde ComentarioCierre del activador.
3. Condición AND: Estado Value = En revision; empty(trim(variables('Comentario'))) = false.
4. Sí: actualizar Estado = Resuelto, FechaResolucion = utcNow(),
   ComentarioResolucion = trim(variables('Comentario')); preservar responsable e inicio.
5. No: terminar con CIERRE_NO_VALIDO.

No usar el objeto Estado completo en la comparación ni el comentario antiguo del elemento.
Los sufijos “Update item 2” son nombres de acciones, no conectores distintos.
Las capturas privadas mostraban la URL del sitio y nombres; se omitieron de la copia pública.

## Pruebas

Confirmadas por el autor: iniciar, impedir iniciar de nuevo y cerrar correctamente.
Pendientes de evidenciar individualmente: cerrar un caso Pendiente, volver a cerrar uno Resuelto,
rechazar un comentario vacío o solo espacios, dos usuarios actuando simultáneamente.
El flujo de Requiere aclaracion no está implementado: es un estado disponible en la lista.
La condición seguida de actualización no implementa un bloqueo atómico para concurrencia.
