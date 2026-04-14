import sqlite3

def conectar():
    return sqlite3.connect('adonai_erp.db', check_same_thread=False)

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    
    # Tabla de Entidades
    c.execute('''
        CREATE TABLE IF NOT EXISTS entidades (
            rif TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            direccion TEXT,
            tipo_persona TEXT,
            tipo_contribuyente TEXT,
            categoria TEXT,
            retencion_islr_pct REAL DEFAULT 0.0,
            retencion_iva_pct REAL DEFAULT 0.0
        )
    ''')
    
    # TABLA DE SUBTIPOS (La que te falta)
    c.execute('''
        CREATE TABLE IF NOT EXISTS subtipos_gasto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            cuenta_contable TEXT
        )
    ''')
    
    # Tabla de Compras
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
            subtipo TEXT,
            aplica_ret_islr INTEGER DEFAULT 1,
            aplica_ret_iva INTEGER DEFAULT 1,
            FOREIGN KEY (rif_proveedor) REFERENCES entidades (rif)
        )
    ''')
    
    conn.commit()
    conn.close()
