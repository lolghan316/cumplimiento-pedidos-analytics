USE PortfolioPedidos;
GO

-- Resultado 1: fecha de corte y carga utilizada.
SELECT *
FROM analytics.vContexto;


-- Resultado 2: conteos y controles.
SELECT
    (
        SELECT COUNT_BIG(*)
        FROM analytics.vCumplimientoLinea
    ) AS LineasAnalizadas,

    (
        SELECT COUNT_BIG(*)
        FROM analytics.vCumplimientoPedido
    ) AS PedidosAnalizados,

    (
        SELECT COUNT_BIG(*)
        FROM analytics.vCumplimientoPedido
        WHERE HasQualityIssue = 1
    ) AS PedidosConRevision,

    (
        SELECT COUNT_BIG(*)
        FROM analytics.vCumplimientoLinea
        WHERE HasOverdelivery = 1
    ) AS LineasConExcesoDeEntrega;


-- Resultado 3: resumen de indicadores.
SELECT *
FROM analytics.vResumenCumplimiento;


-- Resultado 4: estados que mostraremos públicamente.
SELECT
    PublishedStatus,
    COUNT_BIG(*) AS Pedidos
FROM analytics.vCumplimientoPedido
GROUP BY PublishedStatus
ORDER BY PublishedStatus;


-- Resultado 5: muestra de pedidos con información pendiente.
SELECT TOP (10)
    SalesOrderID,
    TerritoryID,
    PromisedDeliveryDate,
    OrderedQty,
    DeliveredQty,
    PendingQty,
    ObservedStatus,
    PublishedStatus,
    EligibleOTIF,
    OTIF
FROM analytics.vCumplimientoPedido
WHERE HasQualityIssue = 1
ORDER BY SalesOrderID;


-- Resultado 6: conciliación entre líneas y pedidos.
SELECT
    (
        SELECT SUM(DeliveredQty)
        FROM analytics.vCumplimientoLinea
    ) AS UnidadesEntregadasEnLineas,

    (
        SELECT SUM(DeliveredQty)
        FROM analytics.vCumplimientoPedido
    ) AS UnidadesEntregadasEnPedidos,

    (
        SELECT SUM(CAST(DeliveredQty AS bigint))
        FROM core.Entrega
        WHERE DeliveryDate <= (
            SELECT CutoffDate
            FROM analytics.vContexto
        )
    ) AS UnidadesEnEventos;
GO