import streamlit as st
import pandas as pd
import database
from datetime import datetime

def modulo_compras():
    st.title("🧾 Registro de Compras")
    
    # Intentamos crear las pestañas. Si falla aquí, el error aparecerá en pantalla.
    try:
        tab1, tab2, tab3 = st.tabs(["📝 Registrar Factura", "⚙️ Configurar Subtipos", "📖 Ver Libro"])

        # --- PESTAÑA 2: CONFIGURACIÓN (PARA DESBLOQUEAR EL SISTEMA) ---
        with tab2:
            st.subheader("Configuración de Cuentas / Subtipos")
            with st.form("form_sub_simple", clear_on_submit=True):
                nombre = st.text_input("Nombre del Gasto (Ej: ALQUILER):").upper().strip()
                cuenta = st.text_input("Código Contable:")
                if st.form_submit_button("Guardar Subtipo"):
                    if nombre and cuenta:
                        conn = database.conectar()
                        conn.execute("INSERT INTO subtipos_gasto (nombre, cuenta_contable) VALUES (?,?)", (nombre, cuenta))
                        conn.commit()
                        conn.close()
                        st.success("¡Subtipo guardado!")
                        st.rerun()

            # Mostrar tabla de subtipos
            try:
                conn = database.conectar()
                df_s = pd.read_sql_query("SELECT * FROM subtipos_gasto", conn)
                conn.close()
                st.table(df_s)
            except:
                st.info("No hay subtipos creados.")

        # --- PESTAÑA 1: REGISTRO ---
        with tab1:
            try:
                conn = database.conectar()
                # Traemos proveedores y subtipos
                provs = pd.read_sql_query("SELECT rif, nombre FROM entidades", conn)
                subs = pd.read_sql_query("SELECT nombre FROM subtipos_gasto", conn)
                conn.close()

                if provs.empty:
                    st.warning("⚠️ No hay proveedores registrados en el Maestro.")
                elif subs.empty:
                    st.warning("⚠️ No hay subtipos. Crea uno en la pestaña 'Configurar Subtipos'.")
                else:
                    with st.form("form_registro_compra"):
                        st.selectbox("Seleccione Proveedor:", provs['rif'] + " - " + provs['nombre'])
                        st.selectbox("Tipo de Gasto:", subs['nombre'])
                        st.number_input("Base Imponible:", min_value=0.0)
                        if st.form_submit_button("Registrar Factura"):
                            st.success("Simulación de registro exitosa.")
            except Exception as e:
                st.error(f"Error al cargar datos: {e}")

        with tab3:
            st.info("Reportes disponibles próximamente.")

    except Exception as e:
        st.error(f"Se produjo un error crítico en el módulo: {e}")
