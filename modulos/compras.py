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
        conn = database.conectar()
        # Traemos proveedores y cuentas contables
        prov_df = pd.read_sql("SELECT rif, nombre, tipo_persona FROM entidades", conn)
        cuentas_df = pd.read_sql("SELECT codigo, nombre FROM cuentas_contables", conn)
        conn.close()

        if prov_df.empty:
            st.warning("⚠️ Registra un proveedor primero en el módulo de Entidades.")
        else:
            with st.form("form_nueva_compra", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Datos del Documento")
                    fecha_doc = st.date_input("Fecha de la Factura", value=date.today())
                    
                    dict_prov = {row['nombre']: row for _, row in prov_df.iterrows()}
                    nombre_p = st.selectbox("Proveedor", list(dict_prov.keys()))
                    p_datos = dict_prov[nombre_p]
                    
                    num_f = st.text_input("N° Factura")
                    num_c = st.text_input("N° Control")
                    
                    # NUEVO: Subtipo y Cuenta
                    subtipo = st.selectbox("Tipo de Compra", ["Bienes", "Servicios", "Activo Fijo"])
                    
                    if not cuentas_df.empty:
                        dict_cuentas = {f"{r['codigo']} - {r['nombre']}": r['codigo'] for _, r in cuentas_df.iterrows()}
                        cuenta_asig = st.selectbox("Cuenta Contable de Gasto/Activo", list(dict_cuentas.keys()))
                        cod_cuenta = dict_cuentas[cuenta_asig]
                    else:
                        st.error("⚠️ No hay cuentas contables creadas.")
                        cod_cuenta = None

                with col2:
                    st.subheader("Montos y Totales")
                    m_exento = st.number_input("Monto Exento", min_value=0.0, step=0.01)
                    base_i = st.number_input("Base Imponible (Gravable)", min_value=0.0, step=0.01)
                    iva_f = round(base_i * 0.16, 2)
                    st.info(f"IVA (16%): {iva_f}")
                    
                    st.divider()
                    st.write("**Resumen de Retenciones**")
                    
                    # Lógica de Retención IVA según Configuración Empresa
                    mi_tipo = conf.get('tipo_contribuyente', 'Ordinario')
                    es_especial = True if mi_tipo == "Especial" else False
                    ap_iva = st.checkbox("Retener IVA", value=es_especial)
                    p_iva = st.selectbox("% Retención IVA", [75, 100], index=0, disabled=not ap_iva)
                    iva_ret = round(iva_f * (p_iva / 100), 2) if ap_iva else 0.0
                    
                    # Lógica ISLR
                    ap_islr = st.checkbox("Retener ISLR", value=True)
                    opciones_islr = {"Honorarios (3%)": 3.0, "Servicios (2%)": 2.0, "Fletes (1%)": 1.0}
                    conc = st.selectbox("Concepto ISLR", list(opciones_islr.keys()), disabled=not ap_islr)
                    tasa = opciones_islr[conc]
                    
                    monto_sustraendo = 0.0
                    if ap_islr and p_datos['tipo_persona'] == "Natural Residente":
                        monto_sustraendo = round((conf['factor_sustraendo'] * conf['ut_valor'] * tasa) / 100, 2)
                    
                    islr_ret = round((base_i * tasa / 100) - monto_sustraendo, 2)
                    if islr_ret < 0: islr_ret = 0.0
                    
                    st.warning(f"IVA Retenido: {iva_ret} | ISLR Retenido: {islr_ret}")

                total_neto = round((m_exento + base_i + iva_f) - iva_ret - islr_ret, 2)
                st.markdown(f"### Total a Pagar al Proveedor: **{total_neto} Bs.**")

                if st.form_submit_button("📥 Registrar Compra"):
                    if not num_f or not cod_cuenta:
                        st.error("Por favor rellene el N° de factura y asigne una cuenta.")
                    else:
                        try:
                            conn = database.conectar()
                            c = conn.cursor()
                            # Insertar con fecha de documento y subtipo
                            query = """INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, 
                                       monto_exento, base_imponible, iva_monto, islr_retenido, iva_retenido, 
                                       total_factura, subtipo) 
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                            c.execute(query, (fecha_doc, p_datos['rif'], num_f, num_c, m_exento, base_i, 
                                              iva_f, islr_ret, iva_ret, total_neto, subtipo))
                            conn.commit()
                            conn.close()
                            st.success("✅ Factura registrada exitosamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

    with tab2:
        st.subheader("📊 Libro de Compras")
        col_m, col_a = st.columns(2)
        mes = col_m.selectbox("Mes", range(1, 13), index=date.today().month-1)
        ano = col_a.number_input("Año", value=date.today().year)

        query_l = """SELECT fecha as "Fecha Doc", rif_proveedor as "RIF", num_factura as "N° Factura", 
                     subtipo as "Tipo", monto_exento as "Exento", base_imponible as "Base", 
                     iva_monto as "IVA", iva_retenido as "IVA Ret.", total_factura as "Total" 
                     FROM compras WHERE EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s"""
        
        conn = database.conectar()
        df = pd.read_sql(query_l, conn, params=[int(mes), int(ano)])
        conn.close()

        if not df.empty:
            st.dataframe(df, use_container_width=True)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='LibroCompras')
            st.download_button("📥 Descargar Excel", output.getvalue(), f"Libro_{mes}_{ano}.xlsx")
        else:
            st.info("No hay registros en este período.")
