import streamlit as st
import pandas as pd
import io
import plotly.express as px

# 1. Configuración e Identidad
st.set_page_config(page_title="Adonai Group - ERP", layout="wide", page_icon="🏦")

# Inicializar estados de memoria
if 'seccion' not in st.session_state:
    st.session_state.seccion = 'Dashboard'
if 'maestro_data' not in st.session_state:
    st.session_state.maestro_data = None
if 'bancos_config' not in st.session_state:
    st.session_state.bancos_config = None

# 2. CSS para Botones Dinámicos
def aplicar_estilo_botones():
    estilo = f"""
    <style>
    div[data-testid="stButton"] button {{
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        font-weight: bold;
    }}
    /* Botón Dashboard */
    div[data-testid="stHeader"] {{ background-color: rgba(0,0,0,0); }}
    </style>
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_botones()

# 3. Encabezado Corporativo
st.markdown("""
    <div style="background-color:#1E3A8A;padding:20px;border-radius:15px;margin-bottom:25px;border-left: 10px solid #FACC15;">
    <h1 style="color:white;text-align:center;margin:0;letter-spacing: 2px;">ADONAI INDUSTRIAL GROUP</h1>
    <p style="color:white;text-align:center;margin:0;opacity:0.8;">Plataforma de Control Financiero Centralizado</p>
    </div>
    """, unsafe_allow_html=True)

# 4. Menú de Navegación con Colores Dinámicos
c1, c2, c3 = st.columns(3)

with c1:
    color = "primary" if st.session_state.seccion == 'Dashboard' else "secondary"
    if st.button("📊 DASHBOARD GERENCIAL", type=color):
        st.session_state.seccion = 'Dashboard'
        st.rerun()

with c2:
    color = "primary" if st.session_state.seccion == 'Libro' else "secondary"
    if st.button("📝 LIBRO DIARIO", type=color):
        st.session_state.seccion = 'Libro'
        st.rerun()

with c3:
    color = "primary" if st.session_state.seccion == 'Maestro' else "secondary"
    if st.button("📂 CONFIGURACIÓN MAESTRO", type=color):
        st.session_state.seccion = 'Maestro'
        st.rerun()

st.divider()

# 5. Lógica de Carga (Persistent Maestro)
with st.sidebar:
    st.header("⚙️ Panel de Control")
    
    # Carga del Maestro (Cerebro)
    if st.session_state.maestro_data is None:
        st.subheader("1. Configurar Cerebro")
        m_file = st.file_uploader("Subir Maestro de Cuentas", type=["xlsx"])
        if m_file:
            try:
                st.session_state.maestro_data = pd.read_excel(m_file, sheet_name="Maestro_Cuentas")
                st.session_state.bancos_config = pd.read_excel(m_file, sheet_name="Bancos")
                st.success("🧠 Cerebro cargado en memoria")
            except Exception as e:
                st.error("Error en pestañas del Maestro")
    else:
        st.success("✅ Maestro cargado en memoria")
        if st.button("🗑️ Borrar Maestro de memoria"):
            st.session_state.maestro_data = None
            st.session_state.bancos_config = None
            st.rerun()

    st.divider()
    
    # Carga de Movimientos
    st.subheader("2. Procesar Movimientos")
    d_file = st.file_uploader("Subir Libro de Bancos", type=["xlsx"])

# 6. Área de Trabajo según Sección
if st.session_state.seccion == 'Dashboard':
    if st.session_state.maestro_data is not None and d_file is not None:
        if st.button("🚀 EJECUTAR PROCESAMIENTO AHORA", use_container_width=True):
            st.balloons()
            st.info("Simulando procesamiento... (Aquí se insertaría la lógica de cruce)")
    
    # Métricas de Ejemplo
    m1, m2, m3 = st.columns(3)
    m1.metric("INGRESOS", "Bs. 0.00", help="Suma de ingresos de todos los bancos")
    m2.metric("EGRESOS", "Bs. 0.00", delta_color="inverse")
    m3.metric("UTILIDAD NETA", "Bs. 0.00")
    
    st.info("Gráficos de Adonai aparecerán aquí tras la ejecución.")

elif st.session_state.seccion == 'Libro':
    st.header("📒 Libro Diario Consolidado")
    st.caption("Asientos contables listos para auditoría y registro.")
    # Tabla vacía de ejemplo
    st.dataframe(pd.DataFrame(columns=["Fecha", "Cuenta", "Descripción", "Debe", "Haber"]), use_container_width=True)

elif st.session_state.seccion == 'Maestro':
    st.header("📂 Visualización del Cerebro")
    if st.session_state.maestro_data is not None:
        tab_m, tab_b = st.tabs(["Cuentas", "Bancos"])
        with tab_m:
            st.dataframe(st.session_state.maestro_data, use_container_width=True)
        with tab_b:
            st.dataframe(st.session_state.bancos_config, use_container_width=True)
    else:
        st.warning("No hay un Maestro cargado en memoria. Súbelo desde el panel lateral.")
