import streamlit as st
import database
import hashlib
import pandas as pd
from datetime import datetime

database.inicializar_db()

# --- GESTIÓN DE SESIÓN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def login():
    st.title("🔒 Acceso ERP Adonai")
    with st.form("login_form"):
        user = st.text_input("Usuario")
        pw = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            h = hashlib.sha256(pw.encode()).hexdigest()
            conn = database.conectar()
            with conn.cursor() as c:
                c.execute("SELECT usuario, rol, nombre FROM usuarios WHERE usuario=%s AND clave=%s", (user, h))
                res = c.fetchone()
            if res:
                st.session_state['autenticado'] = True
                st.session_state['usuario'] = res[0]
                st.session_state['rol'] = res[1]
                st.rerun()
            else:
                st.error("Usuario o clave incorrectos")

if not st.session_state['autenticado']:
    login()
    st.stop()

# --- MENÚ PRINCIPAL ---
st.sidebar.title(f"👤 {st.session_state['usuario']}")
st.sidebar.write(f"Rol: {st.session_state['rol']}")

opcion = st.sidebar.selectbox("Módulo", ["🏠 Inicio", "🛍️ Compras", "🏛️ Contabilidad", "⚙️ Configuración"])

if st.sidebar.button("Cerrar Sesión"):
    st.session_state['autenticado'] = False
    st.rerun()

# --- MÓDULO COMPRAS ---
if opcion == "🛍️ Compras":
    st.header("Registro de Facturas de Compra")
    with st.form("form_compra"):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha")
        rif = c2.text_input("RIF Proveedor")
        n_factura = c1.text_input("N° Factura")
        monto = c2.number_input("Monto Base", min_value=0.0)
        
        if st.form_submit_button("Guardar Factura"):
            database.ejecutar_transaccion(
                "INSERT INTO compras (fecha, rif_proveedor, num_factura, base_imponible, creado_por) VALUES (%s,%s,%s,%s,%s)",
                (fecha, rif, n_factura, monto, st.session_state['usuario'])
            )
            st.success("Factura registrada con éxito")

# --- MÓDULO CONFIGURACIÓN (Usuarios y Empresa) ---
elif opcion == "⚙️ Configuración":
    st.header("Configuración del Sistema")
    t1, t2 = st.tabs(["👥 Usuarios", "🏢 Datos de Empresa"])
    
    with t1:
        if st.session_state['rol'] == "Administrador":
            st.subheader("Crear Usuario")
            with st.form("new_user"):
                u = st.text_input("Nuevo Usuario")
                p = st.text_input("Contraseña", type="password")
                r = st.selectbox("Rol", ["Administrador", "Contador", "Analista"])
                if st.form_submit_button("Crear"):
                    h = hashlib.sha256(p.encode()).hexdigest()
                    database.ejecutar_transaccion("INSERT INTO usuarios (usuario, clave, rol) VALUES (%s,%s,%s)", (u, h, r))
                    st.success("Usuario creado")
        
        st.subheader("Cambiar Mi Contraseña")
        with st.form("change_pw"):
            nueva_p = st.text_input("Nueva Contraseña", type="password")
            if st.form_submit_button("Actualizar Clave"):
                h = hashlib.sha256(nueva_p.encode()).hexdigest()
                database.ejecutar_transaccion("UPDATE usuarios SET clave=%s WHERE usuario=%s", (h, st.session_state['usuario']))
                st.success("Contraseña actualizada")

    with t2:
        st.subheader("Datos Fiscales")
        # Aquí cargarías y guardarías en la tabla configuracion...
        st.info("Configuración de empresa activa.")

# --- MÓDULO CONTABILIDAD ---
elif opcion == "🏛️ Contabilidad":
    st.header("Gestión Contable")
    tab1, tab2 = st.tabs(["📖 Libro Diario", "📅 Períodos"])
    
    with tab2:
        st.subheader("Control de Períodos")
        # Tu lógica original de periodos...
        st.write("Periodos operativos.")
