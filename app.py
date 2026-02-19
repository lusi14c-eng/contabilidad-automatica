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

def procesar_hojas(dict_hojas, moneda_archivo, tasa):
    lista_final = []
    if not dict_hojas: return pd.DataFrame()

    for nombre_hoja, df_raw in dict_hojas.items():
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'resumen', 'gyp']): continue
        
        # 1. Localizar cabecera
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
        
        # 2. SELECCIÓN ESTRICTA DE COLUMNAS (Filtro Anti-interferencia)
        # Si moneda_archivo es 'BS', buscamos 'INGRESOS BS' y RECHAZAMOS 'USD'
        # Si moneda_archivo es 'USD', buscamos 'INGRESOS USD'
        def buscar_col(tipo, moneda_target):
            for c in df.columns:
                if tipo in str(c) and moneda_target in str(c):
                    return c
            # Si no hay match exacto, buscamos el tipo pero que NO tenga la moneda contraria
            contraria = 'USD' if moneda_target == 'BS' else 'BS'
            for c in df.columns:
                if tipo in str(c) and contraria not in str(c):
                    return c
            return None

        c_ing = buscar_col('INGRESOS', moneda_archivo)
        c_egr = buscar_col('EGRESOS', moneda_archivo)
        c_gyp = next((c for c in df.columns if 'GYP' in str(c)), None)
        c_desc = next((c for c in df.columns if any(k in str(c) for k in ['DESC', 'CONCEPTO'])), None)

        if c_ing and c_egr and c_gyp:
            df['I_N'] = df[c_ing].apply(limpiar_monto)
            df['E_N'] = df[c_egr].apply(limpiar_monto)
            
            # Máscara de datos válidos
            mask = (df[c_gyp].notna()) & (df[c_gyp].astype(str).str.strip() != '') & ((df['I_N'] != 0) | (df['E_N'] != 0))
            
            # Filtro de texto seguro (sin AttributeError)
            if c_desc and c_desc in df.columns:
                try:
                    desc_mask = ~df[c_desc].astype(str).upper().str.contains('TOTAL|SALDO|VAN|VIENEN', na=False)
                    mask = mask & desc_mask
                except: pass

            df_valido = df[mask].copy()
            if not df_valido.empty:
                df_valido['CUENTA'] = df_valido[c_gyp].astype(str).str.strip()
                df_valido['MONEDA_ORIGEN'] = moneda_archivo
                lista_final.append(df_valido[['CUENTA', 'MONEDA_ORIGEN', 'I_N', 'E_N']])
    
    return pd.concat(lista_final, ignore_index=True) if lista_final else pd.DataFrame()

# INTERFAZ
st.title("🏦 Ganancias y Pérdidas - Consolidado")

with st.sidebar:
    st.header("Sincronización")
    mes_sel = st.selectbox("Mes de Relación:", range(1, 13), index=10)
    tasa_sel = st.number_input("Tasa BCV del Mes:", value=45.0, format="%.4f")
    if st.button("🔄 Generar G+P Real", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Procesando datos..."):
                d_bs = leer_excel_drive(service, mes_sel, "BS")
                d_usd = leer_excel_drive(service, mes_sel, "USD")
                
                res_bs = procesar_hojas(d_bs, "BS", tasa_sel)
                res_usd = procesar_hojas(d_usd, "USD", tasa_sel)
                
                st.session_state.datos_acumulados = pd.concat([res_bs, res_usd], ignore_index=True)

# CÁLCULOS G+P
df = st.session_state.datos_acumulados
if not df.empty:
    # 1. Convertir todo a una base de Bolívares
    def calcular_gp(row):
        neto = row['I_N'] - row['E_N']
        return neto if row['MONEDA_ORIGEN'] == 'BS' else neto * tasa_sel

    df['VALOR_BS'] = df.apply(calcular_gp, axis=1)
    
    # 2. Agrupar por cuenta GYP
    gp_tabla = df.groupby('CUENTA')['VALOR_BS'].sum().reset_index()
    
    # 3. Conversión final a USD para el total del mes
    gp_tabla['VALOR_USD'] = gp_tabla['VALOR_BS'] / tasa_sel
    
    # Visualización
    t_bs = gp_tabla['VALOR_BS'].sum()
    t_usd = gp_tabla['VALOR_USD'].sum()

    st.markdown("---")
    col1, col2 = st.columns(2)
    col1.metric("G+P TOTAL (BS)", f"Bs. {t_bs:,.2f}")
    col2.metric("G+P TOTAL (USD)", f"$ {t_usd:,.2f}")

    st.subheader("📋 Resumen por Código de Cuenta")
    st.dataframe(
        gp_tabla.style.format({'VALOR_BS': '{:,.2f}', 'VALOR_USD': '{:,.2f}'}),
        use_container_width=True
    )
else:
    st.info("💡 Pendiente de sincronización.")
