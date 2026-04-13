from modulos import entidades  # Importas el archivo que acabamos de crear

# ... dentro del bloque 'if menu == "Maestro de Entidades":'
elif menu == "Maestro de Entidades":
    entidades.modulo_maestro_entidades() # Llamas a la funciónimport streamlit as st
import database
import pandas as pd

# Inicializar base de datos al arrancar
database.inicializar_db()

# --- SEGURIDAD ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Herramienta Contable")
        st.subheader("Adonai Group")
        st.text_input("Contraseña:", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if check_password():
    # --- MENÚ LATERAL ---
    st.sidebar.title("🚀 Adonai ERP")
    menu = st.sidebar.selectbox("Seleccione Módulo:", 
        ["Dashboard", "Maestro de Entidades", "Registro de Compras", "G+P Automático (Drive)"])

    if menu == "Dashboard":
        st.title("📈 Dashboard Contable")
        st.info("Bienvenido. Aquí verás el resumen de tus operaciones pronto.")

    elif menu == "Maestro de Entidades":
        # Aquí llamaremos al código de la carpeta modulos/entidades.py después
        st.title("👥 Gestión de Clientes y Proveedores")
        st.write("Módulo en construcción...")

    elif menu == "Registro de Compras":
        st.title("🧾 Libro de Compras y Retenciones")
        st.write("Módulo en construcción...")
        
    elif menu == "G+P Automático (Drive)":
        st.title("📊 Estado de Resultados (Drive)")
        st.write("Aquí irá el robot que lee tus archivos Excel actuales.")
