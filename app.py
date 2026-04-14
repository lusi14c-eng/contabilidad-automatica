import streamlit as st
import pandas as pd
import database
from modulos import entidades, compras

# 1. Configuración de página
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos
database.inicializar_db()

# --- MÓDULOS DE SEGURIDAD Y PERFIL ---

def modulo_perfil():
    st.title("🔐 Mi Perfil")
    st.info(f"Usuario: **{st.session_state['usuario_autenticado']}**")
    
    with st.form("form_cambio_clave"):
        nueva_p = st.text_input("Nueva Contraseña", type="password")
        conf_p = st.text_input("Confirmar Nueva Contraseña", type="password")
        
        if st.form_submit_button("Actualizar Contraseña"):
            if nueva_p == conf_p and nueva_p != "":
                conn = database.conectar()
                c = conn.cursor()
                c.execute("UPDATE usuarios SET password = %s WHERE username = %s", 
                          (nueva_p, st.session_state['usuario_autenticado']))
                conn.commit()
                conn.close()
                st.success("✅ Contraseña actualizada correctamente.")
            else:
                st.error("❌ Las contraseñas no coinciden o están vacías.")

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    
    # Crear Usuarios (Solo Admin)
    with st.expander("➕ Registrar Nuevo Usuario"):
        with st.form("nuevo_u"):
            u = st.text_input("Username").lower().strip()
            p = st.text_input("Password", type="password")
            r = st.selectbox("Rol", ["usuario", "admin"])
            if st.form_submit_button("Guardar Usuario"):
                if u and p:
                    conn = database.conectar()
                    c = conn.cursor()
                    c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (u, p, r))
                    conn.commit()
                    conn.close()
                    st.success(f"Usuario {u} registrado.")
                    st.rerun()

    st.subheader("Listado de Usuarios")
    conn = database.conectar()
    df_u = pd.read_sql("SELECT username as \"Usuario\", rol as \"Rol\" FROM usuarios", conn)
    conn.close()
    st.dataframe(df_u, use_container_width=True)
    
def modulo_contabilidad():
    st.title("📑 Gestión Contable y Configuración de Gastos")
    
    tab1, tab2 = st.tabs(["🗂️ Plan de Cuentas", "🏷️ Subtipos de Compra"])
    
    with tab1:
        st.subheader("Registrar Cuenta Contable")
        with st.form("nueva_cuenta"):
            col1, col2 = st.columns(2)
            cod = col1.text_input("Código (Ej: 6.1.01.001)")
            nom = col2.text_input("Nombre de la Cuenta")
            tipo = st.selectbox("Tipo", ["Activo", "Pasivo", "Patrimonio", "Ingreso", "Egreso"])
            if st.form_submit_button("Guardar Cuenta"):
                conn = database.conectar()
                c = conn.cursor()
                c.execute("INSERT INTO cuentas_contables (codigo, nombre, tipo) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO NOTHING", (cod, nom, tipo))
                conn.commit()
                conn.close()
                st.success("Cuenta registrada.")
        
        # Listado de cuentas
        conn = database.conectar()
        df_c = pd.read_sql("SELECT codigo, nombre, tipo FROM cuentas_contables ORDER BY codigo", conn)
        conn.close()
        st.dataframe(df_c, use_container_width=True)

    with tab2:
        st.subheader("Definir Subtipos de Gasto/Compra")
        st.info("Aquí defines categorías como 'Papelería' y la asocias a una cuenta contable.")
        
        conn = database.conectar()
        cuentas_df = pd.read_sql("SELECT codigo, nombre FROM cuentas_contables", conn)
        
        with st.form("nuevo_subtipo"):
            nom_sub = st.text_input("Nombre del Subtipo (Ej: Honorarios, Repuestos, Alquiler)")
            dict_c = {f"{r['codigo']} - {r['nombre']}": r['codigo'] for _, r in cuentas_df.iterrows()}
            cuenta_asig = st.selectbox("Cuenta Contable Asociada", list(dict_c.keys()))
            
            if st.form_submit_button("Crear Subtipo"):
                c = conn.cursor()
                c.execute("INSERT INTO compra_subtipos (nombre, cuenta_codigo) VALUES (%s, %s)", (nom_sub, dict_c[cuenta_asig]))
                conn.commit()
                st.success(f"Subtipo '{nom_sub}' creado exitosamente.")
        
        # Listado de subtipos
        df_s = pd.read_sql("""SELECT s.nombre as "Subtipo", s.cuenta_codigo as "Código Cuenta", c.nombre as "Cuenta" 
                             FROM compra_subtipos s JOIN cuentas_contables c ON s.cuenta_codigo = c.codigo""", conn)
        conn.close()
        st.table(df_s)

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
        st.subheader("Parámetros de Cálculo")
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
            st.success("Configuración guardada.")
            st.rerun()

# --- CONTROL DE ACCESO ---

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
    st.sidebar.write(f"Rol: **{st.session_state['rol'].upper()}**")
    
    # Menú base para todos
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras", "Mi Perfil"]
    
    # Opciones solo para Admin
    if st.session_state["rol"] == "admin":
        opciones.append("Gestión de Usuarios")
        opciones.append("Configuración Sistema")
    
    menu = st.sidebar.selectbox("Seleccione Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    # Ruteo
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
