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
        
        conn_prov = database.conectar()
        if conn_prov:
            # Traemos el RIF, Nombre y Tipo de Persona para el sustraendo
            proveedores = pd.read_sql("SELECT rif, nombre, tipo_persona FROM entidades", conn_prov)
            conn_prov.close()
            
            if proveedores.empty:
                st.warning("⚠️ No hay proveedores registrados.")
            else:
                with st.form("form_compras", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fecha = st.date_input("Fecha", value=date.today())
                        # Creamos un diccionario para recuperar los datos del proveedor seleccionado
                        dict_prov = {f"{r} - {n}": {"rif": r, "tipo": t} 
                                    for r, n, t in zip(proveedores['rif'], proveedores['nombre'], proveedores['tipo_persona'])}
                        
                        seleccion = st.selectbox("Proveedor", options=list(dict_prov.keys()))
                        rif_actual = dict_prov[seleccion]["rif"]
                        tipo_persona_actual = dict_prov[seleccion]["tipo"]
                        
                        num_factura = st.text_input("Número de Factura")
                        num_control = st.text_input("Número de Control")

                    with col2:
                        monto_exento = st.number_input("Monto Exento", min_value=0.0, step=0.01)
                        base_imponible = st.number_input("Base Imponible", min_value=0.0, step=0.01)
                        iva_monto = round(base_imponible * 0.16, 2)
                        st.info(f"IVA Facturado: {iva_monto}")

                    st.divider()
                    st.subheader("⚙️ Configuración de Retenciones")
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        aplica_iva = st.checkbox("¿Retener IVA?")
                        pct_iva = st.selectbox("Porcentaje IVA", [75, 100], disabled=not aplica_iva)
                        iva_retenido = round(iva_monto * (pct_iva / 100), 2) if aplica_iva else 0.0
                        if aplica_iva:
                            st.caption(f"IVA a Retener: {iva_retenido}")

                    with c2:
                        aplica_islr = st.checkbox("¿Retener ISLR?", value=True)
                        opciones_islr = {
                            "001 - Honorarios Profesionales (3%)": 3.0,
                            "004 - Fletes (1%)": 1.0,
                            "009 - Ejecución de Obras/Servicios (2%)": 2.0
                        }
                        cod_islr = st.selectbox("Código ISLR", list(opciones_islr.keys()), disabled=not aplica_islr)
                        tasa = opciones_islr[cod_islr]
                        
                        # --- LÓGICA AUTOMÁTICA DE SUSTRAENDO ---
                        config = database.obtener_configuracion_empresa()
                        ut = config["ut_valor"]
                        
                        if aplica_islr:
                            monto_bruto_islr = base_imponible * (tasa / 100)
                            # El sustraendo solo aplica a Naturales Residentes
                            if tipo_persona_actual == "Natural Residente":
                                sustraendo = (ut * 83.3334) * (tasa / 100) # Factor común en Venezuela
                                islr_retenido = round(max(0, monto_bruto_islr - sustraendo), 2)
                                st.warning(f"Sustraendo aplicado (Persona Natural)")
                            else:
                                islr_retenido = round(monto_bruto_islr, 2)
                        else:
                            islr_retenido = 0.0
                            
                        if aplica_islr:
                            st.caption(f"ISLR a Retener: {islr_retenido}")

                    total_neto = round((monto_exento + base_imponible + iva_monto) - iva_retenido - islr_retenido, 2)
                    st.markdown(f"### Total Neto a Pagar: **{total_neto}**")
                    
                    if st.form_submit_button("Guardar Compra"):
                        try:
                            conn = database.conectar()
                            c = conn.cursor()
                            query = """
                                INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, 
                                monto_exento, base_imponible, iva_monto, iva_retenido, islr_retenido, total_factura)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            valores = (fecha, rif_actual, num_factura, num_control,
                                       monto_exento, base_imponible, iva_monto, iva_retenido, islr_retenido, total_neto)
                            c.execute(query, valores)
                            conn.commit()
                            conn.close()
                            st.success("✅ Compra guardada exitosamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error técnico: {e}")

    with tab2:
        st.subheader("📊 Libro de Compras")
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", range(1, 13), index=date.today().month - 1)
        with col2:
            año = st.number_input("Año", value=date.today().year)

        query_libro = """
            SELECT fecha, rif_proveedor, num_factura, num_control, monto_exento, 
            base_imponible, iva_monto, iva_retenido, islr_retenido, total_factura
            FROM compras WHERE EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
        """
        conn = database.conectar()
        if conn:
            df = pd.read_sql(query_libro, conn, params=[int(mes), int(año)])
            conn.close()
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel", output.getvalue(), f"Libro_{mes}_{año}.xlsx")
            else:
                st.info("Sin registros.")
                # Lógica para el sustraendo (Simplificada)
          datos_mi_empresa = database.obtener_datos_empresa()
          ut = datos_mi_empresa["ut"]

          # Si es Persona Natural Residente y el código es de honorarios (ejemplo)
         if tipo_persona_proveedor == "Natural Residente" and aplica_islr:
         sustraendo = (ut * 0.25) * (tasa / 100) # O la fórmula que aplique según la tabla
         islr_retenido = round((base_imponible * (tasa / 100)) - sustraendo, 2)
        else:
        islr_retenido = round(base_imponible * (tasa / 100), 2)
