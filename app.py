import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

st.set_page_config(page_title="Adonai Group - G+P Final", layout="wide", page_icon="📈")

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
    """Extrae el catálogo de cuentas de la pestaña GYP"""
    maestro = {}
    if not dict_hojas or 'GYP' not in dict_hojas: return maestro
    
    df_gyp = dict_hojas['GYP']
    for i in range(len(df_gyp)):
        fila = df_gyp.iloc[i].astype(str).tolist()
        for idx, celda in enumerate(fila):
            match = re.search(r'^([IE]\d+)', celda.strip().upper())
            if match:
                codigo = match.group(1)
                # El nombre suele estar en la columna de al lado
                nombre = "S/N"
                if idx + 1 < len(fila):
                    nombre = fila[idx+1].strip()
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
        # Ignorar hojas administrativas
        if any(x in nombre_hoja.lower() for x in ['portada', 'data', 'resumen', 'gyp']): continue
        
        # 1. Mapeo de columnas por nombre
        header_row = -1
        idx_gyp, idx_ing, idx_egr, idx_desc = -1, -1, -1, -1

        for i in range(min(30, len(df_raw))):
            fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
            if 'GYP' in fila or 'CÓDIGO' in fila:
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
        
        if idx_gyp == -1 or idx_ing == -1: continue

        # 2. Extracción con prevención de totales
        for i in range(header_row + 1, len(df_raw)):
            fila = df_raw.iloc[i]
            raw_cod = str(fila.iloc[idx_gyp]).upper().strip()
            
            # Solo procesar si es un código puro (I001, E002...) 
            # Esto evita sumar filas de "TOTAL" que a veces repiten el código
            match = re.match(r'^([IE]\d+)$', raw_cod)
            if match:
                cod = match.group(1)
                ing = limpiar_monto(fila.iloc[idx_ing])
                egr = limpiar_monto(fila.iloc[idx_egr])
                desc = str(fila.iloc[idx_desc]) if idx_desc != -1 else ""

                if (ing != 0 or egr != 0) and "TOTAL" not in desc.upper():
                    datos_lista.append({
                        'CÓDIGO': cod,
                        'I_ORIGEN': ing,
                        'E_ORIGEN': egr,
                        'DETALLE': desc.strip(),
                        'HOJA': nombre_hoja,
                        'MONEDA': tipo_archivo
                    })

    return pd.DataFrame(datos_lista)

# --- INTERFAZ ---
st.title("📈 Estado de Resultados Consolidado (G+P)")

with st.sidebar:
    mes = st.selectbox("Seleccione Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa BCV oficial:", value=45.0, format="%.4f")
    
    if st.button("🔄 Sincronizar y Calcular", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Leyendo archivos..."):
                d_bs = leer_excel_drive(service, mes, "BS")
                d_usd = leer_excel_drive(service, mes, "USD")
                
                # Cargar nombres de cuentas desde la hoja GYP de BS
                st.session_state.maestro_cuentas = obtener_nombres_cuentas(d_bs)
                
                df_bs = procesar_hojas(d_bs, "BS", tasa)
                df_usd = procesar_hojas(d_usd, "USD", tasa)
                st.session_state.datos_ready = pd.concat([df_bs, df_usd], ignore_index=True)

df = st.session_state.datos_ready
if not df.empty:
    # 1. Normalizar valores a BS
    df['NETO_BS'] = df.apply(lambda r: round(r['I_ORIGEN'] - r['E_ORIGEN'], 2) if r['MONEDA'] == "BS" 
                            else round((r['I_ORIGEN'] - r['E_ORIGEN']) * tasa, 2), axis=1)
    
    # 2. Agrupar
    resumen = df.groupby('CÓDIGO')['NETO_BS'].sum().reset_index()
    
    # 3. Cruzar con nombres de cuentas
    resumen['CUENTA'] = resumen['CÓDIGO'].map(st.session_state.maestro_cuentas).fillna("Cuenta no definida")
    resumen['NETO_USD'] = (resumen['NETO_BS'] / tasa).round(2)
    
    # 4. Separar Ingresos de Egresos para la estructura G+P
    ingresos = resumen[resumen['CÓDIGO'].str.startswith('I')].sort_values('CÓDIGO')
    egresos = resumen[resumen['CÓDIGO'].str.startswith('E')].sort_values('CÓDIGO')

    # Visualización Profesional
    col1, col2 = st.columns(2)
    utilidad_bs = resumen['NETO_BS'].sum()
    col1.metric("UTILIDAD/PÉRDIDA BS", f"Bs. {utilidad_bs:,.2f}")
    col2.metric("UTILIDAD/PÉRDIDA USD", f"$ {utilidad_bs/tasa:,.2f}")

    st.subheader("📊 Estructura del Estado de Resultados")
    
    st.markdown("### 🟢 INGRESOS")
    st.table(ingresos[['CÓDIGO', 'CUENTA', 'NETO_BS', 'NETO_USD']].style.format({'NETO_BS': '{:,.2f}', 'NETO_USD': '{:,.2f}'}))
    
    st.markdown("### 🔴 EGRESOS")
    st.table(egresos[['CÓDIGO', 'CUENTA', 'NETO_BS', 'NETO_USD']].style.format({'NETO_BS': '{:,.2f}', 'NETO_USD': '{:,.2f}'}))

    # Auditoría para I002
    with st.expander("🔍 Auditoría Detallada (Verificar I002)"):
        cod_check = st.text_input("Código a investigar:", "I002")
        detalle = df[df['CÓDIGO'] == cod_check]
        st.write(f"Movimientos encontrados para {cod_check}:")
        st.dataframe(detalle)
else:
    st.info("Haga clic en el botón de la izquierda para procesar los datos.")
