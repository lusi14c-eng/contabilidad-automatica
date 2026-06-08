import streamlit as st
import database
import pandas as pd
from datetime import date
import io
import random

# ==========================================
# LIBRERÍAS PARA GENERACIÓN DE PDF (REPORTLAB)
# ==========================================
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# LIBRERÍAS DE GOOGLE DRIVE API
# ==========================================
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth import default

def subida_credenciales_drive():
    """Autenticación para subir archivos a Google Drive."""
    try:
        creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error al conectar con Google Drive: {e}")
        return None

def generar_pdf_cotizacion(info_empresa, cliente, items, nro_cotizacion, fecha):
    """Genera un archivo PDF estructurado con el membrete y colores de Maquinarias Adonai."""
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
    
    texto_cliente_izq = f"<b>Empresa / Cliente:</b> {cliente['nombre']}<br/><b>RIF / Cédula:</b> {cliente['rif']}"
    texto_cliente_der = f"<b>Dirección Fiscal:</b> {cliente['direccion']}<br/><b>Teléfono:</b> {cliente.get('telefono', 'N/P')}"
    
    t_cliente = Table([[Paragraph(texto_cliente_izq, estilo_normal), Paragraph(texto_cliente_der, estilo_normal)]], colWidths=[240, 300])
    t_cliente.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    story.append(t_cliente)
    story.append(Spacer(1, 15))
    
    tabla_items = [[Paragraph("<b>Cantidad</b>", estilo_tabla_cabecera), Paragraph("<b>Descripción</b>", estilo_tabla_cabecera), Paragraph("<b>Precio U. ($)</b>", estilo_tabla_cabecera), Paragraph("<b>Total ($)</b>", estilo_tabla_cabecera)]]
    subtotal = 0
    for item in items:
        tabla_items.append([Paragraph(str(item['cantidad']), estilo_normal), Paragraph(item['descripcion'], estilo_normal), Paragraph(f"${item['precio']:,.2f}", estilo_normal), Paragraph(f"${item['total']:,.2f}", estilo_normal)])
        subtotal += item['total']
        
    iva = subtotal * 0.16
    tabla_items.append(["", "", Paragraph("<b>Sub-Total:</b>", estilo_normal), Paragraph(f"${subtotal:,.2f}", estilo_normal)])
    tabla_items.append(["", "", Paragraph("<b>I.V.A. (16%):</b>", estilo_normal), Paragraph(f"${iva:,.2f}", estilo_normal)])
    tabla_items.append(["", "", Paragraph("<b>Total General:</b>", estilo_normal), Paragraph(f"<b>${(subtotal + iva):,.2f}</b>", estilo_normal)])
    
    t_items = Table(tabla_items, colWidths=[60, 280, 100, 100])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7F8C8D")),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (2,0), (3,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-4), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    story.append(t_items)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def subir_pdf_a_drive(nombre_archivo, buffer_pdf):
    try:
        servicio = subida_credenciales_drive()
        id_carpeta_destino = st.secrets["google_drive"]["folder_id"]
        metadatos_archivo = {'name': nombre_archivo, 'parents': [id_carpeta_destino]}
        media = MediaIoBaseUpload(buffer_pdf, mimetype='application/pdf', resumable=True)
        servicio.files().create(body=metadatos_archivo, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        st.error(f"Error en Drive: {str(e)}")
        return False

def modulo_crear_cotizaciones():
    st.title("📄 Módulo Comercial - Maquinarias Adonai")
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    with tab1:
        st.subheader("Generador de Presupuestos")
        
        # 1. Carga de datos (esto debe ir fuera del form, pero antes de usarlo)
        conn = database.conectar()
        clientes_df, articulos_df = pd.DataFrame(), pd.DataFrame()
        if conn:
            try:
                clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades ORDER BY nombre ASC", conn)
                articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos ORDER BY codigo ASC", conn)
            except Exception as e:
                st.error(f"Error cargando datos: {e}")
            finally: 
                conn.close()

        if clientes_df.empty:
            st.warning("⚠️ No hay entidades registradas.")
        else:
            clientes_df['selector'] = clientes_df['rif'] + " - " + clientes_df['nombre']
            
            # 2. EL FORMULARIO COMPLETO
            with st.form("form_emision_cotizacion"):
                st.markdown("### 🏢 Seleccionar Cliente")
                col1, col2 = st.columns(2)
                cliente_sel = col1.selectbox("Empresa:", options=clientes_df['selector'].tolist())
                fecha_cot = col2.date_input("Fecha de Emisión:", value=date.today())
                
                info_cliente = clientes_df[clientes_df['selector'] == cliente_sel].iloc[0]
                
                # ... (Aquí iría tu lógica de filas_items que ya tienes) ...
                filas_items = [] # Asegúrate de que esta lista se llene con tus loops de artículos

                # BOTÓN DENTRO DEL FORM
                emitir = st.form_submit_button("⚡ Registrar y Guardar Cotización")
                
                # 3. LA LÓGICA DEBE ESTAR AQUÍ DENTRO
                if emitir:
                    if not filas_items:
                        st.error("Por favor, ingresa al menos un artículo.")
                    else:
                        info_empresa = database.obtener_configuracion_empresa()
                        nro_control = f"CAD-{random.randint(1000, 9999)}"
                        
                        pdf_datos = generar_pdf_cotizacion(info_empresa, info_cliente, filas_items, nro_control, fecha_cot)
                        nombre_archivo_pdf = f"Cotizacion_{nro_control}_{info_cliente['nombre'].replace(' ', '_')}.pdf"
                        
                        pdf_datos.seek(0)
                        with st.spinner("Subiendo respaldo PDF..."):
                            subido = subir_pdf_a_drive(nombre_archivo_pdf, pdf_datos)
                        
                        if subido:
                            st.success("¡Cotización guardada y respaldada en Drive!")
                        
                        st.download_button(label="📥 Descargar PDF", data=pdf_datos, file_name=nombre_archivo_pdf, mime="application/pdf")

    with tab2:
        st.subheader("📦 Registro de Servicios/repuestos")
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
