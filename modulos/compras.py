import streamlit as st
import pandas as pd
import database
from io import BytesIO
from datetime import date

def modulo_compras():
    st.title("📑 Gestión de Compras")
    
    tab1, tab2 = st.tabs(["Registrar Factura", "Libro de Compras (SENIAT)"])
    
    with tab1:
        st.subheader("📝 Nueva Factura de Compra")
        
        with st.form("form_compras", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                fecha = st.date_input("Fecha de Factura", value=date.today())
                # Buscamos los proveedores de la base de datos
                conn = database.conectar()
                proveedores = pd.read_sql("SELECT rif, nombre FROM entidades", conn)
                conn.close()
                
                opciones_prov = {f"{r} - {n}": r for r, n in zip(proveedores['rif'], proveedores['nombre'])}
                prov_seleccionado = st.selectbox("Proveedor", options=list(opciones_prov.keys()))
                
                num_factura = st.text_input("Número de Factura")
                num_control = st.text_input("Número de Control")

            with col2:
                monto_exento = st.number_input("Monto Exento (0%)", min_value=0.0, step=0.01)
                base_imponible = st.number_input("Base Imponible (16%)", min_value=0.0, step=0.01)
                
                # Cálculo automático de IVA
                iva_monto = round(base_imponible * 0.16, 2)
                st.write(f"**IVA (16%):** {iva_monto}")
                
                iva_retenido = st.number_input("IVA Retenido", min_value=0.0, step=0.01)
                islr_retenido = st.number_input("ISLR Retenido", min_value=0.0, step=0.01)

            total = round(monto_exento + base_imponible + iva_monto, 2)
            st.markdown(f"### Total Factura: **{total}**")
            
            submit = st.form_submit_button("Guardar Compra y Generar Asiento")

            if submit:
                try:
                    conn = database.conectar()
                    c = conn.cursor()
                    
                    # 1. Insertar en tabla Compras
                    query_compra = """
                        INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, 
                        monto_exento, base_imponible, iva_monto, iva_retenido, islr_retenido, total_factura)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    valores = (fecha, opciones_prov[prov_seleccionado], num_factura, num_control,
                               monto_exento, base_imponible, iva_monto, iva_retenido, islr_retenido, total)
                    
                    c.execute(query_compra, valores)
                    conn.commit()
                    c.close()
                    conn.close()
                    st.success("✅ Factura registrada exitosamente en el Libro de Compras.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    with tab2:
        # Aquí se queda el código que ya tienes para consultar y descargar el Excel
        st.subheader("Consulta de Libro de Compras")
        # ... (el resto del código que ya pegaste antes)import streamlit as st
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
