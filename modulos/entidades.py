import streamlit as st
import pandas as pd
import re
import database 

def modulo_maestro_entidades():
    st.markdown("### 👥 Maestro de Entidades (Configuración Fiscal)")
    st.info("Complete los datos fiscales. El RIF se usará como código único sin guiones.")
    
    with st.form("form_entidad", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            rif_input = st.text_input("RIF (Código Único):").upper().strip()
            nombre = st.text_input("Razón Social:")
            direccion = st.text_area("Dirección Fiscal:")
            
        with col2:
            categoria = st.selectbox("Categoría:", ["PROVEEDOR", "CLIENTE", "AMBOS"])
            tipo_c = st.selectbox("Tipo de Contribuyente:", 
                                ["Especial", "Ordinario", "Exento", "Formal"])
            
            # --- SECCIÓN DE RETENCIONES ---
            st.markdown("**Configuración de Retenciones**")
            islr_pct = st.number_input("% Retención ISLR (Ej: 2.0, 1.0):", 
                                     min_value=0.0, max_value=100.0, value=2.0, step=0.1)
            
            # Nuevo campo para IVA (75% o 100% usualmente)
            iva_pct = st.selectbox("% Retención IVA (Si aplica):", [0, 75, 100])
            
        btn_guardar = st.form_submit_button("Registrar Entidad")

        if btn_guardar:
            rif_codigo = rif_input.replace("-", "").replace(" ", "")
            
            if not re.match(r'^[VJGPE]\d{7,10}$', rif_codigo):
                st.error("❌ Formato de RIF inválido (Letra + Números).")
            elif len(nombre) < 3:
                st.error("❌ Razón Social obligatoria.")
            else:
                conn = database.conectar()
                c = conn.cursor()
                try:
                    # Actualizamos la consulta para incluir la nueva columna
                    # Nota: Asegúrate de que la tabla en database.py tenga esta columna o se agregue automáticamente
                    c.execute('''
                        INSERT INTO entidades (rif, nombre, direccion, tipo_contribuyente, categoria, retencion_islr_pct, retencion_iva_pct)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (rif_codigo, nombre, direccion, tipo_c, categoria, islr_pct, iva_pct))
                    conn.commit()
                    st.success(f"✅ Entidad {rif_codigo} guardada con éxito.")
                except Exception as e:
                    st.warning(f"⚠️ Error: Verifique si el RIF ya existe o si falta actualizar la tabla.")
                finally:
                    conn.close()

    # --- VISTA DE LA DATA ---
    st.divider()
    conn = database.conectar()
    df = pd.read_sql_query("SELECT * FROM entidades", conn)
    conn.close()
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
