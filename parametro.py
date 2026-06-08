def modulo_configuracion_sistema():
    st.title("⚙️ Configuración Global del Sistema")
    conf = database.obtener_configuracion_empresa()
    
    with st.form("form_configuracion_global"):
        st.subheader("Datos del Agente de Retención (Tu Empresa)")
        col1, col2 = st.columns(2)
        n = col1.text_input("Razón Social / Nombre Legal", value=conf.get('nombre_empresa', 'ADONAI GROUP'))
        r = col2.text_input("RIF de la Empresa", value=conf.get('rif_empresa', ''))
        d = st.text_area("Dirección Fiscal", value=conf.get('direccion_empresa', ''))
        
        contribuyente_actual = conf.get('tipo_contribuyente', 'Ordinario')
        opciones_contribuyente = ["Especial", "Ordinario", "Formal"]
        try: posicion_index = opciones_contribuyente.index(contribuyente_actual)
        except ValueError: posicion_index = 1
            
        t = col1.selectbox("Tipo de Contribuyente", opciones_contribuyente, index=posicion_index)
        
        st.divider()
        st.subheader("Parámetros Fiscales de Control")
        col3, col4 = st.columns(2)
        nueva_ut = col3.number_input("Valor Unidad Tributaria (Bs.)", value=float(conf.get('ut_valor', 0.00)), format="%.2f")
        factor = col4.number_input("Factor Sustraendo (Estándar 83.3334)", value=float(conf.get('factor_sustraendo', 83.3334)), format="%.4f")
        
        if st.form_submit_button("Actualizar Todo el Sistema"):
            database.ejecutar_transaccion(
                """UPDATE configuracion SET 
                   nombre_empresa=%s, rif_empresa=%s, direccion_empresa=%s, 
                   tipo_contribuyente=%s, ut_valor=%s, factor_sustraendo=%s 
                   WHERE id=1""",
                (n, r, d, t, nueva_ut, factor)
            )
            database.registrar_log(st.session_state.get('usuario_autenticado', 'admin'), "EDITAR", "configuracion", "Actualizó datos de empresa")
            st.success("✅ Configuración corporativa sincronizada.")
            st.rerun()

    st.markdown("---")
    st.subheader("📥 Inicialización y Mantenimiento de Datos Maestros")
    
    # --- SUBSISTEMA DE CARGA MASIVA DE CLIENTES ---
    with st.expander("👥 Cargar Listado Maestro de Clientes (Excel)"):
        st.markdown("Sube tu archivo de clientes. El escáner buscará las columnas `RIF`, `NOMBRE` y `DIRECCION` automáticamente.")
        archivo_clientes = st.file_uploader("Selecciona el Excel de Clientes (.xlsx)", type=["xlsx"], key="cfg_clientes")
        
        if archivo_clientes is not None:
            try:
                df_crudo = pd.read_excel(archivo_clientes, header=None)
                fila_cabecera = None
                for idx, fila in df_crudo.iterrows():
                    valores_fila = fila.astype(str).str.strip().str.upper().tolist()
                    if 'RIF' in valores_fila and 'NOMBRE' in valores_fila:
                        fila_cabecera = idx
                        break
                
                if fila_cabecera is not None:
                    df = pd.read_excel(archivo_clientes, header=fila_cabecera)
                    df.columns = df.columns.str.strip().str.upper()
                    st.dataframe(df.head(3), use_container_width=True)
                    
                    if st.button("🚀 Confirmar e Importar Clientes", key="btn_cfg_clientes"):
                        conn = database.conectar()
                        cursor = conn.cursor()
                        contador = 0
                        for index, fila in df.iterrows():
                            if pd.isna(fila['RIF']) or pd.isna(fila['NOMBRE']) or str(fila['RIF']).strip().upper() == 'RIF':
                                continue
                            rif = str(fila['RIF']).strip()
                            nombre = str(fila['NOMBRE']).strip()
                            direccion = str(fila['DIRECCION']).strip() if 'DIRECCION' in df.columns and not pd.isna(fila['DIRECCION']) else "Dirección no especificada"
                            
                            cursor.execute("""
                                INSERT INTO entidades (rif, nombre, direccion, tipo_persona, tipo_contribuyente, categoria) 
                                VALUES (%s, %s, %s, 'Jurídica Domiciliada', 'Ordinario', 'CLIENTE')
                                ON CONFLICT (rif) DO UPDATE SET nombre = EXCLUDED.nombre, direccion = EXCLUDED.direccion
                            """, (rif, nombre, direccion))
                            contador += 1
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success(f"🎉 ¡Éxito! {contador} clientes migrados a Neon.")
                        st.rerun()
                else:
                    st.error("No se encontró la fila con los encabezados 'RIF' y 'NOMBRE'.")
            except Exception as e: st.error(f"Error: {e}")

    # --- SUBSISTEMA DE CARGA MASIVA DE PROVEEDORES ---
    with st.expander("🚛 Cargar Listado Maestro de Proveedores (Excel)"):
        st.markdown("Sube tu archivo de proveedores. El sistema mantendrá la integridad si un proveedor también actúa como cliente.")
        archivo_proveedores = st.file_uploader("Selecciona el Excel de Proveedores (.xlsx)", type=["xlsx"], key="cfg_proveedores")
        
        if archivo_proveedores is not None:
            try:
                df_crudo_prov = pd.read_excel(archivo_proveedores, header=None)
                fila_cabecera_prov = None
                for idx, fila in df_crudo_prov.iterrows():
                    valores_fila = fila.astype(str).str.strip().str.upper().tolist()
                    if 'RIF' in valores_fila and 'NOMBRE' in valores_fila:
                        fila_cabecera_prov = idx
                        break
                
                if fila_cabecera_prov is not None:
                    df_prov = pd.read_excel(archivo_proveedores, header=fila_cabecera_prov)
                    df_prov.columns = df_prov.columns.str.strip().str.upper()
                    st.dataframe(df_prov.head(3), use_container_width=True)
                    
                    if st.button("🚀 Confirmar e Importar Proveedores", key="btn_cfg_prov"):
                        conn = database.conectar()
                        cursor = conn.cursor()
                        contador_prov = 0
                        for index, fila in df_prov.iterrows():
                            if pd.isna(fila['RIF']) or pd.isna(fila['NOMBRE']) or str(fila['RIF']).strip().upper() == 'RIF':
                                continue
                            rif = str(fila['RIF']).strip()
                            nombre = str(fila['NOMBRE']).strip()
                            direccion = str(fila['DIRECCION']).strip() if 'DIRECCION' in df_prov.columns and not pd.isna(fila['DIRECCION']) else "Dirección no especificada"
                            
                            cursor.execute("""
                                INSERT INTO entidades (rif, nombre, direccion, tipo_persona, tipo_contribuyente, categoria) 
                                VALUES (%s, %s, %s, 'Jurídica Domiciliada', 'Ordinario', 'PROVEEDOR')
                                ON CONFLICT (rif) DO UPDATE SET 
                                    nombre = EXCLUDED.nombre, 
                                    direccion = EXCLUDED.direccion,
                                    categoria = CASE WHEN entidades.categoria = 'CLIENTE' THEN 'AMBOS' ELSE 'PROVEEDOR' END
                            """, (rif, nombre, direccion))
                            contador_prov += 1
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success(f"✨ ¡Éxito! {contador_prov} proveedores migrados a Neon.")
                        st.rerun()
                else:
                    st.error("No se encontró la fila con los encabezados 'RIF' y 'NOMBRE'.")
            except Exception as e: st.error(f"Error: {e}")
