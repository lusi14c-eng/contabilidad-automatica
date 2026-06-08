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

def modulo_crear_cotizaciones():
    st.title("📝 Crear Nueva Cotización")
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    # 1. Cargar datos desde la BD (esto es global para la función)
    conn = database.conectar()
    try:
        clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades", conn)
        articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos", conn)
    finally:
        conn.close()

    with tab1:
        with st.form("form_cotizacion_detallada"):
            st.subheader("Datos del Cliente")
            cliente_opciones = clientes_df.apply(lambda x: f"{x['nombre']} (RIF: {x['rif']})", axis=1)
            cliente_sel = st.selectbox("Seleccionar Cliente:", options=cliente_opciones)
            
            st.subheader("Items de la Cotización")
            filas_items = []
            for i in range(3):
                cols = st.columns([2, 1, 1])
                art_opciones = articulos_df.apply(lambda x: f"{x['codigo']} | {x['descripcion']}", axis=1)
                art_sel = cols[0].selectbox(f"Artículo {i+1}:", options=["--"] + art_opciones.tolist(), key=f"art_{i}")
                cant = cols[1].number_input(f"Cant:", min_value=0, key=f"cant_{i}")
                precio = cols[2].number_input(f"Precio:", min_value=0.0, value=0.0, key=f"prec_{i}")
                
                if art_sel != "--" and cant > 0:
                    filas_items.append({"descripcion": art_sel, "cantidad": cant, "precio": precio, "total": cant * precio})

            # EL BOTÓN ÚNICO QUE CONSOLIDA TODO
            if st.form_submit_button("⚡ Generar, Subir y Descargar"):
                if not filas_items:
                    st.error("Debes agregar al menos un artículo.")
                else:
                    # PROCESAMIENTO
                    info_cliente = clientes_df[clientes_df['nombre'] == cliente_sel.split(" (RIF:")[0]].iloc[0]
                    nro_control = f"CAD-{random.randint(1000, 9999)}"
                    
                    # Generar PDF
                    pdf_datos = generar_pdf_cotizacion({"nombre_empresa": "MAQUINARIAS ADONAI"}, info_cliente, filas_items, nro_control, date.today())
                    pdf_datos.seek(0)
                    
                    # Subir a Drive
                    subido = subir_pdf_a_drive(f"Cotizacion_{nro_control}.pdf", pdf_datos)
                    
                    if subido:
                        st.success("¡Respaldo exitoso en Drive!")
                    
                    # Mostrar botón de descarga
                    pdf_datos.seek(0)
                    st.download_button("📥 Descargar PDF", pdf_datos, f"Cotizacion_{nro_control}.pdf", "application/pdf")

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
