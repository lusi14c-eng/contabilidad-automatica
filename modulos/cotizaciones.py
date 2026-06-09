import streamlit as st
import database
import pandas as pd
from datetime import date
import io
import random
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.discovery import build
from google.auth import default

# --- FUNCIONES DE SOPORTE (PDF Y DRIVE) ---
def generar_pdf_cotizacion(info_empresa, cliente, items, nro_cotizacion, fecha):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    estilos = getSampleStyleSheet()
    estilo_normal = ParagraphStyle('Normal', parent=estilos['Normal'], fontSize=9, leading=13)
    estilo_tabla_cabecera = ParagraphStyle('TH', parent=estilos['Normal'], fontSize=10, textColor=colors.white, alignment=1, fontName="Helvetica-Bold")

    texto_membrete = f"<b><font size=14>{info_empresa.get('nombre_empresa', 'MAQUINARIAS ADONAI')}</font></b><br/>"
    story.append(Paragraph(texto_membrete, estilo_normal))
    
    tabla_items = [[Paragraph("Cant", estilo_tabla_cabecera), Paragraph("Desc", estilo_tabla_cabecera), Paragraph("Precio", estilo_tabla_cabecera), Paragraph("Total", estilo_tabla_cabecera)]]
    for item in items:
        tabla_items.append([str(item['cantidad']), item['descripcion'], f"${item['precio']:,.2f}", f"${item['total']:,.2f}"])
    
    t_items = Table(tabla_items, colWidths=[60, 280, 100, 100])
    story.append(t_items)
    doc.build(story)
    buffer.seek(0)
    return buffer

def subir_pdf_a_drive(nombre_archivo, buffer_pdf):
    try:
        creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
        servicio = build('drive', 'v3', credentials=creds)
        id_carpeta_destino = st.secrets["google_drive"]["folder_id"]
        metadatos_archivo = {'name': nombre_archivo, 'parents': [id_carpeta_destino]}
        media = MediaIoBaseUpload(buffer_pdf, mimetype='application/pdf', resumable=True)
        servicio.files().create(body=metadatos_archivo, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        st.error(f"Error en Drive: {e}")
        return False

# --- MÓDULO COMERCIAL ---
def modulo_crear_cotizaciones():
    st.title("📝 Crear Nueva Cotización")
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    conn = database.conectar()
    try:
        clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades", conn)
        articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos", conn)
    finally:
        conn.close()

    with tab1:
        with st.form("form_cotizacion_detallada"):
            cliente_sel = st.selectbox("Cliente:", options=clientes_df['nombre'].tolist())
            filas_items = []
            for i in range(3):
                col1, col2, col3 = st.columns(3)
                art = col1.selectbox(f"Art {i+1}", ["--"] + articulos_df['descripcion'].tolist(), key=f"art_{i}")
                cant = col2.number_input(f"Cant {i+1}", min_value=0, key=f"c_{i}")
                prec = col3.number_input(f"Precio {i+1}", min_value=0.0, key=f"p_{i}")
                if art != "--" and cant > 0:
                    filas_items.append({"descripcion": art, "cantidad": cant, "precio": prec, "total": cant * prec})

            if st.form_submit_button("⚡ Generar y Subir"):
                if not filas_items:
                    st.error("Agrega al menos un artículo.")
                else:
                    info_cliente = clientes_df[clientes_df['nombre'] == cliente_sel].iloc[0]
                    nro = f"CAD-{random.randint(1000, 9999)}"
                    pdf = generar_pdf_cotizacion({"nombre_empresa": "MAQUINARIAS ADONAI"}, info_cliente, filas_items, nro, date.today())
                    if subir_pdf_a_drive(f"Cotizacion_{nro}.pdf", pdf):
                        st.success("¡Éxito!")
                        st.download_button("📥 Descargar", pdf, "cot.pdf", "application/pdf")

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
