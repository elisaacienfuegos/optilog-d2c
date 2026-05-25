-- =============================================================================
--  Esquema de la base de datos  "optilog"
--  Plataforma de optimización logística D2C  —  TFG
--
--  Traduce el modelo Entidad-Relación (11 entidades) a PostgreSQL.
--  Orden de creación respetando las dependencias de claves foráneas.
--  Ejecutar sobre la base de datos `optilog` ya creada en pgAdmin.
-- =============================================================================

-- Limpieza previa (permite re-ejecutar el script desde cero sin errores).
-- CASCADE elimina también las dependencias. El orden inverso al de creación.
DROP TABLE IF EXISTS prediccion        CASCADE;
DROP TABLE IF EXISTS historico_venta   CASCADE;
DROP TABLE IF EXISTS tarifa            CASCADE;
DROP TABLE IF EXISTS envio             CASCADE;
DROP TABLE IF EXISTS linea_pedido      CASCADE;
DROP TABLE IF EXISTS pedido            CASCADE;
DROP TABLE IF EXISTS movimiento_stock  CASCADE;
DROP TABLE IF EXISTS stock             CASCADE;
DROP TABLE IF EXISTS sku               CASCADE;
DROP TABLE IF EXISTS producto          CASCADE;
DROP TABLE IF EXISTS transportista     CASCADE;
DROP TABLE IF EXISTS almacen           CASCADE;


-- ---------------------------------------------------------------------------
--  CATÁLOGO
-- ---------------------------------------------------------------------------

-- Producto: artículo conceptual (p.ej. "Vestido negro").
CREATE TABLE producto (
    id           SERIAL PRIMARY KEY,
    nombre       VARCHAR(120) NOT NULL,
    familia      VARCHAR(60)  NOT NULL,
    descripcion  TEXT
);

-- SKU: variante vendible de un producto (talla + color concretos).
CREATE TABLE sku (
    id           SERIAL PRIMARY KEY,
    producto_id  INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    codigo_sku   VARCHAR(60) NOT NULL UNIQUE,
    color        VARCHAR(30),
    talla        VARCHAR(10)
);


-- ---------------------------------------------------------------------------
--  ALMACENES E INVENTARIO
-- ---------------------------------------------------------------------------

-- Almacén físico.
CREATE TABLE almacen (
    id         SERIAL PRIMARY KEY,
    codigo     VARCHAR(10)  NOT NULL UNIQUE,
    ciudad     VARCHAR(60)  NOT NULL,
    direccion  VARCHAR(200)
);

-- Stock: existencias de un SKU en un almacén, desglosadas por estado.
-- La combinación (sku, almacen) es única: una sola fila por par.
CREATE TABLE stock (
    id           SERIAL PRIMARY KEY,
    sku_id       INTEGER NOT NULL REFERENCES sku(id)     ON DELETE CASCADE,
    almacen_id   INTEGER NOT NULL REFERENCES almacen(id) ON DELETE CASCADE,
    disponible   INTEGER NOT NULL DEFAULT 0 CHECK (disponible  >= 0),
    reservado    INTEGER NOT NULL DEFAULT 0 CHECK (reservado   >= 0),
    en_transito  INTEGER NOT NULL DEFAULT 0 CHECK (en_transito >= 0),
    UNIQUE (sku_id, almacen_id)
);

-- Movimiento de stock: libro de registro de entradas/salidas/reservas/traspasos.
-- El stock actual debe poder reconstruirse a partir de estos movimientos.
CREATE TABLE movimiento_stock (
    id          SERIAL PRIMARY KEY,
    sku_id      INTEGER NOT NULL REFERENCES sku(id)     ON DELETE CASCADE,
    almacen_id  INTEGER NOT NULL REFERENCES almacen(id) ON DELETE CASCADE,
    tipo        VARCHAR(20) NOT NULL
                CHECK (tipo IN ('entrada','salida','reserva',
                                'liberacion','transito','recepcion')),
    cantidad    INTEGER NOT NULL,
    fecha       TIMESTAMP NOT NULL DEFAULT NOW()
);


