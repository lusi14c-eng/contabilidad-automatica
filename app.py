import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Real", layout="wide", page_icon="📈")

# Estilo para reporte contable
st.markdown("""
    <style>
    .report-font { font-family: 'Courier New', Courier, monospace; }
    .metric-container { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; }
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
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'resumen']): continue
        
        idx_titulos = -1
        for i in range(min(50, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if 'GYP' in fila:
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        c_gyp = 'GYP'
        c_ing = next((c for c in df.columns if 'INGRESOS' in c), None)
        c_egr = next((c for c in df.columns if 'EGRESOS' in c), None)
        c_desc = next((c for c in df.columns if 'DESCRIPCION' in c or 'CONCEPTO' in c), None)

        if c_gyp in df.columns and c_ing and c_egr:
            df['ING_NUM'] = df[c_ing].apply(limpiar_monto)
            df['EGR_NUM'] = df[c_egr].apply(limpiar_monto)
            
            # Filtro para evitar filas de totales de Excel y basura
            mask = (df[c_gyp].notna()) & (df[c_gyp].astype(str).str.strip() != '') & \
                   ((df['ING_NUM'] != 0) | (df['EGR_NUM'] != 0))
            
            if c_desc:
                mask = mask & (~df[c_desc].astype(str).upper().str.contains('TOTAL|SALDO|VAN|VIENEN', na=False))

            df_valido = df[mask].copy()
            
            if not df_valido.empty:
                # Todo se procesa primero en su moneda de origen
                df_valido['CUENTA'] = df_valido[c_gyp].astype(str).str.strip()
                df_valido['MONEDA_ORIGEN'] = moneda
                lista_final.append(df_valido[['CUENTA', 'MONEDA_ORIGEN', 'ING_NUM', 'EGR_NUM']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ PRINCIPAL
st.title("🏦 Estado de Ganancias y Pérdidas (G+P)")
st.subheader("Adonai Group Industrial - Consolidado Mensual")

with st.sidebar:
    st.header("⚙️ Parámetros")
    mes_sel = st.selectbox("Mes de Análisis:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa de Conversión (Bs/$):", value=45.0, format="%.4f")
    if st.button("🚀 Generar Reporte G+P", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Calculando saldos y conversiones..."):
                d_bs = leer_excel_drive(service, mes_sel, "BS")
                d_usd = leer_excel_drive(service, mes_sel, "USD")
                
                res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
                res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
                
                st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)

df = st.session_state.datos_acumulados
if not df.empty:
    # --- LÓGICA DE G+P ---
    # 1. Agrupar por cuenta y moneda de origen
    gyp_raw = df.groupby(['CUENTA', 'MONEDA_ORIGEN']).agg({'ING_NUM': 'sum', 'EGR_NUM': 'sum'}).reset_index()
    
    # 2. Calcular montos normalizados
    # Si viene de BS -> Se muestra en BS y se convierte a USD
    # Si viene de USD -> Se muestra en USD y se convierte a BS
    def normalizar(row):
        ing = row['ING_NUM']
        egr = row['EGR_NUM']
        neto = ing - egr
        if row['MONEDA_ORIGEN'] == 'BS':
            return pd.Series([neto, neto / tasa_sel], index=['NETO_BS', 'NETO_USD'])
        else:
            return pd.Series([neto * tasa_sel, neto], index=['NETO_BS', 'NETO_USD'])

    gyp_final = gyp_raw.join(gyp_raw.apply(normalizar, axis=1))
    
    # 3. Agrupación Final por Código GYP (Consolidando BS y USD)
    gp_consolidado = gyp_final.groupby('CUENTA').agg({
        'NETO_BS': 'sum',
        'NETO_USD': 'sum'
    }).reset_index()

    # --- VISUALIZACIÓN ---
    total_bs = gp_consolidado['NETO_BS'].sum()
    total_usd = gp_consolidado['NETO_USD'].sum()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("GANANCIA/PÉRDIDA TOTAL (BS)", f"Bs. {total_bs:,.2f}")
    with col2:
        st.metric("GANANCIA/PÉRDIDA TOTAL (USD)", f"$ {total_usd:,.2f}", delta=f"Tasa: {tasa_sel}")

    st.markdown("### 📋 Detalle de Cuentas GYP")
    
    # Formatear la tabla para que parezca un reporte
    def resaltar_resultado(val):
        color = 'red' if val < 0 else 'green'
        return f'color: {color}'

    st.dataframe(
        gp_consolidado.style.format({
            'NETO_BS': '{:,.2f}',
            'NETO_USD': '{:,.2f}'
        }).applymap(resaltar_resultado, subset=['NETO_BS', 'NETO_USD']),
        use_container_width=True
    )

    # --- EXPORTAR ---
    csv = gp_consolidado.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar Reporte G+P (CSV)", csv, f"GP_Adonai_Mes_{mes_sel}.csv", "text/csv")
else:
    st.info("Haga clic en 'Generar Reporte G+P' para consolidar la información de las cuentas.")
