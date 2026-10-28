# Mejoras futuras

1. Extracción programada desde la fuente y carga incremental con claves y tratamiento de cambios.
2. Corte parametrizado, calendario de cierre e instantáneas históricas de cumplimiento.
3. Huella semántica para evitar publicaciones nuevas por diferencias de formato.
4. Exportaciones importables y versionadas de Power Automate.
5. Alta automática de casos y circuito de corrección con evidencia antes de reprocesar.
6. Refresco de Power BI Service según infraestructura, licencias y permisos disponibles.
7. Pruebas de fallos dentro de la transacción SQL, concurrencia y recuperación.
8. Manejar eventos con SalesOrderID inválido también en la publicación de incidencias:
   hoy 14 convierte a int y puede rechazar el lote si ese identificador no es numérico.
9. Mejorar timeouts y apagado de procesos hijos; un timeout no prueba por sí mismo que SQL no confirmó.
10. Medir tiempo manual y automatizado bajo condiciones comparables.

Estas tareas no se presentan como funcionalidades ya terminadas.
