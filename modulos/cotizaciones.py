import streamlit as st
import database
import pandas as pd
from datetime import date
import io
import random

# LIBRERÍAS PARA GENERACIÓN DE PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# LIBRERÍAS DE GOOGLE DRIVE API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth import default

def subida_credenciales_drive():
    """Autenticación para subir archivos a Google Drive."""
    try:
        # Usa credenciales automáticas (configuradas en el entorno o archivo local)
        creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error al conectar con Google Drive: {e}")
        return None

def generar_pdf_cotizacion(info_empresa, cliente, items, nro_cotizacion, fecha):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    estilos = getSampleStyleSheet()
    estilo_normal = ParagraphStyle('Normal', parent=estilos['Normal'], fontSize=9, leading=13)
    estilo_tabla_cabecera = ParagraphStyle('TH', parent=estilos['Normal'], fontSize=10, textColor=colors.white, alignment=1, fontName="Helvetica-Bold")

    texto_membrete = f"""
    <b><font size=14>{info_empresa.get('nombre_empresa', 'MAQUINARIAS ADONAI DE VENEZUELA, C.A.')}</font></b><br/>
    <b>RIF: {info_empresa.get('rif_empresa', 'J-41166121-0')}</b><br/>
    Reparación de Maquinaria. Hidráulica, a combustión y eléctrica.<br/>
    Correo: madovenca@gmail.com Telf: 0424-471-90-78
    """
    
    texto_control = f"""
    <font size=14 color='#2C3E50'><b>COTIZACIÓN</b></font><br/><br/>
    <b>Cotización N°:</b> {nro_cotizacion}<br/>
    <b>Fecha:</b> {fecha.strftime('%d/%m/%Y')}
    """
    
    t_membrete = Table([[Paragraph(texto_membrete, estilo_normal), Paragraph(texto_control, estilo_normal)]], colWidths=[360, 180])
    t_membrete.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT')]))
    story.append(t_membrete)
    story.append(Spacer(1, 15))
    
    # Datos del cliente
    texto_cliente_izq = f"<b>Empresa:</b> {cliente['nombre']}<br/><b>RIF:</b> {cliente['rif']}"
    texto_cliente_der = f"<b>Dirección:</b> {cliente['direccion']}<br/><b>Teléfono:</b> {cliente.get('telefono', 'N/P')}"
    t_cliente = Table([[Paragraph(texto_cliente_izq, estilo_normal), Paragraph(texto_cliente_der, estilo_normal)]], colWidths=[240, 300])
    story.append(t_cliente)
    story.append(Spacer(1, 15))
    
    # Tabla items
    tabla_items = [[Paragraph("Cant", estilo_tabla_cabecera), Paragraph("Descripción", estilo_tabla_cabecera), Paragraph("Precio U.", estilo_tabla_cabecera), Paragraph("Total", estilo_tabla_cabecera)]]
    subtotal = 0
    for item in items:
        tabla_items.append([Paragraph(str(item['cantidad']), estilo_normal), Paragraph(item['descripcion'], estilo_normal), Paragraph(f"${item['precio']:,.2f}", estilo_normal), Paragraph(f"${item['total']:,.2f}", estilo_normal)])
        subtotal += item['total']
        
    tabla_items.append(["", "", Paragraph("Sub-Total:", estilo_normal), Paragraph(f"${subtotal:,.2f}", estilo_normal)])
    tabla_items.append(["", "", Paragraph("Total General:", estilo_normal), Paragraph(f"${(subtotal*1.16):,.2f}", estilo_normal)])
    
    t_items = Table(tabla_items, colWidths=[60, 280, 100, 100])
    story.append(t_items)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def subir_pdf_a_drive(nombre_archivo, buffer_pdf):
    try:
        servicio = subida_credenciales_drive()
        id_carpeta = st.secrets["google_drive"]["folder_id"]
        metadatos = {'name': nombre_archivo, 'parents': [id_carpeta]}
        media = MediaIoBaseUpload(buffer_pdf, mimetype='application/pdf', resumable=True)
        servicio.files().create(body=metadatos, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        st.error(f"Error al subir: {e}")
        return False

def modulo_crear_cotizaciones():
    st.title("📄 Módulo Comercial")
    with st.form("form_emision"):
        # ... (Tu lógica de selectbox y entradas de items va aquí) ...
        emitir = st.form_submit_button("⚡ Registrar y Guardar")
        
        if emitir:
            # Generar
            pdf_datos = generar_pdf_cotizacion(...) # Pasa tus datos reales
            nombre = f"Cotizacion_{random.randint(1000,9999)}.pdf"
            
            # Subir
            pdf_datos.seek(0)
            if subir_pdf_a_drive(nombre, pdf_datos):
                st.success("¡Subido exitosamente!")
