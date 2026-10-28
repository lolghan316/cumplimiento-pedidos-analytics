USE PortfolioPedidos;
GO

IF OBJECT_ID(N'audit.Publicacion', N'U') IS NULL
BEGIN
    CREATE TABLE audit.Publicacion (
        PublicationID bigint IDENTITY(1,1) NOT NULL
            PRIMARY KEY,
        LoadID bigint NOT NULL UNIQUE,
        BatchID char(32) NOT NULL,
        ContentSHA256 char(64) NOT NULL UNIQUE,
        PublishedAtUTC datetime2(3) NOT NULL
            DEFAULT SYSUTCDATETIME(),
        FOREIGN KEY (LoadID)
            REFERENCES audit.Carga(LoadID)
    );
END;
GO

SELECT *
FROM audit.Publicacion;