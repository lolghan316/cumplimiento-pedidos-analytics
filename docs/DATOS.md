# Archivos y trazabilidad

## Originales

CSV UTF-8 con BOM, sin encabezados, separador coma. Orden declarado en Python 01.
No añadir encabezados sin cambiar el lector.

| Archivo | Filas | Columnas en orden |
|---|---:|---|
| pedidos.csv | 31,465 | SalesOrderID, OrderDate, DueDate, ShipDate, Status, OnlineOrderFlag, CustomerID, TerritoryID, ShipMethodID, CurrencyRateID, SubTotal, TaxAmt, Freight, TotalDue |
| lineas_pedido.csv | 121,317 | SalesOrderID, SalesOrderDetailID, ProductID, OrderQty, UnitPrice, UnitPriceDiscount, LineTotal |
| productos.csv | 504 | ProductID, ProductNumber, ProductName, ProductSubcategoryID, SubcategoryName, ProductCategoryID, CategoryName, SizeUnitMeasureCode, WeightUnitMeasureCode |
| clientes.csv | 19,820 | CustomerID, TerritoryID |
| territorios.csv | 10 | TerritoryID, TerritoryName, CountryRegionCode, TerritoryGroup |

## Generados

- data/synthetic: promesas y eventos de un escenario controlado. Contiene también eventos futuros
  solo como referencia del simulador; no entran al informe al corte.
- data/incoming/entregas_recibidas_v1.csv: entrega observada con errores introducidos.
- data/processed: aceptadas, cuarentena, bitácora, pedidos por revisar y resumen.
- evaluation/ground_truth: manifiesto de errores para evaluar el experimento. No usar como fuente de limpieza.
- data/runs: paquetes de ejecución locales; se crean al ejecutar y se excluyen de Git.
- logs/executions: registros operativos locales excluidos de Git.

Eventos: EventID, SalesOrderID, SalesOrderDetailID, ProductID, DeliveryDate, DeliveredQty, IsSynthetic.
SourceRow identifica la fila de entrada (primera fila de datos = 1).
La bitácora conserva regla, acción, valor anterior y posterior para normalizaciones.
Los rechazos conservan la fila original en cuarentena; la bitácora no llena siempre Before/After.

Las semillas y políticas efectivas están en los generadores y en los JSON de data/synthetic.
Se retiró config/escenario_propuesto.json porque todavía decía “pendiente de inspección” y
no controla los scripts. El corte sigue definido en código; esta versión no lo parametriza.
