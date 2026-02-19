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

# --- ESTILOS ADONAI ---
st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNCIONES DE CONEXIÓN A GOOGLE DRIVE
def conectar_drive():
    try:
        # Cargamos la info de los secrets
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # EL TRUCO MÁGICO: Reemplazamos los saltos de línea mal pegados
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        creds = service_account.Credentials.from_service_account_info(creds_info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None
    
    file_id = archivos[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO(request.execute())
    # header=2 indica que los títulos están en la FILA 3
    return pd.read_excel(fh, sheet_name=None, header=2)

# 3. LÓGICA DE PROCESAMIENTO CONTABLE
def procesar_hojas(dict_hojas, moneda_archivo, tasa_cambio, mes_label):
    lista_movimientos = []
    
    for nombre_banco, df in dict_hojas.items():
        # Limpiar nombres de columnas
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Mapeo de tus columnas exactas
        col_ing = 'ingresos bs' if moneda_archivo == "BS" else 'ingreso usd'
        col_egr = 'egresos bs' if moneda_archivo == "BS" else 'egreso usd'
        
        # Verificar si las columnas existen en la hoja
        if col_ing in df.columns and col_egr in df.columns:
            # Limpiar datos numéricos
            df[col_ing] = pd.to_numeric(df[col_ing], errors='coerce').fillna(0)
            df[col_egr] = pd.to_numeric(df[col_egr], errors='coerce').fillna(0)
            
            # Cálculos bimonetarios
            if moneda_archivo == "BS":
                df['total_bs'] = df[col_ing] - df[col_egr]
                df['total_usd'] = df['total_bs'] / tasa_cambio
            else:
                df['total_usd'] = df[col_ing] - df[col_egr]
                df['total_bs'] = df['total_usd'] * tasa_cambio
            
            # Agregar metadatos
            df['banco'] = nombre_banco
            df['mes_reporte'] = mes_label
            df['moneda_origen'] = moneda_archivo
            
            # Filtrar solo filas con movimientos o códigos GyP
            df_valido = df[ (df[col_ing] > 0) | (df[col_egr] > 0) | (df['gyp'].notna()) ].copy()
            lista_movimientos.append(df_valido)
            
    return pd.concat(lista_movimientos) if lista_movimientos else pd.DataFrame()

# --- INTERFAZ DE USUARIO ---
st.title("🏦 Adonai Industrial Group - ERP")
st.markdown("---")

# Sidebar de Control
with st.sidebar:
    st.header("⚙️ Configuración")
    mes_num = st.selectbox("Seleccione Mes:", range(1, 13), index=1) # Feb por defecto
    tasa = st.number_input("Tasa de Cambio (Bs/USD):", value=36.0, step=0.1)
    
    if st.button("🔄 Sincronizar con Drive"):
        service = conectar_drive()
        if service:
            n_bs = f"relacion de ingresos y egresos {mes_num} bs"
            n_usd = f"relacion de ingresos y egresos {mes_num} USD"
            
            with st.spinner("Leyendo archivos de Drive..."):
                d_bs = leer_excel_drive(service, n_bs)
                d_usd = leer_excel_drive(service, n_usd)
                
                if d_bs and d_usd:
                    res_bs = procesar_hojas(d_bs, "BS", tasa, f"Mes {mes_num}")
                    res_usd = procesar_hojas(d_usd, "USD", tasa, f"Mes {mes_num}")
                    
                    # Unir al histórico acumulado
                    nuevo_mes = pd.concat([res_bs, res_usd])
                    # Evitar duplicados si se pulsa el botón varias veces
                    if not st.session_state.datos_acumulados.empty:
                        st.session_state.datos_acumulados = st.session_state.datos_acumulados[
                            st.session_state.datos_acumulados['mes_reporte'] != f"Mes {mes_num}"
                        ]
                    st.session_state.datos_acumulados = pd.concat([st.session_state.datos_acumulados, nuevo_mes])
                    st.success(f"¡Mes {mes_num} sincronizado!")
                else:
                    st.error("Archivos no encontrados. Revisa los nombres y permisos en Drive.")

# --- DASHBOARD PRINCIPAL ---
if not st.session_state.datos_acumulados.empty:
    df_actual = st.session_state.datos_acumulados[st.session_state.datos_acumulados['mes_reporte'] == f"Mes {mes_num}"]
    
    # 1. Métricas Superiores
    ing_t = df_actual[df_actual['total_usd'] > 0]['total_usd'].sum()
    egr_t = abs(df_actual[df_actual['total_usd'] < 0]['total_usd'].sum())
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos Mes (USD)", f"$ {ing_t:,.2f}")
    c2.metric("Egresos Mes (USD)", f"$ {egr_t:,.2f}")
    c3.metric("Utilidad (USD)", f"$ {ing_t - egr_t:,.2f}")

    # 2. P&L Clasificado por columna GyP
    st.subheader("📊 Ganancias y Pérdidas (P&L)")
    pyl = df_actual.groupby('gyp')[['total_bs', 'total_usd']].sum().reset_index()
    st.dataframe(pyl.style.format({"total_bs": "{:,.2f}", "total_usd": "{:,.2f}"}), use_container_width=True)

    # 3. Gráfico Acumulado
    st.subheader("📈 Crecimiento Acumulado Anual")
    acumulado_grafico = st.session_state.datos_acumulados.groupby('mes_reporte')[['total_usd']].sum().reset_index()
    fig = px.bar(acumulado_grafico, x='mes_reporte', y='total_usd', title="Utilidad Mensual Acumulada")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👋 Bienvenido. Selecciona un mes y presiona 'Sincronizar con Drive' para ver los datos.")
