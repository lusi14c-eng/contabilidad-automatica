import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Real", layout="wide", page_icon="📈")

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
    texto = str(valor).upper().replace('BS', '').replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
    # Caso especial: si hay múltiples puntos tras la limpieza, dejamos solo el último
    if texto.count('.') > 1:
        partes = texto.split('.')
        texto = "".join(partes[:-1]) + "." + partes[-1]
    try: return float(texto)
    except: return 0.0

def procesar_hojas(dict_hojas, moneda, tasa):
    lista_final = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'resumen']): continue
        
        # Encontrar fila de cabecera buscando 'GYP' o 'INGRESOS'
        idx_titulos = -1
        for i in range(min(40, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if 'GYP' in fila or any('INGRESOS' in f for f in fila):
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        # Mapeo de columnas
        c_gyp = next((c for c in df.columns if 'GYP' in c), None)
        c_ing = next((c for c in df.columns if 'INGRESOS' in c), None)
        c_egr = next((c for c in df.columns if 'EGRESOS' in c), None)

        if c_gyp and c_ing and c_egr:
            df['ING_NUM'] = df[c_ing].apply(limpiar_monto)
            df['EGR_NUM'] = df[c_egr].apply(limpiar_monto)
            
            # Filtro: GYP no vacío y que no sea fila de totales
            df_valido = df[df[c_gyp].notna()].copy()
            df_valido = df_valido[df_valido[c_gyp].astype(str).str.strip() != '']
            
            # Solo filas con montos
            df_valido = df_valido[(df_valido['ING_NUM'] != 0) | (df_valido['EGR_NUM'] != 0)]
            
            if not df_valido.empty:
                df_valido['CUENTA'] = df_valido[c_gyp].astype(str).str.strip()
                df_valido['MONEDA_ORIGEN'] = moneda
                lista_final.append(df_valido[['CUENTA', 'MONEDA_ORIGEN', 'ING_NUM', 'EGR_NUM']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 Ganancias y Pérdidas Consolidado")

with st.sidebar:
    mes_sel = st.selectbox("Mes:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa (Bs/$):", value=45.0)
    if st.button("🔄 Generar Reporte"):
        service = conectar_drive()
        if service:
            d_bs = leer_excel_drive(service, mes_sel, "BS")
            d_usd = leer_excel_drive(service, mes_sel, "USD")
            
            res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
            res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
            
            # Resetear estado antes de cargar
            st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
            if st.session_state.datos_acumulados.empty:
                st.warning("No se encontraron registros válidos con columna GYP.")

# PROCESAMIENTO G+P
df = st.session_state.datos_acumulados

if not df.empty and 'CUENTA' in df.columns:
    # 1. Agrupar por cuenta y moneda
    resumen_raw = df.groupby(['CUENTA', 'MONEDA_ORIGEN']).agg({'ING_NUM': 'sum', 'EGR_NUM': 'sum'}).reset_index()
    
    # 2. Conversión a Dólares y Bolívares
    def calcular_gp(row):
        neto = row['ING_NUM'] - row['EGR_NUM']
        if row['MONEDA_ORIGEN'] == 'BS':
            return pd.Series([neto, neto / tasa_sel], index=['BS', 'USD'])
        else:
            return pd.Series([neto * tasa_sel, neto], index=['BS', 'USD'])

    resumen_raw[['NETO_BS', 'NETO_USD']] = resumen_raw.apply(calcular_gp, axis=1)
    
    # 3. Consolidación Final por Código GYP
    gp_final = resumen_raw.groupby('CUENTA').agg({'NETO_BS': 'sum', 'NETO_USD': 'sum'}).reset_index()
    
    # METRICAS
    t_bs = gp_final['NETO_BS'].sum()
    t_usd = gp_final['NETO_USD'].sum()
    
    c1, c2 = st.columns(2)
    c1.metric("Resultado Neto (BS)", f"Bs. {t_bs:,.2f}")
    c2.metric("Resultado Neto (USD)", f"$ {t_usd:,.2f}")

    st.subheader("📋 Detalle G+P por Cuenta")
    st.dataframe(gp_final.style.format({'NETO_BS': '{:,.2f}', 'NETO_USD': '{:,.2f}'}), use_container_width=True)
else:
    st.info("💡 Esperando sincronización de datos...")
