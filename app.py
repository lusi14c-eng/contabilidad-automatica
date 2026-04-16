def modulo_contabilidad_general():
    st.title("🏛️ Gestión Contable Empresarial")
    t1, t2, t3 = st.tabs(["📖 Diario General", "🏢 Centros de Costo", "🔒 Control de Períodos"])

    # --- PESTAÑA 3: CONTROL DE PERÍODOS (MODO ERP) ---
    with t3:
        st.subheader("Estatus de Módulos por Período")
        col_gen1, col_gen2 = st.columns([2, 1])
        anio_op = col_gen1.number_input("Año Fiscal a Gestionar", value=2026)
        if col_gen2.button("Generar Ejercicio Fiscal"):
            for m in range(1, 13):
                p_str = f"{anio_op}-{str(m).zfill(2)}"
                database.ejecutar_transaccion(
                    "INSERT INTO periodos_fiscales (periodo, modulo_cg, modulo_cp) VALUES (%s, 'Cerrado', 'Cerrado') ON CONFLICT DO NOTHING", (p_str,)
                )
            st.success(f"Ejercicio {anio_op} generado.")

        # Tabla de control
        conn = database.conectar()
        df_p = pd.read_sql(f"SELECT periodo, modulo_cg, modulo_cp FROM periodos_fiscales WHERE periodo LIKE '{anio_op}-%%' ORDER BY periodo ASC", conn)
        conn.close()

        if not df_p.empty:
            st.markdown("---")
            for _, row in df_p.iterrows():
                c1, c2, c3, c4, c5 = st.columns([1, 1.2, 1.2, 1, 1])
                c1.write(f"📅 **{row['periodo']}**")
                
                # Estado CG
                cg_icon = "🟢" if row['modulo_cg'] == 'Abierto' else "🔒"
                c2.write(f"{cg_icon} CG: {row['modulo_cg']}")
                if c4.button("Alt. CG", key=f"cg_{row['periodo']}"):
                    n_st = "Cerrado" if row['modulo_cg'] == 'Abierto' else "Abierto"
                    database.ejecutar_transaccion("UPDATE periodos_fiscales SET modulo_cg = %s WHERE periodo = %s", (n_st, row['periodo']))
                    st.rerun()

                # Estado CP
                cp_icon = "🟢" if row['modulo_cp'] == 'Abierto' else "🔒"
                c3.write(f"{cp_icon} CP: {row['modulo_cp']}")
                if c5.button("Alt. CP", key=f"cp_{row['periodo']}"):
                    n_st = "Cerrado" if row['modulo_cp'] == 'Abierto' else "Abierto"
                    database.ejecutar_transaccion("UPDATE periodos_fiscales SET modulo_cp = %s WHERE periodo = %s", (n_st, row['periodo']))
                    st.rerun()

    # --- PESTAÑA 1: DIARIO GENERAL (MODO ODOO) ---
    with t1:
        if st.button("➕ Crear Comprobante Contable"):
            st.session_state["nuevo_asiento"] = True

        if st.session_state.get("nuevo_asiento"):
            with st.expander("📝 Nuevo Asiento / Comprobante", expanded=True):
                with st.form("asiento_erp"):
                    # CABECERA
                    col_h1, col_h2, col_h3 = st.columns(3)
                    fecha_as = col_h1.date_input("Fecha Contable")
                    origen_as = col_h2.selectbox("Diario / Fuente", ["Diario General (CG)", "Compras (CP)", "Bancos (CB)"])
                    ref_as = col_h3.text_input("Referencia / Factura #")
                    desc_as = st.text_input("Descripción General (Glosa)")

                    # DETALLE (PARTIDAS)
                    st.markdown("**Líneas de Comprobante**")
                    # Usamos un editor de datos para máxima velocidad de carga
                    df_init = pd.DataFrame([
                        {"Cuenta": "", "Tercero (RIF)": "", "CC": "", "Descripción": "", "Debe": 0.0, "Haber": 0.0}
                        for _ in range(5)
                    ])
                    asiento_data = st.data_editor(df_init, num_rows="dynamic", use_container_width=True, key="editor_asiento")

                    # VALIDACIÓN
                    total_debe = asiento_data["Debe"].sum()
                    total_haber = asiento_data["Haber"].sum()
                    diferencia = round(total_debe - total_haber, 2)

                    c_v1, c_v2, c_v3 = st.columns(3)
                    c_v1.metric("Total Debe", f"{total_debe:,.2f}")
                    c_v2.metric("Total Haber", f"{total_haber:,.2f}")
                    c_v3.metric("Diferencia", f"{diferencia:,.2f}", delta=diferencia, delta_color="inverse")

                    if st.form_submit_button("✅ Postear Asiento"):
                        # Validar Período
                        p_check = f"{fecha_as.year}-{str(fecha_as.month).zfill(2)}"
                        res_p = database.ejecutar_query("SELECT modulo_cg FROM periodos_fiscales WHERE periodo = %s", (p_check,), fetch=True)
                        
                        if not res_p or res_p[0] == "Cerrado":
                            st.error(f"Error: El período {p_check} para Contabilidad está CERRADO.")
                        elif diferencia != 0:
                            st.error("Error: El asiento no está cuadrado (Partida Doble).")
                        else:
                            # Proceso de guardado Maestro-Detalle
                            num_correlativo = database.obtener_ultimo_correlativo("AS")
                            database.ejecutar_transaccion(
                                "INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen, creado_por) VALUES (%s,%s,%s,%s,%s)",
                                (num_correlativo, fecha_as, desc_as, origen_as, st.session_state['usuario_autenticado'])
                            )
                            st.success(f"Asiento {num_correlativo} posteado.")
                            st.session_state["nuevo_asiento"] = False
                            st.rerun()
                
                if st.button("Cancelar"):
                    st.session_state["nuevo_asiento"] = False
                    st.rerun()

        # Visualización del Diario
        df_diario = pd.read_sql("SELECT num_asiento, fecha, concepto, origen FROM asientos_cabecera ORDER BY id DESC", database.conectar())
        st.dataframe(df_diario, use_container_width=True)
