import streamlit as st
import pandas as pd
import database
from datetime import date
from io import BytesIO

def modulo_compras():
    st.title("📑 Registro y Control de Compras")
    conf = database.obtener_configuracion_empresa()
    
    tab1, tab2 = st.tabs(["✍️ Registrar Factura", "📊 Libro de Compras"])
    
    with tab1:
        # --- CARGA DE DATOS ---
        conn = database.conectar()
        prov_df = pd.read_sql("SELECT rif, nombre, tipo_persona FROM entidades", conn)
        conn.close()

        if prov_df.empty:
            st.warning("⚠️ Registra un proveedor primero.")
        else:
            with st.form("form_nueva_compra", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    fecha = st.date_input("Fecha", value=date.today())
                    dict_prov = {row['nombre']: row for _, row in prov_df.iterrows()}
                    nombre_p = st.selectbox("Proveedor", list(dict_prov.keys()))
                    p_datos = dict_prov[nombre_p] # Datos del proveedor seleccionado
                    num_f = st.text_input("N° Factura")
                    num_c = st.text_input("N° Control")

                with col2:
                    m_exento = st.number_input("Exento", min_value=0.0)
                    base_i = st.number_input("Base Imponible", min_value=0.0)
                    iva_f = round(base_i * 0.16, 2)
                    st.info(f"IVA: {iva_f}")

                st.divider()
                st.subheader("⚙️ Retenciones Automáticas")
                c1, c2 = st.columns(2)

                with c1:
                    ap_iva = st.checkbox("¿Retener IVA?")
                    p_iva = st.selectbox("% IVA", [75, 100], disabled=not ap_iva)
                    iva_ret = round(iva_f * (p_iva / 100), 2) if ap_iva else 0.0

                with c2:
                    ap_islr = st.checkbox("¿Retener ISLR?", value=True)
                    opciones = {"Honorarios (3%)": 3.0, "Servicios (2%)": 2.0, "Fletes (1%)": 1.0}
                    conc = st.selectbox("Concepto", list(opciones.keys()), disabled=not ap_islr)
                    tasa = opciones[conc]

                    # --- LÓGICA DE SUSTRAENDO ---
                    monto_sustraendo = 0.0
                    # Solo aplica si es Natural Residente (Regla SENIAT)
                    if ap_islr and p_datos['tipo_persona'] == "Natural Residente":
                        # Fórmula legal: (83.3334 * UT * tasa) / 100
                        monto_sustraendo = round((83.3334 * conf['ut_valor'] * tasa) / 100, 2)
                    
                    islr_ret = round((base_i * tasa / 100) - monto_sustraendo, 2)
                    if islr_ret < 0: islr_ret = 0.0
                    
                    if ap_islr:
                        st.warning(f"Retención: {islr_ret} (Sustraendo: {monto_sustraendo})")

                total = round((m_exento + base_i + iva_f) - iva_ret - islr_ret, 2)
                st.markdown(f"### Neto a Pagar: **{total}**")

                if st.form_submit_button("Guardar"):
                    conn = database.conectar()
                    c = conn.cursor()
                    query = """INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, 
                               monto_exento, base_imponible, iva_monto, islr_retenido, iva_retenido, total_factura) 
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                    c.execute(query, (fecha, p_datos['rif'], num_f, num_c, m_exento, base_i, iva_f, islr_ret, iva_ret, total))
                    conn.commit()
                    conn.close()
                    st.success("Guardado.")
                    st.rerun()

    with tab2:
        st.subheader("📊 Libro de Compras Mensual")
        col_m, col_a = st.columns(2)
        mes = col_m.selectbox("Mes", range(1, 13), index=date.today().month-1)
        ano = col_a.number_input("Año", value=date.today().year)

        query_l = """SELECT fecha, rif_proveedor, num_factura, num_control, monto_exento, 
                     base_imponible, iva_monto, iva_retenido, islr_retenido, total_factura 
                     FROM compras WHERE EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s"""
        
        conn = database.conectar()
        df = pd.read_sql(query_l, conn, params=[int(mes), int(ano)])
        conn.close()

        if not df.empty:
            st.dataframe(df, use_container_width=True)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='LibroCompras')
            st.download_button("📥 Descargar Libro Excel", output.getvalue(), f"Libro_{mes}_{ano}.xlsx")
        else:
            st.info("No hay datos para este período.")
