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

def limpiar_monto(valor):
    if pd.isna(valor) or str(valor).strip() == '': return 0.0
    try:
        # Quitamos todo lo que no sea número, punto o coma
        v = str(valor).replace('Bs', '').replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
        return float(v)
    except:
        return 0.0

def procesar_hojas(dict_hojas, moneda, tasa):
    lista_final = []
    for nombre_hoja, df_raw in dict_hojas.items():
        if df_raw.empty or 'gyp' in nombre_hoja.lower(): continue
        
        # 1. Encontrar la fila de títulos (buscamos 'ingreso' o 'egreso')
        idx_titulos = -1
        for i in range(min(10, len(df_raw))):
            fila = [str(x).lower() for x in df_raw.iloc[i].values]
            if any('ingreso' in f or 'egreso' in f or 'haber' in f for f in fila):
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        # 2. Limpiar DataFrame
        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().lower() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        df = df.loc[:, ~df.columns.duplicated()].copy() # Eliminar columnas repetidas

        # 3. Identificar columnas de dinero (muy flexible)
        c_ing = next((c for c in df.columns if 'ingreso' in c), None)
        c_egr = next((c for c in df.columns if 'egreso' in c or 'haber' in c), None)

        if c_ing and c_egr:
            df['ing_num'] = df[c_ing].apply(limpiar_monto)
            df['egr_num'] = df[c_egr].apply(limpiar_monto)
            
            # Solo filas con dinero real
            df = df[(df['ing_num'] != 0) | (df['egr_num'] != 0)].copy()
            
            if not df.empty:
                if moneda == "BS":
                    df['total_usd'] = (df['ing_num'] - df['egr_num']) / tasa
                    df['total_bs'] = df['ing_num'] - df['egr_num']
                else:
                    df['total_usd'] = df['ing_num'] - df['egr_num']
                    df['total_bs'] = (df['ing_num'] - df['egr_num']) * tasa
                
                df['origen'] = f"{nombre_hoja} ({moneda})"
                lista_final.append(df)
        else:
            st.warning(f"⚠️ No encontré columnas de dinero en: {nombre_hoja}. Vistas: {list(df.columns)[:4]}")

    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 Adonai Group - ERP Industrial")

with st.sidebar:
    mes = st.selectbox("Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa (Bs/$):", value=45.0)
    if st.button("🔄 Sincronizar Todo"):
        service = conectar_drive()
        if service:
            d_bs = leer_excel_drive(service, f"RELACION INGRESOS Y EGRESOS {mes} BS.xlsx")
            d_usd = leer_excel_drive(service, f"RELACION INGRESOS Y EGRESOS {mes} USD.xlsx")
            
            res_bs = procesar_hojas(d_bs, "BS", tasa) if d_bs else pd.DataFrame()
            res_usd = procesar_hojas(d_usd, "USD", tasa) if d_usd else pd.DataFrame()
            
            st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
            if not st.session_state.datos_acumulados.empty:
                st.success("¡Datos cargados con éxito!")
            else:
                st.error("Sincronizado, pero los archivos parecen estar vacíos o mal formateados.")

# VISTA DE RESULTADOS
df = st.session_state.datos_acumulados
if not df.empty:
    # Métricas
    ing_total = df[df['total_usd'] > 0]['total_usd'].sum()
    egr_total = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos Totales", f"$ {ing_total:,.2f}")
    col2.metric("Egresos Totales", f"$ {egr_total:,.2f}")
    col3.metric("Utilidad", f"$ {ing_total - egr_total:,.2f}")
    
    st.subheader("📋 Detalle de Movimientos Sincronizados")
    st.dataframe(df, use_container_width=True)
else:
    st.info("Sin datos. Revisa que el Mes en el selector coincida con el nombre del archivo en Drive.")
