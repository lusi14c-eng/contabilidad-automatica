import streamlit as st
import pandas as pd
import re
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
                tipo_c = st.selectbox("Tipo de Contribuyente:", ["Especial", "Ordinario", "Exento", "Formal"])
                islr_pct = st.number_input("% Retención ISLR:", min_value=0.0, value=2.0)
                iva_pct = st.selectbox("% Retención IVA:", [0, 75, 100])
            
            submit = st.form_submit_button("✅ Guardar Entidad")

            if submit:
                rif_limpio = rif_input.replace("-", "").replace(" ", "")
                if not re.match(r'^[VJGPE]\d{7,10}$', rif_limpio):
                    st.error("❌ RIF inválido.")
                elif len(nombre) < 3:
                    st.error("❌ Nombre muy corto.")
                else:
                    try:
                        conn = database.conectar()
                        c = conn.cursor()
                        c.execute("SELECT rif FROM entidades WHERE rif = %s", (rif_limpio,))
                        if c.fetchone():
                            st.warning(f"⚠️ El RIF {rif_limpio} ya existe.")
                        else:
                            query = "INSERT INTO entidades (rif, nombre, direccion, tipo_persona, tipo_contribuyente, categoria, retencion_islr_pct, retencion_iva_pct) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                            c.execute(query, (rif_limpio, nombre, direccion, tipo_persona, tipo_c, categoria, islr_pct, iva_pct))
                            conn.commit()
                            st.success("✅ Guardado.")
                        c.close()
                        conn.close()
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab2:
        ver_listado_completo()

def ver_listado_completo():
    st.subheader("🗂️ Base de Datos")
    try:
        conn = database.conectar()
        df = pd.read_sql_query("SELECT * FROM entidades", conn)
        conn.close()
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos.")
    except Exception as e:
        st.error(f"Error: {e}")
