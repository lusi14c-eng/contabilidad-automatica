# app.py
import streamlit as st
import pandas as pd
import database
import hashlib
from datetime import datetime
from modulos import entidades, compras, cotizaciones

# 1. Configuración de página
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos y correr migraciones limpias
database.inicializar_db()

# --- MÓDULOS DE CONTABILIDAD GENERAL (CG) ---

def modulo_contabilidad_general():
    st.title("🏛️ Contabilidad General (CG)")
    t1, t2, t3 = st.tabs(["📖 Diario General", "🏢 Centros de Costo", "🔒 Períodos Fiscales"])

    with t1:
        st.subheader("Asientos Contables")
        st.info("Consulte aquí todos los asientos generados por CP y CG.")
        conn = database.conectar()
        query = """
            SELECT a.num_asiento, a.fecha, a.concepto, a.origen, a.creado_por,
                   COALESCE(SUM(d.debe), 0) as total_debe
            FROM asientos_cabecera a
            LEFT JOIN asientos_detalle d ON a.id = d.asiento_id
            GROUP BY a.id, a.num_asiento, a.fecha, a.concepto, a.origen, a.creado_por 
            ORDER BY a.fecha DESC
        """
        df_asientos = pd.read_sql(query, conn)
        st.dataframe(df_asientos, use_container_width=True)
        conn.close()

    with t2:
        st.subheader("Configuración de Centros de Costo")
        with st.form("n_cc"):
            c1, c2 = st.columns(2)
            cod_cc = c1.text_input("Código Centro (Ej: ADM, VEN, PLT)")
            nom_cc = c2.text_input("Nombre del Departamento")
            if st.form_submit_button("Añadir Centro"):
                if cod_cc and nom_cc:
                    conn = database.conectar()
                    c = conn.cursor()
                    c.execute("INSERT INTO centros_costo (codigo, nombre) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (cod_cc, nom_cc))
                    conn.commit()
                    database.registrar_log(st.session_state['usuario_autenticado'], "CREAR", "centros_costo", f"Añadió CC: {nom_cc}")
                    conn.close()
                    st.success("Centro de costo creado.")
                    st.rerun()
        
        conn = database.conectar()
        df_cc = pd.read_sql("SELECT codigo as \"Código\", nombre as \"Nombre\" FROM centros_costo", conn)
        conn.close()
        st.table(df_cc)

    with t3:
        st.subheader("Cierre de Períodos")
        st.warning("⚠️ Un período cerrado bloquea los registros ante el SENIAT.")

def modulo_auditoria():
    st.title("🕵️ Historial de Actividad (Auditoría)")
    conn = database.conectar()
    df_logs = pd.read_sql("SELECT fecha_hora, usuario, accion, tabla_afectada, detalle FROM logs_actividad ORDER BY fecha_hora DESC LIMIT 100", conn)
    conn.close()
    st.dataframe(df_logs, use_container_width=True)

# --- GESTIÓN DE PERFIL Y USUARIOS ---

def modulo_perfil():
    st.title("👤 Mi Perfil")
    with st.form("form_cambio_clave"):
        nueva_p = st.text_input("Nueva Contraseña", type="password")
        if st.form_submit_button("✅ Actualizar Clave"):
            if nueva_p.strip():
                p_hash = hashlib.sha256(nueva_p.encode()).hexdigest()
                database.ejecutar_transaccion(
                    "UPDATE usuarios SET clave = %s WHERE username = %s", 
                    (p_hash, st.session_state['usuario_autenticado'])
                )
                database.registrar_log(st.session_state['usuario_autenticado'], "EDITAR", "usuarios", "Cambió su contraseña de ingreso")
                st.success("Contraseña actualizada con éxito.")
            else:
                st.error("La contraseña no puede estar vacía.")

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    with st.expander("➕ Registrar Nuevo Usuario"):
        with st.form("nuevo_u"):
            u = st.text_input("Username").lower().strip()
            p = st.text_input("Password", type="password")
            r = st.selectbox("Rol", ["usuario", "admin"])
            if st.form_submit_button("Registrar"):
                if u and p:
                    p_hash = hashlib.sha256(p.encode()).hexdigest()
                    database.ejecutar_transaccion(
                        "INSERT INTO usuarios (username, clave, rol) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", 
                        (u, p_hash, r)
                    )
                    database.registrar_log(st.session_state['usuario_autenticado'], "CREAR", "usuarios", f"Creó usuario: {u}")
                    st.success(f"¡Usuario {u} creado correctamente!")
                    st.rerun()
                else:
                    st.error("Complete los campos obligatorios.")

# --- FORMULARIO DE CONFIGURACIÓN GLOBAL ÚNICO ---

def modulo_configuracion_sistema():
    st.title("⚙️ Configuración Global del Sistema")
    conf = database.obtener_configuracion_empresa()
    
    with st.form("form_configuracion_global"):
        st.subheader("Datos del Agente de Retención (Tu Empresa)")
        col1, col2 = st.columns(2)
        n = col1.text_input("Razón Social / Nombre Legal", value=conf.get('nombre_empresa', 'ADONAI GROUP'))
        r = col2.text_input("RIF de la Empresa", value=conf.get('rif_empresa', ''))
        d = st.text_area("Dirección Fiscal", value=conf.get('direccion_empresa', ''))
        
        contribuyente_actual = conf.get('tipo_contribuyente', 'Ordinario')
        opciones_contribuyente = ["Especial", "Ordinario", "Formal"]
        try:
            posicion_index = opciones_contribuyente.index(contribuyente_actual)
        except ValueError:
            posicion_index = 1
            
        t = col1.selectbox("Tipo de Contribuyente", opciones_contribuyente, index=posicion_index)
        
        st.divider()
        st.subheader("Parámetros Fiscales de Control")
        col3, col4 = st.columns(2)
        nueva_ut = col3.number_input("Valor Unidad Tributaria (Bs.)", value=float(conf.get('ut_valor', 0.00)), format="%.2f")
        factor = col4.number_input("Factor Sustraendo (Estándar 83.3334)", value=float(conf.get('factor_sustraendo', 83.3334)), format="%.4f")
        
        if st.form_submit_button("Actualizar Todo el Sistema"):
            database.ejecutar_transaccion(
                """UPDATE configuracion SET 
                   nombre_empresa=%s, rif_empresa=%s, direccion_empresa=%s, 
                   tipo_contribuyente=%s, ut_valor=%s, factor_sustraendo=%s 
                   WHERE id=1""",
                (n, r, d, t, nueva_ut, factor)
            )
            database.registrar_log(
                st.session_state.get('usuario_autenticado', 'admin'), 
                "EDITAR", 
                "configuracion", 
                "Actualizó datos de empresa y parámetros tributarios unificados"
            )
            st.success("✅ Configuración corporativa y parámetros fiscales sincronizados en Neon.")
            st.rerun()

# --- CONTROL DE ACCESO (MIGRACIÓN CONTABLE INTELIGENTE) ---

def check_password():
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login"):
            user = st.text_input("Usuario").lower().strip()
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                pw_hash = hashlib.sha256(pw.encode()).hexdigest()
                conn = database.conectar()
                c = conn.cursor()
                
                # Paso 1: Intentar buscar por la estructura nueva (Criptográfica en la columna 'clave')
                c.execute("SELECT username, rol FROM usuarios WHERE username = %s AND clave = %s", (user, pw_hash))
                res = c.fetchone()
                
                # Paso 2: Si no lo halla, buscar por la estructura vieja (Texto plano en la columna 'password')
                if not res:
                    c.execute("SELECT username, rol FROM usuarios WHERE username = %s AND password = %s", (user, pw))
                    res = c.fetchone()
                    
                    if res:
                        # ¡AUTOMIGRACIÓN EN CALIENTE! Encriptamos al usuario para blindar su seguridad
                        c.execute("UPDATE usuarios SET clave = %s WHERE username = %s", (pw_hash, user))
                        conn.commit()
                
                conn.close()
                
                if res:
                    st.session_state["usuario_autenticado"] = res[0]
                    st.session_state["rol"] = res[1]
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas o combinación de columnas no válida.")
        return False
    return True

# --- ENRUTADOR DE VISTAS (LÓGICA TOLERANTE A ROLES) ---

if check_password():
    st.sidebar.title("🚀 Adonai ERP")
    opciones = ["Dashboard", "Registrar Entidad", "Cuentas por Pagar (CP)", "Mi Perfil"]
    
    # Tolerancia a variaciones: Acepta tanto 'admin' como 'Administrador' proveniente de Neon
    rol_actual = str(st.session_state.get("rol", "")).lower().strip()
    if rol_actual in ["admin", "administrador"]:
        opciones += ["Contabilidad General (CG)", "Gestión de Usuarios", "Historial de Log", "Configuración Sistema"]
    
    menu = st.sidebar.selectbox("Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        if "rol" in st.session_state:
            del st.session_state["rol"]
        st.rerun()

    if menu == "Dashboard":
        st.title("📈 Dashboard Finanzas")
        st.write(f"Bienvenido al sistema, **{st.session_state['usuario_autenticado'].upper()}**")
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()
    elif menu == "Crear Cotización":
        cotizaciones.modulo_crear_cotizaciones() # <-- NUEVA RUTA ENLAZADA
    elif menu == "Cuentas por Pagar (CP)":
        compras.modulo_compras()
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
