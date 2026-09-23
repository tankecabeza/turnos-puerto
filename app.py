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

# ==========================================
# 1. CONFIGURACIÓN VISUAL Y UX
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
# 2. SISTEMA HÍBRIDO (NUBE / PENDRIVE LOCAL)
# ==========================================
MODO_OFFLINE = platform.system() == "Windows"

if MODO_OFFLINE:
    st.caption("🟢 **MODO PENDRIVE ACTIVADO** (Sin conexión a la nube para evitar el cortafuegos)")
    MEMORIA_FILE = "memoria_local.json"
    PLANTILLA_FILE = "plantilla_local.json"

    def cargar_memoria():
        if os.path.exists(MEMORIA_FILE):
            try:
                with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {k: datetime.strptime(v, "%Y-%m-%d").date() for k, v in data.items()}
            except: return {}
        return {}

    def guardar_memoria(data):
        with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
            json.dump({k: v.strftime("%Y-%m-%d") for k, v in data.items()}, f, ensure_ascii=False, indent=4)

    def cargar_plantilla():
        if os.path.exists(PLANTILLA_FILE):
            try:
                with open(PLANTILLA_FILE, "r", encoding="utf-8") as f:
                    return pd.DataFrame(json.load(f))
            except: return None
        return None

    def guardar_plantilla(df):
        with open(PLANTILLA_FILE, "w", encoding="utf-8") as f:
            json.dump(df.to_dict('records'), f, ensure_ascii=False, indent=4)

else:
    st.caption("☁️ **MODO NUBE ACTIVADO** (Conectado a Firebase)")
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
                df = pd.DataFrame(doc.to_dict()['efectivos'])
                if 'Categoria' not in df.columns:
                    df['Categoria'] = 'RESGUARDO FISCAL'
                return df
            return None

        def guardar_plantilla(df):
            DOC_PLANTILLA.set({'efectivos': df.to_dict('records')})
    except Exception as e:
        st.error(f"❌ Error de conexión a la nube: {e}")
        st.stop()

# ==========================================
# CARGA INICIAL DE DATOS
# ==========================================
plantilla_oficial = pd.DataFrame([
    # JEFES DE TURNO
    {"Categoria": "JEFE DE TURNO", "TIP": "XX", "Nombre": "SARGENTO 1º GÁLVEZ", "Orden": 1},
    {"Categoria": "JEFE DE TURNO", "TIP": "XX", "Nombre": "SARGENTO HUTCHINSON", "Orden": 2},
    {"Categoria": "JEFE DE TURNO", "TIP": "XX", "Nombre": "CABO DAVID", "Orden": 3},
    {"Categoria": "JEFE DE TURNO", "TIP": "XX", "Nombre": "CABO SALVADOR", "Orden": 4},
    {"Categoria": "JEFE DE TURNO", "TIP": "Y14399C", "Nombre": "CABO ANSELMO", "Orden": 5},
    {"Categoria": "JEFE DE TURNO", "TIP": "XX", "Nombre": "CABO MIGUEL", "Orden": 6},
    {"Categoria": "JEFE DE TURNO", "TIP": "XX", "Nombre": "GUARDIA 1º DUARTE", "Orden": 7},
    {"Categoria": "JEFE DE TURNO", "TIP": "XX", "Nombre": "GUARDIA PEDRO", "Orden": 8},
    # RESGUARDO FISCAL
    {"Categoria": "RESGUARDO FISCAL", "TIP": "S49454H", "Nombre": "FRANCISCO JOSÉ GARCÍA TEMBLADOR", "Orden": 1},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "C65480C", "Nombre": "RAFAEL ORTÍZ GONZALEZ", "Orden": 2},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "F10173Y", "Nombre": "ALBERTO FRANCISCO BERLANGA CRUZADO", "Orden": 3},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "W92718I", "Nombre": "ANTONIO MARIANO RODRÍGUEZ MARTÍNEZ", "Orden": 4},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "U09338T", "Nombre": "DAVID JOAQUÍN LÓPEZ ESPINAL", "Orden": 5},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "Z19006G", "Nombre": "ALBERTO CONSTAN CRESPO", "Orden": 6},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "V49093U", "Nombre": "DIEGO MANUEL TORRES KITTS", "Orden": 7},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "N23723F", "Nombre": "CELIA DOMÍNGUEZ BARRANCO", "Orden": 8},
    {"Categoria": "RESGUARDO FISCAL", "TIP": "XXXXXXXX", "Nombre": "IVÁN JUÁREZ VERDUGO", "Orden": 9}
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
    
if 'cuadrante_generado' not in st.session_state:
    st.session_state.cuadrante_generado = False
    st.session_state.img_buffer = None
    st.session_state.texto_novedades = ""
    st.session_state.fecha_generada = None

# ==========================================
# 3. INTERFAZ TIPO APP (Pestañas)
# ==========================================
tab_diario, tab_plantilla = st.tabs(["📋 Cuadrante Diario", "👥 Editar Plantilla"])

