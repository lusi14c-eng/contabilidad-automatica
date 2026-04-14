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
        
        # 1. Tabla de Entidades
        c.execute('''CREATE TABLE IF NOT EXISTS entidades (
            rif TEXT PRIMARY KEY, 
            nombre TEXT, 
            direccion TEXT, 
            tipo_persona TEXT, 
            tipo_contribuyente TEXT, 
            categoria TEXT, 
            retencion_islr_pct DECIMAL, 
            retencion_iva_pct DECIMAL)''')

        # 2. Tabla de Compras
        c.execute('''CREATE TABLE IF NOT EXISTS compras (
            id SERIAL PRIMARY KEY, 
            fecha DATE, 
            rif_proveedor TEXT REFERENCES entidades(rif), 
            num_factura TEXT, 
            num_control TEXT, 
            monto_exento DECIMAL, 
            base_imponible DECIMAL, 
            iva_monto DECIMAL, 
            islr_retenido DECIMAL, 
            iva_retenido DECIMAL, 
            total_factura DECIMAL, 
            subtipo TEXT)''')

        # 3. Tablas de Usuarios
        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)")
        
        # 4. Tabla de Configuración (REVISADA)
        # Se separó el valor por defecto para evitar el error de sintaxis
        c.execute('''CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY DEFAULT 1,
            nombre_empresa TEXT,
            rif_empresa TEXT,
            direccion_empresa TEXT,
            ut_valor DECIMAL,
            factor_sustraendo DECIMAL DEFAULT 83.3334,
            tipo_contribuyente TEXT DEFAULT 'Ordinario'
        )''')

        # Insertar configuración inicial solo si está vacía
        c.execute("SELECT COUNT(*) FROM configuracion")
        if c.fetchone()[0] == 0:
            c.execute("""INSERT INTO configuracion (nombre_empresa, rif_empresa, direccion_empresa, ut_valor, tipo_contribuyente) 
                         VALUES (%s, %s, %s, %s, %s)""", 
                      ('ADONAI INDUSTRIAL GROUP, C.A.', 'J-00000000-0', 'Valencia, Venezuela', 9.00, 'Ordinario'))

        # Usuarios iniciales
        usuarios = [('lgonzalez', 'Adonai.2024', 'admin'), ('jmoreno', 'Adonai.2024', 'usuario')]
        for u, p, r in usuarios:
            c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING", (u, p, r))

        conn.commit()
        c.close()
        conn.close()

# Asegúrate de que tu función obtener_configuracion_empresa en database.py se vea así:
def obtener_configuracion_empresa():
    try:
        conn = conectar()
        c = conn.cursor()
        # Traemos todos los campos necesarios de la tabla configuracion
        c.execute("""SELECT nombre_empresa, rif_empresa, direccion_empresa, 
                            ut_valor, factor_sustraendo, tipo_contribuyente 
                     FROM configuracion WHERE id = 1""")
        res = c.fetchone()
        conn.close()
        if res:
            return {
                "nombre": res[0], 
                "rif": res[1], 
                "direccion": res[2], 
                "ut_valor": float(res[3]), 
                "factor_sustraendo": float(res[4]),
                "tipo_contribuyente": res[5] # 'Especial', 'Ordinario' o 'Formal'
            }
    except Exception as e:
        return {"tipo_contribuyente": "Ordinario", "ut_valor": 0.0}
