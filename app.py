import streamlit as st
import pandas as pd
import database
from datetime import datetime

st.set_page_config(layout="wide", page_title="ERP Adonai")
database.inicializar_db()

# --- SIDEBAR SAP STYLE ---
st.sidebar.title("🚀 ERP Adonai Group")
modulo = st.sidebar.selectbox("Módulo", ["🏛️ Contabilidad (GL)", "🛍️ Compras (AP)", "⚙️ Configuración"])

# --- FUNCIONES DE VALIDACIÓN ---
def es_periodo_abierto(fecha, modulo_db):
    p_str = fecha.strftime("%Y-%m")
    res = database.ejecutar_query(f"SELECT {modulo_db} FROM periodos_fiscales WHERE periodo = %s", (p_str,), fetch=True)
    return res and res[0][0] == 'Abierto'

# --- INTERFAZ DE CONTABILIDAD ---
if modulo == "🏛️ Contabilidad (GL)":
    t1, t2, t3, t4 = st.tabs(["📖 Diario General", "🏢 Centros de Costo", "📑 Plan de Cuentas", "🔒 Períodos"])

    with t4: # PERÍODOS
        st.subheader("Control de Períodos Fiscales")
        c1, c2 = st.columns(2)
        anio = c1.number_input("Ejercicio Económico", 2024, 2030, 2026)
        if c2.button("Generar 12 Meses"):
            for m in range(1, 13):
                p = f"{anio}-{str(m).zfill(2)}"
                database.ejecutar_query("INSERT INTO periodos_fiscales (periodo) VALUES (%s) ON CONFLICT DO NOTHING", (p,))
            st.rerun()

        df_p = pd.read_sql(f"SELECT * FROM periodos_fiscales WHERE periodo LIKE '{anio}-%%' ORDER BY periodo ASC", database.conectar())
        if not df_p.empty:
            st.markdown("---")
            for _, row in df_p.iterrows():
                cols = st.columns([1, 1, 1, 1, 1])
                cols[0].write(f"📅 **{row['periodo']}**")
                # Botones por módulo
                for i, (m_label, m_db) in enumerate([("CG", "modulo_cg"), ("CP", "modulo_cp"), ("CV", "modulo_cv")]):
                    btn_label = f"🟢 {m_label}" if row[m_db] == 'Abierto' else f"🔒 {m_label}"
                    if cols[i+1].button(btn_label, key=f"btn_{m_db}_{row['periodo']}"):
                        nuevo = 'Cerrado' if row[m_db] == 'Abierto' else 'Abierto'
                        database.ejecutar_query(f"UPDATE periodos_fiscales SET {m_db} = %s WHERE periodo = %s", (nuevo, row['periodo']))
                        st.rerun()

    with t2: # CENTROS DE COSTO
        st.subheader("Configuración de Centros de Costo")
        with st.form("f_cc"):
            cod, nom = st.columns(2)
            c_c = cod.text_input("Código")
            n_c = nom.text_input("Nombre del Departamento")
            if st.form_submit_button("Guardar"):
                database.ejecutar_query("INSERT INTO centros_costo (codigo, nombre) VALUES (%s,%s) ON CONFLICT DO NOTHING", (c_c, n_c))
                st.rerun()
        st.table(pd.read_sql("SELECT codigo, nombre FROM centros_costo", database.conectar()))

    with t1: # DIARIO (MODO ODOO)
        st.subheader("Libro Diario General")
        if st.button("➕ Crear Nuevo Comprobante"):
            st.session_state['crear_asiento'] = True

        if st.session_state.get('crear_asiento'):
            with st.form("f_asiento"):
                c1, c2, c3 = st.columns(3)
                f = c1.date_input("Fecha")
                orig = c2.selectbox("Origen", ["CG", "CP", "CB"])
                conc = c3.text_input("Concepto / Glosa")
                
                # Cargar Selectores
                ctas_raw = database.ejecutar_query("SELECT codigo, nombre FROM plan_cuentas", fetch=True)
                lista_ctas = [f"{r[0]} | {r[1]}" for r in ctas_raw] if ctas_raw else []
                cc_raw = database.ejecutar_query("SELECT codigo FROM centros_costo", fetch=True)
                lista_cc = [r[0] for r in cc_raw] if cc_raw else []

                # Editor Maestro-Detalle
                df_lines = pd.DataFrame([{"Cuenta": "", "CC": "", "Debe": 0.0, "Haber": 0.0, "RIF": ""} for _ in range(4)])
                data_edit = st.data_editor(df_lines, num_rows="dynamic", column_config={
                    "Cuenta": st.column_config.SelectboxColumn("Cuenta", options=lista_ctas),
                    "CC": st.column_config.SelectboxColumn("CC", options=lista_cc)
                })

                t_debe, t_haber = data_edit["Debe"].sum(), data_edit["Haber"].sum()
                st.write(f"**Validación:** Debe {t_debe} | Haber {t_haber} | Dif: {round(t_debe-t_haber,2)}")

                if st.form_submit_button("💾 Postear en Diario"):
                    if not es_periodo_abierto(f, 'modulo_cg'):
                        st.error("Período Cerrado para Contabilidad.")
                    elif t_debe != t_haber or t_debe == 0:
                        st.error("El asiento debe estar cuadrado y no ser cero.")
                    else:
                        num = database.obtener_ultimo_correlativo(orig)
                        # Guardar Cabecera
                        database.ejecutar_query("INSERT INTO asientos_cabecera (num_asiento, fecha, concepto, origen) VALUES (%s,%s,%s,%s)", (num, f, conc, orig))
                        st.success(f"Asiento {num} registrado.")
                        st.session_state['crear_asiento'] = False
                        st.rerun()

elif modulo == "⚙️ Configuración":
    st.title("Ajustes de Sistema")
    if st.button("📥 Cargar Catálogo de Cuentas SAP Base"):
        base = [('1', 'ACTIVO', 'A'), ('1.1', 'DISPONIBLE', 'A'), ('2', 'PASIVO', 'P'), ('3', 'PATRIMONIO', 'PT'), ('4', 'INGRESOS', 'I'), ('5', 'GASTOS', 'E')]
        for c in base: database.ejecutar_query("INSERT INTO plan_cuentas VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", c)
        st.success("Plan Base Cargado.")
