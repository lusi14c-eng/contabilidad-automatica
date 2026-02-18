import streamlit as st
import pandas as pd
import io
import plotly.express as px  # Asegúrate de añadir 'plotly' a tu requirements.txt

# Configuración de página
st.set_page_config(page_title="Adonai Industrial Group - Dashboard", layout="wide")

# --- ENCABEZADO PERSONALIZADO ---
st.markdown(f"""
    <div style="background-color:#1E3A8A;padding:20px;border-radius:10px;margin-bottom:20px">
    <h1 style="color:white;text-align:center;margin:0;">ADONAI INDUSTRIAL GROUP</h1>
    <h3 style="color:white;text-align:center;margin:0;opacity:0.8;">Panel de Inteligencia Financiera</h3>
    </div>
    """, unsafe_allow_html=True)

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
            df.columns = [str(c).strip().lower() for c in df.columns]

            for _, row in df.iterrows():
                # Lógica Ingreso
                if pd.notnull(row.get('ingreso')) and row['ingreso'] > 0:
                    cod = row.get('codigo de ingreso')
                    match = df_m[df_m['Codigo'] == cod]
                    if not match.empty:
                        monto = row['ingreso']
                        movimientos_pnl.append({"Categoría": match['Categoría P&L'].values[0], "Monto": monto, "Tipo": "Ingreso"})
                        # (Lógica de asientos omitida aquí por brevedad, se mantiene igual al anterior)

                # Lógica Egreso
                if pd.notnull(row.get('egreso')) and row['egreso'] > 0:
                    cod = row.get('codigo de egreso')
                    match = df_m[df_m['Codigo'] == cod]
                    if not match.empty:
                        monto = row['egreso']
                        movimientos_pnl.append({"Categoría": match['Categoría P&L'].values[0], "Monto": monto, "Tipo": "Egreso"})

    # --- PROCESAMIENTO DE GRÁFICOS ---
    df_pnl_raw = pd.DataFrame(movimientos_pnl)
    
    tab1, tab2 = st.tabs(["📊 Análisis Gerencial (P&L)", "📒 Libro Diario"])

    with tab1:
        if not df_pnl_raw.empty:
            # Métricas Superiores
            total_ingresos = df_pnl_raw[df_pnl_raw["Tipo"] == "Ingreso"]["Monto"].sum()
            total_egresos = df_pnl_raw[df_pnl_raw["Tipo"] == "Egreso"]["Monto"].sum()
            utilidad = total_ingresos - total_egresos
            
            m1, m2, m3 = st.columns(3)
            m1.metric("TOTAL INGRESOS", f"Bs. {total_ingresos:,.2f}")
            m2.metric("TOTAL EGRESOS", f"Bs. {total_egresos:,.2f}", delta=f"-{total_egresos:,.2f}", delta_color="inverse")
            m3.metric("UTILIDAD NETA", f"Bs. {utilidad:,.2f}", delta=f"{(utilidad/total_ingresos)*100:.1f}% Margen" if total_ingresos > 0 else "0%")

            st.write("---")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("Distribución de Gastos y Costos")
                df_gastos = df_pnl_raw[df_pnl_raw["Tipo"] == "Egreso"].groupby("Categoría")["Monto"].sum().reset_index()
                fig_pie = px.pie(df_gastos, values='Monto', names='Categoría', hole=0.4, 
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_chart2:
                st.subheader("Comparativa por Categoría")
                df_cat = df_pnl_raw.groupby(["Categoría", "Tipo"])["Monto"].sum().reset_index()
                fig_bar = px.bar(df_cat, x="Categoría", y="Monto", color="Tipo", barmode="group",
                                 color_discrete_map={"Ingreso": "#10B981", "Egreso": "#EF4444"})
                st.plotly_chart(fig_bar, use_container_width=True)
            
            st.write("### Detalle Contable del P&L")
            resumen_tabla = df_pnl_raw.groupby(["Categoría", "Tipo"])["Monto"].sum().unstack().fillna(0)
            st.table(resumen_tabla.style.format("{:,.2f}"))
        else:
            st.warning("No hay datos suficientes para generar gráficos.")

    with tab2:
        st.info("Aquí se mostrará el listado de asientos contables para exportar.")
        # (Aquí va el código del DataFrame de asientos del paso anterior)

else:
    st.info("👋 Bienvenido. Cargue los archivos para visualizar el análisis de Adonai Industrial Group.")
