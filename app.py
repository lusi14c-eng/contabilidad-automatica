import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Cloud Accounting Tool", layout="wide")

st.title("☁️ Automatización Contable en la Nube")

# --- CARGA DE ARCHIVOS ---
st.sidebar.header("📥 Entrada de Datos")
maestro = st.sidebar.file_uploader("1. Maestro de Cuentas (Excel)", type=["xlsx"])
datos = st.sidebar.file_uploader("2. Movimientos del Mes (Excel)", type=["xlsx"])

if maestro and datos:
    # Leer archivos
    df_m = pd.read_excel(maestro)
    df_d = pd.read_excel(datos)
    
    # Cruce de datos (Join)
    df_unificado = pd.merge(df_d, df_m, on="Codigo", how="left")

    # --- CREACIÓN DE BOTONES/PESTAÑAS ---
    # Usaremos tabs para una navegación más limpia
    tab1, tab2 = st.tabs(["📊 Ganancias y Pérdidas (P&L)", "📝 Asientos Contables"])

    with tab1:
        st.header("Estado de Resultados Dinámico")
        
        # Agrupar por Categoría de P&L
        pnl = df_unificado.groupby("Categoría P&L")["Monto"].sum().reset_index()
        
        # Mostrar métricas rápidas
        ingresos = pnl[pnl["Categoría P&L"].str.contains("Ingreso", case=False, na=False)]["Monto"].sum()
        egresos = pnl[pnl["Categoría P&L"].str.contains("Gasto|Costo", case=False, na=False)]["Monto"].sum()
        utilidad = ingresos - egresos
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Ingresos", f"{ingresos:,.2f}")
        c2.metric("Total Egresos", f"{egresos:,.2f}")
        c3.metric("Utilidad Neta", f"{utilidad:,.2f}", delta=f"{utilidad:,.2f}")
        
        st.table(pnl)

    with tab2:
        st.header("Generador de Asientos (Libro Diario)")
        
        asientos_list = []
        for _, row in df_unificado.iterrows():
            # Registro DEBE
            asientos_list.append({
                "Fecha": row.get("Fecha", "S/F"),
                "Cuenta": row["Cuenta Contable (Debe)"],
                "Glosa": row.get("Descripción", "Registro Automático"),
                "Débito": row["Monto"],
                "Crédito": 0
            })
            # Registro HABER
            asientos_list.append({
                "Fecha": row.get("Fecha", "S/F"),
                "Cuenta": row["Cuenta Contable (Haber)"],
                "Glosa": row.get("Descripción", "Registro Automático"),
                "Débito": 0,
                "Crédito": row["Monto"]
            })
        
        df_asientos = pd.DataFrame(asientos_list)
        st.dataframe(df_asientos, use_container_width=True)

        # Botón para descargar solo los asientos si el usuario lo desea
        output = io.BytesIO()
        df_asientos.to_excel(output, index=False, engine='openpyxl')
        st.download_button(
            label="📥 Descargar Libro Diario (Excel)",
            data=output.getvalue(),
            file_name="asientos_contables.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👋 Bienvenida/o. Por favor, sube los archivos en la barra lateral para comenzar a procesar.")
    # Imagen explicativa de la estructura esperada
    st.image("https://img.freepik.com/free-vector/financial-administration-concept-illustration_114360-1941.jpg", width=400)
