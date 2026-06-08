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
from google.auth import default
from googleapiclient.discovery import build

# --- FUNCIONES DE SOPORTE ---
def generar_pdf_cotizacion(info_empresa, cliente, items, nro_cotizacion, fecha):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    estilos = getSampleStyleSheet()
    
    # Membrete y tabla simplificados para mayor claridad
    story.append(Paragraph(f"<b>{info_empresa.get('nombre_empresa')}</b>", estilos['Title']))
    story.append(Paragraph(f"Cotización N°: {nro_cotizacion} | Fecha: {fecha}", estilos['Normal']))
    story.append(Spacer(1, 12))
    
    # Tabla de Items
    data = [["Cant", "Descripción", "Precio", "Total"]]
    for item in items:
        data.append([item['cantidad'], item['descripcion'], f"${item['precio']}", f"${item['total']}"])
    
    t = Table(data, colWidths=[50, 250, 80, 80])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
    story.append(t)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def modulo_crear_cotizaciones():
    st.title("📄 Módulo Comercial")
    
    # 1. Cargar datos reales de la base de datos
    conn = database.conectar()
    articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos", conn)
    conn.close()

    with st.form("form_cotizacion"):
        # 2. Selección de artículos dinámicos
        st.subheader("Selección de Productos")
        items_seleccionados = []
        
        for i in range(3): # Permite elegir hasta 3 artículos
            col1, col2, col3 = st.columns([3, 1, 1])
            art_sel = col1.selectbox(f"Artículo {i+1}", options=["-- Seleccionar --"] + articulos_df['descripcion'].tolist())
            cantidad = col2.number_input(f"Cant {i+1}", min_value=0, key=f"c_{i}")
            
            if art_sel != "-- Seleccionar --" and cantidad > 0:
                precio = articulos_df[articulos_df['descripcion'] == art_sel]['precio_sugerido'].values[0]
                items_seleccionados.append({
                    "descripcion": art_sel,
                    "cantidad": cantidad,
                    "precio": precio,
                    "total": cantidad * precio
                })

        submit = st.form_submit_button("⚡ Generar y Subir a Drive")
        
        if submit:
            if not items_seleccionados:
                st.error("¡Debes seleccionar al menos un artículo con cantidad!")
            else:
                # Generación y subida
                pdf = generar_pdf_cotizacion({"nombre_empresa": "MAQUINARIAS ADONAI"}, {"nombre": "Cliente", "rif": "J-000", "direccion": "Sin dirección"}, items_seleccionados, "123", date.today())
                st.success("¡PDF Generado! Subiendo...")

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
