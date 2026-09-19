import streamlit as st
import pandas as pd
from datetime import date, datetime
import firebase_admin
from firebase_admin import credentials, firestore

# ==========================================
# 1. CONFIGURACIÓN VISUAL (Móvil-First)
# ==========================================
st.set_page_config(page_title="Gestor de Turnos GC", layout="centered")

st.markdown("""
    <style>
    [data-testid="stHeader"] { background-color: #006B4C; }
    .stButton>button { background-color: #EAB200; color: black; font-weight: bold; width: 100%; border-radius: 8px;}
    .stButton>button:hover { background-color: #CBA000; }
    .dataframe { font-size: 14px !important; text-align: center; }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Generador Táctico (Nube)")

# ==========================================
# 2. CONEXIÓN A FIREBASE Y SINCRONIZACIÓN
# ==========================================
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
            return pd.DataFrame(doc.to_dict()['efectivos'])
        return None

    def guardar_plantilla(df):
        DOC_PLANTILLA.set({'efectivos': df.to_dict('records')})

    if 'efectivos' not in st.session_state:
        plantilla_nube = cargar_plantilla()
        if plantilla_nube is not None and not plantilla_nube.empty:
            st.session_state.efectivos = plantilla_nube
        else:
            datos_base = pd.DataFrame([
                {"TIP": "XX", "Nombre": "FRANCISCO JOSÉ GARCÍA TEMBLADOR", "Orden": 1},
                {"TIP": "XX", "Nombre": "RAFAEL ORTÍZ GONZALEZ", "Orden": 2},
                {"TIP": "F10173Y", "Nombre": "ALBERTO FRANCISCO BERLANGA CRUZADO", "Orden": 3},
                {"TIP": "XXXX", "Nombre": "ANTONIO MARIANO RODRÍGUEZ MARTÍNEZ", "Orden": 4},
                {"TIP": "XXXXXX", "Nombre": "DAVID JOAQUÍN LÓPEZ ESPINAL", "Orden": 5},
                {"TIP": "XXXXXXX", "Nombre": "ALBERTO CONSTAN CRESPO", "Orden": 6},
                {"TIP": "XXXXXXXX", "Nombre": "DIEGO MANUEL TORRES KITTS", "Orden": 7},
                {"TIP": "XXXXXXXX", "Nombre": "CELIA DOMÍNGUEZ BARRANCO", "Orden": 8},
                {"TIP": "XXXXXXXX", "Nombre": "IVÁN JUÁREZ VERDUGO", "Orden": 9}
            ])
            guardar_plantilla(datos_base)
            st.session_state.efectivos = datos_base
            
    if 'historial' not in st.session_state:
        memoria_guardada = cargar_memoria()
        if not memoria_guardada:
            memoria_guardada = {row["Nombre"]: date(2000, 1, 1) for _, row in st.session_state.efectivos.iterrows()}
            guardar_memoria(memoria_guardada)
        st.session_state.historial = memoria_guardada

except Exception as e:
    st.error(f"❌ Error en la conexión a la base de datos: {e}")
    st.stop()

# ==========================================
# 3. INTERFAZ DE SELECCIÓN Y CONFIGURACIÓN
# ==========================================
col1, col2 = st.columns(2)
fecha_servicio = col1.date_input("📅 Fecha", value=date.today())
tipo_turno = col2.radio("⏱️ Turno", ["Mañana", "Noche"], horizontal=True)

col3, col4 = st.columns(2)
intervalo_horas = col3.selectbox("⏳ Rotación cada...", [2, 3, 4], format_func=lambda x: f"{x} Horas")
puestos_input = col4.text_input("📍 Puestos a rotar (comas)", "PUERTAS, POSTA, ROMA")
lista_puestos = [p.strip() for p in puestos_input.split(",") if p.strip()]

# ==========================================
# 4. TABLA INTERACTIVA DE COMPONENTES
# ==========================================
st.subheader("👥 1. Componentes y Roles")
st.info("Haz doble clic en cualquier TIP, Nombre u Orden para modificarlo. Usa la última fila vacía para añadir compañeros. Guarda los cambios para que se reflejen a todos.")

df_ui = st.session_state.efectivos.copy()
df_ui["Asiste"] = False
# Emojis integrados para que nunca fallen en los desplegables de móviles
df_ui["Rol"] = "🛡️ Operativo" 

def color_rol(val):
    if val == '⭐ Jefe de Turno':
        return 'background-color: #FFB3B3; color: black; font-weight: bold;'
    elif val == '📝 Confronta':
        return 'background-color: #B3D9FF; color: black; font-weight: bold;'
    return ''

styled_df = df_ui.style.map(color_rol, subset=['Rol'])

edited_df = st.data_editor(
    styled_df,
    column_config={
        "Asiste": st.column_config.CheckboxColumn(required=True, width="small"),
        "Rol": st.column_config.SelectboxColumn(options=["🛡️ Operativo", "⭐ Jefe de Turno", "📝 Confronta"], required=True, width="medium"),
        "Orden": st.column_config.NumberColumn(required=True, width="small"),
        "TIP": st.column_config.TextColumn(required=True, width="small"),
        "Nombre": st.column_config.TextColumn(required=True)
    },
    hide_index=True, use_container_width=True, height=380, num_rows="dynamic"
)

if st.button("💾 Guardar cambios en la plantilla base (Nube)"):
    nueva_plantilla = edited_df[["TIP", "Nombre", "Orden"]].dropna(subset=["Nombre", "TIP"]).copy()
    nueva_plantilla["Orden"] = pd.to_numeric(nueva_plantilla["Orden"], errors='coerce').fillna(999).astype(int)
    nueva_plantilla = nueva_plantilla.sort_values("Orden").reset_index(drop=True)
    
    guardar_plantilla(nueva_plantilla)
    st.session_state.efectivos = nueva_plantilla
    
    for _, row in nueva_plantilla.iterrows():
        if row["Nombre"] not in st.session_state.historial:
            st.session_state.historial[row["Nombre"]] = date(2000, 1, 1)
    guardar_memoria(st.session_state.historial)
    
    st.success("✅ Plantilla actualizada en la nube. Los cambios ya son visibles para todos.")
    st.rerun()

presentes = edited_df[edited_df["Asiste"]].copy()

# ==========================================
# 5. MOTOR MATEMÁTICO (FRANJAS Y ROTACIÓN)
# ==========================================
def calcular_franjas(turno, intervalo):
    start = 7 if turno == "Mañana" else 19
    slots = int(12 / intervalo)
    franjas = []
    for i in range(slots):
        h_inicio = (start + (i * intervalo)) % 24
        h_fin = (start + ((i + 1) * intervalo)) % 24
        franjas.append(f"{h_inicio:02d}/{h_fin:02d}")
    return franjas

if not presentes.empty:
    operativos = presentes[presentes["Rol"] == "🛡️ Operativo"].copy()
    fijos = presentes[presentes["Rol"] != "🛡️ Operativo"].copy()
    num_ops = len(operativos)
    
    if num_ops > 0:
        st.subheader("🔢 2. Asignación (Automática / Editable)")
        operativos["Ultimo_Maximo"] = operativos["Nombre"].map(st.session_state.historial).fillna(date(2000,1,1))
        operativos = operativos.sort_values(by=["Ultimo_Maximo", "Orden"], ascending=[True, True])
        operativos["Nº Asignado"] = range(num_ops, 0, -1)
        
        numeros_editados = st.data_editor(
            operativos[["Nombre", "Nº Asignado"]].sort_values("Nº Asignado", ascending=False),
            hide_index=True, use_container_width=True
        )
        
        asignados_list = numeros_editados["Nº Asignado"].tolist()
        if len(set(asignados_list)) != num_ops or any(n < 1 or n > num_ops for n in asignados_list):
            st.error(f"¡Error! Los números deben ir del 1 al {num_ops} sin repetirse.")
        else:
            if st.button("🚀 Confirmar Rotación y Generar Puestos"):
                nombre_max = numeros_editados[numeros_editados["Nº Asignado"] == num_ops].iloc[0]["Nombre"]
                
                st.session_state.historial[nombre_max] = fecha_servicio
                guardar_memoria(st.session_state.historial)
                
                franjas_calculadas = calcular_franjas(tipo_turno, intervalo_horas)
                texto = f"📋 *CUADRANTE {fecha_servicio.strftime('%d/%m/%Y')} - {tipo_turno.upper()}*\n\n"
                
                for _, f in fijos.iterrows():
                    texto += f"🔹 *{f['Rol']}*: {f['Nombre']} ({f['TIP']})\n"
                if not fijos.empty: texto += "\n"
                
                cuadrante_final = []
                for _, f in fijos.iterrows():
                    cuadrante_final.append({"Nº": "-", "TIP": f['TIP'], "Nombre": f['Nombre'], "Rol": f['Rol']})

                for _, row in numeros_editados.sort_values("Nº Asignado").iterrows():
                    tip_op = operativos[operativos["Nombre"] == row["Nombre"]].iloc[0]["TIP"]
                    n_asignado = row['Nº Asignado']
                    
                    texto += f"🔸 *Nº {n_asignado} - {row['Nombre']}* ({tip_op})\n"
                    
                    fila_op = {"Nº": n_asignado, "TIP": tip_op, "Nombre": row["Nombre"], "Rol": "OPERATIVO"}
                    
                    for idx, h in enumerate(franjas_calculadas):
                        puesto = lista_puestos[(n_asignado - 1 + idx) % len(lista_puestos)]
                        fila_op[h] = puesto
                        texto += f"  🕒 {h}: {puesto}\n"
                    
                    cuadrante_final.append(fila_op)
                    texto += "\n"
                
                st.subheader("✏️ Visualización Rápida")
                df_final = pd.DataFrame(cuadrante_final)
                st.dataframe(df_final, hide_index=True)

                st.subheader("📱 Texto para Novedades (WhatsApp)")
                st.text_area("Copia el texto (con formato negritas):", value=texto, height=350)
                st.success(f"☁️ Rotación guardada en Firebase. **{nombre_max}** pasa al final de la cola.")
    else:
        st.info("Debe haber al menos 1 Operativo seleccionado para generar la rotación.")
else:
    st.info("Selecciona los guardias que asisten hoy marcando la casilla 'Asiste'.")