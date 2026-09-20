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

st.title("🛡️ Turnos Servicios Puerto")

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
            # NUEVA PLANTILLA BASE ORDENADA
            datos_base = pd.DataFrame([
                {"TIP": "XX", "Nombre": "SARGENTO 1º GÁLVEZ", "Orden": 1},
                {"TIP": "XX", "Nombre": "SARGENTO HUTCHINSON", "Orden": 2},
                {"TIP": "XX", "Nombre": "CABO DAVID", "Orden": 3},
                {"TIP": "XX", "Nombre": "CABO SALVADOR", "Orden": 4},
                {"TIP": "Y14399C", "Nombre": "CABO ANSELMO", "Orden": 5},
                {"TIP": "XX", "Nombre": "CABO MIGUEL", "Orden": 6},
                {"TIP": "XX", "Nombre": "GUARDIA 1º DUARTE", "Orden": 7},
                {"TIP": "XX", "Nombre": "GUARDIA PEDRO", "Orden": 8},
                {"TIP": "S49454H", "Nombre": "FRANCISCO JOSÉ GARCÍA TEMBLADOR", "Orden": 9},
                {"TIP": "C65480C", "Nombre": "RAFAEL ORTÍZ GONZALEZ", "Orden": 10},
                {"TIP": "F10173Y", "Nombre": "ALBERTO FRANCISCO BERLANGA CRUZADO", "Orden": 11},
                {"TIP": "W92718I", "Nombre": "ANTONIO MARIANO RODRÍGUEZ MARTÍNEZ", "Orden": 12},
                {"TIP": "U09338T", "Nombre": "DAVID JOAQUÍN LÓPEZ ESPINAL", "Orden": 13},
                {"TIP": "Z19006G", "Nombre": "ALBERTO CONSTAN CRESPO", "Orden": 14},
                {"TIP": "V49093U", "Nombre": "DIEGO MANUEL TORRES KITTS", "Orden": 15},
                {"TIP": "N23723F", "Nombre": "CELIA DOMÍNGUEZ BARRANCO", "Orden": 16},
                {"TIP": "XXXXXXXX", "Nombre": "IVÁN JUÁREZ VERDUGO", "Orden": 17}
            ])
            guardar_plantilla(datos_base)
            st.session_state.efectivos = datos_base
            
    if 'historial' not in st.session_state:
        memoria_guardada = cargar_memoria()
        if not memoria_guardada:
            memoria_guardada = {row["Nombre"]: date(2000, 1, 1) for _, row in st.session_state.efectivos.iterrows()}
            guardar_memoria(memoria_guardada)
        st.session_state.historial = memoria_guardada
        
    # Inicializar variables de estado para mantener resultados en pantalla
    if 'cuadrante_generado' not in st.session_state:
        st.session_state.cuadrante_generado = False
        st.session_state.img_buffer = None
        st.session_state.texto_novedades = ""
        st.session_state.fecha_generada = None

except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# ==========================================
# 3. INTERFAZ TIPO APP (Pestañas)
# ==========================================
tab_diario, tab_plantilla = st.tabs(["📋 Cuadrante Diario", "👥 Editar Plantilla"])

# ------------------------------------------
# PESTAÑA 2: CONFIGURACIÓN DE PLANTILLA (Móvil)
# ------------------------------------------
with tab_plantilla:
    st.info("💡 Edita los datos de los compañeros o añade nuevos. Los cambios se sincronizarán para todos.")
    
    df_plantilla = st.session_state.efectivos.copy()
    
    # 1. Añadir Nuevo Componente
    with st.expander("➕ AÑADIR NUEVO COMPONENTE", expanded=False):
        col_n1, col_n2 = st.columns(2)
        nuevo_nombre = col_n1.text_input("Nombre Completo (Nuevo)")
        nuevo_tip = col_n2.text_input("TIP (Nuevo)")
        nuevo_orden = st.number_input("Número de Antigüedad (Orden)", min_value=1, value=len(df_plantilla)+1)
        
        if st.button("Añadir a la lista"):
            if nuevo_nombre and nuevo_tip:
                nuevo_registro = pd.DataFrame([{"TIP": nuevo_tip, "Nombre": nuevo_nombre.upper(), "Orden": int(nuevo_orden)}])
                df_plantilla = pd.concat([df_plantilla, nuevo_registro], ignore_index=True)
                st.session_state.efectivos = df_plantilla
                st.success("Añadido temporalmente. Pulsa 'Guardar Cambios en la Nube' abajo para confirmar.")
                st.rerun()

    st.write("---")
    st.write("### 👥 Plantilla Actual")
    
    # 2. Edición táctil mediante tarjetas en lugar de tabla
    df_plantilla = df_plantilla.sort_values("Orden").reset_index(drop=True)
    editados = []
    
    for i, row in df_plantilla.iterrows():
        with st.expander(f"{row['Orden']} - {row['Nombre']} ({row['TIP']})"):
            c1, c2, c3 = st.columns([1, 2, 1])
            e_orden = c1.number_input("Orden", value=int(row['Orden']), key=f"ord_{i}")
            e_nombre = c2.text_input("Nombre", value=row['Nombre'], key=f"nom_{i}")
            e_tip = c3.text_input("TIP", value=row['TIP'], key=f"tip_{i}")
            
            eliminar = st.checkbox("Eliminar compañero", key=f"del_{i}")
            if not eliminar:
                editados.append({"TIP": e_tip.upper(), "Nombre": e_nombre.upper(), "Orden": int(e_orden)})

    if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary"):
        nueva_plantilla = pd.DataFrame(editados)
        if not nueva_plantilla.empty:
            nueva_plantilla = nueva_plantilla.sort_values("Orden").reset_index(drop=True)
            guardar_plantilla(nueva_plantilla)
            st.session_state.efectivos = nueva_plantilla
            
            for _, row in nueva_plantilla.iterrows():
                if row["Nombre"] not in st.session_state.historial:
                    st.session_state.historial[row["Nombre"]] = date(2000, 1, 1)
            guardar_memoria(st.session_state.historial)
            st.success("✅ Plantilla sincronizada correctamente.")
            st.rerun()

