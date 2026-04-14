import streamlit as st
import database
import pandas as pd
from modulos import entidades, compras

# 1. Configuración de página (Siempre de primero)
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos
database.inicializar_db()

# --- 3. FUNCIONES DE GESTIÓN (Perfil y Usuarios) ---

def modulo_perfil():
    st.title("🔐 Configuración de Perfil")
    st.info(f"Usuario actual: **{st.session_state['usuario_autenticado']}**")
    
    with st.form("cambio_password"):
        nueva_pass = st.text_input("Nueva Contraseña", type="password")
        confirmar_pass = st.text_input("Confirme Nueva Contraseña", type="password")
        if st.form_submit_button("Actualizar mi contraseña"):
            if nueva_pass == confirmar_pass and nueva_pass != "":
                conn = database.conectar()
                c = conn.cursor()
                c.execute("UPDATE usuarios SET password = %s WHERE username = %s", (nueva_pass, st.session_state['usuario_autenticado']))
                conn.commit()
                conn.close()
                st.success("✅ Contraseña actualizada.")
            else:
                st.error("❌ Las contraseñas no coinciden")

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    with st.expander("➕ Crear Nuevo Usuario"):
        with st.form("nuevo_u"):
            u = st.text_input("Usuario").lower().strip()
            p = st.text_input("Clave", type="password")
            r = st.selectbox("Rol", ["usuario", "admin"])
            if st.form_submit_button("Guardar"):
                conn = database.conectar()
                c = conn.cursor()
                c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s)", (u, p, r))
                conn.commit()
                conn.close()
                st.success(f"Usuario {u} creado")

# --- 4. SISTEMA DE LOGIN ---

def check_password():
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login_center"):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                conn = database.conectar() # Asegúrate que en database.py se llame conectar()
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

# --- 5. CUERPO PRINCIPAL ---

if check_password():
    # BARRA LATERAL
    st.sidebar.title("🚀 Adonai ERP")
    st.sidebar.write(f"👤 Usuario: **{st.session_state['usuario_autenticado']}**")
    
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras", "Configuración de Perfil"]
    if st.session_state["rol"] == "admin":
        opciones.append("Gestión de Usuarios")
    
    menu = st.sidebar.selectbox("Seleccione Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    # NAVEGACIÓN DE MÓDULOS
    if menu == "Dashboard":
        st.title("📈 Dashboard")
        st.write(f"Bienvenido, {st.session_state['usuario_autenticado']}.")
        
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()

    elif menu == "Registro de Compras":
        compras.modulo_compras()

    elif menu == "Configuración de Perfil":
        modulo_perfil()

    elif menu == "Gestión de Usuarios":
        modulo_gestion_usuarios()
