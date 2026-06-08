# modulos/cotizaciones.py
import streamlit as st
import database
import pandas as pd
from datetime import date

def modulo_crear_cotizaciones():
    st.title("🚜 Módulo Comercial - Maquinarias Adonai")
    
    tab1, tab2, tab3 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos", "📥 Carga Masiva de Clientes"])

    # ==========================================
    # PESTAÑA 1: CREAR COTIZACIÓN (FORMATO EXCEL)
    # ==========================================
    with tab1:
        st.subheader("Generador de Presupuestos")
        
        # Cargar Clientes y Artículos desde la DB
        conn = database.conectar()
        clientes_df, articulos_df = pd.DataFrame(), pd.DataFrame()
        if conn:
            try:
                clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades ORDER BY nombre ASC", conn)
                articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos ORDER BY codigo ASC", conn)
            except Exception as e:
                st.error(f"Error al cargar datos base: {e}")
            finally: conn.close()

        if clientes_df.empty:
            st.warning("⚠️ No hay clientes registrados en el sistema. Utiliza la pestaña de Carga Masiva.")
        else:
            clientes_df['selector'] = clientes_df['rif'] + " - " + clientes_df['nombre']
            
            with st.form("form_emision_cotizacion"):
                st.markdown("### 🏢 Datos del Cliente")
                col1, col2 = st.columns(2)
                cliente_sel = col1.selectbox("Seleccionar Empresa:", options=clientes_df['selector'].tolist())
                fecha_cot = col2.date_input("Fecha de Emisión:", value=date.today())
                
                # Extraer info detallada
                info_cliente = clientes_df[clientes_df['selector'] == cliente_sel].iloc[0]
                st.caption(f"📍 **Dirección Fiscal:** {info_cliente['direccion']}")
                st.divider()

                st.markdown("### 🛒 Ítems de la Cotización")
                
                # Dynamic inputs simulando las líneas de tu formato de Excel
                filas_items = []
                for i in range(1, 5): # Generamos 4 líneas de ejemplo tal como tu formato original
                    st.markdown(f"**Línea N° {i}**")
                    c1, c2, c3 = st.columns([3, 1, 2])
                    
                    # Selector de artículo del catálogo o personalizado
                    opciones_art = ["-- Seleccionar del catálogo --"] + (articulos_df['codigo'] + " | " + articulos_df['descripcion']).tolist() if not articulos_df.empty else ["-- Sin artículos en catálogo --"]
                    art_sel = c1.selectbox(f"Artículo / Repuesto {i}:", options=opciones_art, key=f"art_{i}")
                    
                    cant = c2.number_input("Cantidad:", min_value=0, value=0, step=1, key=f"cant_{i}")
                    
                    # Rellenar precio sugerido automáticamente si se selecciona del catálogo
                    precio_defecto = 0.00
                    desc_defecto = ""
                    if " | " in art_sel:
                        cod_extraido = art_sel.split(" | ")[0]
                        row_art = articulos_df[articulos_df['codigo'] == cod_extraido].iloc[0]
                        precio_defecto = float(row_art['precio_sugerido'])
                        desc_defecto = row_art['descripcion']
                        
                    precio_u = c3.number_input("Precio Unitario ($/Bs):", min_value=0.00, value=precio_defecto, format="%.2f", key=f"precio_{i}")
                    
                    if cant > 0:
                        filas_items.append({
                            "descripcion": desc_defecto if desc_defecto else f"Ítem personalizado {i}",
                            "cantidad": cant,
                            "precio": precio_u,
                            "total": cant * precio_u
                        })
                
                st.divider()
                
                # Cálculos Financieros finales
                if filas_items:
                    df_resumen = pd.DataFrame(filas_items)
                    subtotal = df_resumen['total'].sum()
                    st.dataframe(df_resumen, use_container_width=True)
                    st.metric(label="Total General de la Cotización", value=f"$ {subtotal:,.2f}")
                
                if st.form_submit_button("⚡ Registrar y Guardar Cotización"):
                    if not filas_items:
                        st.error("Debe ingresar al menos una cantidad válida mayor a 0.")
                    else:
                        st.success(f"✅ ¡Cotización guardada exitosamente para {info_cliente['nombre']}!")

    # ==========================================
    # PESTAÑA 2: GESTIÓN DE ARTÍCULOS / REPUESTOS
    # ==========================================
    with tab2:
        st.subheader("📦 Registro de Repuestos y Componentes")
        with st.form("form_nuevo_articulo"):
            col1, col2, col3 = st.columns(3)
            nuevo_cod = col1.text_input("Código de Artículo (Ej: REP-001):").strip().upper()
            nueva_desc = col2.text_input("Descripción Completa (Ej: Radiador):")
            nuevo_p = col3.number_input("Precio Sugerido de Venta ($/Bs):", min_value=0.00, format="%.2f")
            
            if st.form_submit_button("💾 Registrar en Catálogo"):
                if nuevo_cod and nueva_desc:
                    database.ejecutar_transaccion(
                        "INSERT INTO articulos (codigo, descripcion, precio_sugerido) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO UPDATE SET descripcion=%s, precio_sugerido=%s",
                        (nuevo_cod, nueva_desc, nuevo_p, nueva_desc, nuevo_p)
                    )
                    st.success(f"🎉 Artículo [{nuevo_cod}] guardado con éxito en el catálogo.")
                    st.rerun()
                else:
                    st.error("Por favor completa el Código y la Descripción.")

    # ==========================================
    # PESTAÑA 3: CARGA MASIVA DESDE EXCEL
    # ==========================================
    with tab3:
        st.subheader("📥 Subir Listado General de Clientes")
        st.markdown("""
        Arrastra tu archivo de Excel tal y como lo tienes estructurado. El sistema leerá las columnas de forma inteligente.
        **Asegúrate de que las columnas se llamen exactamente:** `RIF`, `NOMBRE`, `DIRECCION`.
        """)
        
        archivo_excel = st.file_uploader("Selecciona tu archivo de Excel (.xlsx)", type=["xlsx"])
        
        if archivo_excel is not None:
            try:
                # Leemos el archivo saltando líneas vacías iniciales si las hay
                df = pd.read_excel(archivo_excel)
                
                # Normalizar nombres de columnas a minúsculas y limpiar espacios en blanco
                df.columns = df.columns.str.strip().str.upper()
                
                st.write("👀 Previsualización de los datos cargados desde tu archivo:")
                st.dataframe(df.head(5), use_container_width=True)
                
                if 'RIF' in df.columns and 'NOMBRE' in df.columns:
                    if st.button("🚀 Confirmar e Importar Clientes a Neon"):
                        conn = database.conectar()
                        cursor = conn.cursor()
                        contador_correctos = 0
                        
                        for index, fila in df.iterrows():
                            # Validar que no falten datos obligatorios
                            if pd.isna(fila['RIF']) or pd.isna(fila['NOMBRE']):
                                continue
                                
                            rif = str(fila['RIF']).strip()
                            nombre = str(fila['NOMBRE']).strip()
                            direccion = str(fila['DIRECCION']).strip() if 'DIRECCION' in df.columns and not pd.isna(fila['DIRECCION']) else "Dirección no especificada"
                            
                            try:
                                # Insertamos respetando la estructura real de tu tabla entidades
                                cursor.execute("""
                                    INSERT INTO entidades (rif, nombre, direccion, tipo_persona, tipo_contribuyente, categoria) 
                                    VALUES (%s, %s, %s, 'Jurídica Domiciliada', 'Ordinario', 'CLIENTE')
                                    ON CONFLICT (rif) DO UPDATE SET nombre = EXCLUDED.nombre, direccion = EXCLUDED.direccion
                                """, (rif, nombre, direccion))
                                contador_correctos += 1
                            except Exception:
                                continue
                        
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success(f"✨ ¡Éxito! Se han procesado e importado {contador_correctos} clientes directo a tu base de datos de Neon.")
                else:
                    st.error("❌ Tu archivo no cumple con el formato requerido. Debe contener las columnas 'RIF' y 'NOMBRE'.")
            except Exception as e:
                st.error(f"Ocurrió un error leyendo el archivo: {e}")
