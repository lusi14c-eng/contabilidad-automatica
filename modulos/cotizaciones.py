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

# --- FUNCIONES DE SOPORTE (PDF Y DRIVE) ---
# [MANTÉN TUS FUNCIONES generar_pdf_cotizacion y subir_pdf_a_drive TAL CUAL LAS TENÍAS]

def modulo_crear_cotizaciones():
    st.title("📄 Módulo Comercial - Maquinarias Adonai")
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    # 1. CARGA DE DATOS (ESENCIAL)
    conn = database.conectar()
    try:
        clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades", conn)
        articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos", conn)
    except:
        clientes_df, articulos_df = pd.DataFrame(), pd.DataFrame()
    finally:
        conn.close()

    with tab1:
        if clientes_df.empty:
            st.warning("No hay clientes registrados en la base de datos.")
        else:
            with st.form("form_emision"):
                cliente_sel = st.selectbox("Seleccionar Cliente", clientes_df['nombre'])
                
                # SELECCIÓN DINÁMICA DE ARTÍCULOS
                filas_items = []
                for i in range(4):
                    st.write(f"--- Línea {i+1} ---")
                    c1, c2 = st.columns(2)
                    art = c1.selectbox(f"Artículo {i+1}", ["--"] + articulos_df['descripcion'].tolist(), key=f"art_{i}")
                    cant = c2.number_input(f"Cantidad {i+1}", min_value=0, key=f"cant_{i}")
                    
                    if art != "--" and cant > 0:
                        precio = articulos_df[articulos_df['descripcion'] == art]['precio_sugerido'].values[0]
                        filas_items.append({"descripcion": art, "cantidad": cant, "precio": precio, "total": cant * precio})

                emitir = st.form_submit_button("⚡ Registrar y Guardar Cotización")

                if emitir:
                    if not filas_items:
                        st.error("Por favor, selecciona al menos un artículo.")
                    else:
                        # PROCESAMIENTO
                        info_cliente = clientes_df[clientes_df['nombre'] == cliente_sel].iloc[0]
                        nro_control = f"CAD-{random.randint(1000, 9999)}"
                        
                        pdf_datos = generar_pdf_cotizacion({"nombre_empresa": "MAQUINARIAS ADONAI"}, info_cliente, filas_items, nro_control, date.today())
                        
                        pdf_datos.seek(0)
                        subido = subir_pdf_a_drive(f"Cotizacion_{nro_control}.pdf", pdf_datos)
                        
                        if subido:
                            st.success("¡Respaldo exitoso en Drive!")
                        st.download_button("📥 Descargar PDF", pdf_datos, "cotizacion.pdf", "application/pdf")

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
