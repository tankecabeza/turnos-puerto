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
# 2. SISTEMA HÍBRIDO (NUBE / PENDRIVE LOCAL)
# ==========================================
MODO_OFFLINE = platform.system() == "Windows"

if MODO_OFFLINE:
    MEMORIA_FILE = "memoria_local.bin"
    PLANTILLA_FILE = "plantilla_local.bin"
    CRED_FILE = "credenciales_local.bin"

    def codificar_datos(data):
        json_str = json.dumps(data, ensure_ascii=False)
        return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    def decodificar_datos(b64_str):
        json_str = base64.b64decode(b64_str).decode('utf-8')
        return json.loads(json_str)

    def cargar_memoria():
        if os.path.exists(MEMORIA_FILE):
            try:
                with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
                    data = decodificar_datos(f.read())
                    return {k: datetime.strptime(v, "%Y-%m-%d").date() for k, v in data.items()}
            except: return {}
        return {}

    def guardar_memoria(data):
        with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
            diccionario_fechas = {k: v.strftime("%Y-%m-%d") for k, v in data.items()}
            f.write(codificar_datos(diccionario_fechas))

    def cargar_plantilla():
        if os.path.exists(PLANTILLA_FILE):
            try:
                with open(PLANTILLA_FILE, "r", encoding="utf-8") as f:
                    return pd.DataFrame(decodificar_datos(f.read()))
            except: return None
        return None

    def guardar_plantilla(df):
        with open(PLANTILLA_FILE, "w", encoding="utf-8") as f:
            f.write(codificar_datos(df.to_dict('records')))
            
    def cargar_credenciales():
        if os.path.exists(CRED_FILE):
            try:
                with open(CRED_FILE, "r", encoding="utf-8") as f:
                    return decodificar_datos(f.read())
            except: return {}
        return {}

    def guardar_credenciales(data):
        with open(CRED_FILE, "w", encoding="utf-8") as f:
            f.write(codificar_datos(data))

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
                return {k: datetime.strptime(v, "%Y-%m-%d").date() for k, v in doc.to_dict().items()}
            return {}

        def guardar_memoria(data):
            DOC_MEMORIA.set({k: v.strftime("%Y-%m-%d") for k, v in data.items()})

        def cargar_plantilla():
            doc = DOC_PLANTILLA.get()
            if doc.exists:
                df = pd.DataFrame(doc.to_dict()['efectivos'])
                if 'Categoria' not in df.columns:
                    df['Categoria'] = 'RESGUARDO FISCAL'
                return df
            return None

        def guardar_plantilla(df):
            DOC_PLANTILLA.set({'efectivos': df.to_dict('records')})
            
        def cargar_credenciales():
            doc = DOC_CREDENCIALES.get()
            return doc.to_dict() if doc.exists else {}

        def guardar_credenciales(data):
            DOC_CREDENCIALES.set(data)
            
    except Exception as e:
        st.error(f"❌ Error de conexión a la nube: {e}")
        st.stop()

