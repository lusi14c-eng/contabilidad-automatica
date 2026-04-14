import streamlit as st
import pandas as pd
import database
from datetime import datetime

def modulo_compras():
    st.title("🧾 Registro de Compras y Contabilidad")
    
    tab1, tab2, tab3 = st.tabs(["📝 Registrar Factura", "⚙️ Configurar Subtipos", "📖 Ver Libro"])

    with tab2:
        # (Se mantiene el código anterior para configurar subtipos)
        pass

    with tab1:
        conn = database.conectar()
        proveedores = pd.read_sql_query("SELECT * FROM entidades", conn)
        subtipos = pd.read_sql_query("SELECT * FROM subtipos_gasto", conn)
        conn.close()

        if proveedores.empty or subtipos.empty:
            st.warning("⚠️ Configure Proveedores y Subtipos de Gasto primero.")
            return

        with st.form("registro_compra"):
            col1, col2 = st.columns(2)
            with col1:
                prov_sel = st.selectbox("Proveedor:", proveedores['rif'] + " - " + proveedores['nombre'])
                rif_prov = prov_sel.split(" - ")[0]
                p_data = proveedores[proveedores['rif'] == rif_prov].iloc[0]
                
                fecha = st.date_input("Fecha Factura:", datetime.now())
                n_factura = st.text_input("Número de Factura:")
                n_control = st.text_input("Número de Control:")
            
            with col2:
                sub_sel = st.selectbox("Clasificación Contable:", subtipos['nombre'])
                base_imp = st.number_input("Base Imponible:", min_value=0.0, format="%.2f")
                iva_pct_monto = st.selectbox("Alícuota IVA:", [16, 8, 0, 31])
                monto_exento = st.number_input("Monto Exento:", min_value=0.0)

            st.divider()
            st.markdown("### ⚖️ Control de Retenciones")
            c_ret1, c_ret2 = st.columns(2)
            
            with c_ret1:
                # El sistema sugiere según el maestro, pero permite cambiarlo
                aplicar_iva = st.toggle("Aplicar Retención IVA", value=(p_data['retencion_iva_pct'] > 0))
                st.caption(f"Sugerido por Maestro: {p_data['retencion_iva_pct']}%")
                
            with c_ret2:
                aplicar_islr = st.toggle("Aplicar Retención ISLR", value=(p_data['retencion_islr_pct'] > 0))
                st.caption(f"Sugerido por Maestro: {p_data['retencion_islr_pct']}%")

            # --- LÓGICA DE CÁLCULO DINÁMICO ---
            iva_facturado = round(base_imp * (iva_pct_monto / 100), 2)
            
            # Cálculo IVA Retenido
            ret_iva = round(iva_facturado * (p_data['retencion_iva_pct'] / 100), 2) if aplicar_iva else 0.0
            
            # Cálculo ISLR Retenido
            sustraendo = 0.0 # Se puede parametrizar luego con la UT
            ret_islr = round((base_imp * (p_data['retencion_islr_pct'] / 100)) - sustraendo, 2) if aplicar_islr else 0.0
            if ret_islr < 0: ret_islr = 0.0

            total_pagar = round(base_imp + iva_facturado + monto_exento - ret_iva - ret_islr, 2)

            # Mostrar resumen antes de guardar
            st.info(f"""
            **Resumen Contable:**
            - Total Factura: **{base_imp + iva_facturado + monto_exento}**
            - (-) Retención IVA: {ret_iva}
            - (-) Retención ISLR: {ret_islr}
            - **Neto a Pagar al Proveedor: {total_pagar}**
            """)

            if st.form_submit_button("📥 Procesar Compra"):
                conn = database.conectar()
                conn.execute('''INSERT INTO compras 
                    (fecha, rif_proveedor, num_factura, num_control, monto_exento, base_imponible, 
                    iva_monto, islr_retenido, iva_retenido, total_factura, subtipo, aplica_ret_islr, aplica_ret_iva)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (fecha.strftime("%Y-%m-%d"), rif_prov, n_factura, n_control, monto_exento, base_imp, 
                    iva_facturado, ret_islr, ret_iva, total_pagar, sub_sel, int(aplicar_islr), int(aplicar_iva)))
                conn.commit()
                conn.close()
                st.success("Factura registrada exitosamente.")
