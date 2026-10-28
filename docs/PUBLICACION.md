# Publicar esta copia en GitHub

## Qué subir

La carpeta cumplimiento-pedidos-analytics es la raíz del repositorio.
Subir su contenido, no el ZIP original con entornos virtuales ni la carpeta de trabajo histórica.
Las capturas permiten revisar el caso sin descargar Power BI ni ejecutar código.

Nombre sugerido: cumplimiento-pedidos-analytics.
Descripción: Análisis de cumplimiento OTIF y calidad de datos con SQL, Python, Power BI y automatización.
Temas sugeridos: data-analysis, sql-server, python, power-bi, data-quality, n8n.

## Pasos desde Windows

1. Extraer el paquete en una carpeta NUEVA, fuera del proyecto operativo.
2. Abrir esa carpeta en VS Code y revisar README.md.
3. Abrir el PBIX y el XLSX localmente para verificar que abren. No es necesario recrear la base existente.
4. Crear en GitHub un repositorio vacío con el nombre elegido, sin generar README ni gitignore.
5. En la terminal de la nueva carpeta, ejecutar:

~~~powershell
git init
git add .
git status
git diff --cached --stat
git commit -m "Publicar MVP de cumplimiento de pedidos y calidad de datos"
git branch -M main
~~~

6. Copiar la URL HTTPS del repositorio recién creado y ejecutar, sustituyendo la URL:

~~~powershell
git remote add origin https://github.com/TU_USUARIO/cumplimiento-pedidos-analytics.git
git push -u origin main
~~~

Si Git solicita identidad, configurar el nombre y correo que el autor quiera asociar al commit,
preferiblemente el correo privado de GitHub si así lo desea. No escribir contraseñas ni tokens en comandos.
Si el repositorio ya existe con contenido, no forzar el push: revisar primero su historial.

## Comprobación posterior

- README visible con su imagen de portada.
- Enlaces internos a documentación, capturas, PBIX y Excel funcionales.
- No aparecen .venv, .venv_anterior, logs ni data/runs en el repositorio.
- Revisar la descripción y fijarlo en el perfil.
- La demostración no promete extracción automática, cierres mensuales ni refresco automático.
- Power Automate está documentado, pero todavía no tiene paquetes importables.
- Para incluir captura de casos, usar responsables ficticios y ocultar la URL del sitio antes de exportarla.

No se creó ni publicó un repositorio durante esta revisión. Hace falta la URL de destino y acceso del autor.
