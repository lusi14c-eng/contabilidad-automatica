import streamlit as st
import pandas as pd
import re
import database  # Importamos la conexión central

def modulo_maestro_entidades():
    st.markdown("### 📋 Registro de Entidades (Clientes / Proveedores)")
    
    # Formulario de entrada
    with st.form("form_entidad", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            rif = st.text_input("RIF (Ej: J-12345678-0):").upper().strip()
            nombre = st.text_input("Razón Social / Nombre:")
            direccion = st.text_area("Dirección Fiscal:")
            
        with col2:
            categoria = st.selectbox("Categoría:", ["PROVEEDOR", "CLIENTE", "AMBOS"])
            tipo_c = st.selectbox("Tipo de Contribuyente:", 
                                ["Especial", "Ordinario", "Exento", "Formal"])
            # Porcentaje base de retención de ISLR (Decreto 1808)
            islr_pct = st.number_input("% Retención ISLR (Sugerido):", 
                                     min_value=0.0, max_value=100.0, value=2.0, step=0.1)
            
        btn_guardar = st.form_submit_button("Guardar en Base de Datos")

        if btn_guardar:
            # Validación de RIF (Formato SENIAT)
            if not re.match(r'^[VJGPE-]\d{7,9}-\d$', rif):
                st.error("❌ El RIF no tiene un formato válido (Ej: J-12345678-0).")
            elif len(nombre) < 3:
                st.error("❌ El nombre es demasiado corto.")
            else:
                conn = database.conectar()
                c = conn.cursor()
                try:
                    c.execute('''
                        INSERT INTO entidades (rif, nombre, direccion, tipo_contribuyente, categoria, retencion_islr_pct)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (rif, nombre, direccion, tipo_c, categoria, islr_pct))
                    conn.commit()
                    st.success(f"✅ Registrado: {nombre} ({rif})")
                except Exception as e:
                    st.warning(f"⚠️ El RIF ya existe o hubo un error: {e}")
                finally:
                    conn.close()

    # --- Sección de Visualización y Edición ---
    st.divider()
    st.subheader("🔍 Listado de Entidades Guardadas")
    
    conn = database.conectar()
    df = pd.read_sql_query("SELECT * FROM entidades", conn)
    conn.close()
    
    if not df.empty:
        # Renombrar columnas para que se vean bien en la interfaz
        df.columns = ["RIF", "Nombre", "Dirección", "Contribuyente", "Categoría", "% ISLR"]
        st.dataframe(df, use_container_width=True)
        
        # Botón para borrar (opcional, con precaución)
        rif_borrar = st.selectbox("Seleccione un RIF para eliminar si es necesario:", [""] + df["RIF"].tolist())
        if st.button("🗑️ Eliminar Entidad") and rif_borrar != "":
            conn = database.conectar()
            c = conn.cursor()
            c.execute("DELETE FROM entidades WHERE rif = ?", (rif_borrar,))
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.info("Aún no hay entidades registradas en el sistema.")
