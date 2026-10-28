USE master;
GO

IF DB_ID(N'PortfolioPedidos') IS NULL
BEGIN
    EXEC(N'CREATE DATABASE PortfolioPedidos;');
END;
GO

USE PortfolioPedidos;
GO

IF SCHEMA_ID(N'stg') IS NULL
    EXEC(N'CREATE SCHEMA stg AUTHORIZATION dbo;');
GO

IF SCHEMA_ID(N'core') IS NULL
    EXEC(N'CREATE SCHEMA core AUTHORIZATION dbo;');
GO

IF SCHEMA_ID(N'analytics') IS NULL
    EXEC(N'CREATE SCHEMA analytics AUTHORIZATION dbo;');
GO

IF SCHEMA_ID(N'audit') IS NULL
    EXEC(N'CREATE SCHEMA audit AUTHORIZATION dbo;');
GO

SELECT
    DB_NAME() AS BaseActual,
    ORIGINAL_LOGIN() AS UsuarioConexion;

SELECT name AS Esquema
FROM sys.schemas
WHERE name IN (N'stg', N'core', N'analytics', N'audit')
ORDER BY name;