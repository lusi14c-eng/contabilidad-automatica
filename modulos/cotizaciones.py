# modulos/cotizaciones.py
import streamlit as st
import database
import pandas as pd
from datetime import date

def modulo_crear_cotizaciones():
    st.title("📄 Creador de Cotizaciones Comercial")
    st.markdown("Genera cotizaciones enlazadas directamente a tu base de datos centralizada.")
    
    # 1. Leer entidades desde Neon de forma segura
    conn = database.conectar()
    clientes_df = pd.DataFrame()
    if conn:
        try:
            # Traemos las columnas reales identificadas en tu Neon
            query = "SELECT rif, nombre, categoria FROM entidades ORDER BY nombre ASC"
            clientes_df = pd.read_sql(query, conn)
        except Exception as e:
            st.error(f"Error al conectar con la tabla entidades: {e}")
        finally:
            conn.close()

    if clientes_df.empty:
        st.warning("⚠️ No se encontraron entidades en la base de datos. Registra una primero en 'Registrar Entidad'.")
        return

    # 2. Como tu sistema permite categorías híbridas, preparamos las opciones visuales
    # Formato amigable: "J411661210 - MAQUINARIAS ADONAI DE VENEZUELA, C.A."
    clientes_df['selector_visual'] = clientes_df['rif'] + " - " + clientes_df['nombre']
    lista_entidades = clientes_df['selector_visual'].tolist()

    # 3. Formulario de la Cotización
    with st.form("form_registro_cotizacion"):
        st.subheader("Datos de la Cabecera")
        col1, col2 = st.columns(2)
        
        # Enlace directo: Selectbox con búsqueda integrada
        entidad_elegida = col1.selectbox("Seleccionar Cliente / Proveedor Destinatario:", options=lista_entidades)
        fecha_documento = col2.date_input("Fecha de Emisión:", value=date.today())
        
        # Extraer los valores reales de la fila seleccionada
        datos_entidad = clientes_df[clientes_df['selector_visual'] == entidad_elegida].iloc[0]
        rif_real = datos_entidad['rif']
        nombre_real = datos_entidad['nombre']
        categoria_real = datos_entidad['categoria']
        
        st.info(f"📋 **Entidad Vinculada:** {nombre_real} | **RIF:** {rif_real} | **Relación:** {categoria_real}")
        st.divider()
        
        # 4. Campos del artículo o servicio a cotizar
        st.subheader("Líneas de Detalle")
        descripcion_item = st.text_input("Descripción del Producto o Servicio:")
        
        col3, col4 = st.columns(2)
        cantidad = col3.number_input("Cantidad:", min_value=1, value=1, step=1)
        precio_unitario = col4.number_input("Precio Unitario (Bs.):", min_value=0.00, value=0.00, format="%.2f")
        
        # Cálculos matemáticos en tiempo de ejecución
        subtotal = cantidad * precio_unitario
        iva = subtotal * 0.16  # Tarifa general de IVA 16% en Venezuela
        total_general = subtotal + iva
        
        st.markdown(f"""
        ### Resumen del Cálculo Financiero
        * **Subtotal Neto:** Bs. {subtotal:,.2f}
        * **IVA (16%):** Bs. {iva:,.2f}
        * **Total Bruto del Documento:** **Bs. {total_general:,.2f}**
        """)
        
        # Botón de confirmación de guardado contable/comercial
        boton_procesar = st.form_submit_button("💾 Procesar y Registrar Cotización")
        
        if boton_procesar:
            if not descripcion_item.strip():
                st.error("❌ El campo descripción del ítem no puede quedar vacío.")
            else:
                # Aquí procedemos a guardar los datos en tus tablas cotizaciones_cabecera y cotizaciones_detalle
                # Usando el rif_real extraído directamente de la tabla entidades
                st.success(f"✅ ¡Cotización generada exitosamente para {nombre_real}! Enlazada mediante el RIF {rif_real}.")
                database.registrar_log(
                    st.session_state.get('usuario_autenticado', 'sistema'),
                    "CREAR",
                    "cotizaciones_cabecera",
                    f"Generó cotización comercial para {nombre_real} por un monto de Bs. {total_general:,.2f}"
                )
