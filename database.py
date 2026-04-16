import psycopg2
import streamlit as st
import hashlib

def conectar():
    try:
        url = st.secrets["database"]["url"]
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def ejecutar_transaccion(query, params=None):
    """Ejecuta una consulta y hace commit inmediatamente."""
    conn = conectar()
    if conn:
        try:
            with conn.cursor() as c:
                c.execute(query, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            st.error(f"Error: {e}")
        finally:
            conn.close()

def inicializar_db():
    # 1. SEGURIDAD (USUARIOS Y ROLES)
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, usuario TEXT UNIQUE, clave TEXT, rol TEXT, nombre TEXT)''')

    # 2. TABLAS CONTABLES Y PERIODOS
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS periodos_fiscales (
        id SERIAL PRIMARY KEY, periodo TEXT UNIQUE, estatus TEXT DEFAULT 'Abierto')''')

    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_cabecera (
        id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE, 
        concepto TEXT, origen TEXT, creado_por TEXT, fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_detalle (
        id SERIAL PRIMARY KEY, asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE,
        cuenta_codigo TEXT, centro_costo_id INTEGER, debe DECIMAL DEFAULT 0, haber DECIMAL DEFAULT 0)''')

    # 3. ENTIDADES Y COMPRAS
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS entidades (
        rif TEXT PRIMARY KEY, nombre TEXT, direccion TEXT, tipo_persona TEXT, 
        tipo_contribuyente TEXT, categoria TEXT, retencion_islr_pct DECIMAL, retencion_iva_pct DECIMAL)''')

    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS compras (
        id SERIAL PRIMARY KEY, fecha DATE, rif_proveedor TEXT REFERENCES entidades(rif), 
        num_factura TEXT, num_control TEXT, monto_exento DECIMAL DEFAULT 0, base_imponible DECIMAL DEFAULT 0, 
        iva_monto DECIMAL DEFAULT 0, total_factura DECIMAL DEFAULT 0, creado_por TEXT)''')

    # 4. CONFIGURACIÓN
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS configuracion (
        id INTEGER PRIMARY KEY DEFAULT 1, nombre_empresa TEXT, rif_empresa TEXT, 
        direccion_empresa TEXT, ut_valor DECIMAL DEFAULT 9.00)''')

    # Datos Iniciales (Usuario Admin: admin123)
    pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
    ejecutar_transaccion("INSERT INTO usuarios (usuario, clave, rol, nombre) VALUES ('admin', %s, 'Administrador', 'Admin Principal') ON CONFLICT DO NOTHING", (pw_hash,))
    ejecutar_transaccion("INSERT INTO configuracion (id, nombre_empresa) VALUES (1, 'ADONAI GROUP') ON CONFLICT (id) DO NOTHING")

def obtener_ultimo_correlativo(prefijo):
    conn = conectar()
    res = None
    if conn:
        try:
            with conn.cursor() as c:
                c.execute("SELECT num_asiento FROM asientos_cabecera WHERE num_asiento LIKE %s ORDER BY num_asiento DESC LIMIT 1", (prefijo + '%',))
                res = c.fetchone()
        finally:
            conn.close()
    if res and res[0]:
        try:
            num = int(res[0].replace(prefijo, "")) + 1
            return f"{prefijo}{str(num).zfill(8)}"
        except: pass
    return f"{prefijo}00000001"
