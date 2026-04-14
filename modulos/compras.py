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
        # Traemos proveedores y los subtipos dinámicos que creaste
        prov_df = pd.read_sql("SELECT rif, nombre, tipo_persona FROM entidades", conn)
        subtipos_df = pd.read_sql("SELECT nombre, cuenta_codigo FROM compra_subtipos", conn)
        conn.close()

        if prov_df.empty:
            st.warning("⚠️ Registra un proveedor primero en el módulo de Entidades.")
        elif subtipos_df.empty:
            st.error("⚠️ No has definido 'Subtipos de Compra' en el módulo de Contabilidad.")
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
                    
                    # --- SELECCIÓN DE SUBTIPO DINÁMICO ---
                    dict_sub = {r['nombre']: r['cuenta_codigo'] for _, r in subtipos_df.iterrows()}
                    sub_nombre = st.selectbox("Subtipo de Compra (Clasificación)", list(dict_sub.keys()))
                    cod_cuenta = dict_sub[sub_nombre]
                    st.caption(f"📍 Cuenta contable asociada: **{cod_cuenta}**")

                with col2:
                    st.subheader("Montos y Retenciones")
                    m_exento = st.number_input("Monto Exento", min_value=0.0, step=0.01)
                    base_i = st.number_input("Base Imponible", min_value=0.0, step=0.01)
                    iva_f = round(base_i * 0.16, 2)
                    st.info(f"IVA (16%): {iva_f}")
                    
                    st.divider()
                    
                    # Lógica de Retención IVA Automática
                    mi_tipo = conf.get('tipo_contribuyente', 'Ordinario')
                    es_especial = True if mi_tipo == "Especial" else False
                    
                    ap_iva = st.checkbox("Retener IVA", value=es_especial)
                    p_iva = st.selectbox("% Retención", [75, 100], index=0, disabled=not ap_iva)
                    iva_ret = round(iva_f * (p_iva / 100), 2) if ap_iva else 0.0
                    
                    # ISLR Simple (Ejemplo 2% para servicios)
                    ap_islr = st.checkbox("Retener ISLR", value=True)
                    tasa_islr = 2.0 # Puedes hacer esto dinámico después
                    islr_ret = round(base_i * (tasa_islr / 100), 2) if ap_islr else 0.0
                    
                    st.warning(f"Retenciones: IVA {iva_ret} | ISLR {islr_ret}")

                total_neto = round((m_exento + base_i + iva_f) - iva_ret - islr_ret, 2)
                st.markdown(f"### Neto a Pagar: **{total_neto} Bs.**")

                if st.form_submit_button("📥 Registrar Factura"):
                    if not num_f:
                        st.error("Debe ingresar el número de factura.")
                    else:
                        try:
                            conn = database.conectar()
                            c = conn.cursor()
                            query = """INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, 
                                       monto_exento, base_imponible, iva_monto, islr_retenido, iva_retenido, 
                                       total_factura, subtipo) 
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                            c.execute(query, (fecha_doc, p_datos['rif'], num_f, num_c, m_exento, base_i, 
                                              iva_f, islr_ret, iva_ret, total_neto, sub_nombre))
                            conn.commit()
                            conn.close()
                            st.success("✅ Compra registrada con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

    with tab2:
        st.subheader("📊 Libro de Compras")
        col_m, col_a = st.columns(2)
        mes = col_m.selectbox("Mes", range(1, 13), index=date.today().month-1)
        ano = col_a.number_input("Año", value=date.today().year)

        query_l = """SELECT fecha as "Fecha Doc", rif_proveedor as "RIF", num_factura as "N° Factura", 
                     subtipo as "Subtipo", base_imponible as "Base", iva_monto as "IVA", 
                     iva_retenido as "Ret. IVA", total_factura as "Neto" 
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
            st.info("No hay registros para este período.")
