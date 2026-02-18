import streamlit as st
import pandas as pd

# 1. Configuración de página
st.set_page_config(page_title="Adonai Group - ERP", layout="wide", page_icon="🏦")

# 2. Lógica de Navegación (Estado)
if 'seccion' not in st.session_state:
    st.session_state.seccion = 'Dashboard'

# 3. CSS para botones dinámicos
def estilo_boton(nombre_seccion):
    if st.session_state.seccion == nombre_seccion:
        # Estilo para el botón ACTIVO (Azul Adonai)
        return "background-color: #1E3A8A; color: white; border: 2px solid #1E3A8A;"
    else:
        # Estilo para el botón INACTIVO (Gris claro)
        return "background-color: #f0f2f6; color: #31333F; border: 1px solid #d1d5db;"

# 4. Encabezado
st.markdown("""
    <div style="background-color:#1E3A8A;padding:15px;border-radius:10px;margin-bottom:20px">
    <h1 style="color:white;text-align:center;margin:0;">ADONAI INDUSTRIAL GROUP</h1>
    </div>
    """, unsafe_allow_html=True)

# 5. Menú de Navegación con Colores Dinámicos
c1, c2, c3 = st.columns(3)

with c1:
    if st.button("📊 DASHBOARD GERENCIAL", key="btn_dash", help="Ver gráficos"):
        st.session_state.seccion = 'Dashboard'
        st.rerun()
    st.markdown(f'<style>div[data-testid="stButton"] button[key="btn_dash"] {{ {estilo_boton("Dashboard")} }}</style>', unsafe_allow_html=True)

with c2:
    if st.button("📝 LIBRO DIARIO", key="btn_libro", help="Ver asientos contables"):
        st.session_state.seccion = 'Libro'
        st.rerun()
    st.markdown(f'<style>div[data-testid="stButton"] button[key="btn_libro"] {{ {estilo_boton("Libro")} }}</style>', unsafe_allow_html=True)

with c3:
    if st.button("📂 MAESTRO DE CUENTAS", key="btn_maestro", help="Configuración de códigos"):
        st.session_state.seccion = 'Maestro'
        st.rerun()
    st.markdown(f'<style>div[data-testid="stButton"] button[key="btn_maestro"] {{ {estilo_boton("Maestro")} }}</style>', unsafe_allow_html=True)

st.divider()

# 6. Área de Carga y Acción (Solo visible en Dashboard para no saturar)
if st.session_state.seccion == 'Dashboard':
    col_file, col_btn = st.columns([3, 1])
    with col_file:
        m_file = st.file_uploader("Cargar archivos...", type=["xlsx"], label_visibility="collapsed")
    with col_btn:
        st.button("🚀 EJECUTAR PROCESO", use_container_width=True)

# 7. Contenido Dinámico según la Sección
st.markdown(f"### 📍 Estás en: **{st.session_state.seccion}**")

with st.container():
    if st.session_state.seccion == 'Dashboard':
        # Tarjetas de métricas
        m1, m2, m3 = st.columns(3)
        m1.metric("INGRESOS", "Bs. 0.00")
        m2.metric("EGRESOS", "Bs. 0.00")
        m3.metric("UTILIDAD", "Bs. 0.00")
        
        # Espacio para gráficos
        st.write("---")
        st.info("Gráficos de Adonai Industrial Group aparecerán aquí al procesar.")

    elif st.session_state.seccion == 'Libro':
        st.write("#### Asientos Contables Consolidados")
        st.caption("Aquí se listará la partida doble generada automáticamente.")
        st.button("📥 Descargar Excel de Asientos")

    elif st.session_state.seccion == 'Maestro':
        st.write("#### Configuración de Códigos y Bancos")
        st.caption("Previsualiza tu 'Cerebro' contable para verificar errores de códigos.")
