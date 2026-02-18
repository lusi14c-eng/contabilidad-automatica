import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Cloud Accounting Tool", layout="wide")

st.title("☁️ Automatización Contable en la Nube")
st.markdown("Sube tus archivos para generar el P&L y Asientos automáticamente.")

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    maestro = st.file_uploader("1. Maestro de Cuentas (Excel)", type=["xlsx"])
with col2:
    datos = st.file_uploader("2. Movimientos del Mes (Excel)", type=["xlsx"])

if maestro and datos:
    df_m = pd.read_excel(maestro)
    df_d = pd.read_excel(datos)
    
    # --- PROCESAMIENTO ---
    # Unimos los movimientos con el maestro usando el código de cuenta
    # Se asume que 'df_d' tiene columna 'Codigo' y 'df_m' también
    df_unificado = pd.merge(df_d, df_m, on="Codigo", how="left")
    
    # --- 1. GENERACIÓN DE P&L ---
    st.header("📊 Estado de Ganancias y Pérdidas")
    pnl = df_unificado.groupby("Categoria P&L")["Monto"].sum().reset_index()
    
    # Cálculo de utilidad (Ingresos - Egresos)
    ingresos = pnl[pnl["Categoria P&L"].str.contains("Ingreso", case=False, na=False)]["Monto"].sum()
    egresos = pnl[pnl["Categoria P&L"].str.contains("Gasto|Costo", case=False, na=False)]["Monto"].sum()
    utilidad = ingresos - egresos
    
    st.table(pnl)
    st.metric("Utilidad Neta", f"{utilidad:,.2f}", delta_color="normal")

    # --- 2. GENERACIÓN DE ASIENTOS CONTABLES ---
    st.header("📝 Libro Diario Automático")
    asientos_list = []
    for _, row in df_unificado.iterrows():
        # Línea del DEBE
        asientos_list.append({
            "Fecha": row.get("Fecha", "S/F"),
            "Cuenta": row["Cuenta Contable (Debe)"],
            "Descripción": row.get("Descripcion", ""),
            "Débito": row["Monto"],
            "Crédito": 0
        })
        # Línea del HABER
        asientos_list.append({
            "Fecha": row.get("Fecha", "S/F"),
            "Cuenta": row["Cuenta Contable (Haber)"],
            "Descripción": row.get("Descripcion", ""),
            "Débito": 0,
            "Crédito": row["Monto"]
        })
    
    df_asientos = pd.DataFrame(asientos_list)
    st.dataframe(df_asientos)

    # --- 3. BOTÓN DE DESCARGA (Excel en Memoria) ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_asientos.to_excel(writer, index=False, sheet_name='Asientos')
        pnl.to_excel(writer, index=False, sheet_name='PyL')
    
    st.download_button(
        label="📥 Descargar Resultado Final",
        data=output.getvalue(),
        file_name="Resultado_Contable.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
