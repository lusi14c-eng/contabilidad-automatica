import streamlit as st
import pandas as pd
import database
from modulos import entidades, compras

# 1. Configuración de página
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos
database.inicializar_db()

# --- MÓDULOS DE ADMINISTRACIÓN Y SEGURIDAD ---

def modulo_configuracion_sistema():
    st.title("⚙️ Configuración del Sistema")
    conf = database.obtener_configuracion_empresa()
    
    with st.form("form_config"):
        st.subheader("Datos de la Empresa")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Razón Social", value=conf['nombre'])
            rif = st.text_input("RIF Empresa", value=conf['rif'])
        with col2:
            dir_f = st.text_area("Dirección Fiscal", value=conf['direccion'])
        
        st.divider()
        st.subheader("Parámetros Fiscales")
        c1, c2 = st.columns(2)
        nueva_ut = c1.number_input("Valor Unidad Tributaria (Bs.)", value=conf['ut_valor'], format="%.2f")
        nuevo_f = c2.number_input("Factor Sustraendo (83.3334)", value=conf['factor_sustraendo'], format="%.4f")
        
        if st.form_submit_button("✅ Guardar Cambios"):
            try:
                conn = database.conectar()
                c = conn.cursor()
                c.execute("""UPDATE configuracion SET nombre_empresa=%s, rif_empresa=%s, 
                             direccion_empresa=%s, ut_valor=%s, factor_sustraendo=%s WHERE id=1""",
                          (nombre, rif, dir_f, nueva_ut, nuevo_f))
                conn.commit()
                conn.close()
                st.success("Configuración actualizada. Los cálculos de ISLR ahora usarán estos valores.")
            except Exception as e:
                st.error(f"Error al guardar: {e}")

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    
    with st.expander("➕ Crear Nuevo Usuario"):
        with st.form("nuevo_u"):
            u = st.text_input("Nombre de Usuario").lower().strip()
            p = st.text_input("Contraseña", type="password")
            r = st.selectbox("Rol", ["usuario", "admin"])
            if st.form_submit_button("Registrar"):
                if u and p:
                    conn = database.conectar()
                    c = conn.cursor()
                    c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (u, p, r))
                    conn.commit()
                    conn.close()
                    st.success(f"Usuario {u} creado.")
                else:
                    st.warning("Faltan datos.")

    st.subheader("Usuarios Registrados")
    conn = database.conectar()
    # IMPORTANTE: No seleccionamos la columna 'password' por seguridad
    df_u = pd.read_sql("SELECT username as \"Usuario\", rol as \"Rol\" FROM usuarios", conn)
    conn.close()
    st.table(df_u)

def modulo_perfil():
    st.title("👤 Mi Perfil")
    with st.form("pass_form"):
        st.write(f"Cambiar contraseña para: **{st.session_state['usuario_autenticado']}**")
        n_pass = st.text_input("Nueva Contraseña", type="password")
        c_pass = st.text_input("Confirmar Contraseña", type="password")
        if st.form_submit_button("Actualizar Clave"):
            if n_pass == c_pass and n_pass != "":
                conn = database.conectar()
                c = conn.cursor()
                c.execute("UPDATE usuarios SET password = %s WHERE username = %s", (n_pass, st.session_state['usuario_autenticado']))
                conn.commit()
                conn.close()
                st.success("Contraseña cambiada.")
            else:
                st.error("Las claves no coinciden.")

# --- CONTROL DE ACCESO ---

def check_password():
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login"):
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
                        st.error("Credenciales incorrectas")
        return False
    return True

if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    st.sidebar.write(f"Rol: **{st.session_state['rol'].upper()}**")
    
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras", "Mi Perfil"]
    if st.session_state["rol"] == "admin":
        opciones.extend(["Gestión de Usuarios", "Configuración Sistema"])
    
    menu = st.sidebar.selectbox("Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    if menu == "Dashboard":
        st.title("📈 Dashboard")
        st.write(f"Bienvenido, {st.session_state['usuario_autenticado']}")
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()
    elif menu == "Registro de Compras":
        compras.modulo_compras()
    elif menu == "Mi Perfil":
        modulo_perfil()
    elif menu == "Gestión de Usuarios":
        modulo_gestion_usuarios()
    elif menu == "Configuración Sistema":
        modulo_configuracion_sistema()
