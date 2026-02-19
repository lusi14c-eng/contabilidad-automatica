import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Adonai Group ERP", layout="wide")

if 'datos_acumulados' not in st.session_state:
    st.session_state.datos_acumulados = pd.DataFrame()

# 2. CONEXIÓN
def conectar_drive():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de credenciales: {e}")
        return None

def leer_excel_drive(service, nombre_archivo):
    try:
        query = f"name = '{nombre_archivo}' and trashed = false"
        resultado = service.files().list(q=query, fields="files(id, name)").execute()
        archivos = resultado.get('files', [])
        if not archivos: return None
        
        file_id = archivos[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO(request.execute())
        # Intentamos leer desde la fila 3 (header=2)
        return pd.read_excel(fh, sheet_name=None, header=2)
    except:
        return None

# 3. PROCESAMIENTO ULTRA-FLEXIBLE
def procesar_hojas(dict_hojas, moneda_archivo, tasa_cambio, mes_label):
    lista_movimientos = []
    
    for nombre_hoja, df in dict_hojas.items():
        # Limpieza de columnas: quitamos espacios y pasamos a minúsculas
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # BUSCADOR DINÁMICO DE COLUMNAS
        # Busca cualquier columna que TENGA la palabra ingreso o egreso
        col_ing = next((c for c in df.columns if 'ingreso' in c), None)
        col_egr = next((c for c in df.columns if 'egreso' in c or 'haber' in c), None)
        col_gyp = next((c for c in df.columns if 'gyp' in c), 'gyp')

        if col_ing and col_egr:
            # Convertir a número lo que sea posible
            df[col_ing] = pd.to_numeric(df[col_ing], errors='coerce').fillna(0)
            df[col_egr] = pd.to_numeric(df[col_egr], errors='coerce').fillna(0)
            
            # Cálculos
            if "BS" in moneda_archivo:
                df['total_bs'] = df[col_ing] - df[col_egr]
                df['total_usd'] = df['total_bs'] / tasa_cambio
            else:
                df['total_usd'] = df[col_ing] - df[col_egr]
                df['total_bs'] = df['total_usd'] * tasa_cambio
            
            df['banco'] = nombre_hoja
            df['mes_reporte'] = mes_label
            
            # Filtramos filas que tengan montos reales
            df_valido = df[(df[col_ing] != 0) | (df[col_egr] != 0)].copy()
            if not df_valido.empty:
                lista_movimientos.append(df_valido)
                
    return pd.concat(lista_movimientos) if lista_movimientos else pd.DataFrame()

# 4. INTERFAZ
st.title("🏦 Adonai Industrial Group - ERP")

with st.sidebar:
    mes_num = st.selectbox("Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa:", value=45.0)
    btn = st.button("🔄 Sincronizar")

if btn:
    service = conectar_drive()
    if service:
        n_bs = f"RELACION INGRESOS Y EGRESOS {mes_num} BS.xlsx"
        n_usd = f"RELACION INGRESOS Y EGRESOS {mes_num} USD.xlsx"
        
        d_bs = leer_excel_drive(service, n_bs)
        d_usd = leer_excel_drive(service, n_usd)
        
        if d_bs and d_usd:
            res_bs = procesar_hojas(d_bs, "BS", tasa, f"Mes {mes_num}")
            res_usd = procesar_hojas(d_usd, "USD", tasa, f"Mes {mes_num}")
            
            st.session_state.datos_acumulados = pd.concat([res_bs, res_usd])
            st.success("¡Sincronizado!")
        else:
            st.error("No se encontraron los archivos .xlsx")

# 5. RESULTADOS
if not st.session_state.datos_acumulados.empty:
    df = st.session_state.datos_acumulados
    
    # MÉTRICAS
    i = df[df['total_usd'] > 0]['total_usd'].sum()
    e = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos (USD)", f"$ {i:,.2f}")
    c2.metric("Egresos (USD)", f"$ {e:,.2f}")
    c3.metric("Utilidad (USD)", f"$ {i-e:,.2f}")
    
    # TABLA DE AUDITORÍA (Para ver qué está leyendo)
    st.write("### 🔍 Vista previa de datos detectados")
    st.dataframe(df[['banco', 'total_bs', 'total_usd']].head(20))
