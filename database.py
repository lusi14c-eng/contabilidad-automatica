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

def inicializar_db():
    conn = conectar()
    if conn:
        try:
            c = conn.cursor()
            
            # 1. TABLAS DE SEGURIDAD
            c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)")
            c.execute('''CREATE TABLE IF NOT EXISTS logs_actividad (
                id SERIAL PRIMARY KEY, fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usuario TEXT, accion TEXT, tabla_afectada TEXT, detalle TEXT)''')

            # 2. CONTABILIDAD GENERAL (CG)
            c.execute('''CREATE TABLE IF NOT EXISTS asientos_cabecera (
                id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE,
                concepto TEXT, origen TEXT, creado_por TEXT, 
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # Forzar columnas en asientos_cabecera
            for col in [("origen", "TEXT"), ("creado_por", "TEXT")]:
                try:
                    c.execute(f"ALTER TABLE asientos_cabecera ADD COLUMN IF NOT EXISTS {col[0]} {col[1]}")
                except: pass

            c.execute('''CREATE TABLE IF NOT EXISTS asientos_detalle (
                id SERIAL PRIMARY KEY, 
                asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE,
                cuenta_codigo TEXT, centro_costo_id INTEGER, 
                debe DECIMAL DEFAULT 0, haber DECIMAL DEFAULT 0)''')

            c.execute("CREATE TABLE IF NOT EXISTS centros_costo (id SERIAL PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT)")

            # 3. CUENTAS POR PAGAR (CP)
            c.execute('''CREATE TABLE IF NOT EXISTS entidades (
                rif TEXT PRIMARY KEY, nombre TEXT, direccion TEXT, 
                tipo_persona TEXT, tipo_contribuyente TEXT, categoria TEXT, 
                retencion_islr_pct DECIMAL, retencion_iva_pct DECIMAL)''')

            c.execute('''CREATE TABLE IF NOT EXISTS compra_subtipos (
                id SERIAL PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, 
                cuenta_codigo TEXT)''')

            c.execute('''CREATE TABLE IF NOT EXISTS compras (
                id SERIAL PRIMARY KEY, fecha DATE, rif_proveedor TEXT REFERENCES entidades(rif), 
                num_factura TEXT, num_control TEXT, tipo_documento TEXT DEFAULT 'FAC',
                monto_exento DECIMAL DEFAULT 0, base_imponible DECIMAL DEFAULT 0, iva_monto DECIMAL DEFAULT 0, 
                iva_retenido DECIMAL DEFAULT 0, islr_retenido DECIMAL DEFAULT 0, total_factura DECIMAL DEFAULT 0,
                saldo_pendiente DECIMAL DEFAULT 0, subtipo TEXT, asiento_id INTEGER, creado_por TEXT)''')

            # MIGRACIÓN DE COLUMNAS PARA COMPRAS
            columnas_compras = [
                ("tipo_documento", "TEXT DEFAULT 'FAC'"),
                ("saldo_pendiente", "DECIMAL DEFAULT 0"),
                ("asiento_id", "INTEGER"),
                ("creado_por", "TEXT")
            ]
            for col, tipo in columnas_compras:
                try:
                    c.execute(f"ALTER TABLE compras ADD COLUMN IF NOT EXISTS {col} {tipo}")
                except: pass

            # Actualizar saldos de facturas antiguas
            c.execute("UPDATE compras SET saldo_pendiente = total_factura WHERE saldo_pendiente IS NULL OR saldo_pendiente = 0")

            # 4. CONFIGURACIÓN
            c.execute('''CREATE TABLE IF NOT EXISTS configuracion (
                id INTEGER PRIMARY KEY DEFAULT 1, nombre_empresa TEXT, rif_empresa TEXT, 
                direccion_empresa TEXT, ut_valor DECIMAL DEFAULT 9.00, 
                factor_sustraendo DECIMAL DEFAULT 83.3334, tipo_contribuyente TEXT DEFAULT 'Ordinario')''')

            # Insertar configuración inicial si no existe
            c.execute("SELECT COUNT(*) FROM configuracion")
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO configuracion (nombre_empresa, rif_empresa, ut_valor) VALUES (%s, %s, %s)", 
                          ('ADONAI INDUSTRIAL GROUP, C.A.', 'J-00000000-0', 9.00))

            conn.commit()
        except Exception as e:
            st.error(f"Error inicializando base de datos: {e}")
        finally:
            c.close()
            conn.close()

def registrar_log(usuario, accion, tabla, detalle):
    conn = conectar()
    if conn:
        try:
            c = conn.cursor()
            c.execute("INSERT INTO logs_actividad (usuario, accion, tabla_afectada, detalle) VALUES (%s, %s, %s, %s)",
                      (usuario, accion, tabla, detalle))
            conn.commit()
        finally:
            conn.close()

def obtener_ultimo_correlativo(prefijo):
    conn = conectar()
    if conn:
        try:
            c = conn.cursor()
            c.execute("SELECT num_asiento FROM asientos_cabecera WHERE num_asiento LIKE %s ORDER BY num_asiento DESC LIMIT 1", (prefijo + '%',))
            res = c.fetchone()
            if res:
                ultimo_num = int(res[0].replace(prefijo, ""))
                return f"{prefijo}{str(ultimo_num + 1).zfill(8)}"
        finally:
            conn.close()
    return f"{prefijo}00000001"

def obtener_configuracion_empresa():
    conn = conectar()
    if conn:
        try:
            c = conn.cursor()
            c.execute("SELECT nombre_empresa, rif_empresa, direccion_empresa, ut_valor, factor_sustraendo, tipo_contribuyente FROM configuracion WHERE id = 1")
            res = c.fetchone()
            if res:
                return {
                    "nombre_empresa": res[0], "rif_empresa": res[1], "direccion_empresa": res[2], 
                    "ut_valor": float(res[3]), "factor_sustraendo": float(res[4]), "tipo_contribuyente": res[5]
                }
        finally:
            conn.close()
    return {"nombre_empresa": "Error", "ut_valor": 9.0, "tipo_contribuyente": "Ordinario", "factor_sustraendo": 83.3334, "rif_empresa": "", "direccion_empresa": ""}
