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
        if any(x in nombre_hoja.lower() for x in ['data', 'portada', 'resumen', 'gyp']): continue
        
        # 1. Encontrar la fila de cabecera 'GYP'
        idx_titulos = -1
        for i in range(min(60, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if 'GYP' in fila:
                idx_titulos = i
                break
        
        if idx_titulos == -1: continue

        # 2. Extraer datos y limpiar nombres de columnas para detección
        titulos = [str(t).upper().strip() for t in df_raw.iloc[idx_titulos].values]
        df_datos = df_raw.iloc[idx_titulos+1:].reset_index(drop=True)
        
        # 3. Mapeo de índices de columnas (Para evitar ValueError por nombres duplicados)
        idx_gyp = -1
        idx_ing = -1
        idx_egr = -1
        idx_desc = -1

        for idx, t in enumerate(titulos):
            if 'GYP' == t or 'COD' in t: idx_gyp = idx
            if 'DESC' in t or 'CONCEPTO' in t: 
                if idx_desc == -1: idx_desc = idx # Solo el primero
            
            # Lógica de exclusión de moneda (USD no entra en archivo BS)
            if 'INGRESOS' in t:
                if tipo_archivo == "BS" and "USD" not in t: idx_ing = idx
                if tipo_archivo == "USD" and "USD" in t: idx_ing = idx
            if 'EGRESOS' in t:
                if tipo_archivo == "BS" and "USD" not in t: idx_egr = idx
                if tipo_archivo == "USD" and "USD" in t: idx_egr = idx

        if idx_gyp != -1 and idx_ing != -1 and idx_egr != -1:
            # Construcción manual fila por fila para evitar errores de alineación
            for _, row in df_datos.iterrows():
                cod_gyp = str(row.iloc[idx_gyp]).strip()
                # Solo procesar si hay un código GYP válido
                if cod_gyp and cod_gyp != 'nan' and cod_gyp != 'None':
                    ing = limpiar_monto(row.iloc[idx_ing])
                    egr = limpiar_monto(row.iloc[idx_egr])
                    
                    if ing != 0 or egr != 0:
                        desc = str(row.iloc[idx_desc]) if idx_desc != -1 else "Sin descripción"
                        datos_lista.append({
                            'CUENTA': cod_gyp,
                            'I_VAL': ing,
                            'E_VAL': egr,
                            'DETALLE': desc,
                            'HOJA': nombre_hoja,
                            'ORIGEN': tipo_archivo
                        })

    return pd.DataFrame(datos_lista)

# --- INTERFAZ ---
st.title("📊 G+P Real Consolidado - Adonai Industrial")

with st.sidebar:
    st.header("Sincronización de Datos")
    mes = st.selectbox("Mes de Relación:", range(1, 13), index=10)
    tasa = st.number_input("Tasa BCV ($/Bs):", value=45.0, format="%.4f")
    
    if st.button("🔄 Generar Reporte Final", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Analizando archivos en Drive..."):
                d_bs = leer_excel_drive(service, mes, "BS")
                d_usd = leer_excel_drive(service, mes, "USD")
                
                df_bs = procesar_hojas(d_bs, "BS", tasa)
                df_usd = procesar_hojas(d_usd, "USD", tasa)
                
                st.session_state.datos_ready = pd.concat([df_bs, df_usd], ignore_index=True)

# --- RESULTADOS ---
res = st.session_state.datos_ready

if not res.empty:
    # Cálculo consolidado en BS
    def calcular_neto_bs(row):
        n = row['I_VAL'] - row['E_VAL']
        return round(n, 2) if row['ORIGEN'] == "BS" else round(n * tasa, 2)

    res['NETO_BS'] = res.apply(calcular_neto_bs, axis=1)
    
    # Agrupación por código GYP
    gp_final = res.groupby('CUENTA')['NETO_BS'].sum().reset_index()
    gp_final['NETO_USD'] = (gp_final['NETO_BS'] / tasa).round(2)
    
    # Métricas
    c1, c2 = st.columns(2)
    c1.metric("UTILIDAD/PÉRDIDA (BS)", f"Bs. {gp_final['NETO_BS'].sum():,.2f}")
    c2.metric("UTILIDAD/PÉRDIDA (USD)", f"$ {gp_final['NETO_USD'].sum():,.2f}")

    st.subheader("📋 Resumen Consolidado por Código")
    st.dataframe(gp_final.style.format({'NETO_BS': '{:,.2f}', 'NETO_USD': '{:,.2f}'}), use_container_width=True)

    # AUDITORÍA DETALLADA
    st.markdown("---")
    st.subheader("🔍 Auditoría de Movimientos")
    cod_auditoria = st.text_input("Ingresa código para auditar (ej: I001):", value="I001")
    
    if cod_auditoria:
        detalle = res[res['CUENTA'] == cod_auditoria]
        if not detalle.empty:
            st.write(f"Movimientos detectados para el código **{cod_auditoria}**:")
            st.dataframe(detalle[['HOJA', 'ORIGEN', 'DETALLE', 'I_VAL', 'E_VAL', 'NETO_BS']])
            suma_i = detalle['I_VAL'].sum()
            suma_e = detalle['E_VAL'].sum()
            st.info(f"Totales en moneda origen para este código -> Ingresos: {suma_i:,.2f} | Egresos: {suma_e:,.2f} | Neto: {suma_i - suma_e:,.2f}")
        else:
            st.warning(f"No se encontró el código {cod_auditoria} en la base de datos.")
else:
    st.info("💡 Por favor, configure los datos en la barra lateral y haga clic en Generar Reporte.")
