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
    t1, t2, t3 = st.tabs(["📖 Diario General", "🏢 Centros de Costo", "🔒 Períodos Fiscales"])

    # --- PESTAÑA 3: PERÍODOS (Lo configuramos primero para que afecte al Diario) ---
    with t3:
        st.subheader("Control de Períodos Mensuales")
        
        # Formulario para abrir nuevos meses
        with st.expander("➕ Abrir Nuevo Período"):
            c_p1, c_p2 = st.columns(2)
            m_new = c_p1.selectbox("Mes", range(1, 13), key="m_new")
            a_new = c_p2.number_input("Año", value=2026, key="a_new")
            if st.button("Confirmar Apertura"):
                per_string = f"{a_new}-{str(m_new).zfill(2)}"
                database.ejecutar_transaccion("INSERT INTO periodos_fiscales (periodo, estatus) VALUES (%s, 'Abierto') ON CONFLICT DO NOTHING", (per_string,))
                st.rerun()

        # Visualización de Estatus
        conn = database.conectar()
        df_p = pd.read_sql("SELECT periodo, estatus FROM periodos_fiscales ORDER BY periodo DESC", conn)
        conn.close()

        for idx, row in df_p.iterrows():
            col_per, col_est, col_acc = st.columns([2, 2, 2])
            col_per.write(f"📅 **{row['periodo']}**")
            
            # Semáforo de estatus
            color = "green" if row['estatus'] == "Abierto" else "red"
            col_est.markdown(f"<{color}>● {row['estatus']}</{color}>", unsafe_allow_html=True)
            
            # Botón de acción
            label = "Cerrar Mes" if row['estatus'] == "Abierto" else "Reabrir"
            if col_acc.button(label, key=f"btn_p_{row['periodo']}"):
                nuevo_est = "Cerrado" if row['estatus'] == "Abierto" else "Abierto"
                database.ejecutar_transaccion("UPDATE periodos_fiscales SET estatus = %s WHERE periodo = %s", (nuevo_est, row['periodo']))
                st.rerun()

    # --- PESTAÑA 1: DIARIO GENERAL (Con validación de bloqueo) ---
    with t1:
        col_a, col_b = st.columns([3, 1])
        col_a.subheader("Movimientos del Diario")
        if col_b.button("➕ Nuevo Asiento Manual"):
            st.session_state["modo_asiento"] = "crear"

        if st.session_state.get("modo_asiento"):
            with st.form("form_asiento_cuadrado"):
                st.markdown("### 📝 Nuevo Registro Contable")
                c1, c2, c3 = st.columns([1, 2, 1])
                f_as = c1.date_input("Fecha de Registro")
                con_as = c2.text_input("Concepto o Glosa")
                tipo_as = c3.selectbox("Tipo", ["CG", "CP", "BAN"])

                # VALIDACIÓN DE PERÍODO CERRADO
                per_actual = f"{f_as.year}-{str(f_as.month).zfill(2)}"
                conn = database.conectar()
                res_p = database.ejecutar_query("SELECT estatus FROM periodos_fiscales WHERE periodo = %s", (per_actual,), fetch=True)
                es_cerrado = (res_p and res_p[0] == "Cerrado")

                # Cuerpo del asiento (simplificado para prueba)
                st.markdown("---")
                total_d, total_h = 0.0, 0.0
                filas = []
                for i in range(3): # 3 filas de ejemplo
                    cx1, cx2, cx3, cx4 = st.columns([2, 1, 1, 1])
                    cta = cx1.text_input(f"Cuenta {i+1}", key=f"f_cta_{i}")
                    cc = cx2.text_input(f"CC", key=f"f_cc_{i}")
                    d = cx3.number_input("Debe", min_value=0.0, key=f"f_d_{i}")
                    h = cx4.number_input("Haber", min_value=0.0, key=f"f_h_{i}")
                    if cta:
                        total_d += d
                        total_h += h
                
                st.divider()
                st.write(f"**Total Debe:** {total_d} | **Total Haber:** {total_h}")
                
                # BOTONES DE GUARDADO CON LÓGICA DE BLOQUEO
                if es_cerrado:
                    st.error(f"🚫 El período {per_actual} está CERRADO. No puede contabilizar.")
                    st.form_submit_button("Guardar (Bloqueado)", disabled=True)
                else:
                    if st.form_submit_button("💾 Validar y Guardar Asiento"):
                        if total_d != total_h:
                            st.warning("⚠️ El asiento está descuadrado.")
                        elif total_d == 0:
                            st.error("No puede guardar un asiento vacío.")
                        else:
                            num = database.obtener_ultimo_correlativo(tipo_as)
                            database.ejecutar_transaccion(
                                "INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen, creado_por) VALUES (%s,%s,%s,%s,%s)",
                                (num, f_as, con_as, tipo_as, st.session_state['usuario_autenticado'])
                            )
                            st.success(f"Asiento {num} registrado con éxito.")
                            st.session_state["modo_asiento"] = None
                            st.rerun()

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
