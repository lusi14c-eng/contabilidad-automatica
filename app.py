import streamlit as st
import database
import pandas as pd
from modulos import entidades, compras

# 1. Configuración de página
st.set_page_config(page_title="Adonai ERP", layout="wide")

# 2. Inicializar base de datos (Crea tablas y usuarios iniciales)
database.inicializar_db()

# --- 3. MÓDULOS DE SEGURIDAD ---

def modulo_perfil():
    st.title("🔐 Configuración de Perfil")
    st.info(f"Usuario actual: **{st.session_state['usuario_autenticado']}**")
    
    with st.form("cambio_password"):
        st.subheader("Cambiar Contraseña")
        nueva_pass = st.text_input("Nueva Contraseña", type="password")
        confirmar_pass = st.text_input("Confirme Nueva Contraseña", type="password")
        
        if st.form_submit_button("Actualizar mi contraseña"):
            if nueva_pass == confirmar_pass and nueva_pass != "":
                try:
                    conn = database.conectar()
                    c = conn.cursor()
                    c.execute("UPDATE usuarios SET password = %s WHERE username = %s", 
                              (nueva_pass, st.session_state['usuario_autenticado']))
                    conn.commit()
                    conn.close()
                    st.success("✅ Contraseña actualizada exitosamente.")
                except Exception as e:
                    st.error(f"Error al actualizar: {e}")
            else:
                st.error("❌ Las contraseñas no coinciden o están vacías.")

def modulo_gestion_usuarios():
    st.title("👥 Gestión de Usuarios")
    
    # Formulario para crear nuevos usuarios
    with st.expander("➕ Registrar Nuevo Usuario"):
        with st.form("nuevo_u"):
            u = st.text_input("Nombre de Usuario (Login)").lower().strip()
            p = st.text_input("Contraseña Temporal", type="password")
            r = st.selectbox("Rol del Usuario", ["usuario", "admin"])
            
            if st.form_submit_button("Guardar Usuario"):
                if u and p:
                    try:
                        conn = database.conectar()
                        c = conn.cursor()
                        c.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s)", (u, p, r))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Usuario '{u}' creado como '{r}'.")
                    except Exception as e:
                        st.error(f"Error: El usuario ya existe o hubo un fallo en BD.")
                else:
                    st.warning("Complete todos los campos.")

    # Listado de usuarios existentes
    st.subheader("Usuarios en el Sistema")
    conn = database.conectar()
    df_u = pd.read_sql("SELECT username, rol FROM usuarios", conn)
    conn.close()
    st.dataframe(df_u, use_container_width=True)

def check_password():
    """Retorna True si el usuario está autenticado."""
    if "usuario_autenticado" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Acceso Adonai ERP</h2>", unsafe_allow_html=True)
        with st.form("login_center"):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                conn = database.conectar()
                if conn:
                    c = conn.cursor()
                    c.execute("SELECT username, rol FROM usuarios WHERE username = %s AND password = %s", (user, pw))
                    res = c.fetchone()
                    conn.close()
                    if res:
                        st.session_state["usuario_autenticado"] = res[0]
                        st.session_state["rol"] = res[1]
                        st.rerun()
                    else:
                        st.error("🚫 Usuario o clave incorrectos")
        return False
    return True

# --- 4. LÓGICA PRINCIPAL ---

if check_password():
    # Barra lateral
    st.sidebar.title("🚀 Adonai ERP")
    st.sidebar.write(f"👤 Usuario: **{st.session_state['usuario_autenticado']}**")
    st.sidebar.write(f"🛡️ Rol: **{st.session_state['rol'].upper()}**")
    
    # Definir opciones del menú según el ROL
    opciones = ["Dashboard", "Registrar Entidad", "Registro de Compras", "Configuración de Perfil"]
    
    # Solo el admin ve la gestión de usuarios
    if st.session_state.get("rol") == "admin":
        opciones.append("Gestión de Usuarios")
    
    menu = st.sidebar.selectbox("Seleccione Módulo:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["usuario_autenticado"]
        st.rerun()

    # Ruteo de módulos
    if menu == "Dashboard":
        st.title("📈 Dashboard")
        st.write(f"Bienvenido al sistema contable, {st.session_state['usuario_autenticado']}.")
        
    elif menu == "Registrar Entidad":
        entidades.modulo_maestro_entidades()

    elif menu == "Registro de Compras":
        compras.modulo_compras()

    elif menu == "Configuración de Perfil":
        modulo_perfil()

    elif menu == "Gestión de Usuarios":
        modulo_gestion_usuarios()
