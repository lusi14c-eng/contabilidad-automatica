# modulos/cotizaciones.py
import streamlit as st
import database
import pandas as pd
from datetime import date
import io
import random

# Librerías de diseño PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Librerías de Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def subida_credenciales_drive():
    """Autentica con Google Drive usando los secretos."""
    info_claves = dict(st.secrets["gcp_service_account"])
    info_claves["private_key"] = info_claves["private_key"].replace("\\n", "\n")
    credenciales = service_account.Credentials.from_service_account_info(info_claves)
    return build('drive', 'v3', credentials=credenciales)

def generar_pdf_cotizacion(info_empresa, cliente, items, nro_cotizacion, fecha):
    """Genera un PDF con el diseño corporativo de Maquinarias Adonai (Membrete y Totales)."""
    buffer = io.BytesIO()
    # Márgenes limpios para aprovechar la hoja tipo carta
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    estilos = getSampleStyleSheet()
    estilo_normal = ParagraphStyle('Normal', parent=estilos['Normal'], fontSize=9, leading=13)
    estilo_tabla_cabecera = ParagraphStyle('TH', parent=estilos['Normal'], fontSize=10, textColor=colors.white, alignment=1, fontName="Helvetica-Bold")

    # 1. MEMBRETE / ENCABEZADO (Basado fielmente en tu Excel corporativo)
    texto_membrete = f"""
    <b><font size=14>{info_empresa.get('nombre_empresa', 'MAQUINARIAS ADONAI DE VENEZUELA, C.A.')}</font></b><br/>
    <b>RIF: {info_empresa.get('rif_empresa', 'J-41166121-0')}</b><br/>
    Reparación de Maquinaria. Hidráulica, a combustión y eléctrica.<br/>
    Correo: madovenca@gmail.com Telf: 0424-471-90-78
    """
    
    texto_control = f"""
    <font size=14 color='#1A365D'><b>COTIZACIÓN</b></font><br/><br/>
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
    
    # 2. DATOS DEL CLIENTE (Estructura limpia en bloque)
    texto_cliente_izq = f"""
    <b>Empresa:</b> {cliente['nombre']}<br/>
    <b>RIF:</b> {cliente['rif']}
    """
    texto_cliente_der = f"""
    <b>Dirección:</b> {cliente['direccion']}<br/>
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
    
    # 3. TABLA DE ARTÍCULOS (Réplica de columnas: Cantidad, Descripción, Precio, Total)
    tabla_items = [[
        Paragraph("<b>Cantidad</b>", estilo_tabla_cabecera), 
        Paragraph("<b>Descripción</b>", estilo_tabla_cabecera), 
        Paragraph("<b>Precio</b>", estilo_tabla_cabecera), 
        Paragraph("<b>Total</b>", estilo_tabla_cabecera)
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
        
    # Cálculos de Totales (Multi-moneda o formato estándar de tu reporte)
    iva = subtotal * 0.16
    total_general = subtotal + iva
    
    tabla_items.append(["", "", Paragraph("<b>Sub-Total:</b>", estilo_normal), Paragraph(f"${subtotal:,.2f}", estilo_normal)])
    tabla_items.append(["", "", Paragraph("<b>I.V.A. (16%):</b>", estilo_normal), Paragraph(f"${iva:,.2f}", estilo_normal)])
    tabla_items.append(["", "", Paragraph("<b>Total General:</b>", estilo_normal), Paragraph(f"<b>${total_general:,.2f}</b>", estilo_normal)])
    
    # Anchos fijos combinados para sumar exactamente 540 puntos (ancho de página letter disponible)
    t_items = Table(tabla_items, colWidths=[60, 280, 100, 100])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7F8C8D")), # Gris oscuro industrial de tu plantilla
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
    """Envia el archivo binario directo a la carpeta compartida en el Google Drive corporativo."""
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
                st.error(f"Error base de datos: {e}")
            finally: conn.close()

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
                            "descripcion": desc_defecto if desc_defecto else f"Ítem personalizado {i}",
                            "cantidad": cant,
                            "precio": precio_u,
                            "total": cant * precio_u
                        })
                
                if st.form_submit_button("⚡ Registrar y Guardar Cotización"):
                    if not filas_items:
                        st.error("Por favor, ingresa al menos un artículo con cantidad mayor a 0.")
                    else:
                        info_empresa = database.obtener_configuracion_empresa()
                        nro_control = f"001{random.randint(100, 999)}" # Correlativo automático simulación
                        
                        # Generar el PDF corporativo limpio
                        pdf_datos = generar_pdf_cotizacion(info_empresa, info_cliente, filas_items, nro_control, fecha_cot)
                        
                        # Subir automáticamente al Drive de la empresa
                        nombre_archivo_pdf = f"Cotizacion_{nro_control}_{info_cliente['nombre'].replace(' ', '_')}.pdf"
                        subido = subir_pdf_a_drive(nombre_archivo_pdf, pdf_datos)
                        
                        if subido:
                            st.success(f"🎉 ¡Cotización {nro_control} emitida con éxito y respaldada en el Google Drive de la empresa!")
                            
                            # Opción complementaria de descarga directa
                            st.download_button(
                                label="📥 Guardar copia local en PDF",
                                data=pdf_datos,
                                file_name=nombre_archivo_pdf,
                                mime="application/pdf"
                            )


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
