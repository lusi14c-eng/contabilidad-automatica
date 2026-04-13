import streamlit as st
import database
import pandas as pd
from modulos import entidades  # Importamos el módulo que creaste

# Inicializar base de datos al arrancar
database.inicializar_db()

# --- SEGURIDAD ---
def check_password():
    def password_entered():
        if "auth" in st.secrets and st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🔐 Acceso Herramienta Contable</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: gray;'>Adonai Group</h3>", unsafe_allow_html=True)
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Contraseña:", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

# --- CUERPO DE LA APP ---
if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    menu = st.sidebar.selectbox("Seleccione Módulo:", 
        ["Dashboard", "Registrar Entidad", "Registro de Compras"])

    if menu == "Dashboard":
        st.title("📈 Dashboard")
        
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades() # Esto abre la pestaña de registro por defecto

    elif menu == "Registro de Compras":
        st.title("🧾 Compras")
        # Próximo paso...
