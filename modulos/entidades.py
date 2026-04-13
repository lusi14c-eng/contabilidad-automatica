import streamlit as st
import pandas as pd
import re
import database 

def modulo_maestro_entidades():
    st.markdown("### 👥 Maestro de Entidades (Base para Cuentas por Pagar/Cobrar)")
    st.info("Nota: El RIF se guardará sin guiones para ser usado como Código Único.")
    
    with st.form("form_entidad", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Entrada del usuario
            rif_input = st.text_input("RIF / Código de Entidad (Ej: J411661210):").upper().strip()
            nombre = st.text_input("Razón Social / Nombre Completo:")
            direccion = st.text_area("Dirección Fiscal:")
            
        with col2:
            categoria = st.selectbox("Categoría de Cuenta:", ["PROVEEDOR", "CLIENTE", "AMBOS"])
            tipo_c = st.selectbox("Tipo de Contribuyente:", 
                                ["Especial", "Ordinario", "Exento", "Formal"])
            islr_pct = st.number_input("% Retención ISLR por Defecto:", 
                                     min_value=0.0, max_value=100.0, value=2.0, step=0.1)
            
        btn_guardar = st.form_submit_button("Registrar en el Sistema")

        if btn_guardar:
            # 1. PROCESAMIENTO: Eliminamos cualquier guion o espacio por seguridad
            rif_codigo = rif_input.replace("-", "").replace(" ", "")
            
            # 2. VALIDACIÓN: Letra + 7 a 10 dígitos (Formato limpio)
            if not re.match(r'^[VJGPE]\d{7,10}$', rif_codigo):
                st.error("❌ Error en el RIF. Debe ser una letra seguida de números (sin guiones).")
            elif len(nombre) < 3:
                st.error("❌ Debe ingresar una Razón Social válida.")
            else:
                conn = database.conectar()
                c = conn.cursor()
                try:
                    # Guardamos el RIF como el código maestro
                    c.execute('''
                        INSERT INTO entidades (rif, nombre, direccion, tipo_contribuyente, categoria, retencion_islr_pct)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (rif_codigo, nombre, direccion, tipo_c, categoria, islr_pct))
                    conn.commit()
                    st.success(f"✅ Código {rif_codigo} registrado correctamente.")
                except Exception as e:
                    st.warning(f"⚠️ El Código/RIF '{rif_codigo}' ya existe en su base de datos.")
                finally:
                    conn.close()

    # --- TABLA DE CONSULTA ---
    st.divider()
    st.subheader("📋 Base de Datos de Clientes y Proveedores")
    
    conn = database.conectar()
    df = pd.read_sql_query("SELECT * FROM entidades", conn)
    conn.close()
    
    if not df.empty:
        # Renombramos para la vista del usuario
        df.columns = ["CÓDIGO (RIF)", "RAZÓN SOCIAL", "DIRECCIÓN", "CONTRIBUYENTE", "TIPO", "% ISLR"]
        st.dataframe(df, use_container_width=True)
        
        # Resumen rápido para tu gestión
        st.caption(f"Total de entidades registradas: {len(df)}")
    else:
        st.info("Aún no hay proveedores o clientes creados.")