# ==========================================
# 3. CARGA INICIAL DE DATOS EXACTOS
# ==========================================
plantilla_oficial = pd.DataFrame([
    # 1. JEFES DE TURNO HABITUALES
    {"Categoria": "JEFE DE TURNO", "TIP": "Q21989J", "Nombre": "SARGENTO 1º JUAN CARLOS GÁLVEZ ÁLVAREZ", "Orden": 1},
    {"Categoria": "JEFE DE TURNO", "TIP": "E57240M", "Nombre": "SARGENTO MARTIN RICO HUTCHISON", "Orden": 2},
    {"Categoria": "JEFE DE TURNO", "TIP": "X49035H", "Nombre": "CABO 1º DAVID MOSTAZO GARCÍA", "Orden": 3},
    {"Categoria": "JEFE DE TURNO", "TIP": "B36115Y", "Nombre": "CABO 1º SALVADOR MARTÍN BAENA", "Orden": 4},
    {"Categoria": "JEFE DE TURNO", "TIP": "Y14399C", "Nombre": "CABO 1º ANSELMO ROMERO MORENO", "Orden": 5},
    {"Categoria": "JEFE DE TURNO", "TIP": "R37053N", "Nombre": "CABO 1º MIGUEL CARMONA FLORES", "Orden": 6},
    {"Categoria": "JEFE DE TURNO", "TIP": "P44826Q", "Nombre": "GUARDIA CIVIL 1º MIGUEL ÁNGEL DUARTE SÁNCHEZ", "Orden": 7},
    {"Categoria": "JEFE DE TURNO", "TIP": "P58735T", "Nombre": "GUARDIA CIVIL MIGUEL MARTÍN DÍAZ", "Orden": 8},
    
    # 2. RESGUARDO FISCAL (GRUPO FIJO)
    {"Categoria": "RESGUARDO FISCAL", "TIP": "S49454H", "Nombre": "FRANCISCO JOSÉ GARCÍA TEMBLADOR", "Orden": 1},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "C65480C", "Nombre": "RAFAEL ORTÍZ GONZALEZ", "Orden": 2},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "F10173Y", "Nombre": "ALBERTO FRANCISCO BERLANGA CRUZADO", "Orden": 3},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "W92718I", "Nombre": "ANTONIO MARIANO RODRÍGUEZ MARTÍNEZ", "Orden": 4},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "U09338T", "Nombre": "DAVID JOAQUÍN LÓPEZ ESPINAL", "Orden": 5},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "Z19006G", "Nombre": "ALBERTO CONSTAN CRESPO", "Orden": 6},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "V49093U", "Nombre": "DIEGO MANUEL TORRES KITTS", "Orden": 7},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "N23723F", "Nombre": "CELIA DOMÍNGUEZ BARRANCO", "Orden": 8},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "X10503B", "Nombre": "IVÁN JUÁREZ VERDUGO", "Orden": 9},

    # 3. RESTO DE PLANTILLA DE LA UNIDAD (ORDEN ALFABÉTICO POR APELLIDOS, SIN ANTIGÜEDAD)
    {"Categoria": "RESTO PLANTILLA", "TIP": "R49856I", "Nombre": "AHMED RACHID, ZOHAIR", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "I51444D", "Nombre": "ALBA RAMAJO, ANDREA (TENIENTE)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "L26693P", "Nombre": "ALBAÑIL ALBAÑIL, ALEJANDRO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "W63047Y", "Nombre": "BERMEJO MORENO, JAVIER", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "H97426N", "Nombre": "BLANCO RODRÍGUEZ, ANTONIO GERMÁN", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "J14296K", "Nombre": "BRICEÑO ESCOBAR, ANTONIO (SARGENTO 1º)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "K18646N", "Nombre": "CANO RODRÍGUEZ, JULIÁN", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "V89107U", "Nombre": "CASTAÑEDA JIMÉNEZ, JAVIER", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "M50512C", "Nombre": "CERDÁN POSTIGO, FRANCISCO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "H19872X", "Nombre": "CUETO PADILLA, JOSÉ LUIS (GUARDIA 1º)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "Y32879A", "Nombre": "FERNÁNDEZ JUSTICIA, PABLO (G.A.P.)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "I12192V", "Nombre": "FERNÁNDEZ TOMÉ, GONZALO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "G45948Z", "Nombre": "GAITÁN LÓPEZ, JOSÉ ANTONIO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "R54704P", "Nombre": "GÁLVEZ SÁNCHEZ RANDO, JOSÉ ANTONIO (CABO 1º)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "W29740H", "Nombre": "GÁMEZ ÁVILA, MIGUEL ÁNGEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "Y74264M", "Nombre": "GARCÍA NAVIA, GERMÁN (BRIGADA)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "B69631D", "Nombre": "GARCÍA ORTEGA, FRANCISCO MANUEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "P90329E", "Nombre": "GIL GARCÍA, JUAN ANTONIO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "H44555F", "Nombre": "GIL ROMERO, JOSÉ ANTONIO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "B29544C", "Nombre": "GÓMEZ JURADO, ANTONIO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "P30694P", "Nombre": "GONZÁLEZ DOMÍNGUEZ, FERNANDO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "L98185Y", "Nombre": "GONZÁLEZ GONZÁLEZ, MARÍA NATALIA", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "T17416E", "Nombre": "GONZÁLEZ SEVILLA, ANA ISABEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "N86843Y", "Nombre": "GUTIÉRREZ ANAYA, JOSÉ MANUEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "I52251V", "Nombre": "HERNÁNDEZ GONZÁLEZ, JAVIER", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "I58896H", "Nombre": "LARA PALOMO, RAFAEL (SARGENTO 1º)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "H00165H", "Nombre": "LIÑÁN PÁEZ, JOSÉ ANTONIO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "M56747G", "Nombre": "LÓPEZ CARRILLO, VICENTE", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "V22287Y", "Nombre": "LÓPEZ PERALES, RAÚL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "M66973T", "Nombre": "LÓPEZ RUEDA, JOSÉ RAMÓN", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "J36746N", "Nombre": "LOZANO PEÑAS, JOSÉ", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "A69961K", "Nombre": "LUQUE MARÍN, FRANCISCO (SUBTENIENTE)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "H50953S", "Nombre": "MARTÍN MARTÍN, PEDRO ALFONSO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "N08103C", "Nombre": "MARTÍNEZ BOUAZZAOUI, FOUAD", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "N55757Y", "Nombre": "MILLÁN HEDRERA, RAFAEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "Z74474D", "Nombre": "MOHAND AISSA, MIMUN", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "E32722J", "Nombre": "OLMO VALLE, DANIEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "B14732T", "Nombre": "ORTEGA MONTIEL, DAMIÁN", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "M64419Z", "Nombre": "PALMA MARTÍN, FANNY", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "S54697I", "Nombre": "PASCUAL GARCÍA, RAFAEL ANTONIO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "T30946G", "Nombre": "PEREIRA JIMÉNEZ, JOSÉ LUIS", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "K86275E", "Nombre": "PÉREZ MOSTAZO, MIGUEL (CABO 1º)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "L29418N", "Nombre": "RAMÍREZ GONZÁLEZ, FRANCISCO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "E05615U", "Nombre": "ROLDÁN GARCÍA, MANUEL JESÚS", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "R15523R", "Nombre": "ROSA VERA, MARÍA FLOR", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "Q49522E", "Nombre": "RUBIO NÚÑEZ, MIGUEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "W20433X", "Nombre": "RUIZ MORENO, FRANCISCO JAVIER", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "J22270M", "Nombre": "RUIZ RUIZ, DAVID", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "C61529C", "Nombre": "SÁNCHEZ JUÁREZ, NORBERTO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "G91609K", "Nombre": "SÁNCHEZ MARTÍN, PEDRO MANUEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "K09011V", "Nombre": "SÁNCHEZ MEDINA, JOSÉ ALBERTO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "P61552X", "Nombre": "SÁNCHEZ REINA, JESÚS MARÍA", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "U49148U", "Nombre": "SANTILLANA BRUNET, ROCÍO (G.A.P.)", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "I72545K", "Nombre": "SANTOS FONTALVA, JOSÉ ANTONIO", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "Y91516U", "Nombre": "SANTOS FONTALVA, LUCAS", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "D71103L", "Nombre": "SUÁREZ SILVENTE, JOSÉ MARÍA", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "C82404J", "Nombre": "TIRADO ROMERO, DANIEL", "Orden": 0},
    {"Categoria": "RESTO PLANTILLA", "TIP": "A22691J", "Nombre": "ZAYAS RUIZ, FRANCISCO JOSÉ", "Orden": 0}
])

