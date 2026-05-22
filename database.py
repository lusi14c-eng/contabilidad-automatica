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
    
    # Validamos si la conexión existe, si está cerrada (closed != 0) o si falló internamente
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
            # Si el cable se rompió en medio de la operación, limpiamos caché y reintentamos UNA vez
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
                pass  # Si la conexión estaba muerta, el rollback fallará, lo ignoramos de forma segura
            st.error(f"Error en transacción contable: {e}")

def registrar_log(usuario, accion, tabla, detalle):
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY, usuario TEXT, accion TEXT, tabla TEXT, detalle TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    ejecutar_transaccion("INSERT INTO logs (usuario, accion, tabla, detalle) VALUES (%s, %s, %s, %s)", (usuario, accion, tabla, detalle))

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
            "tipo_contribuyente": "Ordinario"
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
