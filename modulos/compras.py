import streamlit as st
import pandas as pd
import database
from datetime import date
from io import BytesIO

def modulo_compras():
    st.title("💳 Cuentas por Pagar (CP)")
    conf = database.obtener_configuracion_empresa()
    
    tab1, tab2 = st.tabs(["📝 Registro de Documentos", "📊 Libro de Compras / Auxiliar"])
    
    with tab1:
        conn = database.conectar()
        prov_df = pd.read_sql("SELECT rif, nombre, tipo_persona FROM entidades", conn)
        sub_df = pd.read_sql("SELECT nombre, cuenta_codigo FROM compra_subtipos", conn)
        cc_df = pd.read_sql("SELECT id, nombre FROM centros_costo", conn)
        conn.close()

        if prov_df.empty or sub_df.empty:
            st.warning("⚠️ Verifique que tenga Proveedores y Subtipos de Compra registrados.")
        else:
            with st.form("form_cp_nuevo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    tipo_doc = st.selectbox("Tipo de Documento", ["FAC", "NC"])
                    f_doc = st.date_input("Fecha Documento", value=date.today())
                    
                    prov_sel = st.selectbox("Proveedor", prov_df['nombre'].tolist())
                    rif_p = prov_df[prov_df['nombre'] == prov_sel]['rif'].values[0]
                    
                    n_fact = st.text_input("N° Documento")
                    n_ctrl = st.text_input("N° Control")
                    
                    if tipo_doc == "NC":
                        f_afectada = st.text_input("Factura que Afecta")

                with col2:
                    sub_sel = st.selectbox("Subtipo de Gasto", sub_df['nombre'].tolist())
                    cc_sel = st.selectbox("Centro de Costo", cc_df['nombre'].tolist() if not cc_df.empty else ["N/A"])
                    
                    base = st.number_input("Base Imponible", min_value=0.0, format="%.2f")
                    exento = st.number_input("Monto Exento", min_value=0.0, format="%.2f")
                    iva_m = round(base * 0.16, 2)
                    
                    # Lógica de Retenciones según configuración de empresa
                    es_esp = conf['tipo_contribuyente'] == "Especial"
                    ap_iva = st.checkbox("Retener IVA", value=es_esp)
                    p_iva = st.selectbox("% Retención", [75, 100], index=0 if es_esp else 0)
                    ret_iva = round(iva_m * (p_iva/100), 2) if ap_iva else 0.0
                    
                    ret_islr = st.number_input("Retención ISLR", min_value=0.0, format="%.2f")

                total = round((base + exento + iva_m) - ret_iva - ret_islr, 2)
                # Si es NC, el valor contable y el saldo deben ser negativos para el auxiliar
                monto_final = total if tipo_doc == "FAC" else -total
                
                st.info(f"Total Neto del Documento: {total} Bs.")

                if st.form_submit_button("📥 Registrar en CP"):
                    if not n_fact:
                        st.error("El número de documento es obligatorio.")
                    else:
                        try:
                            conn = database.conectar()
                            c = conn.cursor()
                            
                            # Generar correlativo de asiento CP
                            num_asiento = database.obtener_ultimo_correlativo("CP")
                            
                            # 1. Crear Cabecera de Asiento
                            c.execute("""INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen, creado_por) 
                                         VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                                      (num_asiento, f_doc, f"Registro {tipo_doc} {n_fact} - {prov_sel}", "CP", st.session_state['usuario_autenticado']))
                            asiento_id = c.fetchone()[0]
                            
                            # 2. Registrar en Compras (Auxiliar de CP)
                            query_compra = """INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, tipo_documento,
                                              monto_exento, base_imponible, iva_monto, islr_retenido, iva_retenido, 
                                              total_factura, saldo_pendiente, subtipo, asiento_id, creado_por) 
                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                            c.execute(query_compra, (f_doc, rif_p, n_fact, n_ctrl, tipo_doc, exento, base, iva_m, 
                                                     ret_islr, ret_iva, total, monto_final, sub_sel, asiento_id, 
                                                     st.session_state['usuario_autenticado']))
                            
                            conn.commit()
                            database.registrar_log(st.session_state['usuario_autenticado'], "INSERT", "compras", f"Registró {tipo_doc} {n_fact}")
                            st.success(f"✅ Registrado exitosamente. Asiento: {num_asiento}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                        finally:
                            conn.close()

    with tab2:
        st.subheader("📊 Reporte de Documentos")
        col_m, col_a = st.columns(2)
        mes = col_m.selectbox("Mes", range(1, 13), index=date.today().month-1)
        ano = col_a.number_input("Año", value=date.today().year)

        query_l = """
            SELECT fecha, rif_proveedor, num_factura, tipo_documento, total_factura, saldo_pendiente, creado_por
            FROM compras 
            WHERE EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
        """
        conn = database.conectar()
        df = pd.read_sql(query_l, conn, params=[int(mes), int(ano)])
        conn.close()

        if not df.empty:
            st.dataframe(df, use_container_width=True)
