import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import plotly.express as px

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="📊")

# Inicializar el histórico
if 'datos_acumulados' not in st.session_state:
    st.session_state.datos_acumulados = pd.DataFrame()

# 2. FUNCIONES DE CONEXIÓN (CORREGIDAS)
def conectar_drive():
    try:
        # Extraemos los secretos y los convertimos a un diccionario normal
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # LIMPIEZA CRÍTICA DE LA LLAVE PRIVADA
        if "private_key" in creds_dict:
            # Esto corrige los errores de PEM y Padding automáticamente
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None

def leer_excel_drive(service, nombre_archivo):
    try:
        query = f"name = '{nombre_archivo}' and trashed = false"
        resultado = service.files().list(q=query, fields="files(id, name)").execute()
        archivos = resultado.get('files', [])
        
        if not archivos:
            return None
        
        file_id = archivos[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO(request.execute())
        # header=2 indica que los títulos están en la FILA 3
        return pd.read_excel(fh, sheet_name=None, header=2)
    except Exception as e:
        st.error(f"Error al leer archivo {nombre_archivo}: {e}")
        return None

def procesar_hojas(dict_hojas, moneda_archivo, tasa_cambio, mes_label):
    lista_movimientos = []
    for nombre_banco, df in dict_hojas.items():
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        col_ing = 'ingresos bs' if moneda_archivo == "BS" else 'ingreso usd'
        col_egr = 'egresos bs' if moneda_archivo == "BS" else 'egreso usd'
        
        if col_ing in df.columns and col_egr in df.columns:
            df[col_ing] = pd.to_numeric(df[col_ing], errors='coerce').fillna(0)
            df[col_egr] = pd.to_numeric(df[col_egr], errors='coerce').fillna(0)
            
            if moneda_archivo == "BS":
                df['total_bs'] = df[col_ing] - df[col_egr]
                df['total_usd'] = df['total_bs'] / tasa_cambio
            else:
                df['total_usd'] = df[col_ing] - df[col_egr]
                df['total_bs'] = df['total_usd'] * tasa_cambio
            
            df['banco'] = nombre_banco
            df['mes_reporte'] = mes_label
            df['moneda_origen'] = moneda_archivo
            
            # Filtrado por movimientos o código GyP
            if 'gyp' in df.columns:
                df_valido = df[(df[col_ing] > 0) | (df[col_egr] > 0) | (df['gyp'].notna())].copy()
                lista_movimientos.append(df_valido)
            
    return pd.concat(lista_movimientos) if lista_movimientos else pd.DataFrame()

# 3. INTERFAZ DE USUARIO
st.title("🏦 Adonai Industrial Group - ERP")

with st.sidebar:
    st.header("⚙️ Configuración")
    mes_num = st.selectbox("Seleccione Mes:", range(1, 13), index=0)
    tasa = st.number_input("Tasa de Cambio (Bs/USD):", value=45.0, step=0.1)
    
   if st.button("🔄 Sincronizar con Drive"):
        service = conectar_drive()
        if service:
            # Forzamos los nombres exactos en MAYÚSCULAS como los tienes en Drive
            n_bs = f"RELACION INGRESOS Y EGRESOS {mes_num} BS"
            n_usd = f"RELACION INGRESOS Y EGRESOS {mes_num} USD"
            
            with st.spinner(f"Buscando: {n_bs} ..."):
                d_bs = leer_excel_drive(service, n_bs)
                d_usd = leer_excel_drive(service, n_usd)

# 4. DASHBOARD
if not st.session_state.datos_acumulados.empty:
    df_actual = st.session_state.datos_acumulados[st.session_state.datos_acumulados['mes_reporte'] == f"Mes {mes_num}"]
    
    if not df_actual.empty:
        c1, c2, c3 = st.columns(3)
        ing_t = df_actual[df_actual['total_usd'] > 0]['total_usd'].sum()
        egr_t = abs(df_actual[df_actual['total_usd'] < 0]['total_usd'].sum())
        
        c1.metric("Ingresos (USD)", f"$ {ing_t:,.2f}")
        c2.metric("Egresos (USD)", f"$ {egr_t:,.2f}")
        c3.metric("Utilidad (USD)", f"$ {ing_t - egr_t:,.2f}")
        
        if 'gyp' in df_actual.columns:
            st.subheader("📊 Ganancias y Pérdidas (por Código GyP)")
            pyl = df_actual.groupby('gyp')[['total_bs', 'total_usd']].sum().reset_index()
            st.dataframe(pyl, use_container_width=True)
    else:
        st.warning(f"No hay datos procesados para el Mes {mes_num}")
else:
    st.info("Presiona el botón de Sincronizar para cargar los datos de Google Drive.")
