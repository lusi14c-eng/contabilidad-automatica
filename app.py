import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Final", layout="wide", page_icon="🏦")

if 'datos_ready' not in st.session_state:
    st.session_state.datos_ready = pd.DataFrame()

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

def procesar_hojas(dict_hojas, tipo_archivo, tasa):
    datos_lista = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        if any(x in nombre_hoja.lower() for x in ['portada', 'data', 'resumen', 'gyp']): continue
        
        idx_gyp = -1
        idx_ing = -1
        idx_egr = -1
        idx_desc = -1
        start_row = 0

        for i in range(min(25, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            for idx, cell in enumerate(fila):
                if cell in ['GYP', 'CÓDIGO', 'CODIGO', 'COD.']: idx_gyp = idx
                if 'DESC' in cell or 'CONCEPTO' in cell: idx_desc = idx
                if 'INGRESOS' in cell:
                    if tipo_archivo == "BS" and "USD" not in cell: idx_ing = idx
                    if tipo_archivo == "USD" and "USD" in cell: idx_ing = idx
                if 'EGRESOS' in cell:
                    if tipo_archivo == "BS" and "USD" not in cell: idx_egr = idx
                    if tipo_archivo == "USD" and "USD" in cell: idx_egr = idx
            if idx_gyp != -1 and idx_ing != -1:
                start_row = i + 1
                break

        if idx_gyp == -1:
            for col_test in range(min(5, df_raw.shape[1])):
                sample = df_raw.iloc[:, col_test].astype(str).str.contains(r'^[IE]\d+', regex=True).sum()
                if sample > 0:
                    idx_gyp = col_test
                    break

        if idx_gyp != -1:
            for i in range(start_row, len(df_raw)):
                fila_actual = df_raw.iloc[i]
                # LIMPIEZA AGRESIVA DEL CÓDIGO
                raw_cod = str(fila_actual.iloc[idx_gyp]).upper().strip()
                # Extraer solo el patrón I001 aunque tenga basura alrededor
                match = re.search(r'([IE]\d+)', raw_cod)
                
                if match:
                    cod = match.group(1)
                    ing = limpiar_monto(fila_actual.iloc[idx_ing]) if idx_ing != -1 else 0.0
                    egr = limpiar_monto(fila_actual.iloc[idx_egr]) if idx_egr != -1 else 0.0
                    
                    if ing != 0 or egr != 0:
                        desc = str(fila_actual.iloc[idx_desc]) if idx_desc != -1 else "Sin desc."
                        datos_lista.append({
                            'CUENTA': cod, 
                            'I_VAL': ing,
                            'E_VAL': egr,
                            'DETALLE': desc.strip(),
                            'HOJA': nombre_hoja,
                            'ORIGEN': tipo_archivo
                        })

    return pd.DataFrame(datos_lista)

# --- INTERFAZ ---
st.title("📊 Consolidación G+P - Adonai Industrial")

with st.sidebar:
    mes = st.selectbox("Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa BCV:", value=45.0, format="%.4f")
    
    if st.button("🔄 Sincronizar Todo", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Limpiando y consolidando datos..."):
                d_bs = leer_excel_drive(service, mes, "BS")
                d_usd = leer_excel_drive(service, mes, "USD")
                df_bs = procesar_hojas(d_bs, "BS", tasa)
                df_usd = procesar_hojas(d_usd, "USD", tasa)
                st.session_state.datos_ready = pd.concat([df_bs, df_usd], ignore_index=True)

res = st.session_state.datos_ready

if not res.empty:
    # Asegurar que CUENTA sea texto limpio antes de agrupar
    res['CUENTA'] = res['CUENTA'].astype(str).str.strip()
    
    res['NETO_BS'] = res.apply(lambda r: round(r['I_VAL'] - r['E_VAL'], 2) if r['ORIGEN'] == "BS" else round((r['I_VAL'] - r['E_VAL']) * tasa, 2), axis=1)
    
    # AGRUPACIÓN DEFINITIVA
    gp_final = res.groupby('CUENTA')['NETO_BS'].sum().reset_index()
    gp_final['NETO_USD'] = (gp_final['NETO_BS'] / tasa).round(2)
    
    st.metric("G+P TOTAL (BS)", f"Bs. {gp_final['NETO_BS'].sum():,.2f}")
    
    st.subheader("📋 Resumen Consolidado")
    st.dataframe(gp_final.style.format({'NETO_BS': '{:,.2f}', 'NETO_USD': '{:,.2f}'}), use_container_width=True)

    st.markdown("---")
    st.subheader("🔍 Auditoría de Movimientos")
    cod_auditoria = st.text_input("Código a revisar:", value="I001").upper().strip()
    
    if cod_auditoria:
        detalle = res[res['CUENTA'] == cod_auditoria]
        if not detalle.empty:
            st.write(f"Desglose para **{cod_auditoria}**:")
            # Esta tabla mostrará si hay líneas separadas todavía
            st.table(detalle[['HOJA', 'ORIGEN', 'DETALLE', 'I_VAL', 'E_VAL', 'NETO_BS']])
            
            # Cálculo manual en vivo para comparar
            total_origen = detalle['I_VAL'].sum() - detalle['E_VAL'].sum()
            st.success(f"**SUMA TOTAL DEL CÓDIGO {cod_auditoria}:** {total_origen:,.2f} (en moneda origen)")
        else:
            st.warning("No se encontró el código.")
else:
    st.info("💡 Sincronice para analizar los archivos.")
