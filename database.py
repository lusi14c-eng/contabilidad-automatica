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
        c = conn.cursor()
        
        # 1. SEGURIDAD Y AUDITORÍA
        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)")
        c.execute('''CREATE TABLE IF NOT EXISTS logs_actividad (
            id SERIAL PRIMARY KEY,
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usuario TEXT,
            accion TEXT,
            tabla_afectada TEXT,
            detalle TEXT)''')

        # 2. CONTABILIDAD GENERAL (CG)
        c.execute('''CREATE TABLE IF NOT EXISTS periodos_fiscales (
            periodo TEXT PRIMARY KEY, -- Formato YYYY-MM
            estatus TEXT DEFAULT 'Abierto')''')

        c.execute('''CREATE TABLE IF NOT EXISTS centros_costo (
            id SERIAL PRIMARY KEY,
            codigo TEXT UNIQUE,
            nombre TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS cuentas_contables (
            codigo TEXT PRIMARY KEY, 
            nombre TEXT NOT NULL, 
            tipo TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS asientos_cabecera (
            id SERIAL PRIMARY KEY,
            num_asiento TEXT UNIQUE, -- CP00000001 o CG00000001
            fecha DATE,
            concepto TEXT,
            origen TEXT, -- 'CP' o 'CG'
            creado_por TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        c.execute('''CREATE TABLE IF NOT EXISTS asientos_detalle (
            id SERIAL PRIMARY KEY,
            asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE,
            cuenta_codigo TEXT REFERENCES cuentas_contables(codigo),
            centro_costo_id INTEGER REFERENCES centros_costo(id),
            debe DECIMAL DEFAULT 0,
            haber DECIMAL DEFAULT 0)''')

        # 3. CUENTAS POR PAGAR (CP)
        c.execute('''CREATE TABLE IF NOT EXISTS entidades (
            rif TEXT PRIMARY KEY, nombre TEXT, direccion TEXT, 
            tipo_persona TEXT, tipo_contribuyente TEXT, categoria TEXT, 
            retencion_islr_pct DECIMAL, retencion_iva_pct DECIMAL)''')

        c.execute('''CREATE TABLE IF NOT EXISTS compra_subtipos (
            id SERIAL PRIMARY KEY,
            nombre TEXT UNIQUE NOT NULL,
            cuenta_codigo TEXT REFERENCES cuentas_contables(codigo))''')

        c.execute('''CREATE TABLE IF NOT EXISTS compras (
            id SERIAL PRIMARY KEY, 
            fecha DATE, 
            rif_proveedor TEXT REFERENCES entidades(rif), 
            num_factura TEXT, 
            num_control TEXT, 
            tipo_documento TEXT DEFAULT 'FAC', -- 'FAC' o 'NC'
            monto_exento DECIMAL DEFAULT 0, 
            base_imponible DECIMAL DEFAULT 0, 
            iva_monto DECIMAL DEFAULT 0, 
            islr_retenido DECIMAL DEFAULT 0, 
            iva_retenido DECIMAL DEFAULT 0, 
            total_factura DECIMAL DEFAULT 0,
            saldo_pendiente DECIMAL DEFAULT 0, -- Para Cuentas por Pagar
            subtipo TEXT,
            asiento_id INTEGER REFERENCES asientos_cabecera(id),
            creado_por TEXT)''')

        # 4. CONFIGURACIÓN Y MIGRACIÓN DE COLUMNAS (Para no perder datos)
        try:
            c.execute("ALTER TABLE compras ADD COLUMN IF NOT EXISTS tipo_documento TEXT DEFAULT 'FAC'")
            c.execute("ALTER TABLE compras ADD COLUMN IF NOT EXISTS saldo_pendiente DECIMAL DEFAULT 0")
            c.execute("ALTER TABLE compras ADD COLUMN IF NOT EXISTS asiento_id INTEGER")
            c.execute("ALTER TABLE compras ADD COLUMN IF NOT EXISTS creado_por TEXT")
            # Actualizar saldos de facturas viejas
            c.execute("UPDATE compras SET saldo_pendiente = total_factura WHERE saldo_pendiente IS NULL OR saldo_pendiente = 0")
        except:
            pass

        c.execute('''CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY DEFAULT 1,
            nombre_empresa TEXT, rif_empresa TEXT, direccion_empresa TEXT,
            ut_valor DECIMAL DEFAULT 9.00, factor_sustraendo DECIMAL DEFAULT 83.3334,
            tipo_contribuyente TEXT DEFAULT 'Ordinario')''')

        # 5. DATOS INICIALES
        c.execute("SELECT COUNT(*) FROM configuracion")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO configuracion (nombre_empresa, rif_empresa, ut_valor) VALUES (%s, %s, %s)", 
                      ('Empresa Nueva', 'J-00000000-0', 9.00))

        conn.commit()
        c.close()
        conn.close()

def registrar_log(usuario, accion, tabla, detalle):
    conn = conectar()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO logs_actividad (usuario, accion, tabla_afectada, detalle) VALUES (%s, %s, %s, %s)",
                  (usuario, accion, tabla, detalle))
        conn.commit()
        conn.close()

def obtener_ultimo_correlativo(prefijo):
    """Genera el siguiente número tipo CP00000001"""
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT num_asiento FROM asientos_cabecera WHERE num_asiento LIKE %s ORDER BY num_asiento DESC LIMIT 1", (prefijo + '%',))
    res = c.fetchone()
    conn.close()
    if res:
        ultimo_num = int(res[0].replace(prefijo, ""))
        nuevo_num = ultimo_num + 1
    else:
        nuevo_num = 1
    return f"{prefijo}{str(nuevo_num).zfill(8)}"

def obtener_configuracion_empresa():
    try:
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT nombre_empresa, rif_empresa, direccion_empresa, ut_valor, factor_sustraendo, tipo_contribuyente FROM configuracion WHERE id = 1")
        res = c.fetchone()
        conn.close()
        return {
            "nombre_empresa": res[0], "rif_empresa": res[1], "direccion_empresa": res[2], 
            "ut_valor": float(res[3]), "factor_sustraendo": float(res[4]), "tipo_contribuyente": res[5]
        }
    except:
        return {"nombre_empresa": "Error", "ut_valor": 9.0, "tipo_contribuyente": "Ordinario", "factor_sustraendo": 83.3334}
