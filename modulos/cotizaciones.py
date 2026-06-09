import streamlit as st
import database
import pandas as pd
from datetime import date
import io
import random
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- FUNCIÓN DE GENERACIÓN PDF (LIMPIA) ---
def generar_pdf_cotizacion(info_empresa, cliente_info, items, nro_cotizacion, fecha):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    # Estilos
    estilos = getSampleStyleSheet()
    estilo_normal = ParagraphStyle('Normal', fontSize=10)
    
    # Encabezado (Datos de Maquinarias Adonai)
    story.append(Paragraph(f"<b>{info_empresa['nombre']}</b>", estilos['Heading1']))
    story.append(Paragraph(f"RIF: {info_empresa['rif']}", estilo_normal))
    story.append(Paragraph(f"Telf: {info_empresa['telefono']}", estilo_normal))
    story.append(Spacer(1, 12))
    
    # Datos de Cotización y Cliente
    story.append(Paragraph(f"<b>Cotización:</b> {nro_cotizacion} | <b>Fecha:</b> {fecha}", estilo_normal))
    story.append(Paragraph(f"<b>Cliente:</b> {cliente_info['nombre']} | <b>RIF:</b> {cliente_info['rif']}", estilo_normal))
    story.append(Spacer(1, 12))

    # Tabla de productos
    tabla_data = [["Cant", "Descripción", "Precio", "Total"]]
    subtotal = 0
    for item in items:
        subtotal += item['total']
        tabla_data.append([str(item['cantidad']), item['descripcion'], f"${item['precio']:,.2f}", f"${item['total']:,.2f}"])
    
    # Totales con IVA
    iva = subtotal * 0.16
    tabla_data.append(["", "", "Subtotal:", f"${subtotal:,.2f}"])
    tabla_data.append(["", "", "IVA 16%:", f"${iva:,.2f}"])
    tabla_data.append(["", "", "<b>Total:</b>", f"<b>${subtotal + iva:,.2f}</b>"])
    
    t = Table(tabla_data, colWidths=[50, 250, 80, 80])
    # ... (aplicar diseño de tabla aquí) ...
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- MÓDULO COMERCIAL ---
def modulo_crear_cotizaciones():
    st.title("📝 Crear Nueva Cotización")
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    conn = database.conectar()
    try:
        clientes_df = pd.read_sql("SELECT nombre FROM entidades", conn)
        articulos_df = pd.read_sql("SELECT descripcion, precio_sugerido FROM articulos", conn)
    finally:
        conn.close()

    with tab1:
        # Selección de cliente
        cliente_sel = st.selectbox("Seleccionar Cliente:", options=clientes_df['nombre'].tolist())
        
        # Selección de productos (fuera de un form para que la descarga sea estable)
        filas_items = []
        for i in range(3):
            col1, col2, col3 = st.columns(3)
            art = col1.selectbox(f"Art {i+1}", ["--"] + articulos_df['descripcion'].tolist(), key=f"art_{i}")
            cant = col2.number_input(f"Cant {i+1}", min_value=0, key=f"c_{i}")
            prec = col3.number_input(f"Precio {i+1}", min_value=0.0, key=f"p_{i}")
            if art != "--" and cant > 0:
                filas_items.append({"descripcion": art, "cantidad": cant, "precio": prec, "total": cant * prec})

        # Botón de acción directa
        if st.button("📥 Generar y Descargar PDF"):
            if not filas_items:
                st.error("Debes agregar al menos un artículo.")
            else:
                nro = f"CAD-{random.randint(1000, 9999)}"
                pdf_generado = generar_pdf_cotizacion({"nombre_empresa": "MAQUINARIAS ADONAI"}, cliente_sel, filas_items, nro, date.today())
                
                st.success(f"¡Cotización {nro} generada con éxito!")
                st.download_button(
                    label="Haga clic aquí para descargar el archivo",
                    data=pdf_generado,
                    file_name=f"Cotizacion_{nro}.pdf",
                    mime="application/pdf"
                )

    with tab2:
        # Tu formulario de registro se mantiene igual, este sí funciona bien con st.form
        with st.form("form_nuevo_articulo"):
            # ... (código de tu formulario de catálogo) ...
            st.write("Catálogo de artículos") # Placeholder
            st.form_submit_button("💾 Guardar")
