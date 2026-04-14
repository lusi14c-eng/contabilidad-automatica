import streamlit as st
import pandas as pd
import database
from modulos import entidades, compras

# 1. Configuración de página
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos
database.inicializar_db()

# --- MÓDULOS ---

def modulo_configuracion_sistema():
    st.title("⚙️ Configuración del Sistema")
    conf = database.obtener_configuracion_empresa()
    
    with st.form("form_config"):
        st.subheader("Datos de la Empresa (Agente de Retención)")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Razón Social", value=conf['nombre_empresa'])
            rif = st.text_input("RIF Empresa", value=conf['rif_empresa'])
            # Selector de tipo para tus pruebas
            t_contrib = st.selectbox("Tipo de Contribuyente", ["Especial", "Ordinario", "Formal"], 
                                    index=["Especial", "Ordinario", "Formal"].index(conf['tipo_contribuyente']))
        with col2:
            dir_f = st.text_area("Dirección Fiscal", value=conf['direccion_empresa'])
        
        st.divider()
        st.subheader("Parámetros de Cálculo")
        c1, c2 = st.columns(2)
        nueva_ut = c1.number_input("Valor Unidad Tributaria (Bs.)", value=conf['ut_valor'], format="%.2f")
        nuevo_f = c2.number_input("Factor Sustraendo (83.3334)", value=conf['factor_sustraendo'], format="%.4f")
        
        # Botón INDISPENSABLE dentro del form
        if st.form_submit_button("✅ Guardar Cambios"):
            conn = database.conectar()
            c = conn.cursor()
            c.execute("""UPDATE configuracion SET nombre_empresa=%s, rif_empresa=%s, direccion_empresa=%s, 
                         ut_valor=%s, factor_sustraendo=%s, tipo_contribuyente=%s WHERE id=1""",
                      (nombre, rif, dir_f, nueva_ut, nuevo_f, t_contrib))
            conn.commit()
            conn.close()
            st.success("Configuración actualizada correctamente.")
            st.rerun()

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    conn = database.conectar()
    df_u = pd.read_sql("SELECT username as \"Usuario\", rol as \"Rol\" FROM usuarios", conn)
    conn.close()
    st.table(df_u)

def check_password():
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login_center"):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                conn = database.conectar()
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
        return False
    return True

# --- LÓGICA PRINCIPAL ---

if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    st.sidebar.write(f"Usuario: **{st.session_state['usuario_autenticado']}**")
    
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras"]
    if st.session_state["rol"] == "admin":
        opciones += ["Gestión de Usuarios", "Configuración"]
    
    menu = st.sidebar.selectbox("Menú Principal", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    if menu == "Dashboard":
        st.title("📈 Dashboard")
        st.write(f"Bienvenido al sistema, {st.session_state['usuario_autenticado']}")
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()
    elif menu == "Registro de Compras":
        compras.modulo_compras()
    elif menu == "Gestión de Usuarios":
        modulo_gestion_usuarios()
    elif menu == "Configuración":
        modulo_configuracion_sistema()
