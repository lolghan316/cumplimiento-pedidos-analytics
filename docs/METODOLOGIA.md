# Reglas del caso

## Unidad de análisis y fechas

- Pedido: SalesOrderID. Línea: SalesOrderID + SalesOrderDetailID. Evento: EventID.
- Promesa: fecha de OrderDate + 14 días calendario, hasta el final del día.
- Corte fijo: 2025-06-29, inclusive. No se usa la fecha actual para medir atrasos.
- ShipDate es despacho; no es evidencia de entrega. DueDate no se redefine como promesa.
- Elegible: PromisedDeliveryDate <= corte. Un pedido aún en plazo no entra al denominador.
- Completo: todas sus líneas tienen cantidad acumulada aceptada igual a la pedida.
- A tiempo: fecha de la última entrega que completa el pedido <= promesa.
- Con incidencias que impiden evaluar: OTIF desconocido, no cero.
- El gráfico mensual agrupa por mes de compromiso bajo el mismo corte; no reconstruye cierres mensuales.

## Indicadores

OTIF evaluable = 21.567 / 30.734 = 70,1731 %.
Cobertura = 30.734 / 31.031 = 99,0429 %.
Límite inferior = 21.567 / 31.031 = 69,5015 %.
Límite superior = (21.567 + 297) / 31.031 = 70,4586 %.

Los límites consideran que ninguno o todos los elegibles por aclarar cumplen.
No representan inferencia estadística ni un rango de probabilidad.

## Calidad

Seis grupos de 100 casos introducidos generan siete reglas de 100 alertas:
el producto inexistente activa también “producto no coincide con línea”.
Una fila puede activar varias reglas. Los totales de pedidos afectados se calculan como distintos,
no como suma de los distintos por acción.

Las fechas DD/MM/YYYY se aceptan por el contrato explícito de este experimento.
El campo normalizaciones cuenta acciones; en este lote coincide con 200 filas.
La verdad de evaluación se usa solamente en el evaluador 08, no en el limpiador 07.

## Interpretación y decisiones

- Priorizar los 33 vencidos confirmados para atención operativa.
- Aclarar los 297 pedidos con calidad insuficiente antes de atribuir incumplimiento.
- Examinar causas de entregas tardías; este escenario no contiene evidencia causal sobre transportistas.
- El total “completo a tiempo” es 21.676; 109 todavía no son elegibles. No usar ese total como numerador OTIF.
- No se cuantifican pérdidas ni se suman importes de monedas distintas.
- Las diferencias territoriales son del escenario generado, no una evaluación real de desempeño.
