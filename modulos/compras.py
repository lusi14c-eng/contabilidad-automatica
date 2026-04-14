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
        
        # Conexión para traer proveedores
        conn_prov = database.conectar()
        if conn_prov:
            proveedores = pd.read_sql("SELECT rif, nombre FROM entidades", conn_prov)
            conn_prov.close()
            
            if proveedores.empty:
                st.warning("⚠️ No hay proveedores registrados. Por favor, registre uno en el módulo 'Registrar Entidad' antes de continuar.")
            else:
                with st.form("form_compras", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fecha = st.date_input("Fecha de Factura", value=date.today())
                        opciones_prov = {f"{r} - {n}": r for r, n in zip(proveedores['rif'], proveedores['nombre'])}
                        prov_seleccionado = st.selectbox("Proveedor", options=list(opciones_prov.keys()))
                        num_factura = st.text_input("Número de Factura")
                        num_control = st.text_input("Número de Control")

                    with col2:
                        monto_exento = st.number_input("Monto Exento (0%)", min_value=0.0, step=0.01)
                        base_imponible = st.number_input("Base Imponible (16%)", min_value=0.0, step=0.01)
                        iva_monto = round(base_imponible * 0.16, 2)
                        st.info(f"IVA calculado (16%): {iva_monto}")
                        iva_retenido = st.number_input("IVA Retenido", min_value=0.0, step=0.01)
                        islr_retenido = st.number_input("ISLR Retenido", min_value=0.0, step=0.01)

                    total = round(monto_exento + base_imponible + iva_monto, 2)
                    st.markdown(f"### Total Factura: **{total}**")
                    
                    submit = st.form_submit_button("Guardar Compra")

                    if submit:
                        try:
                            conn = database.conectar()
                            c = conn.cursor()
                            query = """
                                INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, 
                                monto_exento, base_imponible, iva_monto, iva_retenido, islr_retenido, total_factura)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            valores = (fecha, opciones_prov[prov_seleccionado], num_factura, num_control,
                                       monto_exento, base_imponible, iva_monto, iva_retenido, islr_retenido, total)
                            c.execute(query, valores)
                            conn.commit()
                            c.close()
                            conn.close()
                            st.success("✅ Factura registrada con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

    with tab2:
        st.subheader("Consulta de Libro de Compras")
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", range(1, 13), index=date.today().month - 1)
        with col2:
            año = st.number_input("Año", value=date.today().year)

        query_libro = """
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
            df = pd.read_sql(query_libro, conn, params=[int(mes), int(año)])
            conn.close()

            if not df.empty:
                st.dataframe(df, use_container_width=True)
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
                st.info("No hay registros para este período.")
