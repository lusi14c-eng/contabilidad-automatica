import sqlite3

def conectar():
    return sqlite3.connect('adonai_erp.db', check_same_thread=False)

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    
    # 1. Crear tabla si no existe (con estructura base)
    c.execute('''
        CREATE TABLE IF NOT EXISTS entidades (
            rif TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            direccion TEXT,
            tipo_contribuyente TEXT,
            categoria TEXT,
            retencion_islr_pct REAL DEFAULT 0.0
        )
    ''')
    
    # 2. TRUCO MÁGICO: Intentar agregar la columna de IVA por si no existe
    try:
        c.execute('ALTER TABLE entidades ADD COLUMN retencion_iva_pct REAL DEFAULT 0.0')
    except sqlite3.OperationalError:
        # Si da error es porque la columna ya existe, así que no hacemos nada
        pass

    # 3. Tabla de Compras
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
            iva_retenido REAL DEFAULT 0.0,
            total_factura REAL,
            FOREIGN KEY (rif_proveedor) REFERENCES entidades (rif)
        )
    ''')
    
    conn.commit()
    conn.close()
