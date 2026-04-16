import streamlit as st
import pandas as pd
import database
from modulos import entidades, compras

# 1. Configuración de página
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos
database.inicializar_db()

# --- NUEVOS MÓDULOS DE CONTABILIDAD GENERAL (CG) Y AUDITORÍA ---

def modulo_contabilidad_general():
    st.title("🏛️ Contabilidad General (CG)")
    # Definimos exactamente 3 pestañas
    t1, t2, t3 = st.tabs(["📖 Diario General", "🏢 Centros de Costo", "🔒 Períodos"])

    with t1:
        st.subheader("Asientos Contables")
        conn = database.conectar()
        if conn:
            try:
                # Consulta con los nombres de columna que forzamos arriba
                df = pd.read_sql("SELECT num_asiento, fecha, concepto, origen, creado_por FROM asientos_cabecera ORDER BY id DESC", conn)
                st.dataframe(df, use_container_width=True)
            except:
                st.info("No hay asientos registrados aún.")
            finally:
                conn.close()
    # ... resto del código con with t2 y with t3 ...

    with t2:
        st.subheader("Centros de Costo")
        # ... tu código de centros de costo ...

    with t3: # AHORA YA EXISTE t3
        st.subheader("Gestión de Períodos")
        st.info("Módulo de cierre de mes en desarrollo.")

def modulo_auditoria():
    st.title("🕵️ Historial de Actividad (Auditoría)")
    conn = database.conectar()
    df_logs = pd.read_sql("SELECT fecha_hora, usuario, accion, tabla_afectada, detalle FROM logs_actividad ORDER BY fecha_hora DESC LIMIT 100", conn)
    conn.close()
    st.dataframe(df_logs, use_container_width=True)

# --- MÓDULOS EXISTENTES RESTAURADOS ---

def modulo_perfil():
    st.title("👤 Mi Perfil")
    with st.form("form_cambio_clave"):
        nueva_p = st.text_input("Nueva Contraseña", type="password")
        if st.form_submit_button("✅ Actualizar Clave"):
            conn = database.conectar()
            c = conn.cursor()
            c.execute("UPDATE usuarios SET password = %s WHERE username = %s", 
                      (nueva_p, st.session_state['usuario_autenticado']))
            conn.commit()
            database.registrar_log(st.session_state['usuario_autenticado'], "EDITAR", "usuarios", "Cambió su contraseña")
            conn.close()
            st.success("Contraseña actualizada.")

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    with st.expander("➕ Registrar Nuevo Usuario"):
        with st.form("nuevo_u"):
            u = st.text_input("Username").lower().strip()
            p = st.text_input("Password", type="password")
            r = st.selectbox("Rol", ["usuario", "admin"])
            if st.form_submit_button("Registrar"):
                conn = database.conectar()
                c = conn.cursor()
                c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (u, p, r))
                conn.commit()
                database.registrar_log(st.session_state['usuario_autenticado'], "CREAR", "usuarios", f"Creó usuario: {u}")
                conn.close()
                st.rerun()
    # ... tabla de usuarios (se mantiene igual) ...

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
        st.subheader("Parámetros Fiscales")
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
            database.registrar_log(st.session_state['usuario_autenticado'], "UPDATE", "configuracion", "Cambió parámetros del sistema")
            conn.close()
            st.success("Configuración actualizada.")
            st.rerun()

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
    opciones = ["Dashboard", "Registrar Entidad", "Cuentas por Pagar (CP)", "Mi Perfil"]
    
    if st.session_state["rol"] == "admin":
        opciones += ["Contabilidad General (CG)", "Gestión de Usuarios", "Historial de Log", "Configuración Sistema"]
    
    menu = st.sidebar.selectbox("Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    if menu == "Dashboard":
        st.title("📈 Dashboard")
        st.write(f"Bienvenido, {st.session_state['usuario_autenticado']}")
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()
    elif menu == "Cuentas por Pagar (CP)":
        compras.modulo_compras() # Se renombró el menú pero llama a la misma función por ahora
    elif menu == "Mi Perfil":
        modulo_perfil()
    elif menu == "Contabilidad General (CG)":
        modulo_contabilidad_general()
    elif menu == "Gestión de Usuarios":
        modulo_gestion_usuarios()
    elif menu == "Historial de Log":
        modulo_auditoria()
    elif menu == "Configuración Sistema":
        modulo_configuracion_sistema()
