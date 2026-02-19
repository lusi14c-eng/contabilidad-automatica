import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group ERP", layout="wide")

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
        if texto.find('.') < texto.find(','): texto = texto.replace('.', '').replace(',', '.')
        else: texto = texto.replace(',', '')
    elif ',' in texto: texto = texto.replace(',', '.')
    texto = re.sub(r'[^0-9.-]', '', texto)
    try: return float(texto)
    except: return 0.0

def procesar_hojas(dict_hojas, moneda, tasa):
    lista_final = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        # Saltamos hojas de resumen
        if any(x in nombre_hoja.lower() for x in ['gyp', 'data', 'portada', 'hoja1']): continue
        
        # 1. Encontrar la fila donde empiezan los datos (buscamos cualquier número)
        idx_inicio = -1
        for i in range(min(30, len(df_raw))):
            # Si la fila tiene palabras como ingreso/egreso, esa es
            fila_str = [str(x).lower() for x in df_raw.iloc[i].values]
            if any(k in f for f in fila_str for k in ['ing', 'egr', 'hab', 'deb', 'monto']):
                idx_inicio = i
                break
        
        if idx_inicio == -1: idx_inicio = 5 # Si no encuentra, asume fila 5
        
        df = df_raw.iloc[idx_inicio:].copy()
        df.columns = [str(c).strip().lower() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        # 2. Identificar columnas de montos por NOMBRE o por POSICIÓN
        c_ing = next((c for c in df.columns if any(k in str(c) for k in ['ing', 'deb', 'ent'])), None)
        c_egr = next((c for c in df.columns if any(k in str(c) for k in ['egr', 'hab', 'sal'])), None)

        # Si no las encuentra por nombre, intentamos por las columnas G y H (comunes en tus archivos)
        # o simplemente las columnas 6 y 7
        if not c_ing or not c_egr:
            cols_disponibles = df.columns.tolist()
            if len(cols_disponibles) >= 8:
                c_ing = cols_disponibles[6] # Columna 7
                c_egr = cols_disponibles[7] # Columna 8

        if c_ing and c_egr:
            df['ing_f'] = df[c_ing].apply(limpiar_monto)
            df['egr_f'] = df[c_egr].apply(limpiar_monto)
            
            # Filtramos filas vacías
            df_valido = df[(df['ing_f'] != 0) | (df['egr_f'] != 0)].copy()
            
            if not df_valido.empty:
                if moneda == "BS":
                    df_valido['total_bs'] = df_valido['ing_f'] - df_valido['egr_f']
                    df_valido['total_usd'] = df_valido['total_bs'] / tasa
                else:
                    df_valido['total_usd'] = df_valido['ing_f'] - df_valido['egr_f']
                    df_valido['total_bs'] = df_valido['total_usd'] * tasa
                
                df_valido['banco'] = nombre_hoja
                lista_final.append(df_valido)
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 Dashboard Financiero Adonai")

with st.sidebar:
    mes_sel = st.selectbox("Mes:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa:", value=45.0)
    btn = st.button("🔄 Sincronizar")

if btn:
    service = conectar_drive()
    if service:
        d_bs = leer_excel_drive(service, mes_sel, "BS")
        d_usd = leer_excel_drive(service, mes_sel, "USD")
        
        res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
        res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
        
        st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
        if not st.session_state.datos_acumulados.empty:
            st.success("¡Datos cargados!")
        else:
            st.error("No se detectaron montos numéricos en las columnas de dinero.")

# MOSTRAR DATOS
df = st.session_state.datos_acumulados
if not df.empty:
    i = df[df['total_usd'] > 0]['total_usd'].sum()
    e = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos (USD)", f"$ {i:,.2f}")
    c2.metric("Egresos (USD)", f"$ {e:,.2f}")
    c3.metric("Utilidad (USD)", f"$ {i-e:,.2f}")
    st.dataframe(df[['banco', 'total_bs', 'total_usd']], use_container_width=True)
