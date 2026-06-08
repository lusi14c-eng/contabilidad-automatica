import psycopg2
import streamlit as st
import hashlib

@st.cache_resource
def obtener_conexion_base():
    """Crea la conexión base inicial y la guarda en caché."""
    try:
        url = st.secrets["database"]["url"]
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        st.error(f"Error de conexión crítica: {e}")
        return None

def conectar():
    """Retorna la conexión. Si se detecta cerrada o rota, la regenera de inmediato."""
    conn = obtener_conexion_base()
    if conn is None or conn.closed != 0:
        st.cache_resource.clear()  # Limpiamos el cable roto de la memoria
        conn = obtener_conexion_base()  # Creamos un cable nuevo
    return conn

def ejecutar_transaccion(query, params=None):
    """Ejecuta consultas de forma segura controlando errores de interfaz."""
    conn = conectar()
    if conn:
        try:
            with conn.cursor() as c:
                c.execute(query, params)
            conn.commit()
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            st.cache_resource.clear()
            conn = conectar()
            if conn:
                try:
                    with conn.cursor() as c:
                        c.execute(query, params)
                    conn.commit()
                except Exception as e:
                    st.error(f"Error crítico en reintento: {e}")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            st.error(f"Error en transacción contable: {e}")

def registrar_log(usuario, accion, tabla, detalle):
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS logs_actividad (
        id SERIAL PRIMARY KEY, fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP, usuario TEXT, accion TEXT, tabla_afectada TEXT, detalle TEXT)''')
    ejecutar_transaccion("INSERT INTO logs_actividad (usuario, accion, tabla_afectada, detalle) VALUES (%s, %s, %s, %s)", (usuario, accion, tabla, detalle))

def obtener_configuracion_empresa():
    conn = conectar()
    res = None
    if conn:
        try:
            with conn.cursor() as c:
                c.execute("""SELECT nombre_empresa, rif_empresa, direccion_empresa, 
                                    tipo_contribuyente, ut_valor, factor_sustraendo 
                             FROM configuracion WHERE id = 1""")
                res = c.fetchone()
        except Exception: 
            pass
    
    if res:
        return {
            "nombre_empresa": res[0] if res[0] else "ADONAI GROUP", 
            "rif_empresa": res[1] if res[1] else "", 
            "direccion_empresa": res[2] if res[2] else "",
            "tipo_contribuyente": res[3] if res[3] else "Ordinario",
            "ut_valor": float(res[4]) if res[4] is not None else 0.00, # CORREGIDO: de 'is not null' a 'is not None'
            "factor_sustraendo": float(res[5]) if res[5] is not None else 83.3334 # CORREGIDO: de 'is not null' a 'is not None'
        }
    return {"nombre_empresa": "ADONAI GROUP", "rif_empresa": "", "direccion_empresa": "", "tipo_contribuyente": "Ordinario", "ut_valor": 0.00, "factor_sustraendo": 83.3334}

def inicializar_db():
    # Creación de tablas base asegurando restricciones únicas
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, 
        username TEXT UNIQUE, 
        clave TEXT, 
        rol TEXT, 
        nombre TEXT
    )''')
    
    # Migraciones seguras por si la tabla ya existía sin estas columnas
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS username TEXT UNIQUE;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS clave TEXT;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT;")
    
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS periodos_fiscales (id SERIAL PRIMARY KEY, periodo TEXT UNIQUE, estatus TEXT DEFAULT 'Abierto')''')
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_cabecera (id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE, concepto TEXT, origen TEXT, creado_por TEXT)''')
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_detalle (id SERIAL PRIMARY KEY, asiento_id INT, cuenta TEXT, debe NUMERIC(15,2), haber NUMERIC(15,2))''')
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS centros_costo (id SERIAL PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT)''')
    
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS configuracion (
        id INTEGER PRIMARY KEY DEFAULT 1, 
        nombre_empresa TEXT, 
        rif_empresa TEXT, 
        direccion_empresa TEXT,
        tipo_contribuyente TEXT DEFAULT 'Ordinario',
        ut_valor NUMERIC(10,2) DEFAULT 0.00,
        factor_sustraendo NUMERIC(10,4) DEFAULT 83.3334
    )''')
    
    ejecutar_transaccion("ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS tipo_contribuyente TEXT DEFAULT 'Ordinario';")
    ejecutar_transaccion("ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS ut_valor NUMERIC(10,2) DEFAULT 0.00;")
    ejecutar_transaccion("ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS factor_sustraendo NUMERIC(10,4) DEFAULT 83.3334;")

    # CORREGIDO: Forzamos la actualización de la clave del administrador por si quedó un registro corrupto/antiguo
    pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
    ejecutar_transaccion("""
        INSERT INTO usuarios (username, clave, rol, nombre) 
        VALUES ('admin', %s, 'admin', 'Admin Principal') 
        ON CONFLICT (username) 
        DO UPDATE SET clave = EXCLUDED.clave, rol = EXCLUDED.rol;
    """, (pw_hash,))
    
    ejecutar_transaccion("INSERT INTO configuracion (id, nombre_empresa) VALUES (1, 'ADONAI GROUP') ON CONFLICT (id) DO NOTHING")
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS cotizaciones_cabecera (
        id SERIAL PRIMARY KEY, 
        num_cotizacion TEXT UNIQUE, 
        cliente TEXT, 
        fecha DATE, 
        subtotal NUMERIC(15,2), 
        iva NUMERIC(15,2), 
        total NUMERIC(15,2), 
        creado_por TEXT,
        drive_file_id TEXT
    )''')
    
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS cotizaciones_detalle (
        id SERIAL PRIMARY KEY, 
        cotizacion_id INT, 
        descripcion TEXT, 
        cantidad NUMERIC(12,2), 
        precio_unitario NUMERIC(15,2), 
        total_linea NUMERIC(15,2)
    )''')

def obtener_ultimo_correlativo(prefijo):
    conn = conectar()
    res = None
    if conn:
        try:
            with conn.cursor() as c:
                c.execute("SELECT num_asiento FROM asientos_cabecera WHERE num_asiento LIKE %s ORDER BY num_asiento DESC LIMIT 1", (prefijo + '%',))
                res = c.fetchone()
        except Exception: pass
    if res and res[0]:
        try:
            num = int(res[0].replace(prefijo, "")) + 1
            return f"{prefijo}{str(num).zfill(8)}"
        except: pass
    return f"{prefijo}00000001"
