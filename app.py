import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import plotly.express as px

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="📊")

if 'datos_acumulados' not in st.session_state:
    st.session_state.datos_acumulados = pd.DataFrame()

# 2. FUNCIONES DE CONEXIÓN
def conectar_drive():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None

def leer_excel_drive(service, nombre_archivo):
    try:
        # Esto nos dirá en la consola de Streamlit qué archivos está viendo el robot
        resultado = service.files().list(q="trashed = false", fields="files(name)").execute()
        archivos_visibles = [f['name'] for f in resultado.get('files', [])]
        st.write(f"🔍 Archivos que el robot puede ver: {archivos_visibles}") # Esto aparecerá en tu app
        
        query = f"name = '{nombre_archivo}' and trashed = false"
        resultado = service.files().list(q=query, fields="files(id, name)").execute()
        archivos = resultado.get('files', [])
        if not archivos:
            return None
        file_id = archivos[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO(request.execute())
        return pd.read_excel(fh, sheet_name=None, header=2)
    except Exception as e:
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
            
            if 'gyp' in df.columns:
                df_valido = df[(df[col_ing] != 0) | (df[col_egr] != 0) | (df['gyp'].notna())].copy()
                lista_movimientos.append(df_valido)
    return pd.concat(lista_movimientos) if lista_movimientos else pd.DataFrame()

# 3. INTERFAZ DE USUARIO
st.title("🏦 Adonai Industrial Group - ERP")

with st.sidebar:
    st.header("⚙️ Configuración")
    mes_num = st.selectbox("Seleccione Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa de Cambio (Bs/USD):", value=45.0, step=0.1)
    
    if st.button("🔄 Sincronizar con Drive"):
        service = conectar_drive()
        if service:
            n_bs = f"RELACION INGRESOS Y EGRESOS {mes_num} BS"
            n_usd = f"RELACION INGRESOS Y EGRESOS {mes_num} USD"
            
            with st.spinner(f"Sincronizando mes {mes_num}..."):
                d_bs = leer_excel_drive(service, n_bs)
                d_usd = leer_excel_drive(service, n_usd)
                
                if d_bs and d_usd:
                    res_bs = procesar_hojas(d_bs, "BS", tasa, f"Mes {mes_num}")
                    res_usd = procesar_hojas(d_usd, "USD", tasa, f"Mes {mes_num}")
                    
                    nuevo_mes = pd.concat([res_bs, res_usd])
                    if not st.session_state.datos_acumulados.empty:
                        st.session_state.datos_acumulados = st.session_state.datos_acumulados[
                            st.session_state.datos_acumulados['mes_reporte'] != f"Mes {mes_num}"
                        ]
                    st.session_state.datos_acumulados = pd.concat([st.session_state.datos_acumulados, nuevo_mes])
                    st.success("¡Sincronización Exitosa!")
                else:
                    st.error(f"No se encontró: {n_bs} o {n_usd}")

# 4. DASHBOARD (PARTE CORREGIDA)
if not st.session_state.datos_acumulados.empty:
    df_actual = st.session_state.datos_acumulados[st.session_state.datos_acumulados['mes_reporte'] == f"Mes {mes_num}"]
    
    if not df_actual.empty:
        c1, c2, c3 = st.columns(3)
        # Filtramos ingresos y egresos para las métricas
        ing_t = df_actual[df_actual['total_usd'] > 0]['total_usd'].sum()
        # Aquí estaba el error del paréntesis:
        egr_t = abs(df_actual[df_actual['total_usd'] < 0]['total_usd'].sum())
        
        c1.metric("Ingresos (USD)", f"$ {ing_t:,.2f}")
        c2.metric("Egresos (USD)", f"$ {egr_t:,.2f}")
        c3.metric("Utilidad (USD)", f"$ {ing_t - egr_t:,.2f}")
        
        if 'gyp' in df_actual.columns:
            st.subheader("📊 Resumen por Código GyP")
            pyl = df_actual.groupby('gyp')[['total_bs', 'total_usd']].sum().reset_index()
            st.dataframe(pyl, use_container_width=True)
    else:
        st.warning(f"No hay datos para mostrar en el Mes {mes_num}")
else:
    st.info("Configura los parámetros y presiona Sincronizar.")
