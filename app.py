import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="🏦")

# Estilo personalizado para que se vea mejor
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_content_type=True)

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
        # Si es la hoja de resumen GYP, solo la usamos si tiene el detalle de movimientos
        if nombre_hoja.lower() == 'gyp' and moneda == 'BS': continue 

        # 1. Buscar la fila de encabezados que contenga 'GYP'
        idx_titulos = -1
        for i in range(min(40, len(df_raw))):
            fila = [str(x).upper() for x in df_raw.iloc[i].values]
            if 'GYP' in fila:
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        # 2. Identificar columnas clave (Ingresos BS/USD, Egresos BS/USD, GYP)
        c_gyp = 'GYP'
        c_ing = next((c for c in df.columns if 'INGRESOS' in c), None)
        c_egr = next((c for c in df.columns if 'EGRESOS' in c), None)
        c_desc = next((c for c in df.columns if 'DESCRIPCION' in c or 'CONCEPTO' in c), 'DESCRIPCION')

        if c_ing and c_egr:
            df['ING_F'] = df[c_ing].apply(limpiar_monto)
            df['EGR_F'] = df[c_egr].apply(limpiar_monto)
            
            # Filtro: Filas que tengan un código GYP Y algún monto
            df_valido = df[df[c_gyp].notna() & ((df['ING_F'] != 0) | (df['EGR_F'] != 0))].copy()
            
            if not df_valido.empty:
                if moneda == "BS":
                    df_valido['TOTAL_USD'] = (df_valido['ING_F'] - df_valido['EGR_F']) / tasa
                    df_valido['TOTAL_BS'] = df_valido['ING_F'] - df_valido['EGR_F']
                else:
                    df_valido['TOTAL_USD'] = df_valido['ING_F'] - df_valido['EGR_F']
                    df_valido['TOTAL_BS'] = df_valido['TOTAL_USD'] * tasa
                
                df_valido['CUENTA_GYP'] = df_valido[c_gyp]
                df_valido['ORIGEN'] = f"{nombre_hoja} ({moneda})"
                # Intentamos capturar la descripción si existe
                df_valido['DETALLE'] = df_valido[c_desc] if c_desc in df_valido.columns else "S/D"
                
                lista_final.append(df_valido[['CUENTA_GYP', 'DETALLE', 'TOTAL_BS', 'TOTAL_USD', 'ORIGEN']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("📊 Sistema ERP Adonai Industrial")
st.markdown("---")

with st.sidebar:
    st.header("Configuración de Carga")
    mes_sel = st.selectbox("Mes de Relación:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa BCV (Bs/$):", value=45.0, format="%.4f")
    if st.button("🔄 Sincronizar Datos", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Leyendo códigos GYP y montos..."):
                d_bs = leer_excel_drive(service, mes_sel, "BS")
                d_usd = leer_excel_drive(service, mes_sel, "USD")
                
                res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
                res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
                
                st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
                if not st.session_state.datos_acumulados.empty:
                    st.success("¡Información Contable Capturada!")
                else:
                    st.error("No se hallaron montos. Verifique que la columna 'GYP' y 'INGRESOS/EGRESOS' existan.")

# DASHBOARD VISUAL
df = st.session_state.datos_acumulados
if not df.empty:
    # Métricas Principales
    total_ing_usd = df[df['TOTAL_USD'] > 0]['TOTAL_USD'].sum()
    total_egr_usd = abs(df[df['TOTAL_USD'] < 0]['TOTAL_USD'].sum())
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos Totales (USD)", f"$ {total_ing_usd:,.2f}")
    col2.metric("Egresos Totales (USD)", f"$ {total_egr_usd:,.2f}")
    col3.metric("Utilidad Operativa", f"$ {total_ing_usd - total_egr_usd:,.2f}", delta_color="normal")
    
    st.markdown("### 📋 Resumen por Cuentas (GYP)")
    # Agrupamos para mostrar cuánto dinero hay por cada código de cuenta
    resumen_gyp = df.groupby('CUENTA_GYP').agg({
        'TOTAL_BS': 'sum',
        'TOTAL_USD': 'sum'
    }).reset_index()
    
    st.table(resumen_gyp.style.format({"TOTAL_BS": "{:,.2f}", "TOTAL_USD": "{:,.2f}"}))
    
    with st.expander("Ver detalle de todos los movimientos"):
        st.dataframe(df, use_container_width=True)
else:
    st.info("💡 Use la barra lateral para sincronizar los archivos de Google Drive.")
