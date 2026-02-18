import streamlit as st
import pandas as pd
import io
import plotly.express as px

# 1. Configuración de página
st.set_page_config(page_title="Adonai Industrial Group - Contabilidad", layout="wide")

# 2. Encabezado Corporativo
st.markdown(f"""
    <div style="background-color:#1E3A8A;padding:20px;border-radius:10px;margin-bottom:25px">
    <h1 style="color:white;text-align:center;margin:0;">ADONAI INDUSTRIAL GROUP</h1>
    <h3 style="color:white;text-align:center;margin:0;opacity:0.8;">Sistema de Automatización Contable Multibanco</h3>
    </div>
    """, unsafe_allow_html=True)

# 3. Barra Lateral para carga de archivos
st.sidebar.header("📁 Carga de Datos")
archivo_maestro = st.sidebar.file_uploader("1. Subir Maestro de Cuentas (Cerebro)", type=["xlsx"])
archivo_datos = st.sidebar.file_uploader("2. Subir Libro de Bancos (Movimientos)", type=["xlsx"])

if archivo_maestro and archivo_datos:
    try:
        # Carga del Cerebro
        df_m = pd.read_excel(archivo_maestro, sheet_name="Maestro_Cuentas")
        df_b = pd.read_excel(archivo_maestro, sheet_name="Bancos")
        
        # Limpieza básica de datos en el maestro
        df_m['Codigo'] = df_m['Codigo'].astype(str).str.strip()
        dict_bancos = pd.Series(df_b["Cuenta Contable Banco"].values, index=df_b["Nombre Pestaña"]).to_dict()
        
        # Carga de Movimientos (Todas las pestañas)
        dict_hojas = pd.read_excel(archivo_datos, sheet_name=None)
        
    except Exception as e:
        st.error(f"❌ Error al leer los archivos: {e}")
        st.info("Asegúrese de que las pestañas se llamen 'Maestro_Cuentas' y 'Bancos'.")
        st.stop()

    asientos_list = []
    movimientos_pnl = []

    # 4. Procesamiento Lógico
    for banco, df in dict_hojas.items():
        if banco in dict_bancos:
            cta_banco = dict_bancos[banco]
            # Normalizar nombres de columnas a minúsculas y sin espacios
            df.columns = [str(c).strip().lower() for c in df.columns]

            for _, row in df.iterrows():
                # --- PROCESAR INGRESOS ---
                if pd.notnull(row.get('ingreso')) and row['ingreso'] > 0:
                    monto = row['ingreso']
                    cod = str(row.get('codigo de ingreso', '')).strip()
                    match = df_m[df_m['Codigo'] == cod]
                    
                    if not match.empty:
                        cta_contra = match['Cuenta Contable'].values[0]
                        cat_pnl = match['Categoría P&L'].values[0]
                        desc = row.get('descripcion', 'Ingreso Bancario')
                        fecha = row.get('fecha', 'S/F')

                        asientos_list.append({"Fecha": fecha, "Banco": banco, "Cuenta": cta_banco, "Debe": monto, "Haber": 0, "Glosa": desc})
                        asientos_list.append({"Fecha": fecha, "Banco": banco, "Cuenta": cta_contra, "Debe": 0, "Haber": monto, "Glosa": desc})
                        movimientos_pnl.append({"Categoría": cat_pnl, "Monto": monto, "Tipo": "Ingreso"})

                # --- PROCESAR EGRESOS ---
                if pd.notnull(row.get('egreso')) and row['egreso'] > 0:
                    monto = row['egreso']
                    cod = str(row.get('codigo de egreso', '')).strip()
                    match = df_m[df_m['Codigo'] == cod]
                    
                    if not match.empty:
                        cta_contra = match['Cuenta Contable'].values[0]
                        cat_pnl = match['Categoría P&L'].values[0]
                        desc = row.get('descripcion', 'Egreso Bancario')
                        fecha = row.get('fecha', 'S/F')

                        asientos_list.append({"Fecha": fecha, "Banco": banco, "Cuenta": cta_contra, "Debe": monto, "Haber": 0, "Glosa": desc})
                        asientos_list.append({"Fecha": fecha, "Banco": banco, "Cuenta": cta_banco, "Debe": 0, "Haber": monto, "Glosa": desc})
                        movimientos_pnl.append({"Categoría": cat_pnl, "Monto": monto, "Tipo": "Egreso"})

    # 5. Interfaz de Resultados (Tabs)
    tab1, tab2 = st.tabs(["📊 Análisis Gerencial (P&L)", "📒 Libro Diario Consolidados"])

    with tab1:
        if movimientos_pnl:
            df_pnl_raw = pd.DataFrame(movimientos_pnl)
            
            # Métricas
            t_ingresos = df_pnl_raw[df_pnl_raw["Tipo"] == "Ingreso"]["Monto"].sum()
            t_egresos = df_pnl_raw[df_pnl_raw["Tipo"] == "Egreso"]["Monto"].sum()
            utilidad = t_ingresos - t_egresos
            
            c1, c2, c3 = st.columns(3)
            c1.metric("TOTAL INGRESOS", f"Bs. {t_ingresos:,.2f}")
            c2.metric("TOTAL EGRESOS", f"Bs. {t_egresos:,.2f}", delta=f"-{t_egresos:,.2f}", delta_color="inverse")
            c3.metric("UTILIDAD NETA", f"Bs. {utilidad:,.2f}")

            st.write("---")
            
            # Gráficos
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("Distribución de Gastos")
                df_gastos = df_pnl_raw[df_pnl_raw["Tipo"] == "Egreso"].groupby("Categoría")["Monto"].sum().reset_index()
                fig_pie = px.pie(df_gastos, values='Monto', names='Categoría', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with g2:
                st.subheader("Ingresos vs Egresos por Categoría")
                df_cat = df_pnl_raw.groupby(["Categoría", "Tipo"])["Monto"].sum().reset_index()
                fig_bar = px.bar(df_cat, x="Categoría", y="Monto", color="Tipo", barmode="group",
                                 color_discrete_map={"Ingreso": "#10B981", "Egreso": "#EF4444"})
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("No se encontraron movimientos válidos para generar el P&L.")

    with tab2:
        if asientos_list:
            df_final_asientos = pd.DataFrame(asientos_list)
            st.dataframe(df_final_asientos, use_container_width=True)
            
            # Botón de Descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final_asientos.to_excel(writer, index=False, sheet_name='Asientos')
            
            st.download_button(
                label="📥 Descargar Libro Diario para Adonai",
                data=output.getvalue(),
                file_name="Asientos_Contables_Adonai.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("👋 Bienvenido. Cargue el Maestro y el Libro de Bancos para comenzar el análisis de Adonai Industrial Group.")
    st.markdown("""
    **Estructura esperada:**
    - **Maestro:** Pestañas 'Maestro_Cuentas' y 'Bancos'.
    - **Bancos:** Pestañas con nombres de bancos, columnas 'fecha', 'ingreso', 'egreso', 'codigo de ingreso', 'codigo de egreso'.
    """)
