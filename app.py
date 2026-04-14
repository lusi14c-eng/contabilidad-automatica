import streamlit as st
import database
import pandas as pd
from modulos import entidades, compras
st.set_page_config(page_title="Adonai ERP", layout="wide")
# Inicializar base de datos
database.inicializar_db()

def check_password():
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login_center"):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                conn = database.conectar()
                if conn:
                    c = conn.cursor()
                    c.execute("SELECT username, rol FROM usuarios WHERE username = %s AND password = %s", (user, pw))
                    res = c.fetchone()
                    conn.close()
                    if res:
                        st.session_state["usuario_autenticado"] = res[0]
                        st.session_state["rol"] = res[1]
                        st.rerun()
                    else:
                        st.error("Usuario o clave incorrectos")
        return False
    return True

if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras"]
    menu = st.sidebar.selectbox("Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    if menu == "Dashboard":
        st.title("📈 Dashboard")
        st.write(f"Bienvenido, **{st.session_state['usuario_autenticado']}**")
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()
    elif menu == "Registro de Compras":
        compras.modulo_compras()
