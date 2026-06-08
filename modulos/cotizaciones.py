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
from googleapiclient.http import MediaIoBaseUpload  # <--- ESTA ES LA LÍNEA QUE FALTA
from google.auth import default # Para la conexión automática

def subida_credenciales_drive():
    """Autenticación para subir archivos a Google Drive."""
    try:
        # Esto usará los permisos del entorno (en Streamlit Cloud funciona automático)
        creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error al conectar con Google Drive: {e}")
        return None

def generar_pdf_cotizacion(info_empresa, cliente, items, nro_cotizacion, fecha):
    """Genera un archivo PDF estructurado con el membrete y colores de Maquinarias Adonai."""
    buffer = io.BytesIO()
    # Configuración de página tipo carta con márgenes óptimos
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    estilos = getSampleStyleSheet()
    estilo_normal = ParagraphStyle('Normal', parent=estilos['Normal'], fontSize=9, leading=13)
    estilo_tabla_cabecera = ParagraphStyle('TH', parent=estilos['Normal'], fontSize=10, textColor=colors.white, alignment=1, fontName="Helvetica-Bold")

    # 1. MEMBRETE CORPORATIVO DE MAQUINARIAS ADONAI
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
    t_membrete.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))
    story.append(t_membrete)
    story.append(Spacer(1, 15))
    
    # 2. SECCIÓN DE DATOS DEL CLIENTE
    texto_cliente_izq = f"""
    <b>Empresa / Cliente:</b> {cliente['nombre']}<br/>
    <b>RIF / Cédula:</b> {cliente['rif']}
    """
    texto_cliente_der = f"""
    <b>Dirección Fiscal:</b> {cliente['direccion']}<br/>
    <b>Teléfono:</b> {cliente.get('telefono', 'N/P')}
    """
    
    t_cliente = Table([[Paragraph(texto_cliente_izq, estilo_normal), Paragraph(texto_cliente_der, estilo_normal)]], colWidths=[240, 300])
    t_cliente.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    story.append(t_cliente)
    story.append(Spacer(1, 15))
    
    # 3. TABLA DE ARTÍCULOS Y REPUESTOS COMANZADOS
    tabla_items = [[
        Paragraph("<b>Cantidad</b>", estilo_tabla_cabecera), 
        Paragraph("<b>Descripción</b>", estilo_tabla_cabecera), 
        Paragraph("<b>Precio U. ($)</b>", estilo_tabla_cabecera), 
        Paragraph("<b>Total ($)</b>", estilo_tabla_cabecera)
    ]]
    
    subtotal = 0
    for item in items:
        tabla_items.append([
            Paragraph(str(item['cantidad']), estilo_normal),
            Paragraph(item['descripcion'], estilo_normal),
            Paragraph(f"${item['precio']:,.2f}", estilo_normal),
            Paragraph(f"${item['total']:,.2f}", estilo_normal)
        ])
        subtotal += item['total']
        
    # Estructura de Totales e Impuestos (IVA 16%)
    iva = subtotal * 0.16
    total_general = subtotal + iva
    
    tabla_items.append(["", "", Paragraph("<b>Sub-Total:</b>", estilo_normal), Paragraph(f"${subtotal:,.2f}", estilo_normal)])
    tabla_items.append(["", "", Paragraph("<b>I.V.A. (16%):</b>", estilo_normal), Paragraph(f"${iva:,.2f}", estilo_normal)])
    tabla_items.append(["", "", Paragraph("<b>Total General:</b>", estilo_normal), Paragraph(f"<b>${total_general:,.2f}</b>", estilo_normal)])
    
    t_items = Table(tabla_items, colWidths=[60, 280, 100, 100])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7F8C8D")), # Gris industrial Adonai
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (2,0), (3,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-4), 0.5, colors.HexColor("#E2E8F0")), 
        ('LINEBELOW', (2,-3), (3,-1), 1, colors.HexColor("#7F8C8D")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(t_items)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def subir_pdf_a_drive(nombre_archivo, buffer_pdf):
    """Sube el archivo PDF en memoria directo a la carpeta compartida en Google Drive."""
    try:
        servicio = subida_credenciales_drive()
        id_carpeta_destino = st.secrets["google_drive"]["folder_id"]
        
        metadatos_archivo = {
            'name': nombre_archivo,
            'parents': [id_carpeta_destino]
        }
        media = MediaIoBaseUpload(buffer_pdf, mimetype='application/pdf', resumable=True)
        servicio.files().create(body=metadatos_archivo, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        st.error(f"Error al respaldar en Google Drive: {e}")
        return False

def modulo_crear_cotizaciones():
    st.title("📄 Módulo Comercial - Maquinarias Adonai")
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    with tab1:
        st.subheader("Generador de Presupuestos")
        
        conn = database.conectar()
        clientes_df, articulos_df = pd.DataFrame(), pd.DataFrame()
        if conn:
            try:
                clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades ORDER BY nombre ASC", conn)
                articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos ORDER BY codigo ASC", conn)
            except Exception as e:
                st.error(f"Error cargando datos de Neon: {e}")
            finally: 
                conn.close()

        if clientes_df.empty:
            st.warning("⚠️ No hay entidades en el sistema. Regístralas en Configuración Sistema.")
        else:
            clientes_df['selector'] = clientes_df['rif'] + " - " + clientes_df['nombre']
            
            with st.form("form_emision_cotizacion"):
                st.markdown("### 🏢 Seleccionar Cliente")
                col1, col2 = st.columns(2)
                cliente_sel = col1.selectbox("Empresa:", options=clientes_df['selector'].tolist())
                fecha_cot = col2.date_input("Fecha de Emisión:", value=date.today())
                
                info_cliente = clientes_df[clientes_df['selector'] == cliente_sel].iloc[0]
                st.caption(f"📍 **Dirección Fiscal registrada:** {info_cliente['direccion']}")
                st.divider()

                st.markdown("### 🛒 Ítems a Cotizar")
                filas_items = []
                for i in range(1, 5):
                    st.markdown(f"**Línea N° {i}**")
                    c1, c2, c3 = st.columns([3, 1, 2])
                    
                    opciones_art = ["-- Seleccionar del catálogo --"] + (articulos_df['codigo'] + " | " + articulos_df['descripcion']).tolist() if not articulos_df.empty else ["-- Sin artículos --"]
                    art_sel = c1.selectbox(f"Artículo {i}:", options=opciones_art, key=f"art_{i}")
                    cant = c2.number_input("Cant:", min_value=0, value=0, step=1, key=f"cant_{i}")
                    
                    precio_defecto = 0.00
                    desc_defecto = ""
                    if " | " in art_sel:
                        cod_extraido = art_sel.split(" | ")[0]
                        row_art = articulos_df[articulos_df['codigo'] == cod_extraido].iloc[0]
                        precio_defecto = float(row_art['precio_sugerido'])
                        desc_defecto = row_art['descripcion']
                        
                    precio_u = c3.number_input("Precio U.:", min_value=0.00, value=precio_defecto, format="%.2f", key=f"precio_{i}")
                    
                    if cant > 0:
                        filas_items.append({
                            "descripcion": desc_defecto if desc_defecto else f"Reparacion / Servicio Personalizado {i}",
                            "cantidad": cant,
                            "precio": precio_u,
                            "total": cant * precio_u
                        })
                
                # BOTÓN DE PROCESAMIENTO UNIFICADO
                emitir = st.form_submit_button("⚡ Registrar y Guardar Cotización")
                
                if emitir:
                    if not filas_items:
                        st.error("Por favor, ingresa al menos un artículo con cantidad mayor a 0.")
                    else:
                        # 1. Guardar en Base de Datos (Neon)
                        # Nota: Si ya tienes tu función de guardado SQL para insertar en tablas de cotizaciones, llámala aquí.
                        
                        # 2. Generar el PDF corporativo en memoria
                        info_empresa = database.obtener_configuracion_empresa()
                        nro_control = f"CAD-{random.randint(1000, 9999)}" # Correlativo dinámico temporal
                        
                        pdf_datos = generar_pdf_cotizacion(info_empresa, info_cliente, filas_items, nro_control, fecha_cot)
                        nombre_archivo_pdf = f"Cotizacion_{nro_control}_{info_cliente['nombre'].replace(' ', '_')}.pdf"
                        
                        # 3. Subir de forma automática al Google Drive de la empresa
                        with st.spinner("Subiendo respaldo PDF de forma segura al Google Drive empresarial..."):
                            subido = subir_pdf_a_drive(nombre_archivo_pdf, pdf_datos)
                        
                        if subido:
                            st.success(f"¡Cotización guardada exitosamente para Maquinarias Adonai de Venezuela, C.A.!")
                            st.info(f"💾 El documento '{nombre_archivo_pdf}' ha sido respaldado en Google Drive con éxito.")
                            
                            # 4. Habilitar la descarga local para el usuario en pantalla
                            st.download_button(
                                label="📥 Guardar copia local en PDF",
                                data=pdf_datos,
                                file_name=nombre_archivo_pdf,
                                mime="application/pdf"
                            )
                        else:
                            st.warning("⚠️ La cotización se procesó pero no se pudo subir a Drive. Revisa los permisos de la carpeta corporativa.")

    with tab2:
        st.subheader("📦 Registro de Repuestos y Componentes")
        # Aquí mantienes intacto el código de tu formulario existente para insertar artículos a la BD.
