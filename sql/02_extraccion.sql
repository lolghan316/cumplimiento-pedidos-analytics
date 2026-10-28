-- SOLO LECTURA. Ejecutar en la base OLTP confirmada; cinco resultados para exportar.
-- No contiene datos personales, solo claves de cliente.
SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM (VALUES ('Sales.SalesOrderHeader'),('Sales.SalesOrderDetail'),
('Production.Product'),('Production.ProductSubcategory'),('Production.ProductCategory'),
('Sales.Customer'),('Sales.SalesTerritory')) v(objeto) WHERE OBJECT_ID(v.objeto,'U') IS NULL)
BEGIN
 RAISERROR('Faltan tablas OLTP. Ejecuta primero 01_inspeccion.sql.',16,1);
 RETURN;
END;
EXEC sys.sp_executesql N'
-- pedidos.csv
SELECT SalesOrderID,OrderDate,DueDate,ShipDate,Status,OnlineOrderFlag,CustomerID,
TerritoryID,ShipMethodID,CurrencyRateID,SubTotal,TaxAmt,Freight,TotalDue
FROM Sales.SalesOrderHeader ORDER BY SalesOrderID;
-- lineas_pedido.csv
SELECT SalesOrderID,SalesOrderDetailID,ProductID,OrderQty,UnitPrice,
UnitPriceDiscount,LineTotal FROM Sales.SalesOrderDetail
ORDER BY SalesOrderID,SalesOrderDetailID;
-- productos.csv
SELECT p.ProductID,p.ProductNumber,p.Name AS ProductName,
p.ProductSubcategoryID,s.Name AS SubcategoryName,c.ProductCategoryID,
c.Name AS CategoryName,p.SizeUnitMeasureCode,p.WeightUnitMeasureCode
FROM Production.Product p
LEFT JOIN Production.ProductSubcategory s ON s.ProductSubcategoryID=p.ProductSubcategoryID
LEFT JOIN Production.ProductCategory c ON c.ProductCategoryID=s.ProductCategoryID
ORDER BY p.ProductID;
-- clientes.csv
SELECT CustomerID,TerritoryID FROM Sales.Customer ORDER BY CustomerID;
-- territorios.csv
SELECT TerritoryID,Name AS TerritoryName,CountryRegionCode,[Group] AS TerritoryGroup
FROM Sales.SalesTerritory ORDER BY TerritoryID;';
