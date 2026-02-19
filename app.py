import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="🏦")

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
        st.error(f"Error de conexión: {e}")
        return None

def leer_excel_drive(service, mes, moneda):
    nombre = f"RELACION INGRESOS Y EGRESOS {mes} {moneda}.xlsx"
    try:
        query = f"name = '{nombre}' and trashed = false"
        resultado = service.files().list(q=query, fields="files(id, name)").execute()
        archivos = resultado.get('files', [])
        if archivos:
            file_id = archivos[0]['id']
            request = service.files().get_media(fileId=file_id)
            return pd.read_excel(io.BytesIO(request.execute()), sheet_name=None, header=None)
    except: return None

def limpiar_monto(valor):
    if pd.isna(valor) or str(valor).strip() == '': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).upper().replace('BS', '').replace('$', '').replace(' ', '').strip()
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'): texto = texto.replace('.', '').replace(',', '.')
        else: texto = texto.replace(',', '')
    elif ',' in texto: texto = texto.replace(',', '.')
    texto = re.sub(r'[^0-9.-]', '', texto)
    try: return float(texto)
    except: return 0.0

def procesar_hojas(dict_hojas, moneda, tasa):
    lista_final = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'hoja1']): continue
        
        # BUSCADOR DINÁMICO DE FILA DE CABECERA
        idx_titulos = -1
        for i in range(min(60, len(df_raw))):
            fila_valores = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if 'GYP' in fila_valores:
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        # Extraer nombres de columnas y limpiar
        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        df = df.loc[:, ~df.columns.duplicated()].copy()

        # Identificar columnas por contenido de nombre
        c_gyp = 'GYP'
        c_ing = next((c for c in df.columns if 'INGRESOS' in c), None)
        c_egr = next((c for c in df.columns if 'EGRESOS' in c), None)

        if c_gyp in df.columns and c_ing and c_egr:
            df['ING_F'] = df[c_ing].apply(limpiar_monto)
            df['EGR_F'] = df[c_egr].apply(limpiar_monto)
            
            # FILTRO: Que GYP no esté vacío y que haya montos
            mask = (df[c_gyp].notna()) & (df[c_gyp].astype(str).str.strip() != '') & ((df['ING_F'] != 0) | (df['EGR_F'] != 0))
            df_valido = df[mask].copy()
            
            if not df_valido.empty:
                if moneda == "BS":
                    df_valido['VALOR_USD'] = (df_valido['ING_F'] - df_valido['EGR_F']) / tasa
                    df_valido['VALOR_BS'] = df_valido['ING_F'] - df_valido['EGR_F']
                else:
                    df_valido['VALOR_USD'] = df_valido['ING_F'] - df_valido['EGR_F']
                    df_valido['VALOR_BS'] = df_valido['VALOR_USD'] * tasa
                
                df_valido['CUENTA'] = df_valido[c_gyp].astype(str)
                df_valido['ORIGEN'] = f"{nombre_hoja} ({moneda})"
                lista_final.append(df_valido[['CUENTA', 'ORIGEN', 'VALOR_BS', 'VALOR_USD']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 Sistema Adonai ERP - Inteligencia Contable")

with st.sidebar:
    mes_sel = st.selectbox("Seleccione Mes:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa BCV:", value=45.0)
    if st.button("🔄 Sincronizar Cuentas GYP"):
        service = conectar_drive()
        if service:
            with st.spinner("Analizando archivos..."):
                d_bs = leer_excel_drive(service, mes_sel, "BS")
                d_usd = leer_excel_drive(service, mes_sel, "USD")
                
                res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
                res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
                
                # Unimos y nos aseguramos de que no esté vacío
                final_df = pd.concat([res_bs, res_usd], ignore_index=True)
                if not final_df.empty:
                    st.session_state.datos_acumulados = final_df
                    st.success("¡Datos capturados con éxito!")
                else:
                    st.error("Se abrieron los archivos pero no se encontraron filas con el código GYP y montos.")

# VISUALIZACIÓN
df = st.session_state.datos_acumulados
if not df.empty and 'CUENTA' in df.columns:
    # Agrupación segura
    resumen = df.groupby('CUENTA').agg({'VALOR_BS': 'sum', 'VALOR_USD': 'sum'}).reset_index()
    
    c1, c2 = st.columns(2)
    c1.metric("Balance Total (BS)", f"Bs. {df['VALOR_BS'].sum():,.2f}")
    c2.metric("Balance Total (USD)", f"$ {df['VALOR_USD'].sum():,.2f}")

    st.subheader("📊 Resumen Consolidado por Código GYP")
    st.dataframe(resumen.style.format({'VALOR_BS': '{:,.2f}', 'VALOR_USD': '{:,.2f}'}), use_container_width=True)
    
    with st.expander("Ver detalle por Bancos/Moneda"):
        st.dataframe(df, use_container_width=True)
else:
    st.info("💡 Pendiente de sincronización. Asegúrese de que el archivo tenga la columna 'GYP' con códigos.")
