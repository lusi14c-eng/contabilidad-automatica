import streamlit as st
import pandas as pd
import database
from io import BytesIO

def modulo_compras():
    st.title("📑 Gestión de Compras")
    
    tab1, tab2 = st.tabs(["Registrar Factura", "Libro de Compras (SENIAT)"])
    
    with tab1:
        st.subheader("Nueva Compra")
        # Aquí mantén tu formulario de registro actual...
        st.info("Complete los datos de la factura para procesar.")

    with tab2:
        st.subheader("Consulta de Libro de Compras")
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", range(1, 13))
        with col2:
            año = st.number_input("Año", value=2024)

        # QUERY CORREGIDO PARA EVITAR EL INDEX ERROR
        query = """
            SELECT 
                fecha AS "Fecha",
                rif_proveedor AS "RIF Proveedor",
                num_factura AS "Nro Factura",
                num_control AS "Nro Control",
                monto_exento AS "Exento",
                base_imponible AS "Base Imponible",
                iva_monto AS "IVA",
                iva_retenido AS "IVA Retenido",
                islr_retenido AS "ISLR Retenido",
                total_factura AS "Total"
            FROM compras 
            WHERE EXTRACT(MONTH FROM fecha) = %s 
              AND EXTRACT(YEAR FROM fecha) = %s
            ORDER BY fecha ASC
        """
        
        conn = database.conectar()
        if conn:
            # Pasamos los parámetros como una lista [mes, año]
            df = pd.read_sql(query, conn, params=[int(mes), int(año)])
            conn.close()

            if not df.empty:
                st.dataframe(df, use_container_width=True)

                # --- LÓGICA DE EXPORTACIÓN A EXCEL ---
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='LibroCompras')
                
                st.download_button(
                    label="📥 Descargar Libro en Excel",
                    data=output.getvalue(),
                    file_name=f"Libro_Compras_{mes}_{año}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("No hay registros para este período.")
