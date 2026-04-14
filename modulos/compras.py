import streamlit as st
import pandas as pd
import database
from datetime import date
from io import BytesIO

def modulo_compras():
    st.title("📑 Registro y Control de Compras")
    conf = database.obtener_configuracion_empresa()
    
    tab1, tab2 = st.tabs(["✍️ Registrar Factura", "📊 Libro de Compras"])
    
    with tab1:
        conn = database.conectar()
        # Traemos proveedores y los subtipos dinámicos que creaste
        prov_df = pd.read_sql("SELECT rif, nombre, tipo_persona FROM entidades", conn)
        subtipos_df = pd.read_sql("SELECT nombre, cuenta_codigo FROM compra_subtipos", conn)
        conn.close()

        if prov_df.empty:
            st.warning("⚠️ Registra un proveedor primero en el módulo de Entidades.")
        elif subtipos_df.empty:
            st.error("⚠️ No has definido 'Subtipos de Compra' en el módulo de Contabilidad.")
        else:
            with st.form("form_nueva_compra", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Datos del Documento")
                    fecha_doc = st.date_input("Fecha de la Factura", value=date.today())
                    
                    dict_prov = {row['nombre']: row for _, row in prov_df.iterrows()}
                    nombre_p = st.selectbox("Proveedor", list(dict_prov.keys()))
                    p_datos = dict_prov[nombre_p]
                    
                    num_f = st.text_input("N° Factura")
                    num_c = st.text_input("N° Control")
                    
                    # --- SELECCIÓN DE SUBTIPO DINÁMICO ---
                    dict_sub = {r['nombre']: r['cuenta_codigo'] for _, r in subtipos_df.iterrows()}
                    sub_nombre = st.selectbox("Subtipo de Compra (Clasificación)", list(dict_sub.keys()))
                    cod_cuenta = dict_sub[sub_nombre]
                    st.caption(f"📍 Cuenta contable asociada: **{cod_cuenta}**")

                with col2:
                    st.subheader("Montos y Retenciones")
                    m_exento = st.number_input("Monto Exento", min_value=0.0, step=0.01)
                    base_i = st.number_input("Base Imponible", min_value=0.0, step=0.01)
                    iva_f = round(base_i * 0.16, 2)
                    st.info(f"IVA (16%): {iva_f}")
                    
                    st.divider()
                    
                    # Lógica de Retención IVA Automática
                    mi_tipo = conf.get('tipo_contribuyente', 'Ordinario')
                    es_especial = True if mi_tipo == "Especial" else False
                    
                    ap_iva = st.checkbox("Retener IVA", value=es_especial)
                    p_iva = st.selectbox("% Retención", [75, 100], index=0, disabled=not ap_iva)
                    iva_ret = round(iva_f * (p_iva / 100), 2) if ap_iva else 0.0
                    
                    # ISLR Simple (Ejemplo 2% para servicios)
                    ap_islr = st.checkbox("Retener ISLR", value=True)
                    tasa_islr = 2.0 # Puedes hacer esto dinámico después
                    islr_ret = round(base_i * (tasa_islr / 100), 2) if ap_islr else 0.0
                    
                    st.warning(f"Retenciones: IVA {iva_ret} | ISLR {islr_ret}")

                total_neto = round((m_exento + base_i + iva_f) - iva_ret - islr_ret, 2)
                st.markdown(f"### Neto a Pagar: **{total_neto} Bs.**")

                if st.form_submit_button("📥 Registrar Factura"):
                    if not num_f:
                        st.error("Debe ingresar el número de factura.")
                    else:
                        try:
                            conn = database.conectar()
                            c = conn.cursor()
                            query = """INSERT INTO compras (fecha, rif_proveedor, num_factura, num_control, 
                                       monto_exento, base_imponible, iva_monto, islr_retenido, iva_retenido, 
                                       total_factura, subtipo) 
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                            c.execute(query, (fecha_doc, p_datos['rif'], num_f, num_c, m_exento, base_i, 
                                              iva_f, islr_ret, iva_ret, total_neto, sub_nombre))
                            conn.commit()
                            conn.close()
                            st.success("✅ Compra registrada con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

    with tab2:
        st.subheader("📊 Libro de Compras Legal (SENIAT)")
        col_m, col_a = st.columns(2)
        mes = col_m.selectbox("Mes", range(1, 13), index=date.today().month-1)
        ano = col_a.number_input("Año", value=date.today().year)

        # Query con todas las columnas exigidas por la ley
        query_l = """
            SELECT 
                c.fecha AS "Fecha",
                e.rif AS "RIF Proveedor",
                e.nombre AS "Nombre o Razón Social",
                c.num_factura AS "N° Factura",
                c.num_control AS "N° Control",
                '01-Reg' AS "Tipo Transac.", -- 01 Registro, 02 Nota Débito, 03 Nota Crédito
                '' AS "N° Fact. Afectada", -- Para Notas de Crédito/Débito
                c.total_factura AS "Total Compras Incl. IVA",
                c.monto_exento AS "Compras No Sujetas o Exentas",
                c.base_imponible AS "Base Imponible",
                '16%' AS "% Alícuota",
                c.iva_monto AS "Impuesto IVA",
                c.iva_retenido AS "IVA Retenido",
                'N/A' AS "N° Comprobante", -- Aquí irá el número cuando generes el PDF
                EXTRACT(YEAR FROM c.fecha) || LPAD(EXTRACT(MONTH FROM c.fecha)::text, 2, '0') AS "Periodo Fiscal"
            FROM compras c
            JOIN entidades e ON c.rif_proveedor = e.rif
            WHERE EXTRACT(MONTH FROM c.fecha) = %s AND EXTRACT(YEAR FROM c.fecha) = %s
            ORDER BY c.fecha ASC, c.num_factura ASC
        """
        
        conn = database.conectar()
        df = pd.read_sql(query_l, conn, params=[int(mes), int(ano)])
        conn.close()

        if not df.empty:
            st.dataframe(df, use_container_width=True)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # El SENIAT exige que los encabezados empiecen en la fila 5 o 6 después de los datos de la empresa
                df.to_excel(writer, index=False, sheet_name='LIBRO_DE_COMPRAS', startrow=5)
                
                workbook  = writer.book
                worksheet = writer.sheets['LIBRO_DE_COMPRAS']

                # --- FORMATOS ---
                fmt_titulo = workbook.add_format({'bold': True, 'font_size': 14})
                fmt_info = workbook.add_format({'bold': True, 'font_size': 10})
                fmt_header = workbook.add_format({
                    'bold': True, 'bg_color': '#EFEFEF', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True
                })
                fmt_num = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
                fmt_txt = workbook.add_format({'border': 1})

                # --- ENCABEZADO FISCAL ---
                worksheet.write('A1', conf['nombre_empresa'], fmt_titulo)
                worksheet.write('A2', f"RIF: {conf['rif_empresa']}", fmt_info)
                worksheet.write('A3', f"DOMICILIO FISCAL: {conf['direccion_empresa']}", fmt_info)
                worksheet.write('A4', f"LIBRO DE COMPRAS - MES: {mes} AÑO: {ano}", fmt_info)

                # Aplicar formato a encabezados de columna
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(5, col_num, value, fmt_header)
                
                # Ajustar columnas y aplicar formato numérico
                worksheet.set_column('A:A', 12, fmt_txt) # Fecha
                worksheet.set_column('B:B', 15, fmt_txt) # RIF
                worksheet.set_column('C:C', 40, fmt_txt) # Nombre
                worksheet.set_column('D:G', 15, fmt_txt) # Documentos
                worksheet.set_column('H:M', 18, fmt_num) # Montos

                # --- TOTALES FINALES ---
                last_row = len(df) + 6
                worksheet.write(last_row, 6, "TOTALES GENERALES:", fmt_header)
                
                # Sumatorias automáticas de las columnas H a M (Totales, Exento, Base, IVA, Retención)
                columnas_monto = ['H', 'I', 'J', 'L', 'M']
                for col_let in columnas_monto:
                    idx = ord(col_let) - 65
                    worksheet.write_formula(last_row, idx, f"=SUM({col_let}7:{col_let}{last_row})", fmt_num)

            st.download_button(
                label="📥 Generar Reporte Fiscal Excel",
                data=output.getvalue(),
                file_name=f"LIBRO_COMPRAS_{mes}_{ano}_{conf['rif_empresa']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No existen registros para el período seleccionado.")
