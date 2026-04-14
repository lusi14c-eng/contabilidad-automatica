import streamlit as st
import pandas as pd
import database
from io import BytesIO

def modulo_compras():
    st.title("📑 Registro y Libro de Compras")
    
    # --- Pestañas para organizar el módulo ---
    tab1, tab2 = st.tabs(["Registrar Factura", "Consultar Libro de Compras"])
    
    with tab1:
        # Aquí va tu formulario de registro (el que ya tienes)
        # Asegúrate de que al guardar, uses %s para los valores
        st.write("Formulario de registro...")

    with tab2:
        st.subheader("Libro de Compras Mensual")
        
        # Filtros de fecha
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", range(1, 13), index=0)
        with col2:
            año = st.number_input("Año", value=2024)

        # Consulta SQL a Neon
        query = """
            SELECT 
                fecha as "Fecha",
                rif_proveedor as "RIF",
                num_factura as "Factura",
                num_control as "Control",
                monto_exento as "Monto Exento",
                base_imponible as "Base Imponible",
                iva_monto as "IVA (16%)",
                iva_retenido as "IVA Retenido",
                total_factura as "Total"
            FROM compras 
            WHERE EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
        """
        
        conn = database.conectar()
        df = pd.read_sql(query, conn, params=(mes, año))
        conn.close()

        if not df.empty:
            st.dataframe(df)

            # --- BOTÓN PARA DESCARGAR EXCEL ---
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Libro_Compras')
            
            st.download_button(
                label="📥 Descargar Libro de Compras (Excel)",
                data=output.getvalue(),
                file_name=f"Libro_Compras_{mes}_{año}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No hay registros para este período.")
