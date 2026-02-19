import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io

# 1. CONFIGURACIÓN DE PÁGINA E IDENTIDAD
st.set_page_config(page_title="Adonai Industrial Group - ERP", layout="wide", page_icon="🏦")

# Inicializar estados de memoria
if 'historico' not in st.session_state:
    st.session_state.historico = pd.DataFrame()

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetricValue"] { color: #1E3A8A; }
    .stButton>button { border-radius: 10px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNCIONES DE CONEXIÓN A DRIVE
def conectar_drive():
    try:
        # Usa el nombre que pusiste en los Secrets [gcp_service_account]
        creds_info = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def leer_excel_drive(service, nombre_archivo):
    query = f"name = '{nombre_archivo}' and trashed = false"
    resultado = service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultado.get('files', [])
    
    if not archivos:
        return None
    
    id_archivo = archivos[0]['id']
    pedido = service.files().get_media(fileId=id_archivo)
    contenido = io.BytesIO(pedido.execute())
    # Leemos todas las pestañas (bancos)
    return pd.read_excel(contenido, sheet_name=None) 

# --- INTERFAZ ADONAI ---
st.markdown(f"""
    <div style="background-color:#1E3A8A;padding:20px;border-radius:15px;text-align:center;margin-bottom:20px">
        <h1 style="color:white;margin:0;">ADONAI INDUSTRIAL GROUP</h1>
        <p style="color:white;opacity:0.8;">Sistema Contable Bimonetario (Drive Sync)</p>
    </div>
    """, unsafe_allow_html=True)

# PANEL DE CONTROL
with st.container():
    col1, col2, col3 = st.columns([2,2,1])
    
    with col1:
        # Selector de Mes basado en tu nomenclatura (11 para Noviembre)
        mes = st.selectbox("📅 Seleccione Mes para Procesar:", range(1, 13), index=10)
    
    with col2:
        tasa = st.number_input("💵 Tasa de Cambio (Bs/USD):", value=45.00, step=0.10)
        
    with col3:
        st.write("") # Espaciador
        btn_sync = st.button("🔄 SINCRONIZAR DRIVE", use_container_width=True)

st.divider()

# LÓGICA DE PROCESAMIENTO
if btn_sync:
    service = conectar_drive()
    if service:
        with st.spinner(f"Buscando archivos del mes {mes}..."):
            # Buscamos los nombres exactos que me diste
            nombre_bs = f"relacion de ingresos y egresos {mes} bs"
            nombre_usd = f"relacion de ingresos y egresos {mes} USD"
            
            dict_bs = leer_excel_drive(service, nombre_bs)
            dict_usd = leer_excel_drive(service, nombre_usd)
            
            if dict_bs and dict_usd:
                st.success(f"✅ Mes {mes} cargado correctamente desde Drive.")
                
                # --- AQUÍ MOSTRAREMOS RESULTADOS (Ejemplo rápido) ---
                c1, c2, c3 = st.columns(3)
                # Aquí iría la lógica de suma de tus columnas de ingresos/egresos
                c1.metric("Ingresos (Consolidados USD)", f"$ 0.00")
                c2.metric("Egresos (Consolidados USD)", f"$ 0.00")
                c3.metric("Utilidad neta", f"$ 0.00")
                
                st.info("💡 Los datos ya están en la memoria del sistema. Puedes ver el detalle en las otras pestañas.")
            else:
                st.error("❌ No se encontraron los archivos. Verifica que el correo de la cuenta de servicio tenga acceso a la carpeta en Drive.")

# PESTAÑAS DE VISUALIZACIÓN
tab1, tab2, tab3 = st.tabs(["📊 P&L Mensual", "📈 Acumulado Anual", "📑 Libro Diario"])

with tab1:
    st.subheader(f"Estado de Ganancias y Pérdidas - Mes {mes}")
    # Aquí insertarás la tabla del P&L que ya tenías
    st.write("Esperando datos de Drive...")

with tab2:
    st.subheader("Evolución Anual Adonai")
    # Gráfico de barras o líneas
