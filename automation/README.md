# Automatización

n8n coordina un procesamiento manual de archivos mediante un servicio Python local y su publicación SQL.
El workflow está en n8n/procesamiento_entregas_v1.json. Reasignar Header Auth en ambos nodos al importar.
No incluye credenciales ni identificadores de instancia del autor.

Power Automate gestiona el piloto de revisión en SharePoint: ver power-automate/README.md.
No hay sincronización de casos entre SharePoint y SQL, ni refresco automático de Power BI.
