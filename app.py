import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re
from datetime import datetime

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
    # Ajustamos a tu nomenclatura exacta: RELACION INGRESOS Y EGRESOS 11 BS.xlsx
    # Y para USD: RELACION INGRESOS Y EGRESOS 11 USD.xlsx
    nombre = f"RELACION INGRESOS Y EGRESOS {mes} {moneda}.xlsx"
    
    try:
        query = f"name = '{nombre}' and trashed = false"
        resultado = service.files().list(q=query, fields="files(id, name)").execute()
        archivos = resultado.get('files', [])
        if archivos:
            file_id = archivos[0]['id']
            request = service.files().get_media(fileId=file_id)
            # Retorna un diccionario con todas las pestañas {nombre_hoja: dataframe}
            return pd.read_excel(io.BytesIO(request.execute()), sheet_name=None, header=None)
    except Exception as e:
        st.error(f"Error al leer {nombre}: {e}")
    return None

def limpiar_monto_contable(valor):
    if pd.isna(valor) or str(valor).strip() == '': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    # Limpieza para formatos como 1.250,50
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
        # Ignoramos hojas que sabemos que son de resumen
        if any(x in nombre_hoja.lower() for x in ['gyp', 'resumen', 'portada', 'graficos']):
            continue
        
        # BUSCADOR DE CABECERA: Buscamos en las primeras 20 filas
        idx_titulos = -1
        for i in range(min(20, len(df_raw))):
            fila = [str(x).lower().strip() for x in df_raw.iloc[i].values]
            # Buscamos las palabras clave en la fila
            if any('ingreso' in f or 'egreso' in f or 'haber' in f or 'debe' in f for f in fila):
                idx_titulos = i
                break
        
        if idx_titulos == -1:
            continue # Si no tiene encabezados de dinero, saltamos esta pestaña

        # Reconstruimos la hoja desde los títulos encontrados
        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().lower() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        df = df.loc[:, ~df.columns.duplicated()].copy()

        # Identificamos columnas de dinero
        c_ing = next((c for c in df.columns if 'ingreso' in str(c) or 'debe' in str(c)), None)
        c_egr = next((c for c in df.columns if 'egreso' in str(c) or 'haber' in str(c)), None)

        if c_ing and c_egr:
            df['ing_f'] = df[c_ing].apply(limpiar_monto_contable)
            df['egr_f'] = df[c_egr].apply(limpiar_monto_contable)
            
            # Filtramos solo filas que tengan montos reales
            df = df[(df['ing_f'] != 0) | (df['egr_f'] != 0)].copy()
            
            if not df.empty:
                if moneda == "BS":
                    df['total_bs'] = df['ing_f'] - df['egr_f']
                    df['total_usd'] = df['total_bs'] / tasa
                else:
                    df['total_usd'] = df['ing_f'] - df['egr_f']
                    df['total_bs'] = df['total_usd'] * tasa
                
                df['fuente'] = f"{nombre_hoja} ({moneda})"
                lista_final.append(df)

    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 ERP Adonai Industrial Group")

with st.sidebar:
    mes_sel = st.selectbox("Seleccione Mes:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa de Cambio:", value=45.0)
    btn_sync = st.button("🔄 Sincronizar con Drive")

if btn_sync:
    service = conectar_drive()
    if service:
        with st.spinner("Analizando archivos y pestañas dinámicas..."):
            d_bs = leer_excel_drive(service, mes_sel, "BS")
            d_usd = leer_excel_drive(service, mes_sel, "USD")
            
            res_bs = procesar_hojas(d_bs, "BS", tasa_sel) if d_bs else pd.DataFrame()
            res_usd = procesar_hojas(d_usd, "USD", tasa_sel) if d_usd else pd.DataFrame()
            
            st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)
            
            if not st.session_state.datos_acumulados.empty:
                st.success(f"¡Sincronizado! Se procesaron datos de {len(st.session_state.datos_acumulados)} movimientos.")
            else:
                st.error("No se encontraron datos. Verifique que las columnas se llamen 'Ingreso' y 'Egreso'.")

# RESULTADOS
df_final = st.session_state.datos_acumulados
if not df_final.empty:
    ing = df_final[df_final['total_usd'] > 0]['total_usd'].sum()
    egr = abs(df_final[df_final['total_usd'] < 0]['total_usd'].sum())
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos (USD)", f"$ {ing:,.2f}")
    c2.metric("Egresos (USD)", f"$ {egr:,.2f}")
    c3.metric("Balance", f"$ {ing-egr:,.2f}")
    
    st.subheader("📋 Detalle de Movimientos Detectados")
    # Intentamos mostrar columnas útiles
    cols = [c for c in ['fecha', 'descripcion', 'concepto', 'fuente', 'total_bs', 'total_usd'] if c in df_final.columns]
    st.dataframe(df_final[cols] if len(cols) > 2 else df_final, use_container_width=True)
