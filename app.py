import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Consolidado", layout="wide", page_icon="📈")

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

def procesar_hojas(dict_hojas, tipo_archivo):
    datos_lista = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        if any(x in nombre_hoja.lower() for x in ['portada', 'data', 'resumen', 'gyp']): continue
        
        idx_gyp, idx_ing, idx_egr = -1, -1, -1
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
                break
        
        if idx_gyp == -1: continue

        for i in range(header_row + 1, len(df_raw)):
            fila = df_raw.iloc[i]
            cod = str(fila.iloc[idx_gyp]).upper().strip()
            if re.match(r'^[IE]\d+$', cod):
                ing = limpiar_monto(fila.iloc[idx_ing]) if idx_ing != -1 else 0.0
                egr = limpiar_monto(fila.iloc[idx_egr]) if idx_egr != -1 else 0.0
                if ing != 0 or egr != 0:
                    datos_lista.append({'COD': cod, 'MONTO': ing - egr, 'MONEDA': tipo_archivo})
    return pd.DataFrame(datos_lista)

# --- INTERFAZ ---
st.title("🏦 Reporte de Validación G+P Consolidado")

with st.sidebar:
    mes = st.selectbox("Mes de Relación:", range(1, 13), index=10)
    tasa = st.number_input("Tasa de Cambio:", value=45.0, format="%.4f")
    if st.button("🚀 Generar Reporte", use_container_width=True):
        service = conectar_drive()
        if service:
            d_bs = leer_excel_drive(service, mes, "BS")
            d_usd = leer_excel_drive(service, mes, "USD")
            st.session_state.maestro_cuentas = obtener_nombres_cuentas(d_bs)
            df_bs = procesar_hojas(d_bs, "BS")
            df_usd = procesar_hojas(d_usd, "USD")
            st.session_state.datos_ready = pd.concat([df_bs, df_usd], ignore_index=True)

df = st.session_state.datos_ready
if not df.empty:
    # Crear Tabla Matriz
    # 1. Sumar por Código y Moneda
    matriz = df.groupby(['COD', 'MONEDA'])['MONTO'].sum().unstack(fill_value=0).reset_index()
    
    # Asegurar que existan ambas columnas aunque un archivo esté vacío
    if 'BS' not in matriz: matriz['BS'] = 0.0
    if 'USD' not in matriz: matriz['USD'] = 0.0
    
    # 2. Agregar Nombre de Cuenta
    matriz['NOMBRE DE CUENTA'] = matriz['COD'].map(st.session_state.maestro_cuentas).fillna("Otras Cuentas")
    
    # 3. Calcular Consolidado en BS
    matriz['CONSOLIDADO (BS)'] = matriz['BS'] + (matriz['USD'] * tasa)
    
    # 4. Reordenar columnas
    matriz = matriz[['COD', 'NOMBRE DE CUENTA', 'BS', 'USD', 'CONSOLIDADO (BS)']]
    
    # Separar Ingresos y Egresos
    ing = matriz[matriz['COD'].str.startswith('I')]
    egr = matriz[matriz['COD'].str.startswith('E')]

    st.markdown(f"### 🗓️ Periodo: Mes {mes} | Tasa: {tasa}")
    
    st.success("### 🟢 INGRESOS")
    st.dataframe(ing.style.format({'BS': '{:,.2f}', 'USD': '{:,.2f}', 'CONSOLIDADO (BS)': '{:,.2f}'}), use_container_width=True)
    
    st.error("### 🔴 EGRESOS")
    st.dataframe(egr.style.format({'BS': '{:,.2f}', 'USD': '{:,.2f}', 'CONSOLIDADO (BS)': '{:,.2f}'}), use_container_width=True)

    # Totales Finales
    tot_bs = matriz['CONSOLIDADO (BS)'].sum()
    c1, c2 = st.columns(2)
    c1.metric("UTILIDAD NETA (BS)", f"Bs. {tot_bs:,.2f}")
    c2.metric("UTILIDAD NETA (USD)", f"$ {tot_bs/tasa:,.2f}")
else:
    st.info("💡 Configure los parámetros y presione Generar Reporte.")
