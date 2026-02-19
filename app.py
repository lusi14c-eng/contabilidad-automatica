import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import plotly.express as px

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Adonai Group ERP", layout="wide", page_icon="📊")

# Inicializar el histórico en la memoria de la sesión
if 'datos_acumulados' not in st.session_state:
    st.session_state.datos_acumulados = pd.DataFrame()

# 2. FUNCIONES DE CONEXIÓN A GOOGLE DRIVE
def conectar_drive():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            # Limpia automáticamente errores de formato en la clave PEM
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None

def leer_excel_drive(service, nombre_archivo):
    try:
        query = f"name = '{nombre_archivo}' and trashed = false"
        resultado = service.files().list(q=query, fields="files(id, name)").execute()
        archivos = resultado.get('files', [])
        if not archivos:
            return None
        
        file_id = archivos[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO(request.execute())
        # Cargamos el Excel, header=2 significa que los títulos están en la FILA 3
        return pd.read_excel(fh, sheet_name=None, header=2)
    except Exception as e:
        return None

def procesar_hojas(dict_hojas, moneda_archivo, tasa_cambio, mes_label):
    lista_movimientos = []
    
    for nombre_hoja, df in dict_hojas.items():
        # Limpieza profunda de nombres de columnas
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Mapeo de columnas según tu descripción
        col_ing = 'ingresos bs' if moneda_archivo == "BS" else 'ingreso usd'
        col_egr = 'egresos bs' if moneda_archivo == "BS" else 'egreso usd'
        
        # Verificamos si las columnas existen en esta pestaña
        if col_ing in df.columns and col_egr in df.columns:
            # Convertimos datos a números, ignorando textos o errores
            df[col_ing] = pd.to_numeric(df[col_ing], errors='coerce').fillna(0)
            df[col_egr] = pd.to_numeric(df[col_egr], errors='coerce').fillna(0)
            
            # Realizamos cálculos de conversión
            if moneda_archivo == "BS":
                df['total_bs'] = df[col_ing] - df[col_egr]
                df['total_usd'] = df['total_bs'] / tasa_cambio
            else:
                df['total_usd'] = df[col_ing] - df[col_egr]
                df['total_bs'] = df['total_usd'] * tasa_cambio
            
            # Etiquetamos la procedencia
            df['banco'] = nombre_hoja
            df['mes_reporte'] = mes_label
            df['moneda_original'] = moneda_archivo
            
            # Solo guardamos filas que tengan montos reales (distintos de cero)
            df_valido = df[(df[col_ing] != 0) | (df[col_egr] != 0)].copy()
            if not df_valido.empty:
                lista_movimientos.append(df_valido)
                
    return pd.concat(lista_movimientos) if lista_movimientos else pd.DataFrame()

# 3. INTERFAZ DE USUARIO
st.title("🏦 Adonai Industrial Group - ERP")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Configuración")
    mes_num = st.selectbox("Seleccione Mes (Número):", range(1, 13), index=10) # Noviembre por defecto
    tasa = st.number_input("Tasa de Cambio (Bs/USD):", value=45.0, step=0.1)
    
    if st.button("🔄 Sincronizar con Drive"):
        service = conectar_drive()
        if service:
            # Nombres exactos con .xlsx
            n_bs = f"RELACION INGRESOS Y EGRESOS {mes_num} BS.xlsx"
            n_usd = f"RELACION INGRESOS Y EGRESOS {mes_num} USD.xlsx"
            
            with st.spinner(f"Sincronizando mes {mes_num}..."):
                d_bs = leer_excel_drive(service, n_bs)
                d_usd = leer_excel_drive(service, n_usd)
                
                if d_bs and d_usd:
                    res_bs = procesar_hojas(d_bs, "BS", tasa, f"Mes {mes_num}")
                    res_usd = procesar_hojas(d_usd, "USD", tasa, f"Mes {mes_num}")
                    
                    if not res_bs.empty or not res_usd.empty:
                        nuevo_mes = pd.concat([res_bs, res_usd])
                        
                        # Limpiar datos previos del mismo mes para evitar duplicados
                        if not st.session_state.datos_acumulados.empty:
                            st.session_state.datos_acumulados = st.session_state.datos_acumulados[
                                st.session_state.datos_acumulados['mes_reporte'] != f"Mes {mes_num}"
                            ]
                        
                        st.session_state.datos_acumulados = pd.concat([st.session_state.datos_acumulados, nuevo_mes])
                        st.success(f"¡Datos de Mes {mes_num} cargados correctamente!")
                    else:
                        st.warning("Archivos encontrados, pero no se detectaron montos en las columnas de Ingreso/Egreso.")
                else:
                    st.error(f"No se encontraron los archivos: {n_bs} o {n_usd}")

# 4. DASHBOARD DE RESULTADOS
if not st.session_state.datos_acumulados.empty:
    # Filtrar solo el mes seleccionado
    df_actual = st.session_state.datos_acumulados[st.session_state.datos_acumulados['mes_reporte'] == f"Mes {mes_num}"]
    
    if not df_actual.empty:
        # Métricas de la parte superior
        ing_t = df_actual[df_actual['total_usd'] > 0]['total_usd'].sum()
        egr_t = abs(df_actual[df_actual['total_usd'] < 0]['total_usd'].sum())
        
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS TOTALES (USD)", f"$ {ing_t:,.2f}")
        c2.metric("EGRESOS TOTALES (USD)", f"$ {egr_t:,.2f}")
        c3.metric("UTILIDAD NETA (USD)", f"$ {ing_t - egr_t:,.2f}", delta=f"{((ing_t-egr_t)/ing_t)*100:.1f}%" if ing_t != 0 else None)

        # Tabla de Ganancias y Pérdidas (GyP)
        if 'gyp' in df_actual.columns:
            st.subheader("📊 Resumen por Código GyP")
            pyl = df_actual.groupby('gyp')[['total_bs', 'total_usd']].sum().reset_index()
            # Ordenar por el código GyP
            pyl = pyl.sort_values(by='gyp')
            st.table(pyl.style.format({"total_bs": "{:,.2f}", "total_usd": "{:,.2f}"}))
            
        # Vista de los movimientos crudos (Opcional, para auditoría)
        with st.expander("🔍 Ver detalle de movimientos sincronizados"):
            st.dataframe(df_actual[['fecha', 'descripcion', 'banco', 'total_bs', 'total_usd', 'gyp']])
            
    else:
        st.warning(f"No hay datos para mostrar del Mes {mes_num}. Intenta sincronizar de nuevo.")
else:
    st.info("👋 ERP Adonai listo. Selecciona los parámetros en la izquierda y presiona Sincronizar.")
