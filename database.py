import psycopg2
import streamlit as st
from datetime import datetime

def conectar():
    try:
        url = st.secrets["database"]["url"]
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def ejecutar_transaccion(query, params=None):
    """Ejecuta una consulta y hace commit inmediatamente para evitar bloqueos."""
    conn = conectar()
    if conn:
        try:
            with conn.cursor() as c:
                c.execute(query, params)
            conn.commit()
        except Exception as e:
            conn.rollback() # Limpia la transacción fallida
        finally:
            conn.close()

def inicializar_db():
    # 1. TABLA ASIENTOS
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_cabecera (
        id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE,
        concepto TEXT, origen TEXT, creado_por TEXT, fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Intentar añadir columnas una a una (si fallan por ya existir, no importa)
    columnas_asientos = [
        ("num_asiento", "TEXT UNIQUE"), ("origen", "TEXT"), ("creado_por", "TEXT"),
        ("fecha", "DATE"), ("concepto", "TEXT")
    ]
    for col, tipo in columnas_asientos:
        ejecutar_transaccion(f"ALTER TABLE asientos_cabecera ADD COLUMN {col} {tipo}")

    # 2. OTRAS TABLAS
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS asientos_detalle (
        id SERIAL PRIMARY KEY, asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE,
        cuenta_codigo TEXT, centro_costo_id INTEGER, debe DECIMAL DEFAULT 0, haber DECIMAL DEFAULT 0)''')

    ejecutar_transaccion("CREATE TABLE IF NOT EXISTS centros_costo (id SERIAL PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT)")
    
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS entidades (
        rif TEXT PRIMARY KEY, nombre TEXT, direccion TEXT, tipo_persona TEXT, 
        tipo_contribuyente TEXT, categoria TEXT, retencion_islr_pct DECIMAL, retencion_iva_pct DECIMAL)''')

    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS compra_subtipos (
        id SERIAL PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, cuenta_codigo TEXT)''')

    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS compras (
        id SERIAL PRIMARY KEY, fecha DATE, rif_proveedor TEXT REFERENCES entidades(rif), 
        num_factura TEXT, num_control TEXT, tipo_documento TEXT DEFAULT 'FAC',
        monto_exento DECIMAL DEFAULT 0, base_imponible DECIMAL DEFAULT 0, iva_monto DECIMAL DEFAULT 0, 
        iva_retenido DECIMAL DEFAULT 0, islr_retenido DECIMAL DEFAULT 0, total_factura DECIMAL DEFAULT 0,
        saldo_pendiente DECIMAL DEFAULT 0, subtipo TEXT, asiento_id INTEGER, creado_por TEXT)''')

    # Forzar columnas en compras
    for col in [("tipo_documento", "TEXT DEFAULT 'FAC'"), ("saldo_pendiente", "DECIMAL DEFAULT 0"), ("asiento_id", "INTEGER"), ("creado_por", "TEXT")]:
        ejecutar_transaccion(f"ALTER TABLE compras ADD COLUMN {col[0]} {col[1]}")

    # 3. CONFIGURACIÓN
    ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS configuracion (
        id INTEGER PRIMARY KEY DEFAULT 1, nombre_empresa TEXT, rif_empresa TEXT, 
        direccion_empresa TEXT, ut_valor DECIMAL DEFAULT 9.00, 
        factor_sustraendo DECIMAL DEFAULT 83.3334, tipo_contribuyente TEXT DEFAULT 'Ordinario')''')

    # Insertar configuración inicial
    ejecutar_transaccion("INSERT INTO configuracion (id, nombre_empresa) VALUES (1, 'ADONAI GROUP') ON CONFLICT (id) DO NOTHING")

def registrar_log(usuario, accion, tabla, detalle):
    ejecutar_transaccion("INSERT INTO logs_actividad (usuario, accion, tabla_afectada, detalle) VALUES (%s, %s, %s, %s)",
                         (usuario, accion, tabla, detalle))

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

def obtener_configuracion_empresa():
    conn = conectar()
    conf = {"nombre_empresa": "Cargando...", "ut_valor": 9.0, "factor_sustraendo": 83.3334, "tipo_contribuyente": "Ordinario", "rif_empresa": "", "direccion_empresa": ""}
    if conn:
        try:
            with conn.cursor() as c:
                c.execute("SELECT nombre_empresa, rif_empresa, direccion_empresa, ut_valor, factor_sustraendo, tipo_contribuyente FROM configuracion WHERE id = 1")
                res = c.fetchone()
                if res:
                    conf = {"nombre_empresa": res[0], "rif_empresa": res[1], "direccion_empresa": res[2], 
                            "ut_valor": float(res[3]), "factor_sustraendo": float(res[4]), "tipo_contribuyente": res[5]}
        finally:
            conn.close()
    return conf