if 'efectivos' not in st.session_state:
    plantilla_nube = cargar_plantilla()
    if plantilla_nube is not None and not plantilla_nube.empty:
        st.session_state.efectivos = plantilla_nube
    else:
        guardar_plantilla(plantilla_oficial)
        st.session_state.efectivos = plantilla_oficial
        
if 'historial' not in st.session_state:
    memoria_guardada = cargar_memoria()
    if not memoria_guardada:
        memoria_guardada = {row["Nombre"]: date(2000, 1, 1) for _, row in st.session_state.efectivos.iterrows()}
        guardar_memoria(memoria_guardada)
    st.session_state.historial = memoria_guardada
    
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

# ==========================================
# 4. PANTALLA DE LOGIN RESTRINGIDO
# ==========================================
if not st.session_state.autenticado:
    st.markdown("""
        <div style="text-align: center; margin-top: 50px;">
            <h2>🛡️ ACCESO RESTRINGIDO</h2>
            <p style="color: gray;">Sistema de Gestión de Servicios</p>
        </div>
    """, unsafe_allow_html=True)
    
    if MODO_OFFLINE:
        st.caption("🟢 **MODO PENDRIVE ACTIVADO** (Cifrado Local)")
    else:
        st.caption("☁️ **MODO NUBE ACTIVADO** (Conexión Firebase)")
    
    with st.form("login_form"):
        usuario_input = st.text_input("👤 Usuario (Tu número de TIP):", placeholder="Ej: F10173Y").upper().strip()
        pwd_input = st.text_input("🔑 Contraseña:", type="password", autocomplete="current-password")
        submit_btn = st.form_submit_button("Desbloquear Sistema", type="primary")
        
        if submit_btn:
            # Solo tienen acceso de login los titulares de JEFE DE TURNO y RESGUARDO FISCAL (excluyendo eventuales como X10503B)
            df_autorizados = st.session_state.efectivos[
                st.session_state.efectivos['Categoria'].isin(['JEFE DE TURNO', 'RESGUARDO FISCAL'])
            ]
            tips_validos = [
                tip.upper() for tip in df_autorizados['TIP'].tolist()
                if tip.upper() not in ["XX", "", "XXXXXXXX", "X10503B"]
            ]
            
            if usuario_input == "ADMIN" and pwd_input == "Puerto2026*":
                st.session_state.autenticado = True
                st.session_state.usuario_actual = "ADMIN"
                st.rerun()
                
            elif usuario_input in tips_validos:
                pwd_hash = hashlib.sha256(pwd_input.encode()).hexdigest()
                creds = st.session_state.credenciales
                
                if usuario_input in creds:
                    if pwd_hash == creds[usuario_input]:
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = usuario_input
                        st.rerun()
                    else:
                        st.error("❌ Contraseña incorrecta.")
                else:
                    hash_por_defecto = hashlib.sha256("Puerto2026*".encode()).hexdigest()
                    if pwd_hash == hash_por_defecto:
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = usuario_input
                        st.rerun()
                    else:
                        st.error("❌ Primer acceso: Utiliza la contraseña inicial por defecto (Puerto2026*).")
            else:
                st.error("❌ El TIP introducido no consta en la base de datos o no tiene permisos de acceso.")
    
    st.stop()


# ==========================================
# 5. ÁREA PERSONAL Y BARRA LATERAL
# ==========================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.usuario_actual}")
    st.caption("Área Personal Guardia Civil")
    
    with st.expander("🔑 Cambiar mi contraseña"):
        with st.form("form_pass"):
            new_pass = st.text_input("Nueva contraseña:", type="password")
            new_pass2 = st.text_input("Repetir contraseña:", type="password")
            btn_cambiar = st.form_submit_button("Actualizar")
            
            if btn_cambiar:
                if len(new_pass) < 6:
                    st.error("Debe tener al menos 6 caracteres.")
                elif new_pass != new_pass2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    new_hash = hashlib.sha256(new_pass.encode()).hexdigest()
                    st.session_state.credenciales[st.session_state.usuario_actual] = new_hash
                    guardar_credenciales(st.session_state.credenciales)
                    st.success("✅ Contraseña actualizada.")
    
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
    st.info("💡 Edita los datos, añade componentes y pulsa 'Guardar Cambios' al final de la página para actualizar la Base
