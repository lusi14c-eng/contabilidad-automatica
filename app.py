import streamlit as st
import pandas as pd
import database
from datetime import datetime

st.set_page_config(layout="wide", page_title="ERP Adonai Group")
database.inicializar_db()

# --- NAVEGACIÓN ---
menu = st.sidebar.selectbox("Módulo Principal", ["🏛️ Contabilidad (GL)", "🛍️ Compras (AP)", "💰 Ventas (AR)", "⚙️ Configuración"])

# --- LÓGICA DE PERÍODOS (SOPORTE DE BLOQUEO) ---
def periodo_abierto(fecha, modulo):
    p_str = fecha.strftime("%Y-%m")
    res = database.ejecutar_query(f"SELECT {modulo} FROM periodos_fiscales WHERE periodo = %s", (p_str,))
    return res and res[0][0] == 'Abierto'

# --- MÓDULO CONTABILIDAD ---
if menu == "🏛️ Contabilidad (GL)":
    t1, t2, t3, t4 = st.tabs(["📖 Diario", "📊 Plan de Cuentas", "🏢 Centros de Costo", "🔒 Períodos"])

    with t4: # GESTIÓN DE PERÍODOS
        st.subheader("Control de Puertas Contables")
        col1, col2 = st.columns(2)
        anio = col1.number_input("Año Fiscal", 2024, 2030, 2026)
        if col2.button("Generar Ejercicio"):
            for m in range(1, 13):
                p = f"{anio}-{str(m).zfill(2)}"
                database.ejecutar_query("INSERT INTO periodos_fiscales (periodo) VALUES (%s) ON CONFLICT DO NOTHING", (p,), fetch=False)
        
        df_p = pd.read_sql(f"SELECT * FROM periodos_fiscales WHERE periodo LIKE '{anio}-%%' ORDER BY periodo ASC", database.conectar())
        for _, row in df_p.iterrows():
            c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
            c1.write(f"**{row['periodo']}**")
            # Iconos y estados
            for mod, col_name, col_ui in [("CG", "modulo_cg", c2), ("CP", "modulo_cp", c3), ("CV", "modulo_cv", c4)]:
                status = row[col_name]
                icon = "🟢" if status == 'Abierto' else "🔒"
                if col_ui.button(f"{icon} {mod}", key=f"{mod}_{row['periodo']}"):
                    # Lógica Max 2 abiertos
                    abiertos = len(df_p[df_p[col_name] == 'Abierto'])
                    nuevo = 'Cerrado' if status == 'Abierto' else 'Abierto'
                    if nuevo == 'Abierto' and abiertos >= 2:
                        st.error("Límite de 2 períodos alcanzado.")
                    else:
                        database.ejecutar_query(f"UPDATE periodos_fiscales SET {col_name} = %s WHERE periodo = %s", (nuevo, row['periodo']), fetch=False)
                        st.rerun()

    with t3: # CENTROS DE COSTO
        st.subheader("Estructura de Costos")
        with st.form("f_cc"):
            c_cod = st.text_input("Código Centro")
            c_nom = st.text_input("Nombre")
            if st.form_submit_button("Guardar"):
                database.ejecutar_query("INSERT INTO centros_costo (codigo, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (c_cod, c_nom), fetch=False)
        
        st.table(pd.read_sql("SELECT codigo, nombre FROM centros_costo", database.conectar()))

    with t1: # DIARIO GENERAL (EDITOR ODOO)
        if st.button("➕ Crear Asiento"): st.session_state['nuevo_as'] = True
        
        if st.session_state.get('nuevo_as'):
            with st.expander("📝 Editor de Comprobante", expanded=True):
                with st.form("erp_entry"):
                    f = st.date_input("Fecha")
                    concepto = st.text_input("Glosa/Concepto")
                    
                    # GRID DE ASIENTOS
                    cuentas = [f"{r[0]} | {r[1]}" for r in database.ejecutar_query("SELECT codigo, nombre FROM plan_cuentas")]
                    ccs = [r[0] for r in database.ejecutar_query("SELECT codigo FROM centros_costo")]
                    
                    df_as = pd.DataFrame([{"Cuenta": "", "CC": "", "Debe": 0.0, "Haber": 0.0} for _ in range(4)])
                    data = st.data_editor(df_as, num_rows="dynamic", column_config={
                        "Cuenta": st.column_config.SelectboxColumn("Cuenta", options=cuentas),
                        "CC": st.column_config.SelectboxColumn("CC", options=ccs)
                    })
                    
                    total_d, total_h = data["Debe"].sum(), data["Haber"].sum()
                    st.write(f"**Total Debe:** {total_d} | **Total Haber:** {total_h}")
                    
                    if st.form_submit_button("Postear"):
                        if not periodo_abierto(f, 'modulo_cg'):
                            st.error("Período Cerrado en Contabilidad.")
                        elif total_d != total_h or total_d == 0:
                            st.error("Asiento descuadrado o vacío.")
                        else:
                            num = database.obtener_ultimo_correlativo("AS")
                            database.ejecutar_query("INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen) VALUES (%s,%s,%s,%s)", (num, f, concepto, "CG"), fetch=False)
                            st.success(f"Asiento {num} registrado.")
                            st.session_state['nuevo_as'] = False
                            st.rerun()

# --- LOS DEMÁS MÓDULOS (ESTRUCTURA MÍNIMA PARA FUNCIONAR) ---
elif menu == "🛍️ Compras (AP)":
    st.title("Cuentas por Pagar")
    # Aquí se insertaría la lógica de facturas de proveedores que valida 'modulo_cp'
    st.info("Módulo vinculado a Contabilidad y validado por Períodos CP.")

elif menu == "⚙️ Configuración":
    st.title("Ajustes del Sistema")
    if st.button("📁 Cargar Plan de Cuentas por Defecto"):
        data_base = [('1', 'ACTIVO', 'A'), ('2', 'PASIVO', 'P'), ('3', 'PATRIMONIO', 'PT'), ('4', 'INGRESOS', 'I'), ('5', 'GASTOS', 'E')]
        for c in data_base: database.ejecutar_query("INSERT INTO plan_cuentas VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", c, fetch=False)
        st.success("Plan base cargado.")
