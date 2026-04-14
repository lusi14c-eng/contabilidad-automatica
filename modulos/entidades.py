import streamlit as st
import pandas as pd
import re
import sys
import os

# Esto asegura que Python encuentre el archivo database.py que está en la carpeta raíz
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database 

def modulo_maestro_entidades():
    st.title("👥 Gestión de Clientes y Proveedores")

    tab1, tab2 = st.tabs(["🆕 Registrar Nuevo", "📋 Listado General"])

    with tab1:
        st.subheader("Formulario de Registro")
        with st.form("form_entidad", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                rif_input = st.text_input("RIF (Ej: J123456789):").upper().strip()
                nombre = st.text_input("Razón Social / Nombre:")
                direccion = st.text_area("Dirección Fiscal:")
                tipo_persona = st.selectbox("Tipo de Persona:", 
                                         ["Jurídica Domiciliada", "Natural Residente", "Jurídica No Domiciliada", "Natural No Residente", "Gubernamental"])
            with col2:
                categoria = st.selectbox("Categoría:", ["PROVEEDOR", "CLIENTE", "AMBOS"])
                tipo_c = st.selectbox("Tipo de Contribuyente (SENIAT):", 
                                    ["Especial", "Ordinario", "Exento", "Formal"])
                islr_pct = st.number_input("% Retención ISLR:", min_value=0.0, value=2.0)
                iva_pct = st.selectbox("% Retención IVA:", [0, 75, 100])
                
            submit = st.form_submit_button("✅ Guardar Entidad")

            if submit:
                rif_limpio = rif_input.replace("-", "").replace(" ", "")
                
                if not re.match(r'^[VJGPE]\d{7,10}$', rif_limpio):
                    st.error("❌ RIF inválido. Debe empezar con V, J, G, P o E seguido de 7 a 10 números.")
                elif len(nombre) < 3:
                    st.error("❌ El nombre es demasiado corto.")
                else:
                    try:
                        conn = database.conectar()
                        if conn:
                            c = conn.cursor()
                            # 1. VERIFICAR SI YA EXISTE
                            c.execute("SELECT rif FROM entidades WHERE rif = %s", (rif_limpio,))
                            if c.fetchone():
                                st.warning(f"⚠️ El RIF {rif_limpio} ya está registrado.")
                            else:
                                # 2. INSERTAR
                                query_insert = """
                                    INSERT INTO entidades (rif, nombre, direccion, tipo_persona, 
                                    tipo_contribuyente, categoria, retencion_islr_pct, retencion_iva_pct)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """
                                valores = (rif_limpio, nombre, direccion, tipo_persona, 
                                          tipo_c, categoria, islr_pct, iva_pct)
                                
                                c.execute(query_insert, valores)
                                conn.commit()
                                st.success(f"✅ {nombre} registrado exitosamente.")
                            
                            c.close()
                            conn.close()
                    except Exception as e:
                        st.error(f"❌ Error en la base de datos: {e}")

    with tab2:
        ver_listado_completo()

def ver_listado_completo():
    st.subheader("🗂️ Base de Datos de Entidades")
    try:
        conn = database.conectar()
        if conn:
            # Seleccionamos las columnas con nombres limpios para el usuario
            query = """
                SELECT rif as "RIF", nombre as "Nombre", tipo_persona as "Tipo", 
                categoria as "Categoría", tipo_contribuyente as "Contribuyente" 
                FROM entidades
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if not df.empty:
                busqueda = st.text_input("🔍 Filtrar por Nombre o RIF:", key="search_ent")
                if busqueda:
                    df = df[df['Nombre'].str.contains(busqueda, case=False) | df['RIF'].str.contains(busqueda, case=False)]
                
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No hay datos registrados aún.")
    except Exception as e:
        st.error(f"Error al cargar el listado: {e}")
