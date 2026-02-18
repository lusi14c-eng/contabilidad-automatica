import streamlit as st
import pandas as pd
import io

# Configuración de página
st.set_page_config(page_title="Adonai Industrial Group - Contabilidad", layout="wide")

# --- ENCABEZADO PERSONALIZADO ---
st.markdown(f"""
    <div style="background-color:#1E3A8A;padding:20px;border-radius:10px">
    <h1 style="color:white;text-align:center;">ADONAI INDUSTRIAL GROUP</h1>
    <h3 style="color:white;text-align:center;">Sistema de Automatización Contable v1.0</h3>
    </div>
    """, unsafe_allow_html=True)

st.write("---")

# --- BARRA LATERAL ---
st.sidebar.header("📁 Carga de Documentación")
archivo_maestro = st.sidebar.file_uploader("Subir Maestro de Cuentas (Cerebro)", type=["xlsx"])
archivo_datos = st.sidebar.file_uploader("Subir Libro de Bancos (Movimientos)", type=["xlsx"])

if archivo_maestro and archivo_datos:
    # 1. Cargar Configuración
    df_m = pd.read_excel(archivo_maestro, sheet_name="Maestro_Cuentas")
    df_b = pd.read_excel(archivo_maestro, sheet_name="Bancos")
    dict_bancos = pd.Series(df_b["Cuenta Contable Banco"].values, index=df_b["Nombre Pestaña"]).to_dict()

    # 2. Cargar Movimientos
    dict_hojas = pd.read_excel(archivo_datos, sheet_name=None)
    
    asientos_list = []
    movimientos_pnl = []

    for banco, df in dict_hojas.items():
        if banco in dict_bancos:
            cta_banco = dict_bancos[banco]
            # Normalizar nombres de columnas
            df.columns = [str(c).strip().lower() for c in df.columns]

            for _, row in df.iterrows():
                # Lógica Ingreso
                if pd.notnull(row.get('ingreso')) and row['ingreso'] > 0:
                    cod = row.get('codigo de ingreso')
                    match = df_m[df_m['Codigo'] == cod]
                    if not match.empty:
                        monto = row['ingreso']
                        cta_contra = match['Cuenta Contable'].values[0]
                        cat_pnl = match['Categoría P&L'].values[0]
                        
                        asientos_list.append({"Fecha": row.get('fecha'), "Banco": banco, "Cuenta": cta_banco, "Debe": monto, "Haber": 0})
                        asientos_list.append({"Fecha": row.get('fecha'), "Banco": banco, "Cuenta": cta_contra, "Debe": 0, "Haber": monto})
                        movimientos_pnl.append({"Categoría": cat_pnl, "Monto": monto})

                # Lógica Egreso
                if pd.notnull(row.get('egreso')) and row['egreso'] > 0:
                    cod = row.get('codigo de egreso')
                    match = df_m[df_m['Codigo'] == cod]
                    if not match.empty:
                        monto = row['egreso']
                        cta_contra = match['Cuenta Contable'].values[0]
                        cat_pnl = match['Categoría P&L'].values[0]
                        
                        asientos_list.append({"Fecha": row.get('fecha'), "Banco": banco, "Cuenta": cta_contra, "Debe": monto, "Haber": 0})
                        asientos_list.append({"Fecha": row.get('fecha'), "Banco": banco, "Cuenta": cta_banco, "Debe": 0, "Haber": monto})
                        movimientos_pnl.append({"Categoría": cat_pnl, "Monto": -monto})

    # --- DESPLIEGUE DE RESULTADOS ---
    tab1, tab2 = st.tabs(["📊 Ganancias y Pérdidas", "📒 Libro Diario Consolidados"])

    with tab1:
        st.subheader("Estado de Resultados del Periodo")
        if movimientos_pnl:
            resumen_pnl = pd.DataFrame(movimientos_pnl).groupby("Categoría")["Monto"].sum().reset_index()
            # Formatear para que se vea mejor
            resumen_pnl["Monto"] = resumen_pnl["Monto"].map("{:,.2f}".format)
            st.table(resumen_pnl)
            
            total_neto = pd.DataFrame(movimientos_pnl)["Monto"].sum()
            st.metric("UTILIDAD / PÉRDIDA NETA", f"Bs. {total_neto:,.2f}")

    with tab2:
        st.subheader("Asientos Contables Generados")
        if asientos_list:
            df_asientos = pd.DataFrame(asientos_list)
            st.dataframe(df_asientos, use_container_width=True)
            
            # Exportar a Excel
            buffer = io.BytesIO()
            df_asientos.to_excel(buffer, index=False)
            st.download_button(label="📥 Descargar Asientos en Excel", data=buffer.getvalue(), file_name="Asientos_Adonai.xlsx")

else:
    st.info("👋 Bienvenido al portal de Adonai Industrial Group. Cargue los archivos en la izquierda para procesar.")
