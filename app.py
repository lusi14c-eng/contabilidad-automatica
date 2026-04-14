import streamlit as st
import pandas as pd
import database

# Intentar importar los módulos de forma segura
try:
    from modulos import entidades, compras
except ImportError as e:
    st.error(f"🚨 Error crítico de archivos: No se encontró el módulo. Detalles: {e}")
except Exception as e:
    st.error(f"🚨 Error de sintaxis en los archivos internos: {e}")

st.set_page_config(page_title="Adonai ERP", layout="wide")

# Inicialización silenciosa de la base de datos
try:
    database.inicializar_db()
except Exception as e:
    st.error(f"❌ Error al conectar con la base de datos: {e}")

def check_password():
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login_center"):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                try:
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
                            st.error("🚫 Usuario o clave incorrectos")
                except Exception as e:
                    st.error("⚠️ Problema técnico al validar acceso.")
        return False
    return True

if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras"]
    menu = st.sidebar.selectbox("Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    # Manejo de navegación con mensajes amigables
    try:
        if menu == "Dashboard":
            st.title("📈 Dashboard")
            st.write(f"Bienvenido al sistema, **{st.session_state['usuario_autenticado']}**")
        
        elif menu == "Registrar Entidad":
            entidades.modulo_maestro_entidades()
            
        elif menu == "Registro de Compras":
            compras.modulo_compras()
            
    except Exception as e:
        st.warning(f"⚠️ El módulo '{menu}' no pudo cargarse correctamente.")
        st.info("Sugerencia: Revisa si hay campos vacíos o caracteres especiales en el archivo correspondiente.")
