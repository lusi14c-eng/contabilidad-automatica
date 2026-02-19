import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io

st.set_page_config(page_title="Adonai Group ERP", layout="wide")

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
        
        # Leemos todo el libro de Excel
        return pd.read_excel(fh, sheet_name=None, header=None) # Leemos sin cabecera primero para analizar
    except:
        return None

def procesar_hojas(dict_hojas, moneda_archivo, tasa_cambio, mes_label):
    lista_movimientos = []
    
    for nombre_hoja, df_raw in dict_hojas.items():
        # BUSCAR LA FILA DE TÍTULOS AUTOMÁTICAMENTE
        # Buscamos en las primeras 10 filas cuál contiene la palabra "ingreso" o "egreso"
        fila_titulos = 0
        for i in range(min(10, len(df_raw))):
            fila_texto = " ".join(df_raw.iloc[i].astype(str).lower())
            if 'ingreso' in fila_texto or 'egreso' in fila_texto:
                fila_titulos = i
                break
        
        # Reformateamos el DF con la fila de títulos encontrada
        df = df_raw.copy()
        df.columns = [str(c).strip().lower() for c in df.iloc[fila_titulos]]
        df = df.iloc[fila_titulos + 1:].reset_index(drop=True)
        
        # Identificar columnas de dinero
        col_ing = next((c for c in df.columns if 'ingreso' in c), None)
        col_egr = next((c for c in df.columns if 'egreso' in c or 'haber' in c), None)

        if col_ing and col_egr:
            df[col_ing] = pd.to_numeric(df[col_ing], errors='coerce').fillna(0)
            df[col_egr] = pd.to_numeric(df[col_egr], errors='coerce').fillna(0)
            
            if "BS" in moneda_archivo:
                df['total_bs'] = df[col_ing] - df[col_egr]
                df['total_usd'] = df['total_bs'] / tasa_cambio
            else:
                df['total_usd'] = df[col_ing] - df[col_egr]
                df['total_bs'] = df['total_usd'] * tasa_cambio
            
            df['banco'] = nombre_hoja
            df['mes_reporte'] = mes_label
            
            # Solo filas con montos
            df_valido = df[(df[col_ing] != 0) | (df[col_egr] != 0)].copy()
            if not df_valido.empty:
                lista_movimientos.append(df_valido)
        else:
            # Si no encuentra columnas, nos avisa qué columnas vio
            st.warning(f"En la hoja '{nombre_hoja}' no encontré columnas de Ingreso/Egreso. Columnas vistas: {list(df.columns)[:5]}")
                
    return pd.concat(lista_movimientos) if lista_movimientos else pd.DataFrame()

# INTERFAZ
st.title("🏦 Adonai Industrial Group - ERP")

with st.sidebar:
    mes_num = st.selectbox("Mes:", range(1, 13), index=10)
    tasa = st.number_input("Tasa:", value=45.0)
    if st.button("🔄 Sincronizar"):
        service = conectar_drive()
        if service:
            n_bs = f"RELACION INGRESOS Y EGRESOS {mes_num} BS.xlsx"
            n_usd = f"RELACION INGRESOS Y EGRESOS {mes_num} USD.xlsx"
            
            d_bs = leer_excel_drive(service, n_bs)
            d_usd = leer_excel_drive(service, n_usd)
            
            if d_bs or d_usd:
                res_bs = procesar_hojas(d_bs, "BS", tasa, f"Mes {mes_num}") if d_bs else pd.DataFrame()
                res_usd = procesar_hojas(d_usd, "USD", tasa, f"Mes {mes_num}") if d_usd else pd.DataFrame()
                
                st.session_state.datos_acumulados = pd.concat([res_bs, res_usd])
                if not st.session_state.datos_acumulados.empty:
                    st.success("¡Sincronizado con datos!")
                else:
                    st.error("Archivos leídos pero están vacíos o sin columnas de dinero.")
            else:
                st.error("No se encontraron los archivos .xlsx")

# RESULTADOS
df = st.session_state.datos_acumulados
if not df.empty:
    ing = df[df['total_usd'] > 0]['total_usd'].sum()
    egr = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos (USD)", f"$ {ing:,.2f}")
    c2.metric("Egresos (USD)", f"$ {egr:,.2f}")
    c3.metric("Utilidad (USD)", f"$ {ing-egr:,.2f}")
    
    st.markdown("---")
    st.subheader("📋 Detalle de Movimientos")
    st.dataframe(df, use_container_width=True)
else:
    st.info("Sin datos cargados.")
