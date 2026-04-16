import psycopg2
import streamlit as st
import pandas as pd

def conectar():
    try:
        url = st.secrets["database"]["url"]
        conn = psycopg2.connect(url, sslmode='require')
        return conn
    except Exception as e:
        st.error(f"Error crítico de conexión: {e}")
        return None

def ejecutar_query(query, params=None, fetch=True):
    conn = conectar()
    res = None
    if conn:
        try:
            with conn.cursor() as c:
                c.execute(query, params)
                if fetch: res = c.fetchall()
            conn.commit()
        except Exception as e:
            conn.rollback() # Limpia el error para que la interfaz siga viva
            st.error(f"Error en base de datos: {e}")
        finally:
            conn.close()
    return res

def inicializar_db():
    # Estructura Maestra de Módulos (Estilo SAP)
    tablas = [
        # 1. Plan de Cuentas y Centros de Costo
        '''CREATE TABLE IF NOT EXISTS plan_cuentas (codigo TEXT PRIMARY KEY, nombre TEXT, tipo TEXT)''',
        '''CREATE TABLE IF NOT EXISTS centros_costo (id SERIAL PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT)''',
        
        # 2. Control de Períodos por Módulo
        '''CREATE TABLE IF NOT EXISTS periodos_fiscales (
            periodo TEXT PRIMARY KEY, modulo_cg TEXT DEFAULT 'Cerrado', 
            modulo_cp TEXT DEFAULT 'Cerrado', modulo_cv TEXT DEFAULT 'Cerrado')''',
            
        # 3. Entidades (Clientes y Proveedores)
        '''CREATE TABLE IF NOT EXISTS entidades (rif TEXT PRIMARY KEY, nombre TEXT, tipo TEXT)''',
        
        # 4. Contabilidad (Libro Mayor)
        '''CREATE TABLE IF NOT EXISTS asientos_cabecera (
            id SERIAL PRIMARY KEY, num_asiento TEXT UNIQUE, fecha DATE, concepto TEXT, origen TEXT)''',
        '''CREATE TABLE IF NOT EXISTS asientos_detalle (
            id SERIAL PRIMARY KEY, asiento_id INTEGER REFERENCES asientos_cabecera(id) ON DELETE CASCADE,
            cuenta_codigo TEXT, centro_costo TEXT, debe DECIMAL DEFAULT 0, haber DECIMAL DEFAULT 0, rif_tercero TEXT)'''
    ]
    for t in tablas: ejecutar_query(t, fetch=False)

def obtener_ultimo_correlativo(prefijo):
    res = ejecutar_query("SELECT num_asiento FROM asientos_cabecera WHERE num_asiento LIKE %s ORDER BY num_asiento DESC LIMIT 1", (prefijo + '%',), fetch=True)
    if res and res[0][0]:
        num = int(res[0][0].replace(prefijo, "")) + 1
        return f"{prefijo}{str(num).zfill(6)}"
    return f"{prefijo}000001"
