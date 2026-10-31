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

    # 3. RESTO DE PLANTILLA DE LA UNIDAD (ORDEN ALFABÉTICO POR APELLIDOS)
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
        cambios_auto = False
        if "XXXXXXXX" in plantilla_nube["TIP"].values:
            plantilla_nube.loc[plantilla_nube["Nombre"].str.contains("JUÁREZ VERDUGO", na=False), "TIP"] = "X10503B"
            cambios_auto = True
        if "RESTO PLANTILLA" not in plantilla_nube["Categoria"].values:
            df_resto_oficial = plantilla_oficial[plantilla_oficial["Categoria"] == "RESTO PLANTILLA"]
            plantilla_nube = pd.concat([plantilla_nube, df_resto_oficial], ignore_index=True)
            cambios_auto = True
        if cambios_auto:
            guardar_plantilla(plantilla_nube)
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
    st.info("💡 Edita los datos, añade componentes y pulsa 'Guardar Cambios' al final de la página para actualizar la Base de Datos.")
    
    df_plantilla = st.session_state.efectivos.copy()
    
    with st.expander("➕ AÑADIR NUEVO COMPONENTE", expanded=False):
        col_c, col_o = st.columns(2)
        nueva_cat = col_c.radio("Categoría", ["JEFE DE TURNO", "RESGUARDO FISCAL", "RESTO PLANTILLA"])
        
        if nueva_cat == "RESTO PLANTILLA":
            col_o.caption("El resto de la plantilla se ordena alfabéticamente (sin nº de antigüedad).")
            nuevo_orden = 0
        else:
            max_orden_actual = df_plantilla[df_plantilla['Categoria'] == nueva_cat]['Orden'].max()
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
            st.success("✅ Plantilla actualizada permanentemente en la Base de Datos.")
            st.rerun()

    st.write("---")
    st.write("### 🛠️ Opciones Avanzadas de Reseteo")
    with st.expander("⚠️ Zona de Peligro (Cuidado)"):
        st.warning("Estos botones borrarán tus configuraciones actuales.")
        
        if st.button("🔄 Volver a la plantilla original de fábrica (Cargar toda la unidad y TIP de Iván)"):
            guardar_plantilla(plantilla_oficial)
            st.session_state.efectivos = plantilla_oficial
            for _, row in plantilla_oficial.iterrows():
                if row["Nombre"] not in st.session_state.historial:
                    st.session_state.historial[row["Nombre"]] = date(2000, 1, 1)
            guardar_memoria(st.session_state.historial)
            st.success("✅ Plantilla reseteada y actualizada con toda la unidad.")
            st.rerun()
            
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
    
    # Generador dinámico de puestos según el número de operadores seleccionados (Para evitar huecos vacíos)
    if num_ops > 0:
        if modo_vigilancia:
            if num_ops >= 3:
                num_postas = num_ops - 3
                def_puestos_list = ["PARRILLA", "PUERTAS"] + (["POSTA"] * num_postas) + ["ROMA"]
            else:
                def_puestos_list = ["PARRILLA", "PUERTAS", "ROMA"][:num_ops]
        else:
            if num_ops >= 2:
                num_postas = num_ops - 2
                def_puestos_list = ["PUERTAS"] + (["POSTA"] * num_postas) + ["ROMA"]
            else:
                def_puestos_list = ["PUERTAS", "ROMA"][:num_ops]
        def_puestos = ", ".join(def_puestos_list)
    else:
        def_puestos = ""
        
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
            franjas_img.append(f"{h_inicio:02d}/{h_fin:02d}")
            franjas_texto.append(f"{h_inicio:02d}:00 h a {h_fin:02d}:00 h")
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
                        puesto = lista_puestos[(n_asignado - 1 + idx) % len(lista_puestos)]
                        fila_op[h_img] = puesto
                    
                    cuadrante_final.append(fila_op)
                
                for _, row in numeros_editados.sort_values(["Es_Refuerzo", "Orden", "Nombre"], ascending=[True, True, True]).iterrows():
                    tip_op = row["TIP"]
                    n_asignado = row['Nº Asignado']
                    
                    texto += f"{row['Nombre']} ({tip_op})\n"
                    for idx, h_txt in enumerate(franjas_texto):
                        puesto = lista_puestos[(n_asignado - 1 + idx) % len(lista_puestos)]
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
