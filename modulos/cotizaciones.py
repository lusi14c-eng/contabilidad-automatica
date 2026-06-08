# modulos/cotizaciones.py
import streamlit as st
import database
import pandas as pd
from datetime import date

def modulo_crear_cotizaciones():
    st.title("📄 Módulo Comercial - Maquinarias Adonai")
    
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    # ==========================================
    # PESTAÑA 1: CREAR COTIZACIÓN (FORMATO EXCEL)
    # ==========================================
    with tab1:
        st.subheader("Generador de Presupuestos")
        
        conn = database.conectar()
        clientes_df, articulos_df = pd.DataFrame(), pd.DataFrame()
        if conn:
            try:
                clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades ORDER BY nombre ASC", conn)
                try:
                    articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos ORDER BY codigo ASC", conn)
                except Exception:
                    database.ejecutar_transaccion('''CREATE TABLE IF NOT EXISTS articulos (
                        codigo TEXT PRIMARY KEY, descripcion TEXT, precio_sugerido NUMERIC(15,2) DEFAULT 0.00)''')
                    articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos ORDER BY codigo ASC", conn)
            except Exception as e:
                st.error(f"Error al cargar datos base: {e}")
            finally: conn.close()

        if clientes_df.empty:
            st.warning("⚠️ No hay entidades registradas en el sistema. Por favor, inicializa la base de datos en Configuración del Sistema.")
        else:
            clientes_df['selector'] = clientes_df['rif'] + " - " + clientes_df['nombre']
            
            with st.form("form_emision_cotizacion"):
                st.markdown("### 🏢 Datos del Cliente")
                col1, col2 = st.columns(2)
                cliente_sel = col1.selectbox("Seleccionar Empresa:", options=clientes_df['selector'].tolist())
                fecha_cot = col2.date_input("Fecha de Emisión:", value=date.today())
                
                info_cliente = clientes_df[clientes_df['selector'] == cliente_sel].iloc[0]
                st.caption(f"📍 **Dirección Fiscal:** {info_cliente['direccion']}")
                st.divider()

                st.markdown("### 🛒 Ítems de la Cotización")
                filas_items = []
                for i in range(1, 5):
                    st.markdown(f"**Línea N° {i}**")
                    c1, c2, c3 = st.columns([3, 1, 2])
                    
                    opciones_art = ["-- Seleccionar del catálogo --"] + (articulos_df['codigo'] + " | " + articulos_df['descripcion']).tolist() if not articulos_df.empty else ["-- Sin artículos en catálogo --"]
                    art_sel = c1.selectbox(f"Artículo / Repuesto {i}:", options=opciones_art, key=f"art_{i}")
                    
                    cant = c2.number_input("Cantidad:", min_value=0, value=0, step=1, key=f"cant_{i}")
                    
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
                
                if filas_items:
                    df_resumen = pd.DataFrame(filas_items)
                    subtotal = df_resumen['total'].sum()
                    st.dataframe(df_resumen, use_container_width=True)
                    st.metric(label="Total General", value=f"$ {subtotal:,.2f}")
                
                if st.form_submit_button("⚡ Registrar y Guardar Cotización"):
                    if not filas_items:
                        st.error("Debe ingresar al menos una cantidad válida mayor a 0.")
                    else:
                        st.success(f"✅ ¡Cotización guardada exitosamente para {info_cliente['nombre']}!")

    # ==========================================
    # PESTAÑA 2: GESTIÓN DE ARTÍCULOS
    # ==========================================
    with tab2:
        st.subheader("📦 Registro de Repuestos y Componentes")
        with st.form("form_nuevo_articulo"):
            col1, col2, col3 = st.columns(3)
            nuevo_cod = col1.text_input("Código de Artículo (Ej: REP-001):").strip().upper()
            nueva_desc = col2.text_input("Descripción Completa:")
            nuevo_p = col3.number_input("Precio Sugerido de Venta ($/Bs):", min_value=0.00, format="%.2f")
            
            if st.form_submit_button("💾 Registrar en Catálogo"):
                if nuevo_cod and nueva_desc:
                    database.ejecutar_transaccion(
                        "INSERT INTO articulos (codigo, descripcion, precio_sugerido) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO UPDATE SET descripcion=%s, precio_sugerido=%s",
                        (nuevo_cod, nueva_desc, nuevo_p, nueva_desc, nuevo_p)
                    )
                    st.success(f"🎉 Artículo [{nuevo_cod}] guardado con éxito.")
                    st.rerun()
                else:
                    st.error("Por favor completa el Código y la Descripción.")
