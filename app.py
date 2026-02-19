import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Final", layout="wide", page_icon="📈")

# Inicialización de estados
if 'datos_ready' not in st.session_state:
    st.session_state.datos_ready = pd.DataFrame()
if 'maestro_cuentas' not in st.session_state:
    st.session_state.maestro_cuentas = {}

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

def obtener_nombres_cuentas(dict_hojas):
    maestro = {}
    if not dict_hojas or 'GYP' not in dict_hojas: return maestro
    df_gyp = dict_hojas['GYP']
    for i in range(len(df_gyp)):
        fila = df_gyp.iloc[i].astype(str).tolist()
        for idx, celda in enumerate(fila):
            celda_clean = celda.strip().upper()
            if re.match(r'^[IE]\d+', celda_clean):
                codigo = celda_clean
                nombre = fila[idx+1].strip() if idx + 1 < len(fila) else "Sin Nombre"
                if nombre.upper() == 'NAN': nombre = "Cuenta sin descripción"
                maestro[codigo] = nombre
    return maestro

def limpiar_monto(valor):
    if pd.isna(valor) or str(valor).strip() == '' or str(valor).strip().upper() == 'NAN': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).upper().replace('BS', '').replace('$', '').replace(' ', '')
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'): texto = texto.replace('.', '').replace(',', '.')
        else: texto = texto.replace(',', '')
    elif ',' in texto: texto = texto.replace(',', '.')
    texto = re.sub(r'[^0-9.-]', '', texto)
    try: return float(texto)
    except: return 0.0

def procesar_hojas(dict_hojas, tipo_archivo, tasa):
    datos_lista = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        if any(x in nombre_hoja.lower() for x in ['portada', 'data', 'resumen', 'gyp']): continue
        
        idx_gyp, idx_ing, idx_egr, idx_desc = -1, -1, -1, -1
        header_row = -1

        for i in range(min(40, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if any(k in fila for k in ['GYP', 'CÓDIGO', 'CODIGO']):
                header_row = i
                for idx, t in enumerate(fila):
                    if t in ['GYP', 'CÓDIGO', 'CODIGO']: idx_gyp = idx
                    if 'INGRESOS' in t:
                        if tipo_archivo == "BS" and "USD" not in t: idx_ing = idx
                        if tipo_archivo == "USD" and "USD" in t: idx_ing = idx
                    if 'EGRESOS' in t:
                        if tipo_archivo == "BS" and "USD" not in t: idx_egr = idx
                        if tipo_archivo == "USD" and "USD" in t: idx_egr = idx
                    if 'DESC' in t or 'CONCEPTO' in t: idx_desc = idx
                break
        
        if idx_gyp == -1: continue

        for i in range(header_row + 1, len(df_raw)):
            fila = df_raw.iloc[i]
            cod = str(fila.iloc[idx_gyp]).upper().strip()
            
            # FILTRO ANTI-DUPLICADOS: Solo códigos puros (evita filas de Totales)
            if re.match(r'^[IE]\d+$', cod):
                desc_text = str(fila.iloc[idx_desc]).upper() if idx_desc != -1 else ""
                
                # Si la descripción dice TOTAL, saltamos para no duplicar el I002
                if any(x in desc_text for x in ['TOTAL', 'SUBTOTAL', 'VAN', 'VIENEN']): continue
                
                ing = limpiar_monto(fila.iloc[idx_ing]) if idx_ing != -1 else 0.0
                egr = limpiar_monto(fila.iloc[idx_egr]) if idx_egr != -1 else 0.0
                
                if ing != 0 or egr != 0:
                    datos_lista.append({
                        'COD': cod, 'I': ing, 'E': egr, 'MONEDA': tipo_archivo,
                        'HOJA': nombre_hoja, 'DETALLE': desc_text
                    })

    return pd.DataFrame(datos_lista)

# --- UI ---
st.title("🏦 Estado de Resultados Consolidado")

with st.sidebar:
    mes = st.selectbox("Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa BCV:", value=45.0, format="%.4f")
    
    if st.button("🚀 Generar G+P", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Sincronizando..."):
                d_bs = leer_excel_drive(service, mes, "BS")
                d_usd = leer_excel_drive(service, mes, "USD")
                
                st.session_state.maestro_cuentas = obtener_nombres_cuentas(d_bs)
                
                df1 = procesar_hojas(d_bs, "BS", tasa)
                df2 = procesar_hojas(d_usd, "USD", tasa)
                
                st.session_state.datos_ready = pd.concat([df1, df2], ignore_index=True)

df = st.session_state.datos_ready

if not df.empty and 'MONEDA' in df.columns:
    # Cálculo de Netos
    df['NETO_BS'] = df.apply(lambda r: round(r['I'] - r['E'], 2) if r['MONEDA'] == "BS" 
                            else round((r['I'] - r['E']) * tasa, 2), axis=1)
    
    # Agrupación y Nombres
    gp = df.groupby('COD')['NETO_BS'].sum().reset_index()
    gp['CUENTA'] = gp['COD'].map(st.session_state.maestro_cuentas).fillna("Otras Cuentas")
    gp['NETO_USD'] = (gp['NETO_BS'] / tasa).round(2)
    
    # Mostrar Resultados
    st.metric("UTILIDAD NETA (BS)", f"Bs. {gp['NETO_BS'].sum():,.2f}")
    
    col_i, col_e = st.columns(2)
    with col_i:
        st.success("### 🟢 INGRESOS")
        st.dataframe(gp[gp['COD'].str.startswith('I')][['COD', 'CUENTA', 'NETO_BS']], use_container_width=True)
    with col_e:
        st.error("### 🔴 EGRESOS")
        st.dataframe(gp[gp['COD'].str.startswith('E')][['COD', 'CUENTA', 'NETO_BS']], use_container_width=True)

    # Auditoría I002
    with st.expander("🔍 Auditoría I002"):
        st.write(df[df['COD'] == 'I002'])
else:
    st.info("💡 Sincronice para ver el G+P.")
