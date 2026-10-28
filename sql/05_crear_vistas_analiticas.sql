USE PortfolioPedidos;
GO

-- Fecha de corte correspondiente a la última carga confirmada.
CREATE OR ALTER VIEW analytics.vContexto
AS
SELECT TOP (1)
    LoadID,
    LoadedAtUTC,
    CutoffDate
FROM audit.Carga
ORDER BY LoadID DESC;
GO


-- Una fila por línea de pedido.
-- Se consideran únicamente pedidos y entregas hasta el corte.
CREATE OR ALTER VIEW analytics.vCumplimientoLinea
AS
WITH EntregasAlCorte AS (
    SELECT
        e.SalesOrderID,
        e.SalesOrderDetailID,
        SUM(CAST(e.DeliveredQty AS bigint)) AS DeliveredQty,
        MAX(e.DeliveryDate) AS LastDeliveryDate
    FROM core.Entrega AS e
    CROSS JOIN analytics.vContexto AS c
    WHERE e.DeliveryDate <= c.CutoffDate
    GROUP BY
        e.SalesOrderID,
        e.SalesOrderDetailID
)
SELECT
    l.SalesOrderID,
    l.SalesOrderDetailID,
    l.ProductID,
    l.OrderQty,
    COALESCE(e.DeliveredQty, 0) AS DeliveredQty,
    CAST(l.OrderQty AS bigint)
        - COALESCE(e.DeliveredQty, 0) AS PendingQty,
    e.LastDeliveryDate,
    CASE
        WHEN COALESCE(e.DeliveredQty, 0) = l.OrderQty
        THEN 1
        ELSE 0
    END AS IsComplete,
    CASE
        WHEN COALESCE(e.DeliveredQty, 0) > l.OrderQty
        THEN 1
        ELSE 0
    END AS HasOverdelivery,
    c.CutoffDate
FROM core.LineaPedido AS l
INNER JOIN core.Pedido AS p
    ON p.SalesOrderID = l.SalesOrderID
CROSS JOIN analytics.vContexto AS c
LEFT JOIN EntregasAlCorte AS e
    ON e.SalesOrderID = l.SalesOrderID
    AND e.SalesOrderDetailID = l.SalesOrderDetailID
WHERE CAST(p.OrderDate AS date) <= c.CutoffDate;
GO


