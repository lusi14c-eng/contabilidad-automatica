import streamlit as st
import pandas as pd
import database
from modulos import entidades, compras

st.set_page_config(page_title="Adonai ERP", layout="wide")
database.inicializar_db()

def modulo_configuracion_sistema():
    st.title("⚙️ Configuración del Sistema")
    conf = database.obtener_configuracion_empresa()
    
    with st.form("form_global"):
        st.subheader("Datos de la Empresa")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Razón Social", value=conf['nombre_empresa'])
            rif = st.text_input("RIF Empresa", value=conf['rif_empresa'])
            t_contrib = st.selectbox("Tu Tipo de Contribuyente", ["Especial", "Ordinario", "Formal"], 
                                    index=["Especial", "Ordinario", "Formal"].index(conf['tipo_contribuyente']))
        with col2:
            dir_f = st.text_area("Dirección Fiscal", value=conf['direccion_empresa'])
        
        st.divider()
        st.subheader("Parámetros Fiscales")
        c1, c2 = st.columns(2)
        nueva_ut = c1.number_input("UT (Bs.)", value=conf['ut_valor'])
        nuevo_f = c2.number_input("Factor Sustraendo", value=conf['factor_sustraendo'])
        
        if st.form_submit_button("✅ Guardar Cambios"):
            conn = database.conectar()
            c = conn.cursor()
            c.execute("""UPDATE configuracion SET nombre_empresa=%s, rif_empresa=%s, direccion_empresa=%s, 
                         ut_valor=%s, factor_sustraendo=%s, tipo_contribuyente=%s WHERE id=1""",
                      (nombre, rif, dir_f, nueva_ut, nuevo_f, t_contrib))
            conn.commit()
            conn.close()
            st.success("Configuración actualizada.")
            st.rerun()

def modulo_gestion_usuarios():
    st.title("👥 Usuarios")
    conn = database.conectar()
    df = pd.read_sql("SELECT username as \"Usuario\", rol as \"Rol\" FROM usuarios", conn)
    conn.close()
    st.table(df)

def check_password():
    if "auth" not in st.session_state:
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.form_submit_button("Entrar"):
                conn = database.conectar()
                c = conn.cursor()
                c.execute("SELECT username, rol FROM usuarios WHERE username=%s AND password=%s", (u, p))
                res = c.fetchone()
                if res:
                    st.session_state["auth"], st.session_state["rol"] = res[0], res[1]
                    st.rerun()
                else: st.error("Fallo")
        return False
    return True

if check_password():
    st.sidebar.title("Adonai ERP")
    opciones = ["Dashboard", "Entidades", "Compras", "Perfil"]
    if st.session_state["rol"] == "admin":
        opciones += ["Usuarios", "Configuración"]
    
    menu = st.sidebar.selectbox("Menú", opciones)
    
    if menu == "Entidades": entidades.modulo_maestro_entidades()
    elif menu == "Compras": compras.modulo_compras()
    elif menu == "Configuración": modulo_configuracion_sistema()
    elif menu == "Usuarios": modulo_gestion_usuarios()
    elif st.sidebar.button("Salir"): 
        del st.session_state["auth"]
        st.rerun()
