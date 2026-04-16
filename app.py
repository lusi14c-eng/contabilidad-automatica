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
    st.title("🏛️ Gestión Contable Profesional")
    t1, t2, t3 = st.tabs(["📖 Diario General", "🏢 Centros de Costo", "🔒 Control de Períodos"])

    # --- PESTAÑA 1: DIARIO (CON EDICIÓN) ---
    with t1:
        col_btn1, col_btn2 = st.columns([1, 4])
        if col_btn1.button("➕ Nuevo Asiento"):
            st.session_state["editando_id"] = None
            st.session_state["nuevo_asiento"] = True

        # LÓGICA DE VISUALIZACIÓN Y ACCIONES
        df_diario = pd.read_sql("SELECT id, num_asiento, fecha, concepto, origen FROM asientos_cabecera ORDER BY id DESC", database.conectar())
        
        for _, row in df_diario.iterrows():
            with st.expander(f"📑 {row['num_asiento']} | {row['fecha']} | {row['concepto']}"):
                c_edit, c_del, c_view = st.columns(3)
                
                if c_edit.button("📝 Editar Asiento", key=f"ed_{row['id']}"):
                    st.session_state["editando_id"] = row['id']
                    st.session_state["nuevo_asiento"] = True
                    st.rerun()

                if c_del.button("🗑️ Eliminar/Anular", key=f"del_{row['id']}"):
                    # Validar periodo antes de borrar
                    p_check = f"{row['fecha'].year}-{str(row['fecha'].month).zfill(2)}"
                    res_p = database.ejecutar_query("SELECT modulo_cg FROM periodos_fiscales WHERE periodo = %s", (p_check,), fetch=True)
                    if res_p and res_p[0] == "Abierto":
                        database.ejecutar_transaccion("DELETE FROM asientos_cabecera WHERE id = %s", (int(row['id']),))
                        st.warning("Asiento eliminado.")
                        st.rerun()
                    else:
                        st.error("No se puede eliminar: El período está CERRADO.")

        # FORMULARIO DE CREACIÓN / EDICIÓN (MODO ODOO)
        if st.session_state.get("nuevo_asiento"):
            id_a = st.session_state.get("editando_id")
            titulo = "Editando Asiento" if id_a else "Nuevo Asiento"
            
            with st.form("form_asiento_erp"):
                st.subheader(titulo)
                # Si estamos editando, cargar valores previos (Simulado por ahora)
                col_h1, col_h2 = st.columns(2)
                f_as = col_h1.date_input("Fecha Contable")
                desc_as = col_h2.text_input("Concepto")
                
                df_init = pd.DataFrame([{"Cuenta": "", "CC": "", "Debe": 0.0, "Haber": 0.0} for _ in range(5)])
                asiento_data = st.data_editor(df_init, num_rows="dynamic", use_container_width=True)

                if st.form_submit_button("✅ Guardar Cambios"):
                    # Aquí la lógica de UPDATE si id_a existe, o INSERT si es None
                    st.success("Operación exitosa.")
                    st.session_state["nuevo_asiento"] = False
                    st.rerun()

    # --- PESTAÑA 3: CIERRE DEL EJERCICIO (NUEVO) ---
    with t3:
        st.divider()
        st.subheader("🏁 Cierre del Ejercicio Fiscal")
        st.warning("El cierre anual llevará a cero las cuentas nominales y bloqueará todo el año seleccionado.")
        
        c_an1, c_an2 = st.columns([2, 1])
        anio_cierre = c_an1.number_input("Año a Cerrar", value=2026, key="anio_cierre")
        
        if c_an2.button("🚀 Ejecutar Cierre Anual"):
            # 1. Validar que todos los meses del año estén "Cerrados"
            conn = database.conectar()
            df_check = pd.read_sql(f"SELECT estatus FROM periodos_fiscales WHERE periodo LIKE '{anio_cierre}-%%' AND modulo_cg = 'Abierto'", conn)
            
            if not df_check.empty:
                st.error(f"No se puede cerrar el año. Hay {len(df_check)} meses todavía abiertos en Contabilidad.")
            else:
                # 2. Lógica Contable de Cierre (Simulada: se crearía un asiento de tipo 'CIE')
                num_cie = database.obtener_ultimo_correlativo("CIE")
                database.ejecutar_transaccion(
                    "INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen, creado_por) VALUES (%s,%s,%s,%s,%s)",
                    (num_cie, f"{anio_cierre}-12-31", f"CIERRE DEL EJERCICIO {anio_cierre}", "CIE", st.session_state['usuario_autenticado'])
                )
                st.success(f"¡Ejercicio {anio_cierre} cerrado con éxito! Se generó el comprobante {num_cie}.")

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
