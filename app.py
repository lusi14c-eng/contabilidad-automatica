import streamlit as st
import pandas as pd
import database
from datetime import datetime

st.set_page_config(layout="wide", page_title="ERP Adonai v3")
database.inicializar_db()

# --- BARRA LATERAL (NAVEGACIÓN) ---
st.sidebar.title("🏢 Sistema de Gestión")
modulo = st.sidebar.selectbox("Módulo", ["⚙️ Mi Empresa", "🛍️ Compras (Facturación)", "🏛️ Contabilidad", "👥 Proveedores"])

# --- 1. MÓDULO MI EMPRESA (TUS DATOS) ---
if modulo == "⚙️ Mi Empresa":
    st.header("⚙️ Configuración de la Entidad")
    conf = database.ejecutar_query("SELECT nombre_empresa, rif_empresa, direccion, moneda FROM configuracion WHERE id = 1", fetch=True)[0]
    
    with st.form("perfil_empresa"):
        col1, col2 = st.columns(2)
        n_emp = col1.text_input("Nombre de la Empresa", value=conf[0])
        r_emp = col2.text_input("RIF Jurídico", value=conf[1])
        dir_emp = st.text_area("Dirección Fiscal", value=conf[2])
        if st.form_submit_button("Actualizar Datos"):
            database.ejecutar_query("UPDATE configuracion SET nombre_empresa=%s, rif_empresa=%s, direccion=%s WHERE id=1", (n_emp, r_emp, dir_emp))
            st.success("Datos actualizados.")
            st.rerun()

# --- 2. MÓDULO COMPRAS (REGISTRO DE FACTURAS) ---
elif modulo == "🛍️ Compras (Facturación)":
    st.header("🛍️ Registro de Compras y Gastos")
    t1, t2 = st.tabs(["🆕 Nueva Factura", "📋 Historial de Compras"])

    with t1:
        with st.form("f_compra"):
            c1, c2, c3 = st.columns(3)
            fecha = c1.date_input("Fecha Factura")
            rif_prov = c2.text_input("RIF Proveedor")
            n_fact = c3.text_input("Número de Factura")
            
            base = st.number_input("Base Imponible", min_value=0.0, format="%.2f")
            iva = base * 0.16 # IVA 16% Sugerido
            st.write(f"**IVA (16%):** {iva:,.2f} | **Total:** {base + iva:,.2f}")
            
            if st.form_submit_button("Registrar Factura"):
                if rif_prov and n_fact:
                    # Guardar en Compras
                    database.ejecutar_query(
                        "INSERT INTO compras (fecha, rif_proveedor, num_factura, base_imponible, iva_monto, total) VALUES (%s,%s,%s,%s,%s,%s)",
                        (fecha, rif_prov, n_fact, base, iva, base + iva)
                    )
                    st.success(f"Factura {n_fact} registrada correctamente.")
                else:
                    st.error("Faltan datos obligatorios.")

# --- 3. MÓDULO CONTABILIDAD (TU MONITOR FISCAL) ---
elif modulo == "🏛️ Contabilidad":
    st.header("🏛️ Contabilidad General")
    t1, t2, t3 = st.tabs(["📖 Libro Diario", "🔒 Períodos", "📑 Plan de Cuentas"])

    with t2: # PERÍODOS
        st.subheader("Control de Períodos")
        anio = st.number_input("Año", 2024, 2030, 2026)
        if st.button("Aperturar Año Fiscal"):
            for m in range(1,13):
                p = f"{anio}-{str(m).zfill(2)}"
                database.ejecutar_query("INSERT INTO periodos_fiscales (periodo) VALUES (%s) ON CONFLICT DO NOTHING", (p,))
            st.rerun()
        
        df_p = pd.read_sql(f"SELECT * FROM periodos_fiscales WHERE periodo LIKE '{anio}-%%' ORDER BY periodo ASC", database.conectar())
        st.dataframe(df_p)

# --- 4. MÓDULO PROVEEDORES ---
elif modulo == "👥 Proveedores":
    st.header("👥 Maestro de Proveedores")
    with st.form("f_prov"):
        r = st.text_input("RIF")
        n = st.text_input("Razón Social")
        if st.form_submit_button("Añadir Proveedor"):
            database.ejecutar_query("INSERT INTO entidades (rif, nombre, tipo) VALUES (%s,%s,'Proveedor')", (r, n))
            st.success("Proveedor guardado.")
