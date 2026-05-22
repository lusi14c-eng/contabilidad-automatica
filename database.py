import psycopg2
import streamlit as st
import hashlib

@st.cache_resource
def obtener_conexion_persistente():
    try:
        url = st.secrets["database"]["url"]
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        st.error(f"Error de conexión crítica: {e}")
        return None

def conectar():
    conn = obtener_conexion_persistente()
    if conn and conn.closed != 0:
        st.cache_resource.clear()
        conn = obtener_conexion_persistente()
    return conn

def ejecutar_transaccion(query, params=None):
    conn = conectar()
    if conn:
        try:
            with conn.cursor() as c:
                c.execute(query, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            st.error(f"Error en transacción: {e}")

def registrar_log(usuario, accion, tabla, detalle):
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY, usuario TEXT, accion TEXT, tabla TEXT, detalle TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    ejecutar_transaccion("INSERT INTO logs (usuario, accion, tabla, detalle) VALUES (%s, %s, %s, %s)", (usuario, accion, tabla, detalle))

def obtener_configuracion_empresa():
    """Retorna los datos con las llaves exactas que exige tu app.py"""
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
            "tipo_contribuyente": "Ordinario" # Valor seguro por defecto
        }
    return {"nombre_empresa": "ADONAI GROUP", "rif_empresa": "", "direccion_empresa": "", "tipo_contribuyente": "Ordinario"}

def inicializar_db():
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username TEXT UNIQUE, clave TEXT, rol TEXT, nombre TEXT)''')
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS username TEXT UNIQUE;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS usuario TEXT;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS clave TEXT;")
    ejecutar_transaccion("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT;")
    
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS periodos_fiscales (id SERIAL PRIMARY KEY, periodo TEXT UNIQUE, estatus TEXT DEFAULT 'Abierto')''')
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_cabecera (id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE, concepto TEXT, origen TEXT, creado_por TEXT)''')
    
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS configuracion (id INTEGER PRIMARY KEY DEFAULT 1, nombre_empresa TEXT, rif_empresa TEXT, direccion_empresa TEXT)''')

    pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
    ejecutar_transaccion("INSERT INTO usuarios (username, usuario, clave, rol, nombre) VALUES ('admin', 'admin', %s, 'Administrador', 'Admin Principal') ON CONFLICT DO NOTHING", (pw_hash,))
    ejecutar_transaccion("INSERT INTO configuracion (id, nombre_empresa) VALUES (1, 'ADONAI GROUP') ON CONFLICT (id) DO NOTHING")

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
