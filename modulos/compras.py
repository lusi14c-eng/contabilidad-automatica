import streamlit as st
import pandas as pd
import database
from datetime import datetime

def modulo_compras():
    st.title("🧾 Registro de Compras y Contabilidad")
    
    # Creamos las pestañas
    tab1, tab2, tab3 = st.tabs(["📝 Registrar Factura", "⚙️ Configurar Subtipos", "📖 Ver Libro"])

    # --- TAB 2: CONFIGURACIÓN DE CUENTAS (Haz esto primero) ---
    with tab2:
        st.subheader("Configuración de Subtipos de Gasto")
        st.info("Vincule un nombre de gasto (ej. Papelería) a una cuenta contable.")
        
        with st.form("form_subtipo", clear_on_submit=True):
            nombre_subtipo = st.text_input("Nombre del Subtipo:").upper().strip()
            cuenta_contable = st.text_input("Código de Cuenta Contable (Ej: 5.1.01.001):")
            
            if st.form_submit_button("Guardar Subtipo"):
                if nombre_subtipo and cuenta_contable:
                    conn = database.conectar()
                    try:
                        conn.execute("INSERT INTO subtipos_gasto (nombre, cuenta_contable) VALUES (?,?)", 
                                     (nombre_subtipo, cuenta_contable))
                        conn.commit()
                        st.success(f"✅ Subtipo '{nombre_subtipo}' vinculado a la cuenta {cuenta_contable}")
                    except:
                        st.error("❌ Este subtipo ya existe o hubo un error en la DB.")
                    finally:
                        conn.close()
                else:
                    st.warning("Complete ambos campos.")

        # Mostrar los subtipos ya creados
        conn = database.conectar()
        df_sub = pd.read_sql_query("SELECT * FROM subtipos_gasto", conn)
        conn.close()
        if not df_sub.empty:
            st.write("Subtipos actuales:")
            st.dataframe(df_sub, use_container_width=True, hide_index=True)

    # --- TAB 1: REGISTRO DE FACTURA ---
    with tab1:
        conn = database.conectar()
        # Traer proveedores y subtipos
        df_prov = pd.read_sql_query("SELECT * FROM entidades WHERE categoria IN ('PROVEEDOR', 'AMBOS')", conn)
        df_sub_list = pd.read_sql_query("SELECT nombre FROM subtipos_gasto", conn)
        conn.close()

        if df_prov.empty:
            st.warning("⚠️ No hay Proveedores registrados. Vaya al módulo de Maestro de Entidades.")
        elif df_sub_list.empty:
            st.warning("⚠️ No hay Subtipos de Gasto configurados. Use la pestaña 'Configurar Subtipos'.")
        else:
            with st.form("registro_compra"):
                col1, col2 = st.columns(2)
                with col1:
                    prov_sel = st.selectbox("Seleccione Proveedor:", df_prov['rif'] + " - " + df_prov['nombre'])
                    rif_prov = prov_sel.split(" - ")[0]
                    p_data = df_prov[df_prov['rif'] == rif_prov].iloc[0]
                    
                    fecha = st.date_input("Fecha Factura:", datetime.now())
                    n_factura = st.text_input("N° Factura:")
                    n_control = st.text_input("N° Control:")
                
                with col2:
                    sub_sel = st.selectbox("Clasificación Contable:", df_sub_list['nombre'])
                    base_imp = st.number_input("Base Imponible:", min_value=0.0, step=0.01)
                    iva_pct_monto = st.selectbox("Alícuota IVA %:", [16, 8, 0, 31])
                    monto_exento = st.number_input("Monto Exento:", min_value=0.0, step=0.01)

                st.divider()
                st.markdown("### ⚖️ Control de Retenciones")
                c_ret1, c_ret2 = st.columns(2)
                with c_ret1:
                    # Lee el porcentaje directamente de la ficha del proveedor
                    aplicar_iva = st.toggle("Aplicar Retención IVA", value=(p_data['retencion_iva_pct'] > 0))
                    st.caption(f"Sugerido: {p_data['retencion_iva_pct']}%")
                with c_ret2:
                    aplicar_islr = st.toggle("Aplicar Retención ISLR", value=(p_data['retencion_islr_pct'] > 0))
                    st.caption(f"Sugerido: {p_data['retencion_islr_pct']}%")

                # Cálculos
                iva_fact = round(base_imp * (iva_pct_monto / 100), 2)
                ret_iva = round(iva_fact * (p_data['retencion_iva_pct'] / 100), 2) if aplicar_iva else 0.0
                ret_islr = round(base_imp * (p_data['retencion_islr_pct'] / 100), 2) if aplicar_islr else 0.0
                total_neto = round(base_imp + iva_fact + monto_exento - ret_iva - ret_islr, 2)

                st.info(f"**Total Factura:** {base_imp + iva_fact + monto_exento} | **Neto a Pagar:** {total_neto}")

                if st.form_submit_button("📥 Registrar Factura"):
                    conn = database.conectar()
                    conn.execute('''INSERT INTO compras 
                        (fecha, rif_proveedor, num_factura, num_control, monto_exento, base_imponible, 
                        iva_monto, islr_retenido, iva_retenido, total_factura, subtipo, aplica_ret_islr, aplica_ret_iva)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                        (fecha.strftime("%Y-%m-%d"), rif_prov, n_factura, n_control, monto_exento, base_imp, 
                        iva_fact, ret_islr, ret_iva, total_neto, sub_sel, int(aplicar_islr), int(aplicar_iva)))
                    conn.commit()
                    conn.close()
                    st.success("✅ Registro completado.")

    with tab3:
        st.subheader("Libro de Compras")
        # Aquí programaremos el reporte Excel más adelante
        st.write("Próximamente: Exportación de Libro de Compras y TXT de Retenciones.")
