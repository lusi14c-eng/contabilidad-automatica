import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Final", layout="wide", page_icon="📈")

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
    texto = str(valor).upper().replace('BS', '').replace('$', '').replace(' ', '')
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
        col_gyp_idx = -1
        
        # 1. Localizar GYP por contenido de celda
        for i in range(min(50, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            for idx, celda in enumerate(fila):
                if 'GYP' in celda:
                    idx_titulos = i
                    col_gyp_idx = idx
                    break
            if idx_titulos != -1: break
        
        if idx_titulos == -1: continue

        df = df_raw.iloc[idx_titulos:].copy()
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        
        # 2. Identificar columnas de montos e ignorar las que no sirven
        c_ing = next((c for c in df.columns if 'INGRESOS' in str(c)), None)
        c_egr = next((c for c in df.columns if 'EGRESOS' in str(c)), None)
        c_gyp_name = df.columns[col_gyp_idx]
        
        # Buscamos dinámicamente cualquier columna que parezca descripción
        c_desc = next((c for c in df.columns if any(k in str(c) for k in ['DESC', 'CONCEPTO', 'DETALLE'])), None)

        if c_ing and c_egr:
            df['I_N'] = df[c_ing].apply(limpiar_monto)
            df['E_N'] = df[c_egr].apply(limpiar_monto)
            
            # Filtro base: GYP con datos y hay dinero moviéndose
            mask = (df[c_gyp_name].notna()) & \
                   (df[c_gyp_name].astype(str).str.strip() != '') & \
                   ((df['I_N'] != 0) | (df['E_N'] != 0))
            
            # Filtro de seguridad por descripción (solo si existe)
            if c_desc:
                mask = mask & (~df[c_desc].astype(str).upper().str.contains('TOTAL|SALDO|VAN|VIENEN', na=False))

            df_valido = df[mask].copy()

            if not df_valido.empty:
                df_valido['CUENTA'] = df_valido[c_gyp_name].astype(str).str.strip()
                df_valido['MONEDA'] = moneda
                lista_final.append(df_valido[['CUENTA', 'MONEDA', 'I_N', 'E_N']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("📊 G+P Consolidado - Adonai Industrial")

with st.sidebar:
    st.header("Sincronización")
    mes_sel = st.selectbox("Mes de la relación:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa BCV ($/Bs):", value=45.0, format="%.4f")
    if st.button("🔄 Generar Ganancia y Pérdida", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Analizando códigos GYP y consolidando monedas..."):
                d_bs = leer_excel_drive(service, mes_sel, "BS")
                d_usd = leer_excel_drive(service, mes_sel, "USD")
                
                res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
                res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
                
                st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)

df = st.session_state.datos_acumulados
if not df.empty:
    # --- PROCESAMIENTO G+P ---
    def calcular_gp(row):
        neto = row['I_N'] - row['E_N']
        if row['MONEDA'] == 'BS':
            return pd.Series([neto, neto / tasa_sel], index=['NETO_BS', 'NETO_USD'])
        else:
            return pd.Series([neto * tasa_sel, neto], index=['NETO_BS', 'NETO_USD'])

    df_gp = df.copy()
    df_gp[['B_BS', 'B_USD']] = df_gp.apply(calcular_gp, axis=1)
    
    # Agrupación final por código GYP
    gp_final = df_gp.groupby('CUENTA').agg({'B_BS': 'sum', 'B_USD': 'sum'}).reset_index()
    
    # Métricas
    t_bs = gp_final['B_BS'].sum()
    t_usd = gp_final['B_USD'].sum()
    
    c1, c2 = st.columns(2)
    c1.metric("RESULTADO NETO (BS)", f"Bs. {t_bs:,.2f}")
    c2.metric("RESULTADO NETO (USD)", f"$ {t_usd:,.2f}")

    st.subheader("📋 Estado de Ganancias y Pérdidas por Código")
    st.dataframe(gp_final.style.format({'B_BS': '{:,.2f}', 'B_USD': '{:,.2f}'}), use_container_width=True)
else:
    st.info("💡 Use la barra lateral para generar el reporte.")