# ------------------------------------------
# PESTAÑA 2: CONFIGURACIÓN DE PLANTILLA
# ------------------------------------------
with tab_plantilla:
    st.info("💡 Edita los datos, añade nuevos componentes o restaura la lista oficial.")
    
    if st.button("🔄 Restaurar Plantilla Oficial (Sobrescribir)"):
        guardar_plantilla(plantilla_oficial)
        st.session_state.efectivos = plantilla_oficial
        for _, row in plantilla_oficial.iterrows():
            if row["Nombre"] not in st.session_state.historial:
                st.session_state.historial[row["Nombre"]] = date(2000, 1, 1)
        guardar_memoria(st.session_state.historial)
        st.success("✅ Plantilla oficial restaurada con éxito.")
        st.rerun()
    
    df_plantilla = st.session_state.efectivos.copy()
    
    with st.expander("➕ AÑADIR NUEVO COMPONENTE", expanded=False):
        col_c, col_o = st.columns(2)
        nueva_cat = col_c.radio("Categoría", ["JEFE DE TURNO", "RESGUARDO FISCAL"])
        
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

    def renderizar_tarjetas(df_sub, titulo):
        st.markdown(f"#### {titulo}")
        df_sub = df_sub.sort_values("Orden").reset_index(drop=True)
        for _, row in df_sub.iterrows():
            clave_unica = f"{row['Nombre']}_{row['TIP']}"
            with st.expander(f"{row['Orden']} - {row['Nombre']} ({row['TIP']})"):
                c1, c2, c3 = st.columns([1, 2, 1])
                e_orden = c1.number_input("Orden", value=int(row['Orden']), key=f"ord_{clave_unica}")
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

    renderizar_tarjetas(df_plantilla[df_plantilla['Categoria'] == 'JEFE DE TURNO'], "⭐ Jefes de Turno")
    renderizar_tarjetas(df_plantilla[df_plantilla['Categoria'] == 'RESGUARDO FISCAL'], "🛡️ Turno Fijo Guardia (Resguardo Fiscal)")

    if st.button("💾 GUARDAR CAMBIOS", type="primary"):
        nueva_plantilla = pd.DataFrame(editados)
        if not nueva_plantilla.empty:
            guardar_plantilla(nueva_plantilla)
            st.session_state.efectivos = nueva_plantilla
            
            for _, row in nueva_plantilla.iterrows():
                if row["Nombre"] not in st.session_state.historial:
                    st.session_state.historial[row["Nombre"]] = date(2000, 1, 1)
            guardar_memoria(st.session_state.historial)
            st.success("✅ Plantilla guardada correctamente.")
            st.rerun()

    st.write("---")
    st.write("### 🛠️ Opciones Avanzadas")
    if st.button("🗑️ Resetear historial de rotaciones", key="reset_plantilla"):
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
    efectivos_global['Cat_Num'] = efectivos_global['Categoria'].map({'JEFE DE TURNO': 1, 'RESGUARDO FISCAL': 2})
    efectivos_global = efectivos_global.sort_values(['Cat_Num', 'Orden'])
    nombres_lista_global = efectivos_global["Nombre"].tolist()
    
    # -------------------------------------------------------------
    # NUEVOS DESPLEGABLES DE SELECCIÓN ÚNICA (Se cierran al elegir)
    # -------------------------------------------------------------
    opciones_jefe = ["(Ninguno)"] + nombres_lista_global
    jefe_seleccionado = st.selectbox("⭐ Jefe de Turno", options=opciones_jefe)
    jefes_seleccionados = [jefe_seleccionado] if jefe_seleccionado != "(Ninguno)" else []
    
    opciones_confronta = ["(Ninguno)"] + [n for n in nombres_lista_global if n not in jefes_seleccionados]
    confronta_seleccionado = st.selectbox("📝 Confronta", options=opciones_confronta)
    confrontas_seleccionados = [confronta_seleccionado] if confronta_seleccionado != "(Ninguno)" else []
    
    st.write("---")
    st.write("🛡️ **Resguardo Fiscal** (Activa los componentes en rotación)")
    ops_seleccionados = []
    
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
                        ops_seleccionados.append(row)

    num_ops = len(ops_seleccionados)
    num_jefes = len(jefes_seleccionados)
    
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

        fig, ax = plt.subplots(figsize=(11.5, 1.1 * len(df) + 2.5))
        ax.axis('off')
        ax.axis('tight')
        
        table = ax.table(cellText=df_img.values, colLabels=df.columns, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9.5)
        
        col_widths = [0.05, 0.12, 0.26, 0.21] + [0.10] * (len(df.columns) - 4)
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
                    cell.set_text_props(size=9.5)
                else:
                    cell.set_facecolor('#FFFFFF' if row % 2 == 0 else '#F4F6F5')
                    cell.set_text_props(size=9.5)
                
                if df.columns[col] == 'Rol':
                    cell.set_text_props(weight='bold')
        
        plt.title(titulo, fontweight="bold", fontsize=15, color="#006B4C", pad=20)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
        buf.seek(0)
        plt.close()
        return buf

    if num_ops > 0 or num_jefes > 0 or len(confrontas_seleccionados) > 0:
        if num_ops > 0:
            st.write("### 🔢 Asignación de Puestos")
            st.caption("Regla de Antigüedad: El más antiguo tiene el número más alto, salvo si lo tuvo la última vez que trabajó.")
            
            df_ops = pd.DataFrame(ops_seleccionados)
            df_ops["Ultimo_Maximo"] = df_ops["Nombre"].map(st.session_state.historial).fillna(date(2000,1,1))
            
            max_fecha = df_ops["Ultimo_Maximo"].max()
            df_ops["Orden_Calculo"] = df_ops["Orden"]
            
            if max_fecha > date(2000, 1, 1):
                penalizados = df_ops[df_ops["Ultimo_Maximo"] == max_fecha]
                if not penalizados.empty:
                    idx_penalizado = penalizados.index[0]
                    df_ops.loc[idx_penalizado, "Orden_Calculo"] = 999999
            
            df_ops = df_ops.sort_values(by="Orden_Calculo", ascending=True)
            df_ops["Sugerido"] = range(num_ops, 0, -1)
            
            asignaciones_usuario = []
            numeros_disponibles = list(range(1, num_ops + 1))
            
            for _, row in df_ops.iterrows():
                with st.container(border=True):
                    col_n1, col_n2 = st.columns([0.6, 0.4])
                    with col_n1:
                        st.markdown(f"**{row['Nombre']}**")
                        
                        fecha_str = "Sin registro" if row["Ultimo_Maximo"] == date(2000, 1, 1) else row["Ultimo_Maximo"].strftime('%d/%m/%Y')
                        st.caption(f"Nº Antigüedad: {row['Orden']} | Último Nº Alto: {fecha_str}")
                        
                        if row["Orden_Calculo"] == 999999:
                            st.markdown("⚠️ <span style='color:#D32F2F; font-size:0.9em;'>Pasa al Nº 1 (Tuvo el último alto)</span>", unsafe_allow_html=True)

                    with col_n2:
                        default_idx = numeros_disponibles.index(row["Sugerido"])
                        
                        clave_unica = f"turno_limpio_{row['TIP']}_{num_ops}_{fecha_servicio}"
                        
                        n_asignado = st.selectbox(
                            "Nº Asignado",
                            options=numeros_disponibles,
                            index=default_idx,
                            key=clave_unica
                        )
                    asignaciones_usuario.append({
                        "Nombre": row["Nombre"],
                        "TIP": row["TIP"],
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
                nombre_max = numeros_editados[numeros_editados["Nº Asignado"] == num_ops].iloc[0]["Nombre"]
                
                st.session_state.historial[nombre_max] = fecha_servicio
                guardar_memoria(st.session_state.historial)
                
                franjas_img, franjas_texto = calcular_franjas(tipo_turno, intervalo_horas)
                titulo_cuadrante = f"CUADRANTE {fecha_servicio.strftime('%d/%m/%Y')} - {tipo_turno.upper()}"
                
                texto = f"{titulo_cuadrante}\n\n"
                cuadrante_final = []
                
                for nombre_jefe in jefes_seleccionados:
                    tip_jefe = efectivos_global[efectivos_global["Nombre"] == nombre_jefe].iloc[0]["TIP"]
                    texto += f"JEFE DE TURNO: {nombre_jefe} ({tip_jefe})\n"
                    fila_fija = {"Nº": "-", "TIP": tip_jefe, "Nombre": nombre_jefe, "Rol": "JEFE DE TURNO"}
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
                
                for _, row in numeros_editados.sort_values("Nº Asignado").iterrows():
                    tip_op = row["TIP"]
                    n_asignado = row['Nº Asignado']
                    
                    texto += f"{row['Nombre']} ({tip_op})\n"
                    fila_op = {"Nº": str(n_asignado), "TIP": tip_op, "Nombre": row["Nombre"], "Rol": "RESGUARDO FISCAL"}
                    
                    for idx, (h_img, h_txt) in enumerate(zip(franjas_img, franjas_texto)):
                        puesto = lista_puestos[(n_asignado - 1 + idx) % len(lista_puestos)]
                        fila_op[h_img] = puesto
                        texto += f"{h_txt}: {puesto}\n"
                    
                    cuadrante_final.append(fila_op)
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
    
    st.write("---")
    st.write("### 🛠️ Opciones Avanzadas")
    if st.button("🗑️ Resetear historial de rotaciones", key="reset_diario"):
        nuevo_historial = {row["Nombre"]: date(2000, 1, 1) for _, row in st.session_state.efectivos.iterrows()}
        guardar_memoria(nuevo_historial)
        st.session_state.historial = nuevo_historial
        st.success("✅ Historial de rotaciones borrado. Antigüedad pura al 100%.")
        st.rerun()
