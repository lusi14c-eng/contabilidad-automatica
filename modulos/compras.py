import streamlit as st
import pandas as pd
import database
from datetime import date
from io import BytesIO

def modulo_compras():
    st.title("💳 Cuentas por Pagar y Libro de Compras")
    conf = database.obtener_configuracion_empresa()
    
    tab1, tab2 = st.tabs(["📝 Registro FAC/NC", "📊 Libro de Compras Legal"])
    
    with tab1:
        conn = database.conectar()
        prov_df = pd.read_sql("SELECT rif, nombre FROM entidades", conn)
        sub_df = pd.read_sql("SELECT nombre, cuenta_codigo FROM compra_subtipos", conn)
        cc_df = pd.read_sql("SELECT id, nombre FROM centros_costo", conn)
        conn.close()

        if prov_df.empty:
            st.warning("⚠️ Registre proveedores en el módulo de Entidades.")
        else:
            with st.form("registro_cp", clear_on_submit=True):
                c1, c2 = st.columns(2)
                tipo = c1.selectbox("Tipo de Documento", ["FAC", "NC"])
                f_doc = c1.date_input("Fecha Factura/NC", value=date.today())
                prov = c1.selectbox("Proveedor", prov_df['nombre'].tolist())
                rif_p = prov_df[prov_df['nombre'] == prov]['rif'].values[0]
                n_doc = c1.text_input("Número de Documento")
                n_con = c1.text_input("Número de Control")
                
                sub = c2.selectbox("Clasificación Gasto", sub_df['nombre'].tolist())
                cc = c2.selectbox("Centro de Costo", cc_df['nombre'].tolist() if not cc_df.empty else ["No Definido"])
                base = c2.number_input("Base Imponible", min_value=0.0)
                exento = c2.number_input("Exento", min_value=0.0)
                iva = round(base * 0.16, 2)
                
                # Retenciones
                st.divider()
                r_iva = c2.number_input("Retención IVA", min_value=0.0)
                r_islr = c2.number_input("Retención ISLR", min_value=0.0)
                
                total = round((base + exento + iva) - r_iva - r_islr, 2)
                saldo = total if tipo == "FAC" else -total
                st.markdown(f"### Total: {total} Bs.")

                if st.form_submit_button("📥 Procesar Documento"):
                    try:
                        conn = database.conectar()
                        c = conn.cursor()
                        # Generar Asiento CP
                        num_as = database.obtener_ultimo_correlativo("CP")
                        c.execute("INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen, creado_por) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                                  (num_as, f_doc, f"{tipo} {n_doc} - {prov}", "CP", st.session_state['usuario_autenticado']))
                        id_as = c.fetchone()[0]
                        
                        # Guardar Compra
                        c.execute("""INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, tipo_documento, 
                                     base_imponible, monto_exento, iva_monto, iva_retenido, islr_retenido, total_factura, 
                                     saldo_pendiente, subtipo, asiento_id, creado_por) 
                                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                  (f_doc, rif_p, n_doc, n_con, tipo, base, exento, iva, r_iva, r_islr, total, saldo, sub, id_as, st.session_state['usuario_autenticado']))
                        
                        conn.commit()
                        st.success(f"Registrado. Asiento: {num_as}")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                    finally: conn.close()

    with tab2:
        st.subheader("📊 Reporte Fiscal de Compras")
        col_m, col_a = st.columns(2)
        mes, ano = col_m.selectbox("Mes", range(1,13), index=date.today().month-1), col_a.number_input("Año", value=date.today().year)
        
        query = """
            SELECT c.fecha, e.rif, e.nombre, c.num_factura, c.num_control, c.tipo_documento, 
                   c.base_imponible, c.iva_monto, c.iva_retenido, c.total_factura, c.saldo_pendiente
            FROM compras c JOIN entidades e ON c.rif_proveedor = e.rif
            WHERE EXTRACT(MONTH FROM c.fecha) = %s AND EXTRACT(YEAR FROM c.fecha) = %s
        """
        conn = database.conectar()
        df = pd.read_sql(query, conn, params=[int(mes), int(ano)])
        conn.close()
        st.dataframe(df, use_container_width=True)
