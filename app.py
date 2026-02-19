import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import re

# Configuración de la página
st.set_page_config(page_title="Adonai Group - G+P Matriz", layout="wide", page_icon="📊")

# --- FUNCIONES DE CONEXIÓN Y LECTURA ---
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

# --- FUNCIONES DE PROCESAMIENTO ---
def obtener_nombres_cuentas(dict_hojas):
    maestro = {}
    if not dict_hojas or 'GYP' not in dict_hojas: return maestro
    df_gyp = dict_hojas['GYP']
    for i in range(len(df_gyp)):
        fila = df_gyp.iloc[i].astype(str).tolist()
        for idx, celda in enumerate(fila):
            c_clean = celda.strip().upper()
            if re.match(r'^[IE]\d+', c_clean):
                maestro[c_clean] = fila[idx+1].strip() if idx+1 < len(fila) else "S/N"
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
        
        idx_gyp, idx_ing, idx_egr = -1, -1, -1
        start_row = -1

        for i in range(min(35, len(df_raw))):
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

# --- INTERFAZ DE USUARIO ---
if 'datos_ready' not in st.session_state:
    st.session_state.datos_ready = pd.DataFrame()
if 'maestro_cuentas' not in st.session_state:
    st.session_state.maestro_cuentas = {}

with st.sidebar:
    st.header("Configuración")
    mes = st.selectbox("Mes de Relación:", range(1, 13), index=10)
    tasa = st.number_input("Tasa de Cambio (BS/$):", value=45.0, format="%.4f")
    if st.button("🚀 Generar Matriz y Excel", use_container_width=True):
        service = conectar_drive()
        if service:
            with st.spinner("Procesando datos de Drive..."):
                d_bs = leer_excel_drive(service, mes, "BS")
                d_usd = leer_excel_drive(service, mes, "USD")
                st.session_state.maestro_cuentas = obtener_nombres_cuentas(d_bs)
                
                res_bs = procesar_hojas(d_bs, "BS")
                res_usd = procesar_hojas(d_usd, "USD")
                
                todos_datos = res_bs + res_usd
                if todos_datos:
                    st.session_state.datos_ready = pd.DataFrame(todos_datos)
                else:
                    st.session_state.datos_ready = pd.DataFrame()
                    st.warning("No se encontraron movimientos con códigos válidos.")

# --- MOSTRAR RESULTADOS Y BOTÓN DE DESCARGA ---
df = st.session_state.datos_ready

if not df.empty:
    # 1. Crear Matriz
    matriz = df.groupby(['COD', 'MONEDA'])['MONTO'].sum().unstack(fill_value=0).reset_index()
    if 'BS' not in matriz.columns: matriz['BS'] = 0.0
    if 'USD' not in matriz.columns: matriz['USD'] = 0.0
    
    matriz['CUENTA'] = matriz['COD'].map(st.session_state.maestro_cuentas).fillna("S/D")
    matriz['CONSOLIDADO_BS'] = matriz['BS'] + (matriz['USD'] * tasa)
    matriz = matriz[['COD', 'CUENTA', 'BS', 'USD', 'CONSOLIDADO_BS']]

    # 2. Visualización en Streamlit
    ing = matriz[matriz['COD'].str.startswith('I')].sort_values('COD')
    egr = matriz[matriz['COD'].str.startswith('E')].sort_values('COD')

    st.subheader("🟢 Ingresos Consolidados")
    st.dataframe(ing.style.format({'BS': '{:,.2f}', 'USD': '{:,.2f}', 'CONSOLIDADO_BS': '{:,.2f}'}), use_container_width=True)
    
    st.subheader("🔴 Egresos Consolidados")
    st.dataframe(egr.style.format({'BS': '{:,.2f}', 'USD': '{:,.2f}', 'CONSOLIDADO_BS': '{:,.2f}'}), use_container_width=True)

    # 3. Función para exportar a Excel (aquí está lo que pediste)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        matriz.to_excel(writer, index=False, sheet_name='G+P_Consolidado')
        workbook  = writer.book
        worksheet = writer.sheets['G+P_Consolidado']
        # Dar formato de moneda a las columnas C, D y E
        formato_moneda = workbook.add_format({'num_format': '#,##0.00'})
        worksheet.set_column('C:E', 20, formato_moneda)

    st.divider()
    st.download_button(
        label="📥 Descargar Reporte Completo en Excel",
        data=buffer.getvalue(),
        file_name=f"GP_Consolidado_Mes_{mes}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    total_gral = matriz['CONSOLIDADO_BS'].sum()
    st.metric("RESULTADO DEL EJERCICIO (BS)", f"Bs. {total_gral:,.2f}")
else:
    st.info("A la espera de datos. Use el botón de la barra lateral.")
def obtener_nombres_cuentas(dict_hojas):
    """
    Escanea la pestaña GYP para crear el diccionario de nombres.
    Busca patrones tipo I001, E010 y extrae la descripción asociada.
    """
    maestro = {}
    if not dict_hojas or 'GYP' not in dict_hojas:
        return maestro
    
    df_gyp = dict_hojas['GYP'].astype(str) # Forzamos todo a texto para evitar errores
    
    for _, fila in df_gyp.iterrows():
        lista_celdas = [c.strip() for c in fila.values if c != 'nan']
        
        for i, contenido in enumerate(lista_celdas):
            # Buscamos el código (I o E seguido de números)
            match = re.search(r'^([IE]\d+)', contenido.upper())
            if match:
                codigo = match.group(1)
                # Intentamos buscar el nombre en las siguientes celdas de la misma fila
                nombre = "Nombre no encontrado"
                for j in range(i + 1, len(lista_celdas)):
                    texto_candidato = lista_celdas[j]
                    # Si la celda tiene letras y no es otro código, es el nombre
                    if len(texto_candidato) > 3 and not re.search(r'^[IE]\d+', texto_candidato):
                        nombre = texto_candidato
                        break
                maestro[codigo] = nombre
    return maestro
