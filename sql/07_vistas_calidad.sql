USE PortfolioPedidos;
GO

CREATE OR ALTER VIEW analytics.vIncidenciaCalidad
AS
SELECT
    i.IncidentID,
    i.LoadID,
    i.SourceRow,
    i.EventID,
    i.SalesOrderID,
    p.TerritoryID,
    pr.PromisedDeliveryDate,
    i.[Rule],
    i.[Action],
    i.BeforeValue,
    i.AfterValue,
    c.CutoffDate
FROM audit.IncidenciaCalidad AS i
INNER JOIN analytics.vContexto AS c
    ON c.LoadID = i.LoadID
INNER JOIN core.Pedido AS p
    ON p.SalesOrderID = i.SalesOrderID
INNER JOIN core.PromesaEntrega AS pr
    ON pr.SalesOrderID = i.SalesOrderID;
GO

CREATE OR ALTER VIEW analytics.vCalidadCarga
AS
SELECT
    q.*,
    c.CutoffDate
FROM audit.CalidadCarga AS q
INNER JOIN analytics.vContexto AS c
    ON c.LoadID = q.LoadID;
GO

SELECT
    [Action],
    COUNT_BIG(*) AS Incidencias,
    COUNT(DISTINCT SourceRow) AS FilasAfectadas
FROM analytics.vIncidenciaCalidad
GROUP BY [Action];

SELECT *
FROM analytics.vCalidadCarga;
GO