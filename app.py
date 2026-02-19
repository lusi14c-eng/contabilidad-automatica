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
        fh = io.BytesIO(request.execute())
        return pd.read_excel(fh, sheet_name=None, header=None)
    except:
        return None

def limpiar_monto(valor):
    if pd.isna(valor) or str(valor).strip() == '': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    v = str(valor).upper().replace('BS', '').replace('$', '').replace(' ', '').replace(',', '')
    try:
        return float(v)
    except:
        return 0.0

def procesar_hojas(dict_hojas, moneda_archivo, tasa_cambio, mes_label):
    lista_movimientos = []
    
    for nombre_hoja, df_raw in dict_hojas.items():
        if df_raw.empty or 'gyp' in nombre_hoja.lower() or 'resumen' in nombre_hoja.lower():
            continue

        fila_titulos = -1
        for i in range(min(15, len(df_raw))):
            fila_valores = [str(val).lower().strip() for val in df_raw.iloc[i].values]
            if any('ingreso' in val for val in fila_valores) or any('egreso' in val for val in fila_valores):
                fila_titulos = i
                break
        
        if fila_titulos == -1: continue

        df = df_raw.copy()
        # Limpiar nombres de columnas y evitar duplicados
        cabeceras = [str(c).strip().lower() for c in df.iloc[fila_titulos]]
        df.columns = cabeceras
        df = df.iloc[fila_titulos + 1:].reset_index(drop=True)
        
        # ELIMINAR COLUMNAS DUPLICADAS (Esto arregla el InvalidIndexError)
        df = df.loc[:, ~df.columns.duplicated()].copy()
        # Eliminar columnas sin nombre (nan)
        if 'nan' in df.columns: df = df.drop(columns=['nan'])

        col_ing = next((c for c in df.columns if 'ingreso' in str(c)), None)
        col_egr = next((c for c in df.columns if 'egreso' in str(c) or 'haber' in str(c)), None)

        if col_ing and col_egr:
            df[col_ing] = df[col_ing].apply(limpiar_monto)
            df[col_egr] = df[col_egr].apply(limpiar_monto)
            
            if "BS" in moneda_archivo:
                df['total_bs'] = df[col_ing] - df[col_egr]
                df['total_usd'] = df['total_bs'] / tasa_cambio
            else:
                df['total_usd'] = df[col_ing] - df[col_egr]
                df['total_bs'] = df['total_usd'] * tasa_cambio
            
            df['banco_origen'] = nombre_hoja
            df['mes_reporte'] = mes_label
            
            # Filtro de seguridad: solo filas con dinero
            df_valido = df[(df[col_ing] != 0) | (df[col_egr] != 0)].copy()
            if not df_valido.empty:
                lista_movimientos.append(df_valido)
                
    return pd.concat(lista_movimientos, axis=0, ignore_index=True) if lista_movimientos else pd.DataFrame()

# INTERFAZ
st.title("🏦 Adonai Industrial Group - ERP")

with st.sidebar:
    mes_num = st.selectbox("Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa:", value=45.0, step=0.01)
    if st.button("🔄 Sincronizar Drive"):
        service = conectar_drive()
        if service:
            n_bs = f"RELACION INGRESOS Y EGRESOS {mes_num} BS.xlsx"
            n_usd = f"RELACION INGRESOS Y EGRESOS {mes_num} USD.xlsx"
            with st.spinner("Procesando..."):
                d_bs = leer_excel_drive(service, n_bs)
                d_usd = leer_excel_drive(service, n_usd)
                if d_bs or d_usd:
                    res_bs = procesar_hojas(d_bs, "BS", tasa, f"Mes {mes_num}") if d_bs else pd.DataFrame()
                    res_usd = procesar_hojas(d_usd, "USD", tasa, f"Mes {mes_num}") if d_usd else pd.DataFrame()
                    st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], axis=0, ignore_index=True)
                    st.success("¡Sincronizado!")
                else:
                    st.error("Archivos no encontrados.")

# RESULTADOS
df = st.session_state.datos_acumulados
if not df.empty:
    ing = df[df['total_usd'] > 0]['total_usd'].sum()
    egr = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos (USD)", f"$ {ing:,.2f}")
    c2.metric("Egresos (USD)", f"$ {egr:,.2f}")
    c3.metric("Utilidad (USD)", f"$ {ing-egr:,.2f}")
    st.dataframe(df, use_container_width=True)
else:
    st.info("💡 Presiona sincronizar.")
