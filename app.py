import streamlit as st
import pandas as pd
import database
from modulos import entidades, compras

st.set_page_config(page_title="Adonai ERP", layout="wide")
database.inicializar_db()

def modulo_perfil():
    st.title("🔐 Mi Perfil")
    with st.form("f_pass"):
        nueva = st.text_input("Nueva Clave", type="password")
        if st.form_submit_button("Cambiar Clave"):
            conn = database.conectar()
            c = conn.cursor()
            c.execute("UPDATE usuarios SET password=%s WHERE username=%s", (nueva, st.session_state['usuario_autenticado']))
            conn.commit()
            conn.close()
            st.success("Clave actualizada.")

def modulo_contabilidad():
    st.title("🧮 Gestión Contable")
    t1, t2 = st.tabs(["Plan de Cuentas", "Subtipos de Compra"])
    
    with t1:
        with st.form("n_cuenta"):
            col1, col2 = st.columns(2)
            c_cod = col1.text_input("Código")
            c_nom = col2.text_input("Nombre")
            if st.form_submit_button("Guardar Cuenta"):
                conn = database.conectar()
                c = conn.cursor()
                c.execute("INSERT INTO cuentas_contables (codigo, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (c_cod, c_nom))
                conn.commit()
                conn.close()
                st.rerun()
        conn = database.conectar()
        df = pd.read_sql("SELECT codigo, nombre FROM cuentas_contables ORDER BY codigo", conn)
        st.dataframe(df, use_container_width=True)

    with t2:
        st.subheader("Configurar Categorías de Gasto")
        conn = database.conectar()
        cuentas = pd.read_sql("SELECT codigo, nombre FROM cuentas_contables", conn)
        with st.form("n_sub"):
            nom_s = st.text_input("Nombre del Subtipo (Ej: Repuestos)")
            cta = st.selectbox("Asociar a Cuenta", [f"{r['codigo']} | {r['nombre']}" for _, r in cuentas.iterrows()])
            if st.form_submit_button("Crear Subtipo"):
                c = conn.cursor()
                c.execute("INSERT INTO compra_subtipos (nombre, cuenta_codigo) VALUES (%s, %s)", (nom_s, cta.split(" | ")[0]))
                conn.commit()
                st.rerun()
        df_s = pd.read_sql("SELECT nombre, cuenta_codigo FROM compra_subtipos", conn)
        st.table(df_s)
        conn.close()

def modulo_configuracion_sistema():
    st.title("⚙️ Configuración")
    conf = database.obtener_configuracion_empresa()
    with st.form("f_conf"):
        col1, col2 = st.columns(2)
        n = col1.text_input("Razón Social", value=conf['nombre_empresa'])
        r = col1.text_input("RIF", value=conf['rif_empresa'])
        t = col1.selectbox("Contribuyente", ["Especial", "Ordinario", "Formal"], index=["Especial", "Ordinario", "Formal"].index(conf['tipo_contribuyente']))
        ut = col2.number_input("UT", value=conf['ut_valor'])
        if st.form_submit_button("Guardar"):
            conn = database.conectar()
            c = conn.cursor()
            c.execute("UPDATE configuracion SET nombre_empresa=%s, rif_empresa=%s, ut_valor=%s, tipo_contribuyente=%s WHERE id=1", (n, r, ut, t))
            conn.commit()
            conn.close()
            st.rerun()

def check_password():
    if "usuario_autenticado" not in st.session_state:
        with st.form("l"):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.form_submit_button("Entrar"):
                conn = database.conectar()
                c = conn.cursor()
                c.execute("SELECT username, rol FROM usuarios WHERE username=%s AND password=%s", (u, p))
                res = c.fetchone()
                if res:
                    st.session_state["usuario_autenticado"], st.session_state["rol"] = res[0], res[1]
                    st.rerun()
        return False
    return True

if check_password():
    st.sidebar.title("Adonai ERP")
    op = ["Dashboard", "Registrar Entidad", "Registro de Compras", "Mi Perfil"]
    if st.session_state["rol"] == "admin":
        op += ["Contabilidad", "Configuración Sistema"]
    
    menu = st.sidebar.selectbox("Menú", op)
    if menu == "Registrar Entidad": entidades.modulo_maestro_entidades()
    elif menu == "Registro de Compras": compras.modulo_compras()
    elif menu == "Contabilidad": modulo_contabilidad()
    elif menu == "Configuración Sistema": modulo_configuracion_sistema()
    elif menu == "Mi Perfil": modulo_perfil()
