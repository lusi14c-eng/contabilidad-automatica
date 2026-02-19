import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io

st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="📊")

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
        
        # Leemos el Excel sin cabeceras para procesarlo manualmente
        return pd.read_excel(fh, sheet_name=None, header=None)
    except:
        return None

def procesar_hojas(dict_hojas, moneda_archivo, tasa_cambio, mes_label):
    lista_movimientos = []
    
    for nombre_hoja, df_raw in dict_hojas.items():
        # 1. SALTAR HOJAS VACÍAS O DE RESUMEN
        if df_raw.empty or 'gyp' in nombre_hoja.lower() or 'resumen' in nombre_hoja.lower():
            continue # Salta a la siguiente pestaña inmediatamente

        # 2. BUSCAR LA FILA DE TÍTULOS DE FORMA SEGURA
        fila_titulos = -1 # Empezamos en -1 para saber si la encontramos
        for i in range(min(15, len(df_raw))):
            fila_valores = [str(val).lower().strip() for val in df_raw.iloc[i].values]
            if any('ingreso' in val for val in fila_valores) or any('egreso' in val for val in fila_valores) or any('haber' in val for val in fila_valores):
                fila_titulos = i
                break
        
        # Si no encontró una fila con la palabra "ingreso" o "egreso", saltamos esta hoja
        if fila_titulos == -1:
            st.info(f"⏭️ Omitiendo hoja '{nombre_hoja}': No tiene formato de movimientos.")
            continue

        # 3. REESTRUCTURAR EL DATAFRAME
        df = df_raw.copy()
        nuevos_titulos = [str(c).strip().lower() for c in df.iloc[fila_titulos]]
        df.columns = nuevos_titulos
        df = df.iloc[fila_titulos + 1:].reset_index(drop=True)
        
        # 4. IDENTIFICAR COLUMNAS DE DINERO
        col_ing = next((c for c in df.columns if 'ingreso' in str(c)), None)
        col_egr = next((c for c in df.columns if 'egreso' in str(c) or 'haber' in str(c)), None)

        if col_ing and col_egr:
            # Convertir a números
            df[col_ing] = pd.to_numeric(df[col_ing], errors='coerce').fillna(0)
            df[col_egr] = pd.to_numeric(df[col_egr], errors='coerce').fillna(0)
            
            # Cálculos según la moneda
            if "BS" in moneda_archivo:
                df['total_bs'] = df[col_ing] - df[col_egr]
                df['total_usd'] = df['total_bs'] / tasa_cambio
            else:
                df['total_usd'] = df[col_ing] - df[col_egr]
                df['total_bs'] = df['total_usd'] * tasa_cambio
            
            df['banco_origen'] = nombre_hoja
            df['mes_reporte'] = mes_label
            
            # Guardamos solo filas que tengan algún monto
            df_valido = df[(df[col_ing] != 0) | (df[col_egr] != 0)].copy()
            if not df_valido.empty:
                lista_movimientos.append(df_valido)
                
    return pd.concat(lista_movimientos) if lista_movimientos else pd.DataFrame()

# INTERFAZ
st.title("🏦 Adonai Industrial Group - ERP")

with st.sidebar:
    st.header("Configuración")
    mes_num = st.selectbox("Mes a procesar:", range(1, 13), index=10)
    tasa = st.number_input("Tasa de Cambio:", value=45.0, step=0.01)
    
    if st.button("🔄 Sincronizar Drive"):
        service = conectar_drive()
        if service:
            n_bs = f"RELACION INGRESOS Y EGRESOS {mes_num} BS.xlsx"
            n_usd = f"RELACION INGRESOS Y EGRESOS {mes_num} USD.xlsx"
            
            with st.spinner("Procesando hojas y filtrando resúmenes..."):
                d_bs = leer_excel_drive(service, n_bs)
                d_usd = leer_excel_drive(service, n_usd)
                
                if d_bs or d_usd:
                    res_bs = procesar_hojas(d_bs, "BS", tasa, f"Mes {mes_num}") if d_bs else pd.DataFrame()
                    res_usd = procesar_hojas(d_usd, "USD", tasa, f"Mes {mes_num}") if d_usd else pd.DataFrame()
                    
                    st.session_state.datos_acumulados = pd.concat([res_bs, res_usd])
                    
                    if not st.session_state.datos_acumulados.empty:
                        st.success("¡Sincronización exitosa!")
                    else:
                        st.error("No se detectaron movimientos en las hojas procesadas.")
                else:
                    st.error("No se encontraron los archivos con .xlsx en Drive.")

# DASHBOARD
df = st.session_state.datos_acumulados
if not df.empty:
    ing = df[df['total_usd'] > 0]['total_usd'].sum()
    egr = abs(df[df['total_usd'] < 0]['total_usd'].sum())
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos (USD)", f"$ {ing:,.2f}")
    c2.metric("Egresos (USD)", f"$ {egr:,.2f}")
    c3.metric("Utilidad (USD)", f"$ {ing-egr:,.2f}")
    
    st.markdown("---")
    st.subheader("📋 Detalle de Movimientos Detectados")
    # Mostramos las columnas relevantes que existan
    columnas_disponibles = [c for c in ['fecha', 'descripcion', 'concepto', 'banco_origen', 'total_bs', 'total_usd', 'gyp'] if c in df.columns]
    
    # Si no encuentra columnas descriptivas estándar, muestra todo
    if len(columnas_disponibles) < 3:
        st.dataframe(df, use_container_width=True)
    else:
        st.dataframe(df[columnas_disponibles], use_container_width=True)
else:
    st.info("💡 ERP listo. Presiona Sincronizar Drive.")
