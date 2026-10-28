section Section1;

shared Pedidos = let
    Origen = Sql.Databases("localhost"),
    PortfolioPedidos = Origen{[Name="PortfolioPedidos"]}[Data],
    core_Pedido = PortfolioPedidos{[Schema="core",Item="Pedido"]}[Data]
in
    core_Pedido;

shared Lineas = let
    Origen = Sql.Databases("localhost"),
    PortfolioPedidos = Origen{[Name="PortfolioPedidos"]}[Data],
    core_LineaPedido = PortfolioPedidos{[Schema="core",Item="LineaPedido"]}[Data]
in
    core_LineaPedido;

shared Promesas = let
    Origen = Sql.Databases("localhost"),
    PortfolioPedidos = Origen{[Name="PortfolioPedidos"]}[Data],
    core_PromesaEntrega = PortfolioPedidos{[Schema="core",Item="PromesaEntrega"]}[Data]
in
    core_PromesaEntrega;

shared Entregas = let
    Origen = Sql.Databases("localhost"),
    PortfolioPedidos = Origen{[Name="PortfolioPedidos"]}[Data],
    core_Entrega = PortfolioPedidos{[Schema="core",Item="Entrega"]}[Data]
in
    core_Entrega;

shared PedidosRevision = let
    Origen = Sql.Databases("localhost"),
    PortfolioPedidos = Origen{[Name="PortfolioPedidos"]}[Data],
    core_PedidoRevision = PortfolioPedidos{[Schema="core",Item="PedidoRevision"]}[Data]
in
    core_PedidoRevision;

shared MuestraPedidos = let
    Origen = Sql.Database(
        "localhost",
        "PortfolioPedidos",
        [
            Query = "
                WITH Muestra AS (
                    SELECT
                        SalesOrderID,
                        OrderDate,
                        PromisedDeliveryDate,
                        CutoffDate,
                        HasQualityIssue,
                        PublishedStatus AS EstadoSQL,
                        DeliveredQty AS EntregadasSQL,
                        PendingQty AS PendientesSQL,
                        OTIF AS OTIFSQL,
                        ROW_NUMBER() OVER (
                            PARTITION BY PublishedStatus
                            ORDER BY SalesOrderID
                        ) AS Posicion
                    FROM analytics.vCumplimientoPedido
                )
                SELECT
                    SalesOrderID,
                    OrderDate,
                    PromisedDeliveryDate,
                    CutoffDate,
                    HasQualityIssue,
                    EstadoSQL,
                    EntregadasSQL,
                    PendientesSQL,
                    OTIFSQL
                FROM Muestra
                WHERE Posicion <= 2
                ORDER BY EstadoSQL, SalesOrderID;
            "
        ]
    ),
    Tipos = Table.TransformColumnTypes(
        Origen,
        {
            {"SalesOrderID", Int64.Type},
            {"OrderDate", type date},
            {"PromisedDeliveryDate", type date},
            {"CutoffDate", type date},
            {"HasQualityIssue", Int64.Type},
            {"EntregadasSQL", Int64.Type},
            {"PendientesSQL", Int64.Type},
            {"OTIFSQL", Int64.Type}
        }
    )
in
    Tipos;

shared MuestraLineas = let
    Base = Table.SelectColumns(
        Lineas,
        {
            "SalesOrderID",
            "SalesOrderDetailID",
            "ProductID",
            "OrderQty"
        }
    ),
    Cruce = Table.NestedJoin(
        Base,
        {"SalesOrderID"},
        MuestraPedidos,
        {"SalesOrderID"},
        "Pedido",
        JoinKind.Inner
    ),
    Expandir = Table.ExpandTableColumn(
        Cruce,
        "Pedido",
        {"CutoffDate"},
        {"CutoffDate"}
    ),
    Tipos = Table.TransformColumnTypes(
        Expandir,
        {
            {"SalesOrderID", Int64.Type},
            {"SalesOrderDetailID", Int64.Type},
            {"ProductID", Int64.Type},
            {"OrderQty", Int64.Type},
            {"CutoffDate", type date}
        }
    )
in
    Tipos;

shared MuestraEntregas = let
    Base = Table.SelectColumns(
        Entregas,
        {
            "EventID",
            "SalesOrderID",
            "SalesOrderDetailID",
            "ProductID",
            "DeliveryDate",
            "DeliveredQty"
        }
    ),
    Cruce = Table.NestedJoin(
        Base,
        {"SalesOrderID"},
        MuestraPedidos,
        {"SalesOrderID"},
        "Pedido",
        JoinKind.Inner
    ),
    Seleccion = Table.RemoveColumns(
        Cruce,
        {"Pedido"}
    ),
    Tipos = Table.TransformColumnTypes(
        Seleccion,
        {
            {"SalesOrderID", Int64.Type},
            {"SalesOrderDetailID", Int64.Type},
            {"ProductID", Int64.Type},
            {"DeliveryDate", type date},
            {"DeliveredQty", Int64.Type}
        }
    )
in
    Tipos;