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
    
    # ... (mantenemos la carga de proveedores que ya tienes) ...

    with st.form("form_compras", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha = st.date_input("Fecha de Factura", value=date.today())
            opciones_prov = {f"{r} - {n}": r for r, n in zip(proveedores['rif'], proveedores['nombre'])}
            prov_seleccionado = st.selectbox("Proveedor", options=list(opcodes_prov.keys()))
            num_factura = st.text_input("Número de Factura")
            num_control = st.text_input("Número de Control")

        with col2:
            monto_exento = st.number_input("Monto Exento (0%)", min_value=0.0, step=0.01)
            base_imponible = st.number_input("Base Imponible (16%)", min_value=0.0, step=0.01)
            iva_monto = round(base_imponible * 0.16, 2)
            st.info(f"IVA Facturado: {iva_monto}")

        st.divider()
        st.subheader("⚙️ Configuración de Retenciones")
        
        c1, c2 = st.columns(2)
        
        with c1:
            aplica_iva = st.checkbox("¿Generar Retención de IVA?")
            pct_iva = st.selectbox("Porcentaje de Retención IVA", [75, 100], disabled=not aplica_iva)
            iva_retenido = round(iva_monto * (pct_iva / 100), 2) if aplica_iva else 0.0
            if aplica_iva:
                st.warning(f"Monto a retener (IVA): {iva_retenido}")

        with c2:
            aplica_islr = st.checkbox("¿Generar Retención de ISLR?")
            # Códigos comunes en Venezuela
            dict_islr = {
                "001 - Honorarios Profesionales (3%)": 3.0,
                "002 - Servicios de Publicidad (3%)": 3.0,
                "003 - Comisiones (3%)": 3.0,
                "004 - Fletes (1%)": 1.0,
                "005 - Arrendamiento Inmuebles (3%)": 3.0,
                "009 - Ejecución de Obras/Servicios (2%)": 2.0
            }
            codigo_islr = st.selectbox("Código de Concepto ISLR", list(dict_islr.keys()), disabled=not aplica_islr)
            tasa_islr = dict_islr[codigo_islr]
            
            # Cálculo de ISLR (Base * Tasa)
            islr_retenido = round(base_imponible * (tasa_islr / 100), 2) if aplica_islr else 0.0
            if aplica_islr:
                st.warning(f"Monto a retener (ISLR {tasa_islr}%): {islr_retenido}")

        total_pagar = round((monto_exento + base_imponible + iva_monto) - iva_retenido - islr_retenido, 2)
        st.markdown(f"### Total Neto a Pagar: **{total_pagar}**")
        
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
