import streamlit as st
import pandas as pd
import database
from modulos import entidades, compras

# 1. Configuración de página
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos
database.inicializar_db()

# --- MÓDULOS DE ADMINISTRACIÓN Y SEGURIDAD ---

def modulo_perfil():
    st.title("👤 Mi Perfil")
    st.info(f"Usuario activo: **{st.session_state['usuario_autenticado']}**")
    
    with st.form("form_cambio_clave"):
        st.subheader("Actualizar Contraseña")
        nueva_p = st.text_input("Nueva Contraseña", type="password")
        conf_p = st.text_input("Confirmar Nueva Contraseña", type="password")
        
        if st.form_submit_button("✅ Actualizar Clave"):
            if nueva_p == conf_p and nueva_p != "":
                conn = database.conectar()
                c = conn.cursor()
                c.execute("UPDATE usuarios SET password = %s WHERE username = %s", 
                          (nueva_p, st.session_state['usuario_autenticado']))
                conn.commit()
                conn.close()
                st.success("Contraseña actualizada exitosamente.")
            else:
                st.error("Las contraseñas no coinciden o el campo está vacío.")

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    
    # Crear Usuarios (Solo Admin)
    with st.expander("➕ Registrar Nuevo Usuario"):
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
                    st.rerun()

    st.subheader("Usuarios Registrados")
    conn = database.conectar()
    df_u = pd.read_sql("SELECT username as \"Usuario\", rol as \"Rol\" FROM usuarios", conn)
    conn.close()
    st.dataframe(df_u, use_container_width=True)

def modulo_configuracion_sistema():
    st.title("⚙️ Configuración del Sistema")
    conf = database.obtener_configuracion_empresa()
    
    with st.form("form_config"):
        st.subheader("Datos de la Empresa")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Razón Social", value=conf['nombre_empresa'])
            rif = st.text_input("RIF Empresa", value=conf['rif_empresa'])
            t_contrib = st.selectbox("Tipo de Contribuyente", ["Especial", "Ordinario", "Formal"], 
                                    index=["Especial", "Ordinario", "Formal"].index(conf['tipo_contribuyente']))
        with col2:
            dir_f = st.text_area("Dirección Fiscal", value=conf['direccion_empresa'])
        
        st.divider()
        st.subheader("Parámetros Fiscales y de Cálculo")
        c1, c2 = st.columns(2)
        nueva_ut = c1.number_input("Valor Unidad Tributaria (Bs.)", value=conf['ut_valor'], format="%.2f")
        nuevo_f = c2.number_input("Factor Sustraendo", value=conf['factor_sustraendo'], format="%.4f")
        
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

def modulo_contabilidad():
    st.title("🧮 Gestión Contable")
    t1, t2 = st.tabs(["📊 Plan de Cuentas", "🏷️ Subtipos de Compra"])
    
    with t1:
        st.subheader("Añadir Cuenta Contable")
        with st.form("n_cuenta"):
            col1, col2 = st.columns(2)
            c_cod = col1.text_input("Código de Cuenta")
            c_nom = col2.text_input("Nombre de la Cuenta")
            if st.form_submit_button("Guardar Cuenta"):
                if c_cod and c_nom:
                    conn = database.conectar()
                    c = conn.cursor()
                    c.execute("INSERT INTO cuentas_contables (codigo, nombre) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (c_cod, c_nom))
                    conn.commit()
                    conn.close()
                    st.success("Cuenta añadida.")
                    st.rerun()
        
        conn = database.conectar()
        df = pd.read_sql("SELECT codigo as \"Código\", nombre as \"Cuenta\" FROM cuentas_contables ORDER BY codigo", conn)
        conn.close()
        st.dataframe(df, use_container_width=True)

    with t2:
        st.subheader("Vincular Subtipos a Cuentas")
        conn = database.conectar()
        cuentas = pd.read_sql("SELECT codigo, nombre FROM cuentas_contables", conn)
        
        with st.form("n_sub"):
            nom_s = st.text_input("Nombre del Subtipo (Ej: Alquiler)")
            cta = st.selectbox("Cuenta Asociada", [f"{r['codigo']} | {r['nombre']}" for _, r in cuentas.iterrows()])
            if st.form_submit_button("Crear Subtipo"):
                c = conn.cursor()
                c.execute("INSERT INTO compra_subtipos (nombre, cuenta_codigo) VALUES (%s, %s)", (nom_s, cta.split(" | ")[0]))
                conn.commit()
                st.success("Subtipo creado.")
                st.rerun()
        
        df_s = pd.read_sql("SELECT nombre as \"Subtipo\", cuenta_codigo as \"Cuenta Asociada\" FROM compra_subtipos", conn)
        conn.close()
        st.table(df_s)

# --- CONTROL DE ACCESO ---

def check_password():
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login"):
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
                    st.error("Credenciales incorrectas")
        return False
    return True

# --- RUTA PRINCIPAL ---

if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    st.sidebar.write(f"Rol: **{st.session_state['rol'].upper()}**")
    
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras", "Mi Perfil"]
    if st.session_state["rol"] == "admin":
        opciones += ["Gestión de Usuarios", "Contabilidad", "Configuración Sistema"]
    
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
    elif menu == "Contabilidad":
        modulo_contabilidad()
    elif menu == "Configuración Sistema":
        modulo_configuracion_sistema()
