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
    st.title("📝 Módulo Comercial - Maquinarias Adonai")
    
    # 1. Definir los tabs al principio
    tab1, tab2 = st.tabs(["📄 Nueva Cotización", "📦 Catálogo de Artículos"])

    # 2. Cargar datos desde la BD (necesarios para ambos tabs)
    conn = database.conectar()
    try:
        clientes_df = pd.read_sql("SELECT rif, nombre, direccion FROM entidades", conn)
        articulos_df = pd.read_sql("SELECT codigo, descripcion, precio_sugerido FROM articulos", conn)
    except:
        clientes_df, articulos_df = pd.DataFrame(), pd.DataFrame()
    finally:
        conn.close()

    # 3. Lógica del Tab 1
    with tab1:
        with st.form("form_cotizacion_final"):
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

            if st.form_submit_button("⚡ Generar y Guardar Cotización"):
                if not filas_items:
                    st.error("Por favor, agrega al menos un artículo.")
                else:
                    info_cliente = clientes_df[clientes_df['nombre'] == cliente_sel.split(" (RIF:")[0]].iloc[0]
                    nro_control = f"CAD-{random.randint(1000, 9999)}"
                    # Aquí llamarías a tu función de generación de PDF
                    st.success(f"Cotización {nro_control} procesada.")

    # 4. Lógica del Tab 2
    with tab2:
        st.subheader("📦 Registro de Servicios/repuestos")
        with st.form("form_nuevo_articulo"):
            c1, c2, c3 = st.columns(3)
            cod = c1.text_input("Código:").strip().upper()
            desc = c2.text_input("Descripción:")
            prec = c3.number_input("Precio:", min_value=0.0)
            
            if st.form_submit_button("💾 Registrar en Catálogo"):
                if cod and desc:
                    database.ejecutar_transaccion("INSERT INTO articulos ...", (cod, desc, prec))
                    st.success("Guardado.")
                    st.rerun()
