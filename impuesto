def modulo_configuracion_sistema():
    st.title("⚙️ Configuración Global del Sistema")
    conf = database.obtener_configuracion_empresa()

    with st.form("form_config"):
        st.subheader("Datos del Agente de Retención (Tu Empresa)")
        nombre = st.text_input("Nombre Legal", value=conf['nombre'])
        rif = st.text_input("RIF", value=conf['rif'])
        dir_f = st.text_area("Dirección Fiscal", value=conf['direccion'])
        
        st.divider()
        st.subheader("Parámetros Fiscales")
        col1, col2 = st.columns(2)
        nueva_ut = col1.number_input("Valor Unidad Tributaria (Bs.)", value=conf['ut_valor'], format="%.2f")
        factor = col2.number_input("Factor Sustraendo (Estándar 83.3334)", value=conf['factor_sustraendo'], format="%.4f")

        if st.form_submit_button("Actualizar Parámetros"):
            conn = database.conectar()
            c = conn.cursor()
            c.execute("""UPDATE configuracion SET nombre_empresa=%s, rif_empresa=%s, 
                         direccion_empresa=%s, ut_valor=%s, factor_sustraendo=%s WHERE id=1""",
                      (nombre, rif, dir_f, nueva_ut, factor))
            conn.commit()
            conn.close()
            st.success("✅ Sistema actualizado. Los nuevos cálculos de ISLR usarán estos valores.")