-- ---------------------------------------------------------------------------
--  PEDIDOS
-- ---------------------------------------------------------------------------

-- Pedido: cabecera.
CREATE TABLE pedido (
    id          SERIAL PRIMARY KEY,
    referencia  VARCHAR(40) NOT NULL UNIQUE,
    estado      VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                CHECK (estado IN ('pendiente','confirmado','preparado',
                                  'enviado','entregado','cancelado')),
    fecha       TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Línea de pedido: detalle (un SKU con su cantidad dentro de un pedido).
CREATE TABLE linea_pedido (
    id         SERIAL PRIMARY KEY,
    pedido_id  INTEGER NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
    sku_id     INTEGER NOT NULL REFERENCES sku(id),
    cantidad   INTEGER NOT NULL CHECK (cantidad > 0)
);


-- ---------------------------------------------------------------------------
--  LOGÍSTICA
-- ---------------------------------------------------------------------------

-- Transportista: operador logístico (mock). fiabilidad en [0,1].
CREATE TABLE transportista (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(60) NOT NULL UNIQUE,
    fiabilidad  REAL NOT NULL DEFAULT 0.9
                CHECK (fiabilidad >= 0 AND fiabilidad <= 1)
);

-- Tarifa: coste y plazo de un transportista para una zona de destino.
CREATE TABLE tarifa (
    id               SERIAL PRIMARY KEY,
    transportista_id INTEGER NOT NULL REFERENCES transportista(id) ON DELETE CASCADE,
    zona             VARCHAR(40) NOT NULL,
    coste_base       REAL NOT NULL CHECK (coste_base >= 0),
    plazo_dias       INTEGER NOT NULL CHECK (plazo_dias >= 0)
);

-- Envío: expedición de un pedido a través de un transportista.
CREATE TABLE envio (
    id               SERIAL PRIMARY KEY,
    pedido_id        INTEGER NOT NULL UNIQUE REFERENCES pedido(id) ON DELETE CASCADE,
    transportista_id INTEGER REFERENCES transportista(id),
    peso_kg          REAL,
    destino          VARCHAR(60),
    estado           VARCHAR(20) NOT NULL DEFAULT 'preparando'
                     CHECK (estado IN ('preparando','en_transito','entregado'))
);


-- ---------------------------------------------------------------------------
--  DATA SCIENCE
-- ---------------------------------------------------------------------------

-- Histórico de venta: serie temporal de demanda (carga desde el CSV sintético).
CREATE TABLE historico_venta (
    id          SERIAL PRIMARY KEY,
    sku_id      INTEGER NOT NULL REFERENCES sku(id)     ON DELETE CASCADE,
    almacen_id  INTEGER NOT NULL REFERENCES almacen(id) ON DELETE CASCADE,
    fecha       DATE NOT NULL,
    unidades    INTEGER NOT NULL CHECK (unidades >= 0),
    UNIQUE (sku_id, almacen_id, fecha)
);

-- Predicción: salida de los modelos (Prophet / SARIMA) por SKU, almacén y fecha.
CREATE TABLE prediccion (
    id              SERIAL PRIMARY KEY,
    sku_id          INTEGER NOT NULL REFERENCES sku(id)     ON DELETE CASCADE,
    almacen_id      INTEGER NOT NULL REFERENCES almacen(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL,
    unidades_pred   REAL NOT NULL,
    modelo          VARCHAR(20) NOT NULL
                    CHECK (modelo IN ('prophet','sarima','baseline'))
);


-- ---------------------------------------------------------------------------
--  ÍNDICES  (aceleran las consultas más frecuentes del dashboard y la API)
-- ---------------------------------------------------------------------------
CREATE INDEX idx_historico_sku_alm_fecha ON historico_venta (sku_id, almacen_id, fecha);
CREATE INDEX idx_prediccion_sku_alm      ON prediccion      (sku_id, almacen_id);
CREATE INDEX idx_movimiento_sku_alm      ON movimiento_stock(sku_id, almacen_id);
CREATE INDEX idx_linea_pedido_pedido     ON linea_pedido    (pedido_id);

-- Fin del esquema.
