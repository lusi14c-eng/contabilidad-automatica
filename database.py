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
        # ... (tablas base de usuarios y logs se mantienen igual) ...
        
        # Asegurar tabla asientos_cabecera con todas sus columnas
        c.execute('''CREATE TABLE IF NOT EXISTS asientos_cabecera (
            id SERIAL PRIMARY KEY,
            num_asiento TEXT UNIQUE,
            fecha DATE,
            concepto TEXT,
            origen TEXT,
            creado_por TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        # FORZAR COLUMNAS SI NO EXISTEN (Manejo de errores UndefinedColumn)
        columnas_asientos = [
            ("origen", "TEXT"),
            ("creado_por", "TEXT")
        ]
        for col, tipo in columnas_asientos:
            try:
                c.execute(f"ALTER TABLE asientos_cabecera ADD COLUMN IF NOT EXISTS {col} {tipo}")
            except: pass

        # Asegurar tabla asientos_detalle
        c.execute('''CREATE TABLE IF NOT EXISTS asientos_detalle (
            id SERIAL PRIMARY KEY,
            asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE,
            cuenta_codigo TEXT,
            centro_costo_id INTEGER,
            debe DECIMAL DEFAULT 0,
            haber DECIMAL DEFAULT 0)''')

        # ... (resto de tablas: compras, entidades, etc) ...
        conn.commit()
        c.close()
        conn.close()

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
