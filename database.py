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
    """Retorna la conexión. Si se detecta cerrada o rota, la regenera."""
    conn = obtener_conexion_base()
    if conn is None or conn.closed != 0:
        st.cache_resource.clear()  # Limpia la caché si la conexión se rompió
        conn = obtener_conexion_base()
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
            except Exception: pass
            st.error(f"Error en transacción: {e}")

def registrar_log(usuario, accion, tabla_afectada, detalle):
    """Sincronizado con la tabla logs_actividad real de tu base de datos Neon."""
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS logs_actividad (
        id SERIAL PRIMARY KEY, fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        usuario TEXT, accion TEXT, tabla_afectada TEXT, detalle TEXT)''')
    ejecutar_transaccion(
        "INSERT INTO logs_actividad (usuario, accion, tabla_afectada, detalle) VALUES (%s, %s, %s, %s)", 
        (usuario, accion, tabla_afectada, detalle)
    )

def obtener_configuracion_empresa():
    conn = conectar()
    res = None
    if conn:
        try:
            with conn.cursor() as c:
                c.execute("SELECT nombre_empresa, rif_empresa, direccion_empresa FROM configuracion WHERE id = 1")
                res = c.fetchone()
        except Exception: pass
    
    if res:
        return {
            "nombre_empresa": res[0] if res[0] else "ADONAI GROUP", 
            "rif_empresa": res[1] if res[1] else "", 
            "direccion_empresa": res[2] if res[2] else "",
            "tipo_contribuyente": "Ordinario",
            "ut_valor": 0.00,
            "factor_sustraendo": 83.3334
        }
    return {"nombre_empresa": "ADONAI GROUP", "rif_empresa": "", "direccion_empresa": "", "tipo_contribuyente": "Ordinario", "ut_valor": 0.00, "factor_sustraendo": 83.3334}

def inicializar_db():
    """Garantiza la existencia de las tablas principales respetando las columnas existentes."""
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, rol TEXT, usuario TEXT, clave TEXT)''')
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS username TEXT UNIQUE;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password TEXT;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS clave TEXT;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT;")
    
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS periodos_fiscales (id SERIAL PRIMARY KEY, periodo TEXT UNIQUE, estatus TEXT DEFAULT 'Abierto')''')
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_cabecera (id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE, concepto TEXT, origen TEXT, creado_por TEXT)''')
    
    # Asegurar parámetros fiscales en configuración
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS configuracion (
        id INTEGER PRIMARY KEY DEFAULT 1, nombre_empresa TEXT, rif_empresa TEXT, 
        direccion_empresa TEXT, tipo_contribuyente TEXT, ut_valor NUMERIC(12,2), factor_sustraendo NUMERIC(12,4))''')
    ejecutar_transaccion("ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS tipo_contribuyente TEXT;")
    ejecutar_transaccion("ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS ut_valor NUMERIC(12,2);")
    ejecutar_transaccion("ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS factor_sustraendo NUMERIC(12,4);")

    # Inicializaciones por defecto
    pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
    ejecutar_transaccion("INSERT INTO usuarios (username, usuario, password, rol) VALUES ('admin', 'admin', 'admin123', 'admin') ON CONFLICT DO NOTHING")
    ejecutar_transaccion("INSERT INTO configuracion (id, nombre_empresa) VALUES (1, 'ADONAI GROUP') ON CONFLICT (id) DO NOTHING")
