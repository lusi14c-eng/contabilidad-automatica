import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io

st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="📊")

if 'datos_acumulados' not in st.session_state:
    st.session_state.datos_acumulados = pd.DataFrame()

def conectar_drive():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de credenciales: {e}")
        return None

def leer_excel_drive(service, nombre_archivo):
    try:
        query = f"name = '{nombre_archivo}' and trashed = false"
        resultado = service.files().list(q=query, fields="files(id, name)").execute()
        archivos = resultado.get('files', [])
        if not archivos: return None
        file_id = archivos[0]['id']
        request = service.files().get_media(fileId=file_id)
        return pd.read_excel(io.BytesIO(request.execute()), sheet_name=None, header=None)
    except:
        return None

def limpiar_monto_extremo(valor):
    """Limpia cualquier rastro de texto para dejar solo números."""
    if pd.isna(valor) or str(valor).strip() == '': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    
    texto = str(valor).strip().lower()
    # Quitar símbolos comunes
    for s in ['bs', '$', '.', ' ', '\xa0']: 
        texto = texto.replace(s, '')
    # Cambiar coma decimal por punto si existe
    texto = texto.replace(',', '.')
    
    try:
        return float(texto)
    except:
        return 0.0

def procesar_hojas(dict_hojas, moneda, tasa):
    lista_final = []
    for nombre_hoja, df_raw in dict_hojas.items():
        if df_raw.empty or 'gyp' in nombre_hoja.lower() or 'resumen' in nombre_hoja.lower(): 
            continue
        
        # Encontrar fila de títulos
        idx_titulos = -1
        for i in range(min(15, len(df_raw))):
            fila = [str(x).lower() for x in df_raw.iloc[i].values]
            if any(k in f for f in fila for k in ['ingreso', 'egreso', 'haber', 'debe']):
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().lower() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        df = df.loc[:, ~df.columns.duplicated()].copy()

        c_ing = next((c for c in df.columns if 'ingreso' in str(c) or 'debe' in str(c)), None)
        c_egr = next((c for c in df.columns if 'egreso' in str(c) or 'haber' in str(c)), None)

        if c_ing and c_egr:
            df['ing_limpio'] = df[c_ing].apply(limpiar_monto_extremo)
            df['egr_limpio'] = df[c_egr].apply(limpiar_monto_extremo)
            
            # Cálculo de totales
            if moneda == "BS":
                df['total_bs'] = df['ing_limpio'] - df['egr_limpio']
                df['total_usd'] = df['total_bs'] / tasa
            else:
                df['total_usd'] = df['ing_limpio'] - df['egr_limpio']
                df['total_bs'] = df['total_usd'] * tasa
            
            df['pestaña'] = nombre_hoja
            df['moneda_origen'] = moneda
            
            # Solo añadir si hay algún valor numérico detectado
            if df['ing_limpio'].sum() != 0 or df['egr_limpio'].sum() != 0:
                lista_final.append(df)

    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 ERP Adonai Industrial")

with st.sidebar:
    mes = st.selectbox("Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa (Bs/$):", value=45.0)
    if st.button("🔄 Sincronizar"):
        service = conectar_drive()
        if service:
            d_bs = leer_excel_drive(service, f"RELACION INGRESOS Y EGRESOS {mes} BS.xlsx")
            d_usd = leer_excel_drive(service, f"RELACION INGRESOS Y EGRESOS {mes} USD.xlsx")
            
            res_bs = procesar_hojas(d_bs, "BS", tasa) if d_bs else pd.DataFrame()
            res_usd = procesar_hojas(d_usd, "USD", tasa) if d_usd else pd.DataFrame()
            
            st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
            if not st.session_state.datos_acumulados.empty:
                st.success(f"¡Sincronizado! Se detectaron datos en el mes {mes}")
            else:
                st.warning("Archivos encontrados pero los montos parecen estar en 0 o vacíos.")

# TABLERO
df = st.session_state.datos_acumulados
if not df.empty:
    i = df[df['total_usd'] > 0]['total_usd'].sum()
    e = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos Totales", f"$ {i:,.2f}")
    c2.metric("Egresos Totales", f"$ {e:,.2f}")
    c3.metric("Utilidad", f"$ {i-e:,.2f}")
    
    st.subheader("📋 Movimientos Detectados")
    # Mostrar solo columnas útiles para no saturar
    cols_a_ver = [c for c in ['fecha', 'descripcion', 'concepto', 'pestaña', 'total_bs', 'total_usd'] if c in df.columns]
    st.dataframe(df[cols_a_ver] if len(cols_a_ver) > 2 else df, use_container_width=True)
else:
    st.info("Sin datos. Intenta Sincronizar.")
