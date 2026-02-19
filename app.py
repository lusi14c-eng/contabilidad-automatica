import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Final", layout="wide", page_icon="🏦")

# Inicializar estado
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
        # Ignorar hojas que no son de movimientos
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'resumen', 'gyp']): continue
        
        # 1. Encontrar la cabecera 'GYP'
        idx_titulos = -1
        for i in range(min(60, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if 'GYP' in fila:
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        # 2. Preparar el DataFrame de la hoja
        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        # 3. Identificar columnas (EVITAR INTERFERENCIA USD en archivos BS)
        # Buscamos la columna GYP real
        c_gyp = next((c for c in df.columns if 'GYP' == str(c)), None)
        if not c_gyp: c_gyp = next((c for c in df.columns if 'GYP' in str(c)), None)

        c_ing = None
        c_egr = None
        
        # Lógica de exclusión estricta
        for col in df.columns:
            c_str = str(col).upper()
            if 'INGRESOS' in c_str:
                if tipo_archivo == "BS" and "USD" not in c_str: c_ing = col
                if tipo_archivo == "USD" and "USD" in c_str: c_ing = col
            if 'EGRESOS' in c_str:
                if tipo_archivo == "BS" and "USD" not in c_str: c_egr = col
                if tipo_archivo == "USD" and "USD" in c_str: c_egr = col

        # Columna de descripción (tomamos solo la primera si hay varias)
        c_desc_list = [c for c in df.columns if any(k in str(c) for k in ['DESC', 'CONCEPTO'])]
        c_desc = c_desc_list[0] if c_desc_list else None

        if c_ing and c_egr and c_gyp:
            # Creamos una copia limpia para trabajar
            temp_df = pd.DataFrame()
            temp_df['CUENTA'] = df[c_gyp].astype(str).str.strip()
            temp_df['I_VAL'] = df[c_ing].apply(limpiar_monto)
            temp_df['E_VAL'] = df[c_egr].apply(limpiar_monto)
            temp_df['DETALLE'] = df[c_desc].astype(str) if c_desc else "Sin descripción"
            temp_df['HOJA'] = nombre_hoja
            temp_df['ORIGEN'] = tipo_archivo

            # FILTRO: Solo si hay cuenta GYP y hubo movimiento de dinero
            mask = (temp_df['CUENTA'] != 'NAN') & (temp_df['CUENTA'] != '') & \
                   ((temp_df['I_VAL'] != 0) | (temp_df['E_VAL'] != 0))
            
            datos_lista.append(temp_df[mask])

    return pd.concat(datos_lista, ignore_index=True) if datos_lista else pd.DataFrame()

# --- INTERFAZ STREAMLIT ---
st.title("📊 G+P Consolidado Preciso")

with st.sidebar:
    st.header("Configuración")
    mes = st.selectbox("Mes de Relación:", range(1, 13), index=10)
    tasa = st.number_input("Tasa BCV oficial:", value=45.0, format="%.4f")
    
    if st.button("🚀 Generar Reporte", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Procesando datos de Drive..."):
                d_bs = leer_excel_drive(service, mes, "BS")
                d_usd = leer_excel_drive(service, mes, "USD")
                
                df_bs = procesar_hojas(d_bs, "BS", tasa)
                df_usd = procesar_hojas(d_usd, "USD", tasa)
                
                st.session_state.datos_ready = pd.concat([df_bs, df_usd], ignore_index=True)

# --- PRESENTACIÓN DE RESULTADOS ---
res = st.session_state.datos_ready

if not res.empty:
    # Cálculo de valores netos en BS
    def calcular_neto_bs(row):
        n = row['I_VAL'] - row['E_VAL']
        return round(n, 2) if row['ORIGEN'] == "BS" else round(n * tasa, 2)

    res['NETO_BS'] = res.apply(calcular_neto_bs, axis=1)
    
    # Tabla G+P Agrupada
    gp_final = res.groupby('CUENTA')['NETO_BS'].sum().reset_index()
    gp_final['NETO_USD'] = (gp_final['NETO_BS'] / tasa).round(2)
    
    # Métricas principales
    c1, c2 = st.columns(2)
    c1.metric("UTILIDAD/PÉRDIDA (BS)", f"Bs. {gp_final['NETO_BS'].sum():,.2f}")
    c2.metric("UTILIDAD/PÉRDIDA (USD)", f"$ {gp_final['NETO_USD'].sum():,.2f}")

    st.subheader("📋 Estado de Resultados por Código")
    st.dataframe(gp_final.style.format({'NETO_BS': '{:,.2f}', 'NETO_USD': '{:,.2f}'}), use_container_width=True)

    # AUDITORÍA (Para revisar el caso I001)
    st.markdown("---")
    st.subheader("🔍 Auditoría de Movimientos")
    cod_auditoria = st.text_input("Código a auditar (ej: I001):", value="I001")
    
    if cod_auditoria:
        detalle = res[res['CUENTA'] == cod_auditoria]
        if not detalle.empty:
            st.write(f"Movimientos detectados para **{cod_auditoria}**:")
            st.dataframe(detalle[['HOJA', 'ORIGEN', 'DETALLE', 'I_VAL', 'E_VAL', 'NETO_BS']])
            suma_origen = detalle['I_VAL'].sum() - detalle['E_VAL'].sum()
            st.info(f"Suma en moneda original: {suma_origen:,.2f}")
        else:
            st.warning("No se encontró ese código en los registros.")

else:
    st.info("💡 Presione el botón en la barra lateral para procesar la información.")
