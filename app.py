import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

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
    except:
        pass
    return None

def limpiar_monto(valor):
    if pd.isna(valor) or str(valor).strip() == '': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).upper().replace('BS', '').replace('$', '').replace(' ', '').strip()
    # Manejo de 1.500,00 -> 1500.00
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
        # Saltamos hojas que no sirven
        if any(x in nombre_hoja.lower() for x in ['resumen', 'portada', 'grafic', 'lista']): continue
        
        # BUSCADOR AGRESIVO DE CABECERAS (Busca en 50 filas)
        idx_titulos = -1
        palabras_clave = ['ingreso', 'egreso', 'haber', 'debe', 'entrada', 'salida', 'monto']
        
        for i in range(min(50, len(df_raw))):
            fila = [str(x).lower().strip() for x in df_raw.iloc[i].values]
            if any(k in f for f in fila for k in palabras_clave):
                # Verificamos que al menos haya dos de estas palabras en la fila
                coincidencias = sum(1 for k in palabras_clave if any(k in f for f in fila))
                if coincidencias >= 1:
                    idx_titulos = i
                    break
        
        if idx_titulos == -1: continue

        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().lower() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        df = df.loc[:, ~df.columns.duplicated()].copy()

        # Buscamos columnas de Ingreso y Egreso con variaciones
        c_ing = next((c for c in df.columns if any(k in str(c) for k in ['ingreso', 'debe', 'entrada'])), None)
        c_egr = next((c for c in df.columns if any(k in str(c) for k in ['egreso', 'haber', 'salida'])), None)

        if c_ing and c_egr:
            df['ing_f'] = df[c_ing].apply(limpiar_monto)
            df['egr_f'] = df[c_egr].apply(limpiar_monto)
            
            df_con_datos = df[(df['ing_f'] != 0) | (df['egr_f'] != 0)].copy()
            
            if not df_con_datos.empty:
                if moneda == "BS":
                    df_con_datos['total_bs'] = df_con_datos['ing_f'] - df_con_datos['egr_f']
                    df_con_datos['total_usd'] = df_con_datos['total_bs'] / tasa
                else:
                    df_con_datos['total_usd'] = df_con_datos['ing_f'] - df_con_datos['egr_f']
                    df_con_datos['total_bs'] = df_con_datos['total_usd'] * tasa
                
                df_con_datos['pestaña'] = nombre_hoja
                df_con_datos['archivo'] = moneda
                lista_final.append(df_con_datos)
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 ERP Adonai Industrial Group")

with st.sidebar:
    mes_sel = st.selectbox("Mes:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa:", value=45.0)
    if st.button("🔄 Sincronizar"):
        service = conectar_drive()
        if service:
            d_bs = leer_excel_drive(service, mes_sel, "BS")
            d_usd = leer_excel_drive(service, mes_sel, "USD")
            
            # Diagnóstico rápido si no encuentra nada
            if d_usd: st.sidebar.write(f"📂 Pestañas USD: {list(d_usd.keys())}")
            if d_bs: st.sidebar.write(f"📂 Pestañas BS: {list(d_bs.keys())}")
            
            res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
            res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
            
            st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
            
            if not st.session_state.datos_acumulados.empty:
                st.success("¡Datos capturados!")
            else:
                st.error("No se detectaron montos. Revisa los nombres de las columnas en el Excel.")

# TABLERO
df = st.session_state.datos_acumulados
if not df.empty:
    i = df[df['total_usd'] > 0]['total_usd'].sum()
    e = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", f"$ {i:,.2f}")
    c2.metric("Egresos", f"$ {e:,.2f}")
    c3.metric("Saldo", f"$ {i-e:,.2f}")
    st.dataframe(df, use_container_width=True)
