import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

# Configuración inicial sin errores de parámetros
st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="🏦")

# Estilo visual corregido
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; }
    </style>
    """, unsafe_allow_html=True)

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
    # Estandarizar separadores: 1.500,00 -> 1500.00
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
        # Ignorar hojas de sistema
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'hoja1']): continue
        
        # BUSCAR FILA DE TÍTULOS (Donde esté 'GYP')
        idx_titulos = -1
        for i in range(min(50, len(df_raw))):
            fila = [str(x).strip().upper() for x in df_raw.iloc[i].values]
            if 'GYP' in fila:
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        # Ajustar DataFrame
        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        # Identificar columnas exactas
        c_gyp = 'GYP'
        # Buscamos columnas que contengan "INGRESOS" o "EGRESOS" y la moneda
        c_ing = next((c for c in df.columns if 'INGRESOS' in c and moneda in c), None)
        c_egr = next((c for c in df.columns if 'EGRESOS' in c and moneda in c), None)
        
        # Si no las halla tan específicas, busca solo INGRESOS/EGRESOS
        if not c_ing: c_ing = next((c for c in df.columns if 'INGRESOS' in c), None)
        if not c_egr: c_egr = next((c for c in df.columns if 'EGRESOS' in c), None)

        if c_ing and c_egr and c_gyp in df.columns:
            df['ING_F'] = df[c_ing].apply(limpiar_monto)
            df['EGR_F'] = df[c_egr].apply(limpiar_monto)
            
            # Filtro clave: Debe tener código GYP y algún movimiento de dinero
            df_valido = df[df[c_gyp].notna() & ((df['ING_F'] != 0) | (df['EGR_F'] != 0))].copy()
            
            if not df_valido.empty:
                if moneda == "BS":
                    df_valido['VALOR_USD'] = (df_valido['ING_F'] - df_valido['EGR_F']) / tasa
                    df_valido['VALOR_BS'] = df_valido['ING_F'] - df_valido['EGR_F']
                else:
                    df_valido['VALOR_USD'] = df_valido['ING_F'] - df_valido['EGR_F']
                    df_valido['VALOR_BS'] = df_valido['VALOR_USD'] * tasa
                
                df_valido['CUENTA'] = df_valido[c_gyp]
                df_valido['BANCO'] = nombre_hoja
                lista_final.append(df_valido[['CUENTA', 'BANCO', 'VALOR_BS', 'VALOR_USD']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 Dashboard Contable - Adonai Group")

with st.sidebar:
    st.header("Sincronización")
    mes_sel = st.selectbox("Mes:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa BCV:", value=45.0)
    if st.button("🔄 Cargar Datos"):
        service = conectar_drive()
        if service:
            with st.spinner("Procesando archivos..."):
                d_bs = leer_excel_drive(service, mes_sel, "BS")
                d_usd = leer_excel_drive(service, mes_sel, "USD")
                
                res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
                res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
                
                st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
                if not st.session_state.datos_acumulados.empty:
                    st.success("¡Datos cargados correctamente!")
                else:
                    st.warning("No se encontraron registros con códigos GYP.")

# VISUALIZACIÓN
df = st.session_state.datos_acumulados
if not df.empty:
    # Agrupación por cuenta GYP
    resumen = df.groupby('CUENTA').agg({'VALOR_BS': 'sum', 'VALOR_USD': 'sum'}).reset_index()
    
    c1, c2 = st.columns(2)
    c1.metric("Balance Total (BS)", f"Bs. {df['VALOR_BS'].sum():,.2f}")
    c2.metric("Balance Total (USD)", f"$ {df['VALOR_USD'].sum():,.2f}")

    st.subheader("📊 Resumen por Código GYP")
    st.dataframe(resumen.style.format({'VALOR_BS': '{:,.2f}', 'VALOR_USD': '{:,.2f}'}), use_container_width=True)
    
    with st.expander("Ver detalle por bancos"):
        st.dataframe(df, use_container_width=True)
else:
    st.info("💡 Seleccione el mes y haga clic en 'Cargar Datos'.")
