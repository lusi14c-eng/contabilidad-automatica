import psycopg2
import streamlit as st

def conectar():
    try:
        url = st.secrets["database"]["url"]
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def ejecutar_query(query, params=None, fetch=False):
    conn = conectar()
    res = None
    if conn:
        try:
            with conn.cursor() as c:
                c.execute(query, params)
                if fetch:
                    res = c.fetchall()
            conn.commit()
        except Exception as e:
            conn.rollback() # Limpia el error para evitar el mensaje rojo "aborted transaction"
            st.error(f"Error en DB: {e}")
        finally:
            conn.close()
    return res

def inicializar_db():
    # Estructura Maestra
    queries = [
        # Plan de Cuentas y Centros de Costo
        "CREATE TABLE IF NOT EXISTS plan_cuentas (codigo TEXT PRIMARY KEY, nombre TEXT, tipo TEXT)",
        "CREATE TABLE IF NOT EXISTS centros_costo (id SERIAL PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT)",
        
        # Períodos con columnas específicas por módulo (SAP Style)
        "CREATE TABLE IF NOT EXISTS periodos_fiscales (periodo TEXT PRIMARY KEY, estatus TEXT DEFAULT 'Abierto')",
        
        # Diario General (Maestro-Detalle)
        "CREATE TABLE IF NOT EXISTS asientos_cabecera (id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE, concepto TEXT, origen TEXT, creado_por TEXT)",
        "CREATE TABLE IF NOT EXISTS asientos_detalle (id SERIAL PRIMARY KEY, asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE, cuenta_codigo TEXT, centro_costo TEXT, debe DECIMAL DEFAULT 0, haber DECIMAL DEFAULT 0, rif_tercero TEXT)"
    ]
    for q in queries: ejecutar_query(q)

    # MIGRACIÓN AUTOMÁTICA: Asegurar columnas de módulos
    for col in ["modulo_cg", "modulo_cp", "modulo_cv", "modulo_cb"]:
        ejecutar_query(f"ALTER TABLE periodos_fiscales ADD COLUMN IF NOT EXISTS {col} TEXT DEFAULT 'Cerrado'")

def obtener_ultimo_correlativo(prefijo):
    res = ejecutar_query("SELECT num_asiento FROM asientos_cabecera WHERE num_asiento LIKE %s ORDER BY num_asiento DESC LIMIT 1", (prefijo + '%',), fetch=True)
    if res and res[0][0]:
        try:
            num = int(res[0][0].replace(prefijo, "")) + 1
            return f"{prefijo}{str(num).zfill(6)}"
        except: pass
    return f"{prefijo}000001"
