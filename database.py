import sqlite3

def conectar():
    conn = sqlite3.connect('adonai_erp.db', check_same_thread=False)
    return conn

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    
    # Tabla de Entidades (Clientes y Proveedores)
    c.execute('''
        CREATE TABLE IF NOT EXISTS entidades (
            rif TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            direccion TEXT,
            tipo_contribuyente TEXT,
            categoria TEXT,
            retencion_islr_pct REAL DEFAULT 0.0
            retencion_iva_pct REAL DEFAULT 0.0
        )
    ''')
    
    # Tabla de Facturas de Compra
    c.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            rif_proveedor TEXT,
            num_factura TEXT,
            num_control TEXT,
            monto_exento REAL DEFAULT 0.0,
            base_imponible REAL DEFAULT 0.0,
            iva_monto REAL DEFAULT 0.0,
            islr_retenido REAL DEFAULT 0.0,
            total_factura REAL,
            FOREIGN KEY (rif_proveedor) REFERENCES entidades (rif)
        )
    ''')
    
    conn.commit()
    conn.close()
