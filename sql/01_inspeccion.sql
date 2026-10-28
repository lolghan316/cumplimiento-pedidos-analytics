-- SOLO LECTURA. Selecciona tu base AdventureWorks en SSMS antes de ejecutar.
SET NOCOUNT ON;
-- Resultado 1: contexto técnico.
SELECT DB_NAME() AS base_actual,
 CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) AS version_motor,
 CAST(SERVERPROPERTY('Edition') AS nvarchar(128)) AS edicion;
-- Resultado 2: objetos requeridos; no asume variante por el nombre.
SELECT v.objeto, CASE WHEN OBJECT_ID(v.objeto,'U') IS NOT NULL THEN 'OK' ELSE 'FALTA' END AS estado
FROM (VALUES ('Sales.SalesOrderHeader'),('Sales.SalesOrderDetail'),
('Production.Product'),('Production.ProductSubcategory'),('Production.ProductCategory'),
('Sales.Customer'),('Sales.SalesTerritory')) v(objeto);
-- Resultado 3: diccionario de las tablas de interés.
SELECT s.name AS esquema,t.name AS tabla,c.column_id,c.name AS columna,
 ty.name AS tipo,c.max_length,c.precision,c.scale,c.is_nullable
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.columns c ON c.object_id=t.object_id
JOIN sys.types ty ON ty.user_type_id=c.user_type_id
WHERE (s.name='Sales' AND t.name IN ('SalesOrderHeader','SalesOrderDetail','Customer','SalesTerritory'))
OR (s.name='Production' AND t.name IN ('Product','ProductSubcategory','ProductCategory'))
ORDER BY s.name,t.name,c.column_id;
-- Resultado 4: conteos exactos y fechas; SQL dinámico evita compilar tablas ausentes.
IF OBJECT_ID('Sales.SalesOrderHeader','U') IS NOT NULL
EXEC sys.sp_executesql N'SELECT COUNT_BIG(*) AS pedidos,MIN(OrderDate) AS fecha_min,
MAX(OrderDate) AS fecha_max,SUM(CASE WHEN ShipDate IS NULL THEN 1 ELSE 0 END) AS sin_despacho
FROM Sales.SalesOrderHeader;';
ELSE SELECT 'No se encontro Sales.SalesOrderHeader: detener extraccion OLTP.' AS aviso;
-- Resultado 5: distribución de estados y referencias de moneda.
IF OBJECT_ID('Sales.SalesOrderHeader','U') IS NOT NULL
EXEC sys.sp_executesql N'SELECT Status,CurrencyRateID,COUNT_BIG(*) AS pedidos
FROM Sales.SalesOrderHeader GROUP BY Status,CurrencyRateID ORDER BY Status,CurrencyRateID;';
