import streamlit as st
import pandas as pd
from datetime import date, datetime
import firebase_admin
from firebase_admin import credentials, firestore
import matplotlib.pyplot as plt
import textwrap
import io

# ==========================================
# 1. CONFIGURACIÓN VISUAL Y UX (App-First)
# ==========================================
st.set_page_config(page_title="Gestor de Turnos GC", layout="centered", initial_sidebar_state="collapsed")

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

st.title("🛡️ Táctico GC")

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
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# ==========================================
# 3. INTERFAZ TIPO APP (Pestañas)
# ==========================================
tab_diario, tab_plantilla = st.tabs(["📋 Cuadrante Diario", "👥 Editar Plantilla"])

# ------------------------------------------
# PESTAÑA 2: CONFIGURACIÓN DE PLANTILLA
# ------------------------------------------
with tab_plantilla:
    st.info("💡 Usa esta tabla solo para añadir compañeros nuevos o editar errores en los TIPs. Los cambios se guardan para todos.")
    
    df_plantilla = st.session_state.efectivos.copy()
    
    plantilla_editada = st.data_editor(
        df_plantilla,
        column_config={
            "Orden": st.column_config.NumberColumn(required=True, width="small"),
            "TIP": st.column_config.TextColumn(required=True, width="small"),
            "Nombre": st.column_config.TextColumn(required=True)
        },
        hide_index=True, use_container_width=True, height=450, num_rows="dynamic"
    )

    if st.button("💾 Guardar Plantilla en la Nube"):
        nueva_plantilla = plantilla_editada.dropna(subset=["Nombre", "TIP"]).copy()
        nueva_plantilla["Orden"] = pd.to_numeric(nueva_plantilla["Orden"], errors='coerce').fillna(999).astype(int)
        nueva_plantilla = nueva_plantilla.sort_values("Orden").reset_index(drop=True)
        
        guardar_plantilla(nueva_plantilla)
        st.session_state.efectivos = nueva_plantilla
        
        for _, row in nueva_plantilla.iterrows():
            if row["Nombre"] not in st.session_state.historial:
                st.session_state.historial[row["Nombre"]] = date(2000, 1, 1)
        guardar_memoria(st.session_state.historial)
        
        st.success("✅ Plantilla sincronizada.")
        st.rerun()

