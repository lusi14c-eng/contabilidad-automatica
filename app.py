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
    st.title("🏛️ Gestión Contable Empresarial")
    t1, t2, t3 = st.tabs(["📖 Diario General", "🏢 Centros de Costo", "🔒 Control de Períodos"])

    # --- PESTAÑA 3: CONTROL DE PERÍODOS (MODO ERP) ---
    with t3:
        st.subheader("Estatus de Módulos por Período")
        col_gen1, col_gen2 = st.columns([2, 1])
        anio_op = col_gen1.number_input("Año Fiscal a Gestionar", value=2026)
        if col_gen2.button("Generar Ejercicio Fiscal"):
            for m in range(1, 13):
                p_str = f"{anio_op}-{str(m).zfill(2)}"
                database.ejecutar_transaccion(
                    "INSERT INTO periodos_fiscales (periodo, modulo_cg, modulo_cp) VALUES (%s, 'Cerrado', 'Cerrado') ON CONFLICT DO NOTHING", (p_str,)
                )
            st.success(f"Ejercicio {anio_op} generado.")

        # Tabla de control
        conn = database.conectar()
        df_p = pd.read_sql(f"SELECT periodo, modulo_cg, modulo_cp FROM periodos_fiscales WHERE periodo LIKE '{anio_op}-%%' ORDER BY periodo ASC", conn)
        conn.close()

        if not df_p.empty:
            st.markdown("---")
            for _, row in df_p.iterrows():
                c1, c2, c3, c4, c5 = st.columns([1, 1.2, 1.2, 1, 1])
                c1.write(f"📅 **{row['periodo']}**")
                
                # Estado CG
                cg_icon = "🟢" if row['modulo_cg'] == 'Abierto' else "🔒"
                c2.write(f"{cg_icon} CG: {row['modulo_cg']}")
                if c4.button("Alt. CG", key=f"cg_{row['periodo']}"):
                    n_st = "Cerrado" if row['modulo_cg'] == 'Abierto' else "Abierto"
                    database.ejecutar_transaccion("UPDATE periodos_fiscales SET modulo_cg = %s WHERE periodo = %s", (n_st, row['periodo']))
                    st.rerun()

                # Estado CP
                cp_icon = "🟢" if row['modulo_cp'] == 'Abierto' else "🔒"
                c3.write(f"{cp_icon} CP: {row['modulo_cp']}")
                if c5.button("Alt. CP", key=f"cp_{row['periodo']}"):
                    n_st = "Cerrado" if row['modulo_cp'] == 'Abierto' else "Abierto"
                    database.ejecutar_transaccion("UPDATE periodos_fiscales SET modulo_cp = %s WHERE periodo = %s", (n_st, row['periodo']))
                    st.rerun()

    # --- PESTAÑA 1: DIARIO GENERAL (MODO ODOO) ---
    with t1:
        if st.button("➕ Crear Comprobante Contable"):
            st.session_state["nuevo_asiento"] = True

        if st.session_state.get("nuevo_asiento"):
            with st.expander("📝 Nuevo Asiento / Comprobante", expanded=True):
                with st.form("asiento_erp"):
                    # CABECERA
                    col_h1, col_h2, col_h3 = st.columns(3)
                    fecha_as = col_h1.date_input("Fecha Contable")
                    origen_as = col_h2.selectbox("Diario / Fuente", ["Diario General (CG)", "Compras (CP)", "Bancos (CB)"])
                    ref_as = col_h3.text_input("Referencia / Factura #")
                    desc_as = st.text_input("Descripción General (Glosa)")

                    # DETALLE (PARTIDAS)
                    st.markdown("**Líneas de Comprobante**")
                    # Usamos un editor de datos para máxima velocidad de carga
                    df_init = pd.DataFrame([
                        {"Cuenta": "", "Tercero (RIF)": "", "CC": "", "Descripción": "", "Debe": 0.0, "Haber": 0.0}
                        for _ in range(5)
                    ])
                    asiento_data = st.data_editor(df_init, num_rows="dynamic", use_container_width=True, key="editor_asiento")

                    # VALIDACIÓN
                    total_debe = asiento_data["Debe"].sum()
                    total_haber = asiento_data["Haber"].sum()
                    diferencia = round(total_debe - total_haber, 2)

                    c_v1, c_v2, c_v3 = st.columns(3)
                    c_v1.metric("Total Debe", f"{total_debe:,.2f}")
                    c_v2.metric("Total Haber", f"{total_haber:,.2f}")
                    c_v3.metric("Diferencia", f"{diferencia:,.2f}", delta=diferencia, delta_color="inverse")

                    if st.form_submit_button("✅ Postear Asiento"):
                        # Validar Período
                        p_check = f"{fecha_as.year}-{str(fecha_as.month).zfill(2)}"
                        res_p = database.ejecutar_query("SELECT modulo_cg FROM periodos_fiscales WHERE periodo = %s", (p_check,), fetch=True)
                        
                        if not res_p or res_p[0] == "Cerrado":
                            st.error(f"Error: El período {p_check} para Contabilidad está CERRADO.")
                        elif diferencia != 0:
                            st.error("Error: El asiento no está cuadrado (Partida Doble).")
                        else:
                            # Proceso de guardado Maestro-Detalle
                            num_correlativo = database.obtener_ultimo_correlativo("AS")
                            database.ejecutar_transaccion(
                                "INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen, creado_por) VALUES (%s,%s,%s,%s,%s)",
                                (num_correlativo, fecha_as, desc_as, origen_as, st.session_state['usuario_autenticado'])
                            )
                            st.success(f"Asiento {num_correlativo} posteado.")
                            st.session_state["nuevo_asiento"] = False
                            st.rerun()
                
                if st.button("Cancelar"):
                    st.session_state["nuevo_asiento"] = False
                    st.rerun()

        # Visualización del Diario
        df_diario = pd.read_sql("SELECT num_asiento, fecha, concepto, origen FROM asientos_cabecera ORDER BY id DESC", database.conectar())
        st.dataframe(df_diario, use_container_width=True)

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
