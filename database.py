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
            
            # 1. TABLA ASIENTOS (CON TODAS SUS COLUMNAS)
            c.execute('''CREATE TABLE IF NOT EXISTS asientos_cabecera (
                id SERIAL PRIMARY KEY,
                num_asiento TEXT UNIQUE,
                fecha DATE,
                concepto TEXT,
                origen TEXT,
                creado_por TEXT,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # CIRUGÍA DE COLUMNAS PARA ASIENTOS
            columnas_asientos = [
                ("num_asiento", "TEXT UNIQUE"),
                ("origen", "TEXT"),
                ("creado_por", "TEXT"),
                ("fecha", "DATE"),
                ("concepto", "TEXT")
            ]
            for col, tipo in columnas_asientos:
                try:
                    c.execute(f"ALTER TABLE asientos_cabecera ADD COLUMN {col} {tipo}")
                except: pass

            # 2. OTRAS TABLAS CONTABLES
            c.execute('''CREATE TABLE IF NOT EXISTS asientos_detalle (
                id SERIAL PRIMARY KEY,
                asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE,
                cuenta_codigo TEXT,
                centro_costo_id INTEGER,
                debe DECIMAL DEFAULT 0,
                haber DECIMAL DEFAULT 0)''')

            c.execute("CREATE TABLE IF NOT EXISTS centros_costo (id SERIAL PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT)")

            # 3. ENTIDADES Y COMPRAS
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
                    c.execute(f"ALTER TABLE compras ADD COLUMN {col} {tipo}")
                except: pass

            # Actualizar saldos
            c.execute("UPDATE compras SET saldo_pendiente = total_factura WHERE saldo_pendiente IS NULL OR saldo_pendiente = 0")

            # 4. CONFIGURACIÓN
            c.execute('''CREATE TABLE IF NOT EXISTS configuracion (
                id INTEGER PRIMARY KEY DEFAULT 1, nombre_empresa TEXT, rif_empresa TEXT, 
                direccion_empresa TEXT, ut_valor DECIMAL DEFAULT 9.00, 
                factor_sustraendo DECIMAL DEFAULT 83.3334, tipo_contribuyente TEXT DEFAULT 'Ordinario')''')

            c.execute("SELECT COUNT(*) FROM configuracion")
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO configuracion (nombre_empresa, rif_empresa, ut_valor) VALUES (%s, %s, %s)", 
                          ('ADONAI INDUSTRIAL GROUP, C.A.', 'J-00000000-0', 9.00))

            conn.commit()
        except Exception as e:
            st.error(f"Error inicializando base de datos: {e}")
        finally:
            # EL CIERRE SIEMPRE AL FINAL DE TODO
            c.close()
            conn.close()

# --- LAS DEMÁS FUNCIONES (registrar_log, obtener_correlativo, etc) SE MANTIENEN IGUAL ---
