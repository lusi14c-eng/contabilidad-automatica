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
        # Crear todas las tablas necesarias
        c.execute("CREATE TABLE IF NOT EXISTS entidades (rif TEXT PRIMARY KEY, nombre TEXT, direccion TEXT, tipo_persona TEXT, tipo_contribuyente TEXT, categoria TEXT, retencion_islr_pct DECIMAL, retencion_iva_pct DECIMAL)")
        c.execute("CREATE TABLE IF NOT EXISTS subtipos_gasto (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, cuenta_contable TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS compras (id SERIAL PRIMARY KEY, fecha DATE, rif_proveedor TEXT, num_factura TEXT, num_control TEXT, monto_exento DECIMAL, base_imponible DECIMAL, iva_monto DECIMAL, islr_retenido DECIMAL, iva_retenido DECIMAL, total_factura DECIMAL, subtipo TEXT, aplica_ret_islr BOOLEAN, aplica_ret_iva BOOLEAN)")
        
        # TABLA DE USUARIOS
        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)")
        
        # INSERTAR USUARIOS (lgonzalez como admin, jmoreno como usuario)
        usuarios = [
            ('lgonzalez', 'Adonai.2024', 'admin'),
            ('jmoreno', 'Adonai.2024', 'usuario')
        ]
        for u, p, r in usuarios:
            c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING", (u, p, r))
        
        conn.commit()
        c.close()
        conn.close()
