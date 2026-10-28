USE PortfolioPedidos;
GO

SELECT 'Territorio' AS Tabla, COUNT_BIG(*) AS Filas
FROM core.Territorio
UNION ALL
SELECT 'Cliente', COUNT_BIG(*) FROM core.Cliente
UNION ALL
SELECT 'Producto', COUNT_BIG(*) FROM core.Producto
UNION ALL
SELECT 'Pedido', COUNT_BIG(*) FROM core.Pedido
UNION ALL
SELECT 'LineaPedido', COUNT_BIG(*) FROM core.LineaPedido
UNION ALL
SELECT 'PromesaEntrega', COUNT_BIG(*) FROM core.PromesaEntrega
UNION ALL
SELECT 'Entrega', COUNT_BIG(*) FROM core.Entrega
UNION ALL
SELECT 'PedidoRevision', COUNT_BIG(*) FROM core.PedidoRevision;
GO