# modulos/cotizaciones.py
import streamlit as st
import pandas as pd
import database
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- INTEGRACIÓN CON GOOGLE DRIVE ---
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def subir_a_google_drive(pdf_bytes, nombre_archivo):
    """Sube el archivo PDF generado en memoria directamente a Google Drive."""
    try:
        # Extrae las credenciales guardadas de forma segura en Streamlit Secrets
        creds_dict = st.secrets["google_drive"]
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': nombre_archivo,
            'mimeType': 'application/pdf'
        }
        
        # Opcional: Si configuras un ID de carpeta específica en tus secrets
        if "folder_id" in st.secrets["google_drive"]:
            file_metadata['parents'] = [st.secrets["google_drive"]["folder_id"]]
            
        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype='application/pdf', resumable=True)
        file_drive = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file_drive.get('id')
    except Exception as e:
        st.error(f"⚠️ Alerta Drive: No se pudo subir la copia a la nube. Detalle: {e}")
        return None

# --- GENERADOR DE PDF PROFESIONAL ---
def generar_pdf_cotizacion(conf_empresa, num_cot, cliente, df_items, subtotal, iva, total):
    """Genera un reporte PDF estético y corporativo listo para descargar."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor("#1A365D"), spaceAfter=6)
    normal_style = ParagraphStyle('DocNormal', parent=styles['Normal'], fontSize=9, leading=12)
    bold_style = ParagraphStyle('DocBold', parent=styles['Normal'], fontSize=9, fontName="Helvetica-Bold", leading=12)
    
    # Header: Datos de la Empresa y la Cotización
    info_empresa = f"<b>{conf_empresa['nombre_empresa']}</b><br/>RIF: {conf_empresa['rif_empresa']}<br/>Dirección: {conf_empresa['direccion_empresa']}"
    info_cotizacion = f"<b>COTIZACIÓN</b><br/>Número: {num_cot}<br/>Fecha: {datetime.today().strftime('%d/%m/%Y')}<br/>Validez: 15 Días"
    
    header_table = Table([[Paragraph(info_empresa, normal_style), Paragraph(info_cotizacion, normal_style)]], colWidths=[340, 200])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(header_table)
    story.append(Spacer(1, 20))
    
    # Datos del Cliente
    story.append(Paragraph(f"<b>CLIENTE / RAZÓN SOCIAL:</b> {cliente.upper()}", normal_style))
    story.append(Spacer(1, 15))
    
    # Tabla de Productos/Servicios
    table_data = [[Paragraph("<b>Descripción del Ítem</b>", bold_style), Paragraph("<b>Cant.</b>", bold_style), Paragraph("<b>P. Unit (Bs.)</b>", bold_style), Paragraph("<b>Total (Bs.)</b>", bold_style)]]
    
    for _, fila in df_items.iterrows():
        desc = fila["Descripción"]
        cant = float(fila["Cantidad"])
        precio = float(fila["Precio Unitario (Bs.)"])
        linea_total = cant * precio
        
        table_data.append([
            Paragraph(desc, normal_style),
            Paragraph(f"{cant:,.2f}", normal_style),
            Paragraph(f"{precio:,.2f}", normal_style),
            Paragraph(f"{linea_total:,.2f}", normal_style)
        ])
    
    # Bloque de Totales
    table_data.append(["", "", Paragraph("<b>Subtotal:</b>", normal_style), Paragraph(f"{subtotal:,.2f}", normal_style)])
    table_data.append(["", "", Paragraph("<b>I.V.A (16%):</b>", normal_style), Paragraph(f"{iva:,.2f}", normal_style)])
    table_data.append(["", "", Paragraph("<b>Total General:</b>", bold_style), Paragraph(f"<b>{total:,.2f}</b>", bold_style)])
    
    productos_table = Table(table_data, colWidths=[280, 60, 100, 100])
    productos_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-4), 0.5, colors.lightgrey),
        ('LINEBELOW', (2,-3), (3,-1), 1, colors.HexColor("#1A365D")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    
    story.append(productos_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- MÓDULO PRINCIPAL INTERFAZ STREAMLIT ---
def modulo_crear_cotizaciones():
    st.title("📝 Generador de Cotizaciones")
    conf = database.obtener_configuracion_empresa()
    
    # Generamos correlativo único simulado basado en marcas de tiempo para evitar colisiones
    num_cot_sugerido = database.obtener_ultimo_correlativo("COT")
    
    col_c1, col_c2 = st.columns([2, 1])
    cliente = col_c1.text_input("Razón Social o Nombre del Cliente")
    fecha_cot = col_c2.date_input("Fecha Emisión", datetime.today())
    
    st.markdown("#### 📦 Detalle de Conceptos / Productos")
    st.caption("Haz doble clic sobre una celda para editar y presiona el botón '+' abajo a la izquierda para agregar más filas.")
    
    # Estructura de tabla dinámica intuitiva para el usuario
    if "items_cotizacion" not in st.session_state:
        st.session_state.items_cotizacion = pd.DataFrame([
            {"Descripción": "Servicio de Consultoría Financiera", "Cantidad": 1.0, "Precio Unitario (Bs.)": 2500.00}
        ])
        
    df_editado = st.data_editor(
        st.session_state.items_cotizacion,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_cotizacion"
    )
    
    # Cálculos en Caliente
    subtotal = 0.0
    for _, r in df_editado.iterrows():
        try:
            subtotal += float(r["Cantidad"] or 0) * float(r["Precio Unitario (Bs.)"] or 0)
        except: pass
        
    iva = subtotal * 0.16
    total_general = subtotal + iva
    
    # Panel de Resumen Monetario
    c_t1, c_t2, c_t3 = st.columns(3)
    c_t1.metric("Subtotal", f"Bs. {subtotal:,.2f}")
    c_t2.metric("I.V.A (16%)", f"Bs. {iva:,.2f}")
    c_t3.metric("Total General", f"Bs. {total_general:,.2f}")
    
    if st.button("🚀 Procesar, Guardar y Sincronizar Cotización", type="primary"):
        if not cliente.strip():
            st.error("Por favor, introduzca el nombre del cliente.")
            return
        if df_editado.empty or df_editado.iloc[0]["Descripción"] == "":
            st.error("La tabla de ítems no puede estar vacía.")
            return
            
        # 1. Generar el binario del PDF en Memoria
        pdf_data = generar_pdf_cotizacion(conf, num_cot_sugerido, cliente, df_editado, subtotal, iva, total_general)
        
        # 2. Respaldar en Google Drive de forma automática
        nombre_pdf = f"{num_cot_sugerido}_{cliente.replace(' ', '_')}.pdf"
        drive_id = subir_a_google_drive(pdf_data, nombre_pdf)
        
        # 3. Almacenar en la Base de Datos Relacional de Neon
        database.ejecutar_transaccion(
            """INSERT INTO cotizaciones_cabecera (num_cotizacion, cliente, fecha, subtotal, iva, total, creado_por, drive_file_id) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (num_cot_sugerido, cliente, fecha_cot, subtotal, iva, total_general, st.session_state['usuario_autenticado'], drive_id)
        )
        
        # Recuperar ID insertado para asociar el desglose
        conn = database.conectar()
        c = conn.cursor()
        c.execute("SELECT id FROM cotizaciones_cabecera WHERE num_cotizacion = %s", (num_cot_sugerido,))
        cot_id = c.fetchone()[0]
        conn.close()
        
        for _, fila in df_editado.iterrows():
            c_linea = float(fila["Cantidad"])
            p_linea = float(fila["Precio Unitario (Bs.)"])
            database.ejecutar_transaccion(
                """INSERT INTO cotizaciones_detalle (cotizacion_id, descripcion, cantidad, precio_unitario, total_linea) 
                   VALUES (%s, %s, %s, %s, %s)""",
                (cot_id, fila["Descripción"], c_linea, p_linea, c_linea * p_linea)
            )
            
        database.registrar_log(st.session_state['usuario_autenticado'], "CREAR", "cotizaciones_cabecera", f"Generó cotización {num_cot_sugerido}")
        
        st.success(f"✅ ¡Cotización {num_cot_sugerido} procesada!")
        if drive_id:
            st.info(f"☁️ Guardada con éxito en Google Drive (ID: {drive_id})")
            
        # Botón de Descarga Nativo en la interfaz para el usuario local
        st.download_button(
            label="📥 Descargar PDF de la Cotización",
            data=pdf_data,
            file_name=nombre_pdf,
            mime="application/pdf"
        )