# ------------------------------------------
# PESTAÑA 1: USO DIARIO
# ------------------------------------------
with tab_diario:
    col1, col2 = st.columns(2)
    fecha_servicio = col1.date_input("📅 Fecha", value=date.today())
    tipo_turno = col2.radio("⏱️ Turno", ["Mañana", "Noche"], horizontal=True)

    st.write("### 👥 Componentes de Hoy")
    
    efectivos_ordenados = st.session_state.efectivos.sort_values("Orden")
    nombres_lista = efectivos_ordenados["Nombre"].tolist()
    
    # Desplegables múltiples para Mandos
    jefes_seleccionados = st.multiselect("⭐ Jefes de Turno (Desplegable)", options=nombres_lista)
    
    opciones_confronta = [n for n in nombres_lista if n not in jefes_seleccionados]
    confrontas_seleccionados = st.multiselect("📝 Confronta (Desplegable)", options=opciones_confronta)
    
    # Interruptores para Operativos (excluyendo a los mandos ya elegidos)
    st.write("🛡️ **Operativos** (Activa los que trabajan)")
    ops_seleccionados = []
    
    for i, row in efectivos_ordenados.iterrows():
        if row['Nombre'] not in jefes_seleccionados and row['Nombre'] not in confrontas_seleccionados:
            with st.container(border=True):
                col_izq, col_der = st.columns([0.8, 0.2])
                with col_izq:
                    st.markdown(f"**{row['Nombre']}**")
                    st.caption(f"TIP: {row['TIP']} | Nº Antigüedad: {row['Orden']}")
                with col_der:
                    if st.toggle("Sí", key=f"tog_{i}", label_visibility="collapsed"):
                        ops_seleccionados.append(row)

    # Lógica Inteligente de Rotación
    num_ops = len(ops_seleccionados)
    num_jefes = len(jefes_seleccionados)
    
    # Por defecto 3 horas (índice 1), pero si hay 3 ops y >=1 jefe, 2 horas (índice 0)
    indice_defecto = 1 
    if num_ops == 3 and num_jefes >= 1:
        indice_defecto = 0

    col3, col4 = st.columns(2)
    intervalo_horas = col3.selectbox("⏳ Rotación cada...", [2, 3, 4], index=indice_defecto, format_func=lambda x: f"{x} Horas")
    
    if intervalo_horas == 2:
        def_puestos = "PUERTAS, POSTA, ROMA"
    elif intervalo_horas == 3:
        def_puestos = "PUERTAS, POSTA, POSTA, ROMA"
    else:
        def_puestos = "PUERTAS, POSTA, ROMA"
        
    puestos_input = col4.text_input("📍 Puestos", value=def_puestos)
    lista_puestos = [p.strip() for p in puestos_input.split(",") if p.strip()]

    # ==========================================
    # 5. MOTOR MATEMÁTICO Y GENERADOR
    # ==========================================
    def calcular_franjas(turno, intervalo):
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

        fig, ax = plt.subplots(figsize=(14, 1.1 * len(df) + 2.5))
        ax.axis('off')
        ax.axis('tight')
        
        table = ax.table(cellText=df_img.values, colLabels=df.columns, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9.5)
        
        col_widths = [0.06, 0.13, 0.38, 0.13] + [0.10] * (len(df.columns) - 4)
        for col_idx, width in enumerate(col_widths):
            if col_idx < len(df.columns):
                table.get_celld()[(0, col_idx)].set_width(width)
                for r in range(1, len(df) + 1):
                    table.get_celld()[(r, col_idx)].set_width(width)
                    
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

    if num_ops > 0 or num_jefes > 0 or len(confrontas_seleccionados) > 0:
        if num_ops > 0:
            st.write("### 🔢 Asignación de Puestos")
            st.caption("Asignación justa automática (El más antiguo que lleve más tiempo sin el número alto).")
            
            df_ops = pd.DataFrame(ops_seleccionados)
            df_ops["Ultimo_Maximo"] = df_ops["Nombre"].map(st.session_state.historial).fillna(date(2000,1,1))
            
            # Orden estricto: Primero por fecha más antigua, en caso de empate por Orden más bajo (más antiguo)
            df_ops = df_ops.sort_values(by=["Ultimo_Maximo", "Orden"], ascending=[True, True])
            
            # Asignación segura del 1 al Num_ops
            df_ops["Sugerido"] = range(num_ops, 0, -1)
            
            asignaciones_usuario = []
            numeros_disponibles = list(range(1, num_ops + 1))
            
            for idx, row in df_ops.iterrows():
                with st.container(border=True):
                    col_n1, col_n2 = st.columns([0.6, 0.4])
                    with col_n1:
                        st.markdown(f"**{row['Nombre']}**")
                    with col_n2:
                        default_idx = numeros_disponibles.index(row["Sugerido"])
                        n_asignado = st.selectbox(
                            "Nº Asignado",
                            options=numeros_disponibles,
                            index=default_idx,
                            key=f"num_op_{row['TIP']}"
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
                boton_generar = False
            else:
                boton_generar = st.button("🚀 Confirmar Rotación y Generar", type="primary")
                
            if boton_generar:
                nombre_max = numeros_editados[numeros_editados["Nº Asignado"] == num_ops].iloc[0]["Nombre"]
                
                st.session_state.historial[nombre_max] = fecha_servicio
                guardar_memoria(st.session_state.historial)
                
                franjas_img, franjas_texto = calcular_franjas(tipo_turno, intervalo_horas)
                titulo_cuadrante = f"CUADRANTE {fecha_servicio.strftime('%d/%m/%Y')} - {tipo_turno.upper()}"
                
                # Generación de Texto Plano (Sin asteriscos)
                texto = f"{titulo_cuadrante}\n\n"
                
                cuadrante_final = []
                
                # Procesar Jefes
                for nombre_jefe in jefes_seleccionados:
                    tip_jefe = efectivos_ordenados[efectivos_ordenados["Nombre"] == nombre_jefe].iloc[0]["TIP"]
                    texto += f"JEFE DE TURNO: {nombre_jefe} ({tip_jefe})\n"
                    fila_fija = {"Nº": "-", "TIP": tip_jefe, "Nombre": nombre_jefe, "Rol": "Jefe de Turno"}
                    for h in franjas_img: fila_fija[h] = "-"
                    cuadrante_final.append(fila_fija)
                    
                # Procesar Confrontas
                for nombre_conf in confrontas_seleccionados:
                    tip_conf = efectivos_ordenados[efectivos_ordenados["Nombre"] == nombre_conf].iloc[0]["TIP"]
                    texto += f"CONFRONTA: {nombre_conf} ({tip_conf})\n"
                    fila_fija = {"Nº": "-", "TIP": tip_conf, "Nombre": nombre_conf, "Rol": "Confronta"}
                    for h in franjas_img: fila_fija[h] = "-"
                    cuadrante_final.append(fila_fija)
                
                if jefes_seleccionados or confrontas_seleccionados:
                    texto += "\n"
                
                # Procesar Operativos
                for _, row in numeros_editados.sort_values("Nº Asignado").iterrows():
                    tip_op = row["TIP"]
                    n_asignado = row['Nº Asignado']
                    
                    texto += f"{row['Nombre']} ({tip_op})\n"
                    fila_op = {"Nº": str(n_asignado), "TIP": tip_op, "Nombre": row["Nombre"], "Rol": "OPERATIVO"}
                    
                    for idx, (h_img, h_txt) in enumerate(zip(franjas_img, franjas_texto)):
                        puesto = lista_puestos[(n_asignado - 1 + idx) % len(lista_puestos)]
                        fila_op[h_img] = puesto
                        texto += f"{h_txt}: {puesto}\n"
                    
                    cuadrante_final.append(fila_op)
                    texto += "\n"
                
                df_final = pd.DataFrame(cuadrante_final)
                img_buffer = crear_imagen_tabla(df_final, titulo_cuadrante)
                
                # Guardar en memoria para que no se borre
                st.session_state.cuadrante_generado = True
                st.session_state.img_buffer = img_buffer
                st.session_state.texto_novedades = texto
                st.session_state.fecha_generada = fecha_servicio.strftime('%d_%m_%Y')
                
                st.success(f"☁️ Guardado en Firebase. {nombre_max} pasa al final de la cola.")

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
        st.info("Selecciona compañeros arriba para generar el cuadrante.")