-- Una fila por pedido.
CREATE OR ALTER VIEW analytics.vCumplimientoPedido
AS
WITH LineasAgrupadas AS (
    SELECT
        SalesOrderID,
        COUNT_BIG(*) AS OrderLines,
        SUM(CAST(OrderQty AS bigint)) AS OrderedQty,
        SUM(DeliveredQty) AS DeliveredQty,
        SUM(PendingQty) AS PendingQty,
        MIN(IsComplete) AS IsComplete,
        MAX(HasOverdelivery) AS HasOverdelivery,
        MAX(LastDeliveryDate) AS LastDeliveryDate
    FROM analytics.vCumplimientoLinea
    GROUP BY SalesOrderID
),
Base AS (
    SELECT
        p.SalesOrderID,
        p.CustomerID,
        p.TerritoryID,
        p.OnlineOrderFlag,
        CAST(p.OrderDate AS date) AS OrderDate,
        pr.PromisedDeliveryDate,
        c.CutoffDate,
        l.OrderLines,
        l.OrderedQty,
        l.DeliveredQty,
        l.PendingQty,
        l.IsComplete,
        l.HasOverdelivery,
        CASE
            WHEN l.IsComplete = 1
            THEN l.LastDeliveryDate
            ELSE NULL
        END AS CompleteDeliveryDate,
        CASE
            WHEN r.SalesOrderID IS NOT NULL
                OR l.HasOverdelivery = 1
                OR pr.SalesOrderID IS NULL
            THEN 1
            ELSE 0
        END AS HasQualityIssue,
        CASE
            WHEN pr.PromisedDeliveryDate <= c.CutoffDate
            THEN 1
            ELSE 0
        END AS EligibleOTIF
    FROM core.Pedido AS p
    INNER JOIN LineasAgrupadas AS l
        ON l.SalesOrderID = p.SalesOrderID
    LEFT JOIN core.PromesaEntrega AS pr
        ON pr.SalesOrderID = p.SalesOrderID
    LEFT JOIN core.PedidoRevision AS r
        ON r.SalesOrderID = p.SalesOrderID
    CROSS JOIN analytics.vContexto AS c
),
Estados AS (
    SELECT
        *,
        CASE
            WHEN IsComplete = 1
                AND CompleteDeliveryDate <= PromisedDeliveryDate
            THEN 'COMPLETO_A_TIEMPO'

            WHEN IsComplete = 1
            THEN 'COMPLETO_TARDE'

            WHEN EligibleOTIF = 1
            THEN 'PENDIENTE_VENCIDO'

            ELSE 'PENDIENTE_EN_PLAZO'
        END AS ObservedStatus
    FROM Base
)
SELECT
    *,
    CASE
        WHEN HasQualityIssue = 1
        THEN 'INFORMACION_EN_REVISION'
        ELSE ObservedStatus
    END AS PublishedStatus,

    -- NULL significa que no corresponde evaluar
    -- o que la información requiere revisión.
    CASE
        WHEN EligibleOTIF = 0 OR HasQualityIssue = 1
        THEN CAST(NULL AS int)

        WHEN IsComplete = 1
            AND CompleteDeliveryDate <= PromisedDeliveryDate
        THEN 1

        ELSE 0
    END AS OTIF,

    CASE
        WHEN HasQualityIssue = 0 AND IsComplete = 1
        THEN DATEDIFF(
            day,
            OrderDate,
            CompleteDeliveryDate
        )
        ELSE NULL
    END AS CycleDays
FROM Estados;
GO


CREATE OR ALTER VIEW analytics.vResumenCumplimiento
AS
WITH Conteos AS (
    SELECT
        CutoffDate,
        COUNT_BIG(*) AS TotalOrders,

        SUM(CAST(HasQualityIssue AS bigint))
            AS OrdersWithQualityIssue,

        SUM(CAST(EligibleOTIF AS bigint))
            AS EligibleOrders,

        SUM(CAST(
            CASE
                WHEN EligibleOTIF = 1 AND HasQualityIssue = 0
                THEN 1 ELSE 0
            END AS bigint
        )) AS EvaluableEligibleOrders,

        SUM(CAST(
            CASE
                WHEN EligibleOTIF = 1 AND HasQualityIssue = 1
                THEN 1 ELSE 0
            END AS bigint
        )) AS UnknownEligibleOrders,

        SUM(CAST(
            CASE WHEN OTIF = 1 THEN 1 ELSE 0 END
            AS bigint
        )) AS ConfirmedOTIFOrders

    FROM analytics.vCumplimientoPedido
    GROUP BY CutoffDate
)
SELECT
    *,

    CAST(
        100.0 * ConfirmedOTIFOrders
        / NULLIF(EvaluableEligibleOrders, 0)
        AS decimal(9,4)
    ) AS OTIFAmongEvaluablePct,

    CAST(
        100.0 * EvaluableEligibleOrders
        / NULLIF(EligibleOrders, 0)
        AS decimal(9,4)
    ) AS EvaluationCoveragePct,

    CAST(
        100.0 * ConfirmedOTIFOrders
        / NULLIF(EligibleOrders, 0)
        AS decimal(9,4)
    ) AS ConservativeLowerOTIFPct,

    CAST(
        100.0 * (
            ConfirmedOTIFOrders + UnknownEligibleOrders
        )
        / NULLIF(EligibleOrders, 0)
        AS decimal(9,4)
    ) AS ConservativeUpperOTIFPct

FROM Conteos;
GO


