import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

# 1. Función de Seguridad
def check_password():
    def password_entered():
        if "auth" in st.secrets and st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Contraseña de acceso:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Contraseña incorrecta. Intente de nuevo:", type="password", on_change=password_entered, key="password")
        st.error("😕 Acceso denegado")
        return False
    return True

# 2. Configuración de página (Debe ir después de los imports)
st.set_page_config(page_title="Adonai Group - G+P Final", layout="wide", page_icon="🔒")

# --- SOLO SI LA CONTRASEÑA ES CORRECTA ---
if check_password():
    
    # --- FUNCIONES DE DRIVE Y PROCESAMIENTO ---
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
            fila = [str(x).strip() for x in df_gyp.iloc[i].values]
            for idx, celda in enumerate(fila):
                c_clean = celda.upper()
                if re.match(r'^[IE]\d+', c_clean):
                    codigo = c_clean
                    nombre = "Sin descripción"
                    for j in range(idx + 1, len(fila)):
                        if fila[j] != 'nan' and len(fila[j]) > 3:
                            nombre = fila[j]
                            break
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

    def procesar_hojas(dict_hojas, tipo_moneda):
        lista_temp = []
        if not dict_hojas: return lista_temp
        for nombre_hoja, df_raw in dict_hojas.items():
            if any(x in nombre_hoja.lower() for x in ['portada', 'data', 'resumen', 'gyp']): continue
            idx_gyp, idx_ing, idx_egr, start_row = -1, -1, -1, -1
            for i in range(min(40, len(df_raw))):
                fila = [str(x).upper().strip() for x in df_raw.iloc[i].values]
                if any(k in fila for k in ['GYP', 'COD', 'CÓDIGO']):
                    start_row = i + 1
                    for idx, t in enumerate(fila):
                        if any(x in t for x in ['GYP', 'COD']): idx_gyp = idx
                        if 'INGRESOS' in t:
                            if tipo_moneda == "BS" and "USD" not in t: idx_ing = idx
                            elif tipo_moneda == "USD" and "USD" in t: idx_ing = idx
                        if 'EGRESOS' in t:
                            if tipo_moneda == "BS" and "USD" not in t: idx_egr = idx
                            elif tipo_moneda == "USD" and "USD" in t: idx_egr = idx
                    break
            if idx_gyp != -1 and idx_ing != -1:
                for i in range(start_row, len(df_raw)):
                    fila = df_raw.iloc[i]
                    cod = str(fila.iloc[idx_gyp]).upper().strip()
                    if re.match(r'^[IE]\d+$', cod):
                        m_ing = limpiar_monto(fila.iloc[idx_ing])
                        m_egr = limpiar_monto(fila.iloc[idx_egr]) if idx_egr != -1 else 0.0
                        if m_ing != 0 or m_egr != 0:
                            lista_temp.append({'COD': cod, 'MONTO': m_ing - m_egr, 'MONEDA': tipo_moneda})
        return lista_temp

    # --- LÓGICA DE INTERFAZ ---
    if 'datos_ready' not in st.session_state: st.session_state.datos_ready = pd.DataFrame()
    if 'maestro_cuentas' not in st.session_state: st.session_state.maestro_cuentas = {}

    with st.sidebar:
        st.title("🏦 Adonai Group")
        mes = st.selectbox("Mes:", range(1, 13), index=10)
        tasa = st.number_input("Tasa BCV:", value=45.0, format="%.4f")
        if st.button("🚀 Procesar Reporte"):
            service = conectar_drive()
            if service:
                with st.spinner("Cargando..."):
                    d_bs = leer_excel_drive(service, mes, "BS")
                    d_usd = leer_excel_drive(service, mes, "USD")
                    st.session_state.maestro_cuentas = obtener_nombres_cuentas(d_bs)
                    res = procesar_hojas(d_bs, "BS") + procesar_hojas(d_usd, "USD")
                    st.session_state.datos_ready = pd.DataFrame(res) if res else pd.DataFrame()

    df = st.session_state.datos_ready
    if not df.empty:
        matriz = df.groupby(['COD', 'MONEDA'])['MONTO'].sum().unstack(fill_value=0).reset_index()
        if 'BS' not in matriz.columns: matriz['BS'] = 0.0
        if 'USD' not in matriz.columns: matriz['USD'] = 0.0
        matriz['CUENTA'] = matriz['COD'].map(st.session_state.maestro_cuentas).fillna("Código no en GYP")
        matriz['TOTAL_BS'] = matriz['BS'] + (matriz['USD'] * tasa)
        matriz = matriz[['COD', 'CUENTA', 'BS', 'USD', 'TOTAL_BS']]

        st.subheader("📊 Consolidado General")
        st.dataframe(matriz.style.format({'BS': '{:,.2f}', 'USD': '{:,.2f}', 'TOTAL_BS': '{:,.2f}'}), use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            matriz.to_excel(writer, index=False, sheet_name='G+P')
            workbook = writer.book
            fmt = workbook.add_format({'num_format': '#,##0.00'})
            writer.sheets['G+P'].set_column('C:E', 20, fmt)

        st.download_button("📥 Descargar Excel", buffer.getvalue(), f"GP_Mes_{mes}.xlsx", "application/vnd.ms-excel")
    else:
        st.info("Utilice el menú lateral para procesar los datos.")
