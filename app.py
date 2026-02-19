import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Auditoría", layout="wide", page_icon="📈")

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
    if isinstance(valor, (int, float)): return round(float(valor), 2)
    texto = str(valor).upper().replace('BS', '').replace('$', '').replace(' ', '')
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'): texto = texto.replace('.', '').replace(',', '.')
        else: texto = texto.replace(',', '')
    elif ',' in texto: texto = texto.replace(',', '.')
    texto = re.sub(r'[^0-9.-]', '', texto)
    try: return round(float(texto), 2)
    except: return 0.0

def procesar_hojas(dict_hojas, moneda_archivo, tasa):
    lista_final = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'resumen']): continue
        
        idx_titulos = -1
        for i in range(min(60, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if 'GYP' in fila:
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        # BUSCADOR QUIRÚRGICO DE COLUMNAS
        # Si moneda_archivo es 'BS', buscamos 'INGRESOS BS' y prohibimos 'USD'
        # Si moneda_archivo es 'USD', buscamos 'INGRESOS USD'
        c_ing = None
        c_egr = None
        for col in df.columns:
            c_str = str(col).upper()
            if 'INGRESOS' in c_str:
                if moneda_archivo == 'BS' and 'USD' not in c_str: c_ing = col
                if moneda_archivo == 'USD' and 'USD' in c_str: c_ing = col
            if 'EGRESOS' in c_str:
                if moneda_archivo == 'BS' and 'USD' not in c_str: c_egr = col
                if moneda_archivo == 'USD' and 'USD' in c_str: c_egr = col

        c_gyp = next((c for c in df.columns if 'GYP' in str(c)), None)
        c_desc = next((c for c in df.columns if any(k in str(c) for k in ['DESC', 'CONCEPTO'])), 'DESCRIPCION')

        if c_ing and c_egr and c_gyp:
            df['I_N'] = df[c_ing].apply(limpiar_monto)
            df['E_N'] = df[c_egr].apply(limpiar_monto)
            
            # FILTRO: Si tiene Código GYP y tiene montos, VA PARA ADENTRO.
            # Eliminamos el filtro de texto 'TOTAL' porque nos hacía perder datos reales.
            mask = (df[c_gyp].notna()) & (df[c_gyp].astype(str).str.strip() != '') & ((df['I_N'] != 0) | (df['E_N'] != 0))
            
            df_valido = df[mask].copy()
            if not df_valido.empty:
                df_valido['CUENTA'] = df_valido[c_gyp].astype(str).str.strip()
                df_valido['MONEDA_ORIGEN'] = moneda_archivo
                df_valido['HOJA'] = nombre_hoja
                # Guardamos la descripción para auditoría
                df_valido['DETALLE'] = df_valido[c_desc] if c_desc in df_valido.columns else "Sin desc."
                lista_final.append(df_valido[['CUENTA', 'MONEDA_ORIGEN', 'HOJA', 'DETALLE', 'I_N', 'E_N']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 Auditoría de Resultados - Adonai")

with st.sidebar:
    mes_sel = st.selectbox("Mes:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa BCV:", value=45.0, format="%.4f")
    if st.button("🔄 Ejecutar Consolidación"):
        service = conectar_drive()
        if service:
            with st.spinner("Calculando con precisión..."):
                d_bs = leer_excel_drive(service, mes_sel, "BS")
                d_usd = leer_excel_drive(service, mes_sel, "USD")
                res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
                res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
                st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)

df = st.session_state.datos_acumulados
if not df.empty:
    # Cálculo de G+P con redondeo forzado
    def calcular_gp(row):
        neto = round(row['I_N'] - row['E_N'], 2)
        return neto if row['MONEDA_ORIGEN'] == 'BS' else round(neto * tasa_sel, 2)

    df['VALOR_BS'] = df.apply(calcular_gp, axis=1)
    gp_tabla = df.groupby('CUENTA')['VALOR_BS'].sum().round(2).reset_index()
    gp_tabla['VALOR_USD'] = (gp_tabla['VALOR_BS'] / tasa_sel).round(2)

    c1, c2 = st.columns(2)
    c1.metric("G+P TOTAL (BS)", f"Bs. {gp_tabla['VALOR_BS'].sum():,.2f}")
    c2.metric("G+P TOTAL (USD)", f"$ {gp_tabla['VALOR_USD'].sum():,.2f}")

    st.subheader("📋 Resumen G+P")
    st.dataframe(gp_tabla, use_container_width=True)

    # SECCIÓN DE AUDITORÍA PARA EL USUARIO
    st.markdown("---")
    st.subheader("🔍 Buscador de Auditoría")
    codigo_buscar = st.text_input("Ingresa un código para ver sus filas (ej. I001):", value="I001")
    
    if codigo_buscar:
        detalle_codigo = df[df['CUENTA'] == codigo_buscar]
        if not detalle_codigo.empty:
            st.write(f"Filas detectadas para el código **{codigo_buscar}**:")
            st.dataframe(detalle_codigo)
            st.info(f"Suma total en moneda origen para este código: {detalle_codigo['I_N'].sum() - detalle_codigo['E_N'].sum():,.2f}")
        else:
            st.warning("No se encontraron filas con ese código.")
else:
    st.info("💡 Sincronice para ver resultados.")
