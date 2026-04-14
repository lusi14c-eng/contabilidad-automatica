import psycopg2
import streamlit as st

def conectar():
    try:
        url = st.secrets["database"]["url"]
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def inicializar_db():
    conn = conectar()
    if conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS entidades (
            rif TEXT PRIMARY KEY, nombre TEXT, direccion TEXT, 
            tipo_persona TEXT, tipo_contribuyente TEXT, categoria TEXT, 
            retencion_islr_pct DECIMAL, retencion_iva_pct DECIMAL)''')

        c.execute('''CREATE TABLE IF NOT EXISTS compras (
            id SERIAL PRIMARY KEY, fecha DATE, rif_proveedor TEXT REFERENCES entidades(rif), 
            num_factura TEXT, num_control TEXT, monto_exento DECIMAL, 
            base_imponible DECIMAL, iva_monto DECIMAL, islr_retenido DECIMAL, 
            iva_retenido DECIMAL, total_factura DECIMAL, subtipo TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS cuentas_contables (
            codigo TEXT PRIMARY KEY, nombre TEXT NOT NULL, tipo TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS asientos_cabecera (
            id SERIAL PRIMARY KEY, fecha DATE, descripcion TEXT, 
            referencia_tipo TEXT, referencia_id INTEGER)''')

        c.execute('''CREATE TABLE IF NOT EXISTS asientos_detalle (
            id SERIAL PRIMARY KEY, asiento_id INTEGER REFERENCES asientos_cabecera(id), 
            cuenta_codigo TEXT, debe DECIMAL DEFAULT 0, haber DECIMAL DEFAULT 0)''')

        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)")
        
        usuarios = [('lgonzalez', 'Adonai.2024', 'admin'), ('jmoreno', 'Adonai.2024', 'usuario')]
        for u, p, r in usuarios:
            c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING", (u, p, r))

        conn.commit()
        c.close()
        conn.close()

def obtener_configuracion_empresa():
    return {
        "nombre": "ADONAI INDUSTRIAL GROUP, C.A.", 
        "rif": "J-00000000-0",           
        "direccion": "Valencia, Venezuela",
        "ut_valor": 9.00,                
        "factor_sustraendo": 0.25         
    }
