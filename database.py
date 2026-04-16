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
                if fetch: res = c.fetchall()
            conn.commit()
        except Exception as e:
            conn.rollback()
            st.error(f"Error en DB: {e}")
        finally:
            conn.close()
    return res

def inicializar_db():
    queries = [
        # 1. Configuración de Empresa
        "CREATE TABLE IF NOT EXISTS configuracion (id INTEGER PRIMARY KEY DEFAULT 1, nombre_empresa TEXT, rif_empresa TEXT, direccion TEXT, moneda TEXT DEFAULT 'USD')",
        # 2. Entidades (Proveedores / Clientes)
        "CREATE TABLE IF NOT EXISTS entidades (rif TEXT PRIMARY KEY, nombre TEXT, tipo TEXT, contribuyente TEXT)",
        # 3. Contabilidad
        "CREATE TABLE IF NOT EXISTS plan_cuentas (codigo TEXT PRIMARY KEY, nombre TEXT, tipo TEXT)",
        "CREATE TABLE IF NOT EXISTS periodos_fiscales (periodo TEXT PRIMARY KEY, modulo_cg TEXT DEFAULT 'Cerrado', modulo_cp TEXT DEFAULT 'Cerrado')",
        "CREATE TABLE IF NOT EXISTS asientos_cabecera (id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE, concepto TEXT, origen TEXT)",
        "CREATE TABLE IF NOT EXISTS asientos_detalle (id SERIAL PRIMARY KEY, asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE, cuenta_codigo TEXT, debe DECIMAL, haber DECIMAL)",
        # 4. Compras (Facturación)
        "CREATE TABLE IF NOT EXISTS compras (id SERIAL PRIMARY KEY, fecha DATE, rif_proveedor TEXT, num_factura TEXT, base_imponible DECIMAL, iva_monto DECIMAL, total DECIMAL, asiento_id INTEGER)"
    ]
    for q in queries: ejecutar_query(q)
    # Datos iniciales de empresa
    ejecutar_query("INSERT INTO configuracion (id, nombre_empresa) VALUES (1, 'NUEVA EMPRESA') ON CONFLICT DO NOTHING")

def obtener_ultimo_correlativo(prefijo):
    res = ejecutar_query("SELECT num_asiento FROM asientos_cabecera WHERE num_asiento LIKE %s ORDER BY num_asiento DESC LIMIT 1", (prefijo + '%',), fetch=True)
    if res and res[0][0]:
        num = int(res[0][0].replace(prefijo, "")) + 1
        return f"{prefijo}{str(num).zfill(6)}"
    return f"{prefijo}000001"
