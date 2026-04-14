import streamlit as st
import database
import pandas as pd
from modulos import entidades, compras  # <--- 1. ASEGÚRATE DE IMPORTAR 'compras'

# Inicializar base de datos al arrancar
database.inicializar_db()

# --- SEGURIDAD (Se mantiene igual) ---
def check_password():
    # Dentro del bloque: if check_password():

st.sidebar.title(f"👤 {st.session_state['usuario_autenticado']}")

opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras", "Configuración de Perfil"]

# Si es admin, agregamos el módulo de Gestión de Usuarios
if st.session_state.get("rol") == "admin":
    opciones.append("Gestión de Usuarios")

menu = st.sidebar.selectbox("Seleccione Módulo:", opciones)

# ... (Lógica de los otros módulos)

elif menu == "Configuración de Perfil":
    modulo_perfil() # Función para cambiar clave

elif menu == "Gestión de Usuarios":
    modulo_gestion_usuarios() # Solo para lgonzalez
    if "usuario_autenticado" not in st.session_state:
        st.title("🔐 Acceso Adonai ERP")
        with st.form("login"):
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                conn = database.conectar()
                c = conn.cursor()
                c.execute("SELECT username, rol FROM usuarios WHERE username = %s AND password = %s", (user, password))
                res = c.fetchone()
                conn.close()
                if res:
                    st.session_state["usuario_autenticado"] = res[0]
                    st.session_state["rol"] = res[1]
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
        return False
    return True

# --- CUERPO DE LA APP ---
if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    menu = st.sidebar.selectbox("Seleccione Módulo:", 
        ["Dashboard", "Registrar Entidad", "Registro de Compras"])

    if menu == "Dashboard":
        st.title("📈 Dashboard")
        st.write("Bienvenido al sistema contable de Adonai Group.")
        
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()

    elif menu == "Registro de Compras":
        # --- 2. AQUÍ LLAMAMOS A LA FUNCIÓN QUE ESTÁ EN modulos/compras.py ---
        compras.modulo_compras()