# ------------------------------------------
# PESTAÑA 1: USO DIARIO
# ------------------------------------------
with tab_diario:
    col1, col2 = st.columns(2)
    fecha_servicio = col1.date_input("📅 Fecha", value=date.today())
    tipo_turno = col2.radio("⏱️ Turno", ["Mañana", "Noche"], horizontal=True)

    col3, col4 = st.columns(2)
    intervalo_horas = col3.selectbox("⏳ Rotación cada...", [2, 3, 4], format_func=lambda x: f"{x} Horas")
    
    if intervalo_horas == 2:
        def_puestos = "PUERTAS, POSTA, ROMA"
    elif intervalo_horas == 3:
        def_puestos = "PUERTAS, POSTA, POSTA, ROMA"
    else:
        def_puestos = "PUERTAS, POSTA, ROMA"
        
    puestos_input = col4.text_input("📍 Puestos", value=def_puestos)
    lista_puestos = [p.strip() for p in puestos_input.split(",") if p.strip()]

    st.write("### 👥 Componentes de Hoy")
    st.caption("Activa el interruptor de los que trabajan hoy y asigna su rol.")
    
    presentes_list = []
    efectivos_ordenados = st.session_state.efectivos.sort_values("Orden")
    
    for i, row in efectivos_ordenados.iterrows():
        with st.container(border=True):
            col_izq, col_der = st.columns([0.8, 0.2])
            with col_izq:
                st.markdown(f"**{row['Nombre']}**")
                st.caption(f"TIP: {row['TIP']} | Nº: {row['Orden']}")
            with col_der:
                asiste = st.toggle("Sí", key=f"tog_{i}", label_visibility="collapsed")
            
            if asiste:
                rol_elegido = st.selectbox(
                    "Selecciona su Rol:", 
                    ["🛡️ Operativo", "⭐ Jefe de Turno", "📝 Confronta"], 
                    key=f"rol_{i}"
                )
                presentes_list.append({
                    "Nombre": row["Nombre"], 
                    "TIP": row["TIP"], 
                    "Rol": rol_elegido, 
                    "Orden": row["Orden"]
                })

    presentes = pd.DataFrame(presentes_list) if presentes_list else pd.DataFrame()

    # ==========================================
    # 5. MOTOR MATEMÁTICO Y GENERADOR DE IMAGEN HD ANTISOLAPE
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

    def crear_imagen_tabla(df, titulo):
        df_img = df.copy()
        if 'Nombre' in df_img.columns:
            # Ancho de envoltura mayor (22) para que el nombre ocupe más espacio horizontal y evite solapes verticales
            df_img['Nombre'] = df_img['Nombre'].apply(lambda x: '\n'.join(textwrap.wrap(str(x), width=22)))

        # Lienzo amplio con altura proporcional generosa para evitar cualquier solapamiento
        fig, ax = plt.subplots(figsize=(14, 1.1 * len(df) + 2.5))
        ax.axis('off')
        ax.axis('tight')
        
        table = ax.table(cellText=df_img.values, colLabels=df.columns, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9.5)
        
        # Anchos de columna óptimos dando más protagonismo a la columna Nombre
        col_widths = [0.06, 0.13, 0.38, 0.13] + [0.10] * (len(df.columns) - 4)
        for col_idx, width in enumerate(col_widths):
            if col_idx < len(df.columns):
                table.get_celld()[(0, col_idx)].set_width(width)
                for r in range(1, len(df) + 1):
                    table.get_celld()[(r, col_idx)].set_width(width)
                    
        # Escala vertical holgada (3.2) para que las líneas multilínea respiren perfectamente
        table.scale(1, 3.2)
        
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor('#B0C4DE') 
            if row == 0:
                cell.set_facecolor('#006B4C') 
                cell.set_text_props(color='white', weight='bold', size=10)
            else:
                if df.iloc[row-1]['Nº'] == '-':
                    cell.set_facecolor('#E6F0EC') 
                    cell.set_text_props(weight='bold', size=9.5)
                else:
                    cell.set_facecolor('#FFFFFF' if row % 2 == 0 else '#F4F6F5')
                    cell.set_text_props(size=9.5)
        
        plt.title(titulo, fontweight="bold", fontsize=14, color="#006B4C", pad=20)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
        buf.seek(0)
        plt.close()
        return buf

    if not presentes.empty:
        operativos = presentes[presentes["Rol"] == "🛡️ Operativo"].copy()
        fijos = presentes[presentes["Rol"] != "🛡️ Operativo"].copy()
        num_ops = len(operativos)
        
        if num_ops > 0:
            st.write("### 🔢 Asignación de Puestos")
            st.caption("Propuesta automática basada en el historial de la nube. Puedes ajustar el número mediante el desplegable.")
            
            operativos["Ultimo_Maximo"] = operativos["Nombre"].map(st.session_state.historial).fillna(date(2000,1,1))
            operativos = operativos.sort_values(by=["Ultimo_Maximo", "Orden"], ascending=[True, True])
            operativos["Sugerido"] = range(num_ops, 0, -1)
            
            asignaciones_usuario = []
            numeros_disponibles = list(range(1, num_ops + 1))
            
            for idx, row in operativos.iterrows():
                with st.container(border=True):
                    col_n1, col_n2 = st.columns([0.6, 0.4])
                    with col_n1:
                        st.markdown(f"**{row['Nombre']}**")
                        st.caption(f"TIP: {row['TIP']}")
                    with col_n2:
                        default_idx = numeros_disponibles.index(row["Sugerido"]) if row["Sugerido"] in numeros_disponibles else 0
                        n_asignado = st.selectbox(
                            "Nº Asignado",
                            options=numeros_disponibles,
                            index=default_idx,
                            key=f"num_op_{row['TIP']}_{idx}"
                        )
                    asignaciones_usuario.append({
                        "Nombre": row["Nombre"],
                        "TIP": row["TIP"],
                        "Nº Asignado": n_asignado
                    })
            
            numeros_editados = pd.DataFrame(asignaciones_usuario)
            asignados_list = numeros_editados["Nº Asignado"].tolist()
            
            if len(set(asignados_list)) != num_ops:
                st.error("⚠️ ¡Atención! No puedes repetir el mismo número asignado entre distintos operativos.")
            else:
                if st.button("🚀 Confirmar Rotación y Generar", type="primary"):
                    nombre_max = numeros_editados[numeros_editados["Nº Asignado"] == num_ops].iloc[0]["Nombre"]
                    
                    st.session_state.historial[nombre_max] = fecha_servicio
                    guardar_memoria(st.session_state.historial)
                    
                    franjas_calculadas = calcular_franjas(tipo_turno, intervalo_horas)
                    titulo_cuadrante = f"CUADRANTE {fecha_servicio.strftime('%d/%m/%Y')} - {tipo_turno.upper()}"
                    texto = f"📋 *{titulo_cuadrante}*\n\n"
                    
                    for _, f in fijos.iterrows():
                        texto += f"🔹 *{f['Rol']}*: {f['Nombre']} ({f['TIP']})\n"
                    if not fijos.empty: texto += "\n"
                    
                    cuadrante_final = []
                    for _, f in fijos.iterrows():
                        fila_fija = {"Nº": "-", "TIP": f['TIP'], "Nombre": f['Nombre'], "Rol": f['Rol'].replace("🛡️ ", "").replace("⭐ ", "").replace("📝 ", "")}
                        for h in franjas_calculadas: fila_fija[h] = "-"
                        cuadrante_final.append(fila_fija)

                    for _, row in numeros_editados.sort_values("Nº Asignado").iterrows():
                        tip_op = operativos[operativos["Nombre"] == row["Nombre"]].iloc[0]["TIP"]
                        n_asignado = row['Nº Asignado']
                        
                        texto += f"🔸 *Nº {n_asignado} - {row['Nombre']}* ({tip_op})\n"
                        fila_op = {"Nº": str(n_asignado), "TIP": tip_op, "Nombre": row["Nombre"], "Rol": "OPERATIVO"}
                        
                        for idx, h in enumerate(franjas_calculadas):
                            puesto = lista_puestos[(n_asignado - 1 + idx) % len(lista_puestos)]
                            fila_op[h] = puesto
                            texto += f"  🕒 {h}: {puesto}\n"
                        
                        cuadrante_final.append(fila_op)
                        texto += "\n"
                    
                    df_final = pd.DataFrame(cuadrante_final)
                    
                    st.success(f"☁️ Guardado en Firebase. **{nombre_max}** pasa al final de la cola.")
                    
                    st.write("### 📸 Imagen para WhatsApp")
                    img_buffer = crear_imagen_tabla(df_final, titulo_cuadrante)
                    
                    st.download_button(
                        label="📥 DESCARGAR IMAGEN (PNG)",
                        data=img_buffer,
                        file_name=f"Cuadrante_{fecha_servicio}.png",
                        mime="image/png"
                    )
                        
                    st.write("### 📝 Texto para Novedades")
                    st.text_area("Copia el texto:", value=texto, height=200)
                    
        else:
            st.info("Selecciona al menos 1 Operativo para rotar los puestos.")
