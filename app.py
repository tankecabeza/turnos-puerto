import streamlit as st
import pandas as pd
from datetime import date, datetime
import firebase_admin
from firebase_admin import credentials, firestore
import matplotlib.pyplot as plt
import textwrap
import io
import platform
import json
import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken

# ==========================================
# 1. CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Turnos Servicios Puerto", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    [data-testid="stHeader"] { background-color: #006B4C; }
    .stButton>button { background-color: #006B4C; color: white; font-weight: bold; width: 100%; border-radius: 8px; padding: 12px; border: none;}
    .stButton>button:hover { background-color: #EAB200; color: black; }
    .stDownloadButton>button { background-color: #EAB200; color: black; }
    .stDownloadButton>button:hover { background-color: #CBA000; }
    div[data-testid="stTabs"] button { font-size: 16px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SISTEMA DE CIFRADO (FERNET + SCRYPT)
# ==========================================
# Leemos las claves desde los secretos seguros de Streamlit, NUNCA en el código
try:
    FERNET_KEY = st.secrets["FERNET_KEY"]
    OLD_XOR_KEY = st.secrets.get("OLD_XOR_KEY", "PuertoMalaga2026_SeguridadLOPD_Max_V1")
    fernet = Fernet(FERNET_KEY)
except Exception:
    st.error("🚨 Error de Seguridad: Faltan las claves criptográficas en st.secrets.")
    st.stop()

def cifrar_datos(data_dict):
    """Cifra los datos usando criptografía simétrica Fernet."""
    json_bytes = json.dumps(data_dict, ensure_ascii=False).encode('utf-8')
    return fernet.encrypt(json_bytes).decode('utf-8')

def descifrar_datos(b64_str):
    """Descifra con Fernet. Si falla, hace fallback al XOR antiguo para migrar datos heredados."""
    try:
        # 1. Intentar descifrado seguro Fernet
        descifrado_bytes = fernet.decrypt(b64_str.encode('utf-8'))
        return json.loads(descifrado_bytes.decode('utf-8'))
    except (InvalidToken, ValueError, TypeError):
        # 2. Fallback Puente: Descifrado XOR Antiguo (Migración)
        try:
            cifrado_bytes = base64.b64decode(b64_str)
            clave_bytes = OLD_XOR_KEY.encode('utf-8')
            descifrado_bytes = bytearray(
                b ^ clave_bytes[i % len(clave_bytes)] 
                for i, b in enumerate(cifrado_bytes)
            )
            return json.loads(descifrado_bytes.decode('utf-8'))
        except Exception:
            # 3. Fallback: Base64 puro (texto plano antiguo)
            try:
                return json.loads(base64.b64decode(b64_str).decode('utf-8'))
            except Exception:
                return None

def hash_scrypt(password, salt=None):
    """Genera un hash scrypt altamente seguro con salteado aleatorio."""
    if salt is None:
        salt = os.urandom(16)
    else:
        if isinstance(salt, str):
            salt = bytes.fromhex(salt)
    # Parámetros recomendados de seguridad
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, maxmem=0)
    return f"{salt.hex()}:{key.hex()}"

def verificar_password(password, stored_hash):
    """Verifica la clave. Retorna (Es_Valida, Necesita_Actualizar_A_Scrypt)"""
    if ":" not in stored_hash:
        # Es un hash SHA-256 antiguo (Migración)
        old_sha = hashlib.sha256(password.encode()).hexdigest()
        if old_sha == stored_hash:
            return True, True
        return False, False
    else:
        # Es un hash scrypt moderno
        try:
            salt_hex, _ = stored_hash.split(":")
            if hash_scrypt(password, salt_hex) == stored_hash:
                return True, False
        except Exception:
            pass
    return False, False

MODO_OFFLINE = platform.system() == "Windows"

if MODO_OFFLINE:
    MEMORIA_FILE = "memoria_local.bin"
    PLANTILLA_FILE = "plantilla_local.bin"
    CRED_FILE = "credenciales_local.bin"

    def cargar_memoria():
        if os.path.exists(MEMORIA_FILE):
            try:
                with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
                    data = descifrar_datos(f.read())
                    if data: return {k: datetime.strptime(v, "%Y-%m-%d").date() for k, v in data.items()}
            except: return {}
        return {}

    def guardar_memoria(data):
        with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
            diccionario_fechas = {k: v.strftime("%Y-%m-%d") for k, v in data.items()}
            f.write(cifrar_datos(diccionario_fechas))

    def cargar_plantilla():
        if os.path.exists(PLANTILLA_FILE):
            try:
                with open(PLANTILLA_FILE, "r", encoding="utf-8") as f:
                    data = descifrar_datos(f.read())
                    if data: return pd.DataFrame(data)
            except: return None
        return None

    def guardar_plantilla(df):
        with open(PLANTILLA_FILE, "w", encoding="utf-8") as f:
            f.write(cifrar_datos(df.to_dict('records')))
            
    def cargar_credenciales():
        if os.path.exists(CRED_FILE):
            try:
                with open(CRED_FILE, "r", encoding="utf-8") as f:
                    data = descifrar_datos(f.read())
                    if data: return data
            except: return {}
        return {}

    def guardar_credenciales(data):
        with open(CRED_FILE, "w", encoding="utf-8") as f:
            f.write(cifrar_datos(data))

else:
    @st.cache_resource
    def init_firebase():
        if not firebase_admin._apps:
            secrets_dict = dict(st.secrets["firebase"])
            secrets_dict["private_key"] = secrets_dict["private_key"].replace('\\n', '\n')
            cred = credentials.Certificate(secrets_dict)
            firebase_admin.initialize_app(cred)
        return firestore.client()

    try:
        db = init_firebase()
        DOC_MEMORIA = db.collection('gestion_turnos').document('memoria_rotacion')
        DOC_PLANTILLA = db.collection('gestion_turnos').document('plantilla_efectivos')
        DOC_CREDENCIALES = db.collection('gestion_turnos').document('credenciales_usuarios')
        
        def cargar_memoria():
            doc = DOC_MEMORIA.get()
            if doc.exists:
                dic = doc.to_dict()
                if 'datos_seguros' in dic:
                    data = descifrar_datos(dic['datos_seguros'])
                    if data:
                        return {k: datetime.strptime(v, "%Y-%m-%d").date() for k, v in data.items()}
                else:
                    return {k: datetime.strptime(v, "%Y-%m-%d").date() for k, v in dic.items() if k != 'datos_seguros'}
            return {}

        def guardar_memoria(data):
            diccionario_fechas = {k: v.strftime("%Y-%m-%d") for k, v in data.items()}
            DOC_MEMORIA.set({'datos_seguros': cifrar_datos(diccionario_fechas)})

        def cargar_plantilla():
            doc = DOC_PLANTILLA.get()
            if doc.exists:
                dic = doc.to_dict()
                if 'datos_seguros' in dic:
                    data = descifrar_datos(dic['datos_seguros'])
                    if data:
                        df = pd.DataFrame(data)
                        if 'Categoria' not in df.columns:
                            df['Categoria'] = 'RESGUARDO FISCAL'
                        return df
                elif 'efectivos' in dic:
                    df = pd.DataFrame(dic['efectivos'])
                    if 'Categoria' not in df.columns:
                        df['Categoria'] = 'RESGUARDO FISCAL'
                    return df
            return None

        def guardar_plantilla(df):
            DOC_PLANTILLA.set({'datos_seguros': cifrar_datos(df.to_dict('records'))})
            
        def cargar_credenciales():
            doc = DOC_CREDENCIALES.get()
            if doc.exists:
                dic = doc.to_dict()
                if 'datos_seguros' in dic:
                    data = descifrar_datos(dic['datos_seguros'])
                    if data: return data
                else:
                    return {k: v for k, v in dic.items() if k != 'datos_seguros'}
            return {}

        def guardar_credenciales(data):
            DOC_CREDENCIALES.set({'datos_seguros': cifrar_datos(data)})
            
    except Exception as e:
        st.error(f"❌ Error de conexión a la nube: {e}")
        st.stop()

# ==========================================
# 3. CARGA INICIAL (Sin datos personales)
# ==========================================
if 'efectivos' not in st.session_state:
    plantilla_nube = cargar_plantilla()
    if plantilla_nube is not None and not plantilla_nube.empty:
        st.session_state.efectivos = plantilla_nube
    else:
        # Si la base de datos estuviera 100% vacía, inicializa estructura vacía
        st.session_state.efectivos = pd.DataFrame(columns=["Categoria", "TIP", "Nombre", "Orden"])
        
if 'historial' not in st.session_state:
    memoria_guardada = cargar_memoria()
    if not memoria_guardada and not st.session_state.efectivos.empty:
        memoria_guardada = {row["Nombre"]: date(2000, 1, 1) for _, row in st.session_state.efectivos.iterrows()}
        guardar_memoria(memoria_guardada)
    st.session_state.historial = memoria_guardada if memoria_guardada else {}
    
if 'credenciales' not in st.session_state:
    st.session_state.credenciales = cargar_credenciales()

if 'cuadrante_generado' not in st.session_state:
    st.session_state.cuadrante_generado = False
    st.session_state.img_buffer = None
    st.session_state.texto_novedades = ""
    st.session_state.fecha_generada = None

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_actual = ""
if "forzar_cambio_clave" not in st.session_state:
    st.session_state.forzar_cambio_clave = False

# ==========================================
# 4. PANTALLA DE LOGIN RESTRINGIDO
# ==========================================
if not st.session_state.autenticado:
    st.markdown("""
        <div style="text-align: center; margin-top: 50px;">
            <h2>🛡️ ACCESO RESTRINGIDO</h2>
            <p style="color: gray;">Sistema Seguro de Gestión de Servicios</p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        usuario_input = st.text_input("👤 Usuario (Tu número de TIP):", placeholder="Ej: F10173Y").upper().strip()
        pwd_input = st.text_input("🔑 Contraseña:", type="password", autocomplete="current-password")
        submit_btn = st.form_submit_button("Desbloquear Sistema", type="primary")
        
        if submit_btn:
            admin_user = st.secrets.get("ADMIN_USER", "ADMIN")
            admin_pass = st.secrets.get("ADMIN_PASS", "Puerto2026*")
            
            if usuario_input == admin_user and pwd_input == admin_pass:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = "ADMIN"
                st.session_state.forzar_cambio_clave = False
                st.rerun()
                
            elif not st.session_state.efectivos.empty:
                df_autorizados = st.session_state.efectivos[
                    st.session_state.efectivos['Categoria'].isin(['JEFE DE TURNO', 'RESGUARDO FISCAL'])
                ]
                tips_validos = [tip.upper() for tip in df_autorizados['TIP'].tolist() if tip.upper() not in ["XX", "", "XXXXXXXX"]]
                
                if usuario_input in tips_validos:
                    creds = st.session_state.credenciales
                    hash_por_defecto_sha = hashlib.sha256(admin_pass.encode()).hexdigest()
                    
                    if usuario_input in creds:
                        is_valid, needs_upgrade = verificar_password(pwd_input, creds[usuario_input])
                        
                        if is_valid:
                            # Forzar cambio si aún usa la por defecto
                            if creds[usuario_input] == hash_por_defecto_sha or pwd_input == admin_pass:
                                st.session_state.forzar_cambio_clave = True
                            elif needs_upgrade:
                                # Migración silenciosa a Scrypt en segundo plano
                                creds[usuario_input] = hash_scrypt(pwd_input)
                                guardar_credenciales(creds)
                                st.session_state.forzar_cambio_clave = False
                            else:
                                st.session_state.forzar_cambio_clave = False
                                
                            st.session_state.autenticado = True
                            st.session_state.usuario_actual = usuario_input
                            st.rerun()
                        else:
                            st.error("❌ Contraseña incorrecta.")
                    else:
                        # Primer acceso (comprueba contra el SHA256 por defecto antiguo)
                        if hashlib.sha256(pwd_input.encode()).hexdigest() == hash_por_defecto_sha:
                            st.session_state.autenticado = True
                            st.session_state.usuario_actual = usuario_input
                            st.session_state.forzar_cambio_clave = True
                            st.rerun()
                        else:
                            st.error("❌ Primer acceso: Utiliza la contraseña inicial de la unidad.")
                else:
                    st.error("❌ No tienes permisos de acceso.")
    st.stop()

# ==========================================
# PANTALLA FORZOSA DE CAMBIO DE CONTRASEÑA
# ==========================================
if st.session_state.forzar_cambio_clave:
    st.warning("⚠️ **Por motivos de seguridad LOPD, es OBLIGATORIO cambiar tu contraseña antes de acceder a la aplicación.**")
    with st.form("form_fuerza_pass"):
        new_pass_force = st.text_input("Nueva contraseña (mínimo 6 caracteres):", type="password")
        new_pass2_force = st.text_input("Repetir nueva contraseña:", type="password")
        btn_cambiar_force = st.form_submit_button("Actualizar y Entrar", type="primary")
        
        if btn_cambiar_force:
            admin_pass = st.secrets.get("ADMIN_PASS", "Puerto2026*")
            if len(new_pass_force) < 6:
                st.error("❌ La contraseña debe tener al menos 6 caracteres.")
            elif new_pass_force != new_pass2_force:
                st.error("❌ Las contraseñas no coinciden.")
            elif new_pass_force == admin_pass:
                st.error("❌ No puedes volver a usar la contraseña por defecto.")
            else:
                st.session_state.credenciales[st.session_state.usuario_actual] = hash_scrypt(new_pass_force)
                guardar_credenciales(st.session_state.credenciales)
                st.session_state.forzar_cambio_clave = False
                st.success("✅ Contraseña actualizada y cifrada correctamente.")
                st.rerun()
    st.stop()


# ==========================================
# 5. ÁREA PERSONAL Y BARRA LATERAL
# ==========================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.usuario_actual}")
    st.caption("Área Personal Guardia Civil")
    
    with st.expander("🔑 Cambiar mi contraseña"):
        with st.form("form_pass_side"):
            new_pass = st.text_input("Nueva contraseña:", type="password")
            new_pass2 = st.text_input("Repetir contraseña:", type="password")
            btn_cambiar = st.form_submit_button("Actualizar")
            
            if btn_cambiar:
                if len(new_pass) < 6:
                    st.error("Debe tener al menos 6 caracteres.")
                elif new_pass != new_pass2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    st.session_state.credenciales[st.session_state.usuario_actual] = hash_scrypt(new_pass)
                    guardar_credenciales(st.session_state.credenciales)
                    st.success("✅ Contraseña actualizada (Cifrado Avanzado).")
    
    st.write("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""
        st.rerun()

st.title("🛡️ Turnos Servicios Puerto")

# ==========================================
# 6. INTERFAZ TIPO APP (Pestañas)
# ==========================================
tab_diario, tab_plantilla = st.tabs(["📋 Cuadrante Diario", "👥 Editar Plantilla"])

# ------------------------------------------
# PESTAÑA 2: CONFIGURACIÓN DE PLANTILLA
# ------------------------------------------
with tab_plantilla:
    st.info("💡 Edita los datos, añade componentes y pulsa 'Guardar Cambios' al final de la página para actualizar la Base de Datos.")
    
    df_plantilla = st.session_state.efectivos.copy()
    
    with st.expander("➕ AÑADIR NUEVO COMPONENTE", expanded=False):
        col_c, col_o = st.columns(2)
        nueva_cat = col_c.radio("Categoría", ["JEFE DE TURNO", "RESGUARDO FISCAL", "RESTO PLANTILLA"])
        
        if nueva_cat == "RESTO PLANTILLA":
            col_o.caption("El resto de la plantilla se ordena alfabéticamente (sin nº de antigüedad).")
            nuevo_orden = 0
        else:
            max_orden_actual = df_plantilla[df_plantilla['Categoria'] == nueva_cat]['Orden'].max() if not df_plantilla.empty else 0
            siguiente_orden = int(max_orden_actual + 1) if pd.notna(max_orden_actual) else 1
            nuevo_orden = col_o.number_input("Nº de Antigüedad", min_value=1, value=siguiente_orden)
        
        col_n1, col_n2 = st.columns(2)
        nuevo_nombre = col_n1.text_input("Nombre Completo")
        nuevo_tip = col_n2.text_input("TIP")
        
        if st.button("Añadir a la lista"):
            if nuevo_nombre and nuevo_tip:
                nuevo_registro = pd.DataFrame([{"Categoria": nueva_cat, "TIP": nuevo_tip.upper(), "Nombre": nuevo_nombre.upper(), "Orden": int(nuevo_orden)}])
                df_plantilla = pd.concat([df_plantilla, nuevo_registro], ignore_index=True)
                st.session_state.efectivos = df_plantilla
                st.success("Añadido temporalmente. Pulsa 'Guardar Cambios' abajo para confirmar.")
                st.rerun()

    st.write("---")
    st.write("### 👥 Plantilla Actual")
    editados = []

    def renderizar_tarjetas(df_sub, titulo, mostrar_orden=True):
        st.markdown(f"#### {titulo}")
        if df_sub.empty: return
        
        if mostrar_orden:
            df_sub = df_sub.sort_values("Orden").reset_index(drop=True)
        else:
            df_sub = df_sub.sort_values("Nombre").reset_index(drop=True)
            
        for idx_r, row in df_sub.iterrows():
            clave_unica = f"{row['Categoria']}_{row['Nombre']}_{row['TIP']}_{idx_r}"
            etiqueta = f"{row['Orden']} - {row['Nombre']} ({row['TIP']})" if mostrar_orden else f"{row['Nombre']} ({row['TIP']})"
            with st.expander(etiqueta):
                if mostrar_orden:
                    c1, c2, c3 = st.columns([1, 2, 1])
                    e_orden = c1.number_input("Orden", value=int(row['Orden']), key=f"ord_{clave_unica}")
                    e_nombre = c2.text_input("Nombre", value=row['Nombre'], key=f"nom_{clave_unica}")
                    e_tip = c3.text_input("TIP", value=row['TIP'], key=f"tip_{clave_unica}")
                else:
                    c2, c3 = st.columns([3, 1])
                    e_orden = 0
                    e_nombre = c2.text_input("Nombre", value=row['Nombre'], key=f"nom_{clave_unica}")
                    e_tip = c3.text_input("TIP", value=row['TIP'], key=f"tip_{clave_unica}")
                
                eliminar = st.checkbox("Eliminar componente", key=f"del_{clave_unica}")
                if not eliminar:
                    editados.append({
                        "Categoria": row['Categoria'], 
                        "TIP": e_tip.upper(), 
                        "Nombre": e_nombre.upper(), 
                        "Orden": int(e_orden)
                    })

    if not df_plantilla.empty:
        renderizar_tarjetas(df_plantilla[df_plantilla['Categoria'] == 'JEFE DE TURNO'], "⭐ Jefes de Turno", mostrar_orden=True)
        renderizar_tarjetas(df_plantilla[df_plantilla['Categoria'] == 'RESGUARDO FISCAL'], "🛡️ Turno Fijo Guardia (Resguardo Fiscal)", mostrar_orden=True)
        with st.expander("📋 Ver / Editar Resto de Plantilla de la Unidad (Orden Alfabético)", expanded=False):
            renderizar_tarjetas(df_plantilla[df_plantilla['Categoria'] == 'RESTO PLANTILLA'], "👥 Resto de Plantilla", mostrar_orden=False)

    if st.button("💾 GUARDAR CAMBIOS EN LA BASE DE DATOS", type="primary"):
        nueva_plantilla = pd.DataFrame(editados)
        if not nueva_plantilla.empty:
            guardar_plantilla(nueva_plantilla)
            st.session_state.efectivos = nueva_plantilla
            
            for _, row in nueva_plantilla.iterrows():
                if row["Nombre"] not in st.session_state.historial:
                    st.session_state.historial[row["Nombre"]] = date(2000, 1, 1)
            guardar_memoria(st.session_state.historial)
            st.success("✅ Plantilla actualizada permanentemente en la Base de Datos con Fernet.")
            st.rerun()

    st.write("---")
    st.write("### 🛠️ Opciones Avanzadas de Reseteo")
    with st.expander("⚠️ Zona de Peligro (Cuidado)"):
        if st.button("🗑️ Resetear historial de rotaciones (Antigüedad pura)", key="reset_plantilla"):
            nuevo_historial = {row["Nombre"]: date(2000, 1, 1) for _, row in st.session_state.efectivos.iterrows()}
            guardar_memoria(nuevo_historial)
            st.session_state.historial = nuevo_historial
            st.success("✅ Historial de rotaciones borrado. Antigüedad pura al 100%.")
            st.rerun()

# ------------------------------------------
# PESTAÑA 1: USO DIARIO
# ------------------------------------------
with tab_diario:
    if st.session_state.efectivos.empty:
        st.warning("⚠️ No hay efectivos en la base de datos. Ve a la pestaña 'Editar Plantilla' para añadirlos.")
        st.stop()
        
    col1, col2 = st.columns(2)
    fecha_servicio = col1.date_input("📅 Fecha", value=date.today())
    tipo_turno = col2.radio("⏱️ Turno", ["Mañana", "Noche"], horizontal=True)

    st.write("### 👥 Asignación de Roles")
    
    efectivos_global = st.session_state.efectivos.copy()
    efectivos_global['Cat_Num'] = efectivos_global['Categoria'].map({
        'JEFE DE TURNO': 1,
        'RESGUARDO FISCAL': 2,
        'RESTO PLANTILLA': 3
    }).fillna(3)
    efectivos_global = efectivos_global.sort_values(['Cat_Num', 'Orden', 'Nombre'])
    nombres_lista_global = efectivos_global["Nombre"].tolist()
    
    jefes_seleccionados_raw = st.multiselect(
        "⭐ Jefe/s de Turno (El 1º será Jefe de Turno y el 2º Jefe Adjunto)",
        options=nombres_lista_global,
        placeholder="Selecciona uno o varios..."
    )
    
    if jefes_seleccionados_raw:
        df_jefes_sel = efectivos_global[efectivos_global["Nombre"].isin(jefes_seleccionados_raw)].copy()
        df_jefes_sel["Orden_Sel"] = [
            r["Orden"] if r["Categoria"] in ["JEFE DE TURNO", "RESGUARDO FISCAL"] else 100 + jefes_seleccionados_raw.index(r["Nombre"])
            for _, r in df_jefes_sel.iterrows()
        ]
        df_jefes_ordenados = df_jefes_sel.sort_values(['Cat_Num', 'Orden_Sel'])
        jefes_seleccionados = df_jefes_ordenados["Nombre"].tolist()
    else:
        jefes_seleccionados = []
    
    if len(jefes_seleccionados) == 1:
        st.caption(f"🎖️ **Jefe de Turno:** {jefes_seleccionados[0]}")
    elif len(jefes_seleccionados) >= 2:
        st.caption(f"🎖️ **Jefe de Turno:** {jefes_seleccionados[0]} &nbsp;|&nbsp; **Jefe Adjunto:** {', '.join(jefes_seleccionados[1:])}")
    
    opciones_confronta_disp = [n for n in nombres_lista_global if n not in jefes_seleccionados]
    
    confrontas_seleccionados_raw = st.multiselect(
        "📝 Confronta (Puedes elegir uno o varios)", 
        options=opciones_confronta_disp,
        placeholder="Selecciona uno o varios..."
    )
    
    if confrontas_seleccionados_raw:
        df_conf_sel = efectivos_global[efectivos_global["Nombre"].isin(confrontas_seleccionados_raw)].copy()
        df_conf_sel["Orden_Sel"] = [
            r["Orden"] if r["Categoria"] in ["JEFE DE TURNO", "RESGUARDO FISCAL"] else 100 + confrontas_seleccionados_raw.index(r["Nombre"])
            for _, r in df_conf_sel.iterrows()
        ]
        df_conf_ordenados = df_conf_sel.sort_values(['Cat_Num', 'Orden_Sel'])
        confrontas_seleccionados = df_conf_ordenados["Nombre"].tolist()
    else:
        confrontas_seleccionados = []
    
    st.write("---")
    st.write("🛡️ **Resguardo Fiscal** (Activa los componentes fijos del grupo en rotación)")
    ops_fijos_seleccionados = []
    
    df_operativos_solo = efectivos_global[efectivos_global['Categoria'] == 'RESGUARDO FISCAL'].sort_values("Orden")
    
    for _, row in df_operativos_solo.iterrows():
        if row['Nombre'] not in jefes_seleccionados and row['Nombre'] not in confrontas_seleccionados:
            with st.container(border=True):
                col_izq, col_der = st.columns([0.8, 0.2])
                with col_izq:
                    st.markdown(f"**{row['Nombre']}**")
                    st.caption(f"TIP: {row['TIP']} | Nº Antigüedad: {row['Orden']}")
                with col_der:
                    if st.toggle("Sí", key=f"tog_{row['TIP']}", label_visibility="collapsed"):
                        ops_fijos_seleccionados.append(row)

    st.write("➕ **Resto de Plantilla (Refuerzos para el turno)**")
    df_resto_disponible = efectivos_global[
        (efectivos_global['Categoria'] == 'RESTO PLANTILLA') &
        (~efectivos_global['Nombre'].isin(jefes_seleccionados)) &
        (~efectivos_global['Nombre'].isin(confrontas_seleccionados))
    ].sort_values("Nombre")
    
    nombres_refuerzos_sel = st.multiselect(
        "Selecciona uno o varios componentes que refuercen hoy (Orden alfabético):",
        options=df_resto_disponible["Nombre"].tolist(),
        placeholder="Buscar por apellido o nombre..."
    )
    ops_refuerzos_seleccionados = []
    if nombres_refuerzos_sel:
        for _, row_ref in df_resto_disponible[df_resto_disponible["Nombre"].isin(nombres_refuerzos_sel)].iterrows():
            ops_refuerzos_seleccionados.append(row_ref)

    num_ops = len(ops_fijos_seleccionados) + len(ops_refuerzos_seleccionados)
    num_jefes = len(jefes_seleccionados)
    
    st.write("---")
    modo_vigilancia = st.toggle("🚨 MODO VIGILANCIA: Activar puesto provisional (PARRILLA)")
    
    if num_ops == 3 and num_jefes >= 1:
        indice_defecto = 0
    elif num_ops == 5:
        indice_defecto = 1
    else:
        indice_defecto = 2

    col3, col4 = st.columns(2)
    intervalo_horas = col3.selectbox(
        "⏳ Rotación cada...",
        [2, 2.33, 3, 4],
        index=indice_defecto,
        format_func=lambda x: "2h 20m" if x == 2.33 else f"{x} Horas"
    )
    
    if modo_vigilancia:
        if num_ops == 6:
            def_puestos = "PUERTAS, POSTA, PARRILLA, POSTA, POSTA, ROMA"
        elif num_ops == 5:
            def_puestos = "PUERTAS, POSTA, PARRILLA, POSTA, ROMA"
        elif num_ops == 4:
            def_puestos = "PUERTAS, PARRILLA, POSTA, ROMA"
        elif num_ops == 3:
            def_puestos = "PUERTAS, PARRILLA, ROMA"
        else:
            def_puestos = "PUERTAS, " + ", ".join(["POSTA"] * max(0, num_ops - 3)) + ", PARRILLA, ROMA"
    else:
        if num_ops == 6:
            def_puestos = "PUERTAS, POSTA, POSTA, POSTA, POSTA, ROMA"
        elif num_ops == 5:
            def_puestos = "PUERTAS, POSTA, POSTA, POSTA, ROMA"
        elif num_ops == 4:
            def_puestos = "PUERTAS, POSTA, POSTA, ROMA"
        elif num_ops == 3:
            def_puestos = "PUERTAS, POSTA, ROMA"
        else:
            def_puestos = "PUERTAS, " + ", ".join(["POSTA"] * max(0, num_ops - 2)) + ", ROMA"
        
    puestos_input = col4.text_input("📍 Puestos", value=def_puestos)
    lista_puestos = [p.strip() for p in puestos_input.split(",") if p.strip()]

    # ==========================================
    # 5. MOTOR MATEMÁTICO Y GENERADOR
    # ==========================================
    def calcular_franjas(turno, intervalo):
        if intervalo == 2.33:
            if turno == "Noche":
                franjas_img = ["19/21:20", "21:20/23:40", "23:40/02", "02/04:20", "04:20/07"]
                franjas_texto = ["19:00 h a 21:20 h", "21:20 h a 23:40 h", "23:40 h a 02:00 h", "02:00 h a 04:20 h", "04:20 h a 07:00 h"]
            else:
                franjas_img = ["07/09:20", "09:20/11:40", "11:40/14", "14/16:20", "16:20/19"]
                franjas_texto = ["07:00 h a 09:20 h", "09:20 h a 11:40 h", "11:40 h a 14:00 h", "14:00 h a 16:20 h", "16:20 h a 19:00 h"]
            return franjas_img, franjas_texto

        start = 7 if turno == "Mañana" else 19
        slots = int(12 / intervalo)
        franjas_img = []
        franjas_texto = []
        for i in range(slots):
            h_inicio = (start + (i * intervalo)) % 24
            h_fin = (start + ((i + 1) * intervalo)) % 24
            img_str = f"{int(h_inicio):02d}/{int(h_fin):02d}"
            franjas_img.append(img_str)
            txt_str = f"{int(h_inicio):02d}:00 h a {int(h_fin):02d}:00 h"
            franjas_texto.append(txt_str)
        return franjas_img, franjas_texto

    def crear_imagen_tabla(df, titulo):
        df_img = df.copy()
        if 'Nombre' in df_img.columns:
            df_img['Nombre'] = df_img['Nombre'].apply(lambda x: '\n'.join(textwrap.wrap(str(x), width=22)))

        num_franjas = len(df.columns) - 4
        
        if num_franjas >= 6:
            ancho_lienzo = 14.5
        elif num_franjas == 5:
            ancho_lienzo = 13.0
        else:
            ancho_lienzo = 11.5
            
        alto_lienzo = 0.65 * (len(df) + 1)
        
        fig, ax = plt.subplots(figsize=(ancho_lienzo, alto_lienzo))
        ax.axis('off')
        
        if num_franjas == 5:
            ancho_col_franja = 0.11
        elif num_franjas >= 6:
            ancho_col_franja = 0.09
        else:
            ancho_col_franja = 0.10
            
        col_widths = [0.05, 0.12, 0.26, 0.21] + [ancho_col_franja] * num_franjas
        
        table = ax.table(
            cellText=df_img.values,
            colLabels=df.columns,
            colWidths=col_widths,
            bbox=[0, 0, 1, 1],
            cellLoc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9.5)
        
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor('#B0C4DE') 
            if row == 0:
                cell.set_facecolor('#006B4C') 
                cell.set_text_props(color='white', weight='bold', size=9.5 if num_franjas >= 5 else 10)
            else:
                if df.iloc[row-1]['Nº'] == '-':
                    cell.set_facecolor('#E6F0EC') 
                    cell.set_text_props(size=9.5)
                else:
                    cell.set_facecolor('#FFFFFF' if row % 2 == 0 else '#F4F6F5')
                    cell.set_text_props(size=9.5)
                
                if df.columns[col] == 'Rol':
                    cell.set_text_props(weight='bold')
        
        ax.set_title(titulo, fontweight="bold", fontsize=15, color="#006B4C", pad=12)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.2, dpi=300)
        buf.seek(0)
        plt.close()
        return buf

    if num_ops > 0 or num_jefes > 0 or len(confrontas_seleccionados) > 0:
        if num_ops > 0:
            st.write("### 🔢 Asignación de Puestos")
            if modo_vigilancia:
                st.caption("🚨 Modo Vigilancia activo: Cadencia perfecta adaptada.")
            else:
                st.caption("Rueda de Antigüedad para los fijos del grupo y asignación manual libre para los refuerzos de la unidad.")
            
            if len(ops_fijos_seleccionados) > 0:
                df_fijos = pd.DataFrame(ops_fijos_seleccionados).sort_values(by="Orden", ascending=True).reset_index(drop=True)
                df_fijos["Ultimo_Maximo"] = df_fijos["Nombre"].map(st.session_state.historial).fillna(date(2000, 1, 1))
                df_fijos["Es_Refuerzo"] = False
                
                max_fecha = df_fijos["Ultimo_Maximo"].max()
                nombre_pivote_auto = "(Antigüedad pura - Sin rotación previa)"
                if max_fecha > date(2000, 1, 1):
                    penalizados = df_fijos[df_fijos["Ultimo_Maximo"] == max_fecha].sort_values(by="Orden", ascending=False)
                    if not penalizados.empty:
                        nombre_pivote_auto = penalizados.iloc[0]["Nombre"]

                opciones_pivote = ["(Antigüedad pura - Sin rotación previa)"] + df_fijos["Nombre"].tolist()
                idx_pivote = opciones_pivote.index(nombre_pivote_auto) if nombre_pivote_auto in opciones_pivote else 0

                pivote_seleccionado = st.selectbox(
                    "🔄 ¿Quién del grupo fijo tuvo el Nº más alto en el último servicio? (Pasa al Nº bajo y rota el resto):",
                    options=opciones_pivote,
                    index=idx_pivote
                )

                if pivote_seleccionado != "(Antigüedad pura - Sin rotación previa)":
                    orden_pivote = df_fijos[df_fijos["Nombre"] == pivote_seleccionado].iloc[0]["Orden"]
                    def calcular_posicion_rueda(orden_actual):
                        if orden_actual == orden_pivote:
                            return 999999
                        elif orden_actual > orden_pivote:
                            return orden_actual - orden_pivote
                        else:
                            return 1000 + orden_actual
                    df_fijos["Orden_Calculo"] = df_fijos["Orden"].apply(calcular_posicion_rueda)
                else:
                    df_fijos["Orden_Calculo"] = df_fijos["Orden"]
                
                df_fijos = df_fijos.sort_values(by="Orden_Calculo", ascending=True).reset_index(drop=True)
            else:
                df_fijos = pd.DataFrame()
                pivote_seleccionado = "ninguno"

            if len(ops_refuerzos_seleccionados) > 0:
                df_ref = pd.DataFrame(ops_refuerzos_seleccionados).sort_values(by="Nombre", ascending=True).reset_index(drop=True)
                df_ref["Ultimo_Maximo"] = date(2000, 1, 1)
                df_ref["Es_Refuerzo"] = True
                df_ref["Orden_Calculo"] = 2000000
                df_ref["Orden"] = range(100, 100 + len(df_ref))
                df_ops = pd.concat([df_fijos, df_ref], ignore_index=True) if not df_fijos.empty else df_ref
            else:
                df_ops = df_fijos

            df_ops["Sugerido"] = range(num_ops, 0, -1)
            
            asignaciones_usuario = []
            numeros_disponibles = list(range(1, num_ops + 1))
            
            for _, row in df_ops.iterrows():
                with st.container(border=True):
                    col_n1, col_n2 = st.columns([0.6, 0.4])
                    with col_n1:
                        st.markdown(f"**{row['Nombre']}**")
                        
                        if row["Es_Refuerzo"]:
                            st.caption(f"TIP: {row['TIP']} | ➕ **Refuerzo de Unidad** (Asignar Nº manualmente)")
                        else:
                            fecha_str = "Sin registro" if row["Ultimo_Maximo"] == date(2000, 1, 1) else row["Ultimo_Maximo"].strftime('%d/%m/%Y')
                            st.caption(f"Nº Antigüedad: {row['Orden']} | Último Nº Alto: {fecha_str}")
                            
                            if row["Orden_Calculo"] == 999999:
                                st.markdown("⚠️ <span style='color:#D32F2F; font-size:0.9em;'>Tuvo el último alto</span>", unsafe_allow_html=True)

                    with col_n2:
                        default_idx = numeros_disponibles.index(row["Sugerido"])
                        clave_unica = f"turno_rueda_{row['TIP']}_{num_ops}_{fecha_servicio}_{pivote_seleccionado}"
                        n_asignado = st.selectbox(
                            "Nº Asignado",
                            options=numeros_disponibles,
                            index=default_idx,
                            key=clave_unica
                        )
                    asignaciones_usuario.append({
                        "Nombre": row["Nombre"],
                        "TIP": row["TIP"],
                        "Orden": int(row["Orden"]),
                        "Es_Refuerzo": bool(row["Es_Refuerzo"]),
                        "Nº Asignado": n_asignado
                    })
            
            numeros_editados = pd.DataFrame(asignaciones_usuario)
            asignados_list = numeros_editados["Nº Asignado"].tolist()
            
            if len(set(asignados_list)) != num_ops:
                st.error("⚠️ ¡Atención! No puedes repetir el mismo número asignado entre distintos componentes.")
                boton_generar = False
            else:
                boton_generar = st.button("🚀 Confirmar Rotación y Generar", type="primary")
                
            if boton_generar:
                fijos_hoy = numeros_editados[~numeros_editados["Es_Refuerzo"]]
                if not fijos_hoy.empty:
                    max_num_fijo = fijos_hoy["Nº Asignado"].max()
                    nombre_max = fijos_hoy[fijos_hoy["Nº Asignado"] == max_num_fijo].iloc[0]["Nombre"]
                    st.session_state.historial[nombre_max] = fecha_servicio
                    guardar_memoria(st.session_state.historial)
                else:
                    nombre_max = numeros_editados[numeros_editados["Nº Asignado"] == num_ops].iloc[0]["Nombre"]
                
                franjas_img, franjas_texto = calcular_franjas(tipo_turno, intervalo_horas)
                titulo_cuadrante = f"CUADRANTE {fecha_servicio.strftime('%d/%m/%Y')} - {tipo_turno.upper()}"
                
                texto = f"{titulo_cuadrante}\n\n"
                cuadrante_final = []
                
                for idx_j, nombre_jefe in enumerate(jefes_seleccionados):
                    rol_jefe = "JEFE DE TURNO" if idx_j == 0 else "JEFE ADJUNTO"
                    tip_jefe = efectivos_global[efectivos_global["Nombre"] == nombre_jefe].iloc[0]["TIP"]
                    texto += f"{rol_jefe}: {nombre_jefe} ({tip_jefe})\n"
                    fila_fija = {"Nº": "-", "TIP": tip_jefe, "Nombre": nombre_jefe, "Rol": rol_jefe}
                    for h in franjas_img: fila_fija[h] = "-"
                    cuadrante_final.append(fila_fija)
                    
                for nombre_conf in confrontas_seleccionados:
                    tip_conf = efectivos_global[efectivos_global["Nombre"] == nombre_conf].iloc[0]["TIP"]
                    texto += f"CONFRONTA: {nombre_conf} ({tip_conf})\n"
                    fila_fija = {"Nº": "-", "TIP": tip_conf, "Nombre": nombre_conf, "Rol": "CONFRONTA"}
                    for h in franjas_img: fila_fija[h] = "-"
                    cuadrante_final.append(fila_fija)
                
                if jefes_seleccionados or confrontas_seleccionados:
                    texto += "\n"
                
                for _, row in numeros_editados.sort_values("Nº Asignado", ascending=True).iterrows():
                    tip_op = row["TIP"]
                    n_asignado = row['Nº Asignado']
                    fila_op = {"Nº": str(n_asignado), "TIP": tip_op, "Nombre": row["Nombre"], "Rol": "RESGUARDO FISCAL"}
                    
                    for idx, h_img in enumerate(franjas_img):
                        L = len(lista_puestos)
                        if L > 0:
                            if modo_vigilancia and num_ops == 5 and L == 5:
                                mapa_vigilancia_5 = {
                                    1: ["PUERTAS", "POSTA", "PARRILLA", "POSTA", "ROMA"],
                                    2: ["POSTA", "ROMA", "PUERTAS", "POSTA", "PARRILLA"],
                                    3: ["POSTA", "PARRILLA", "POSTA", "ROMA", "PUERTAS"],
                                    4: ["PARRILLA", "POSTA", "ROMA", "POSTA", "PUERTAS"],
                                    5: ["ROMA", "PUERTAS", "POSTA", "PARRILLA", "POSTA"]
                                }
                                fila_op[h_img] = mapa_vigilancia_5.get(n_asignado, lista_puestos)[idx]
                            else:
                                puesto = lista_puestos[(n_asignado - 1 + idx) % L]
                                fila_op[h_img] = puesto
                        else:
                            fila_op[h_img] = ""
                    
                    cuadrante_final.append(fila_op)
                
                for _, row in numeros_editados.sort_values(["Es_Refuerzo", "Orden", "Nombre"], ascending=[True, True, True]).iterrows():
                    tip_op = row["TIP"]
                    n_asignado = row['Nº Asignado']
                    
                    texto += f"{row['Nombre']} ({tip_op})\n"
                    for idx, h_txt in enumerate(franjas_texto):
                        L = len(lista_puestos)
                        if L > 0:
                            if modo_vigilancia and num_ops == 5 and L == 5:
                                mapa_vigilancia_5 = {
                                    1: ["PUERTAS", "POSTA", "PARRILLA", "POSTA", "ROMA"],
                                    2: ["POSTA", "ROMA", "PUERTAS", "POSTA", "PARRILLA"],
                                    3: ["POSTA", "PARRILLA", "POSTA", "ROMA", "PUERTAS"],
                                    4: ["PARRILLA", "POSTA", "ROMA", "POSTA", "PUERTAS"],
                                    5: ["ROMA", "PUERTAS", "POSTA", "PARRILLA", "POSTA"]
                                }
                                puesto = mapa_vigilancia_5.get(n_asignado, lista_puestos)[idx]
                            else:
                                puesto = lista_puestos[(n_asignado - 1 + idx) % L]
                        else:
                            puesto = ""
                        texto += f"{h_txt}: {puesto}\n"
                    texto += "\n"
                
                df_final = pd.DataFrame(cuadrante_final)
                img_buffer = crear_imagen_tabla(df_final, titulo_cuadrante)
                
                st.session_state.cuadrante_generado = True
                st.session_state.img_buffer = img_buffer
                st.session_state.texto_novedades = texto
                st.session_state.fecha_generada = fecha_servicio.strftime('%d_%m_%Y')
                
                st.success(f"☁️ Guardado con éxito. {nombre_max} pasa al final de la cola.")

        # ==========================================
        # 6. MOSTRAR RESULTADOS GUARDADOS EN MEMORIA
        # ==========================================
        if st.session_state.get('cuadrante_generado', False):
            st.write("---")
            st.write("### 📸 Imagen para WhatsApp")
            st.download_button(
                label="📥 DESCARGAR IMAGEN (PNG)",
                data=st.session_state.img_buffer,
                file_name=f"Cuadrante_{st.session_state.fecha_generada}.png",
                mime="image/png"
            )
                
            st.write("### 📝 Texto para Novedades")
            st.text_area("Copia el texto plano (sin símbolos):", value=st.session_state.texto_novedades, height=250)
            
    else:
        st.info("Selecciona componentes arriba para generar el cuadrante.")
