import streamlit as st
import pandas as pd
import re
import database 

def modulo_maestro_entidades():
    st.title("👥 Gestión de Clientes y Proveedores")

    # Creamos pestañas para organizar mejor la vista
    tab1, tab2 = st.tabs(["🆕 Registrar Nuevo", "📋 Listado de Entidades"])

    with tab1:
        st.subheader("Formulario de Registro")
        with st.form("form_entidad", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                rif_input = st.text_input("RIF (Ej: J411661210):").upper().strip()
                nombre = st.text_input("Razón Social / Nombre:")
                direccion = st.text_area("Dirección Fiscal:")
                tipo_persona = st.selectbox("Tipo de Persona:", 
                                         ["Jurídica Domiciliada", "Natural Residente", "Jurídica No Domiciliada", "Natural No Residente", "Gubernamental"])
                
            with col2:
                categoria = st.selectbox("Categoría:", ["PROVEEDOR", "CLIENTE", "AMBOS"])
                tipo_c = st.selectbox("Tipo de Contribuyente (SENIAT):", 
                                    ["Especial", "Ordinario", "Exento", "Formal"])
                
                st.markdown("**Configuración de Retenciones**")
                islr_pct = st.number_input("% Retención ISLR sugerido:", 
                                         min_value=0.0, max_value=100.0, value=2.0, step=0.1)
                iva_pct = st.selectbox("% Retención IVA (Si aplica):", [0, 75, 100])
                
            btn_guardar = st.form_submit_button("✅ Guardar Entidad")

            if btn_guardar:
                rif_codigo = rif_input.replace("-", "").replace(" ", "")
                
                if not re.match(r'^[VJGPE]\d{7,10}$', rif_codigo):
                    st.error("❌ RIF inválido. Debe ser una letra y números.")
                elif len(nombre) < 3:
                    st.error("❌ La Razón Social es obligatoria.")
                else:
                    conn = database.conectar()
                    c = conn.cursor()
                    try:
                        # Guardamos con el nuevo campo tipo_persona
                        # Nota: Asegúrate de que database.py tenga esta columna o usa el truco del ALTER TABLE
                        c.execute('''
                            INSERT INTO entidades (rif, nombre, direccion, tipo_persona, tipo_contribuyente, categoria, retencion_islr_pct, retencion_iva_pct)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (rif_codigo, nombre, direccion, tipo_persona, tipo_c, categoria, islr_pct, iva_pct))
                        conn.commit()
                        st.success(f"🎊 ¡Éxito! El {categoria} **{nombre}** ha sido creado correctamente con el código **{rif_codigo}**.")
                        st.balloons() # Un toque de celebración
                    except Exception as e:
                        st.error(f"⚠️ No se pudo guardar. Es posible que el RIF ya exista o debas actualizar la base de datos.")
                    finally:
                        conn.close()

    with tab2:
        st.subheader("Entidades Registradas")
        conn = database.conectar()
        # Traemos todos los datos para visualizarlos
        df = pd.read_sql_query("SELECT * FROM entidades", conn)
        conn.close()
        
        if not df.empty:
            # Filtro rápido en la tabla
            busqueda = st.text_input("🔍 Buscar por nombre o RIF:")
            if busqueda:
                df = df[df['nombre'].str.contains(busqueda, case=False) | df['rif'].str.contains(busqueda, case=False)]
            
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay entidades registradas aún.")
