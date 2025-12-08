import smtplib
from email.mime.text import MIMEText
import streamlit as st
import requests
import json
import gspread
import datetime
import base64
import io
import re
from gtts import gTTS
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

# --- 1. DATOS DEL USUARIO ---
TU_EMAIL_GMAIL = "juanjesusmartinsr@gmail.com"

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Asistente Personal",
                   page_icon="🟣", layout="wide")

st.markdown("""
<style>
    /* DERECHA (Panel Principal) */
    .stApp { background-color: #FAF5FF !important; color: #000000 !important; }
    .stMarkdown p, h1, h2, h3, div, span, li, label { color: #000000 !important; }
    
    /* BARRA LATERAL (Izquierda) */
    [data-testid="stSidebar"] { background-color: #1a0b2e !important; }
    /* Texto general blanco */
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    /* EXCEPCIÓN: Botón "Browse files" (letras negras para que se vea) */
    [data-testid="stFileUploader"] button { color: #000000 !important; }
    
    /* INPUTS */
    .stTextInput > div > div > input { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #D1C4E9 !important; }
    .stButton > button { background-color: #6A1B9A !important; color: white !important; border: none !important; }
    
    /* CHAT */
    .stChatMessage { background-color: #FFFFFF !important; border: 1px solid #E1BEE7 !important; color: #000000 !important; }
    
    /* Estilo para el input de audio */
    [data-testid="stAudioInput"] { margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE INSTRUCCIONES DEL SISTEMA ---
# Esto asegura que el asistente sepa usar las 15 tareas y el comando EXTENDER
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": """
Eres un asistente personal eficiente y estricto con la seguridad.

PROTOCOLO OBLIGATORIO DE GUARDADO:
PASO 1 (El Borrador):
Cuando te pidan una tarea, NO uses el comando todavía. Muestra el borrador EXACTAMENTE con este formato visual:

📂 **Borrador de Tarea:**
* Tarea: [Nombre]
* Subtareas:
  1. [Sub1]
  2. [Sub2]
  ...

📅 Fecha: [YYYY-MM-DD]

¿Es correcto?

PASO 2 (La Ejecución):
Si confirman, lanza el comando LIMPIO. 
CUIDADO: El último dato del comando es la fecha. NO escribas nada después de la fecha en la misma línea del comando.
Correcto: "TAREA_CMD: AGREGAR | ... | 2025-12-09"
Incorrecto: "TAREA_CMD: AGREGAR | ... | 2025-12-09 ✅ Listo" (Esto corrompe la hoja).

COMANDOS TÉCNICOS (Solo usar tras confirmación):
- Para guardar: "TAREA_CMD: AGREGAR | Título | Sub1 | Sub2 | ... | Fecha"
- Para ver lista: "TAREA_CMD: LISTAR"
- Para extender: "TAREA_CMD: EXTENDER | ID_Fila"
- Para marcar: "TAREA_CMD: CHECK | ID_Fila | N_Subtarea"

Recuerda: Tu prioridad es la precisión. No asumas, consulta.
"""}
    ]


# --- 3. FUNCIONES DE AUDIO Y LIMPIEZA ---


def limpiar_texto_para_audio(texto):
    # Quita asteriscos, guiones bajos, hashtags y links
    t = re.sub(r'[*_#]', '', texto)
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
    return t


def texto_a_audio(texto):
    try:
        if not texto or len(texto) < 2:
            return None
        limpio = limpiar_texto_para_audio(texto)
        tts = gTTS(text=limpio, lang='es')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except:
        return None

# --- 4. FUNCIONES DE CONEXIÓN Y ALERTA ---


def obtener_credenciales():
    try:
        json_text = st.secrets["GOOGLE_CREDENTIALS"]
        creds_dict = json.loads(json_text, strict=False)
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/calendar'
        ]
        return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except:
        return None


def conectar_memoria(creds):
    try:
        client = gspread.authorize(creds)
        wb = client.open("Memoria_Asistente")
        return wb.sheet1, wb.worksheet("Perfil")
    except:
        return None, None


def crear_evento_calendario(creds, resumen, inicio_iso, fin_iso, nota_alerta="", recurrence=None):
    try:
        service = build('calendar', 'v3', credentials=creds)
        reminders = {'useDefault': False, 'overrides': [
            {'method': 'popup', 'minutes': 10}]}

        description = f"Agendado por Asistente.\n{nota_alerta}"
        evento = {
            'summary': resumen,
            'description': description,
            'start': {'dateTime': inicio_iso, 'timeZone': 'America/Lima'},
            'end': {'dateTime': fin_iso, 'timeZone': 'America/Lima'},
            'reminders': reminders
        }

        # Si hay regla de repetición, la agregamos
        if recurrence:
            evento['recurrence'] = [recurrence]

        creado = service.events().insert(calendarId=TU_EMAIL_GMAIL, body=evento).execute()
        return True, creado.get('htmlLink')
    except Exception as e:
        return False, str(e)


def enviar_correo_gmail(destinatario, asunto, cuerpo):
    try:
        remitente = st.secrets["GMAIL_USER"]
        password = st.secrets["GMAIL_PASSWORD"]

        msg = MIMEText(cuerpo)
        msg['Subject'] = asunto
        msg['From'] = remitente
        msg['To'] = destinatario

        # Conexión con Gmail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
        server.quit()
        return True, "Correo enviado"
    except Exception as e:
        return False, str(e)

# --- FUNCIONES DE GESTIÓN DE TAREAS (TABLA CORREGIDA + CÁLCULO) ---

def gestionar_tareas(modo, datos=None):
    try:
        import json
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        import streamlit as st

        scope = ['https://www.googleapis.com/auth/spreadsheets',
                 'https://www.googleapis.com/auth/drive']
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"], strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(st.secrets["SPREADSHEET_ID"]).worksheet("Tareas")

        if modo == "LISTAR":
            registros = sheet.get_all_records()
            if not registros:
                return "No hay tareas registradas."

            texto = "\n| ID | Tarea | Subtareas | Avance |\n| :---: | :--- | :--- | :---: |\n"

            for i, r in enumerate(registros, start=2):
                hechas = 0
                total = 0
                iconos = ""

                # Recorremos de la Subtarea 1 a la 15
                for n in range(1, 16):
                    clave = f"Subtarea {n}"
                    valor = str(r.get(clave, "")).strip().upper()

                    # Solo contamos si la celda NO está vacía
                    if valor in ["TRUE", "FALSE"]:
                        total += 1
                        if valor == "TRUE":
                            hechas += 1
                            iconos += "✅ "
                        else:
                            iconos += "⬜ "
                
                # Evitar división por cero si no hay subtareas
                porcentaje = "0%"
                if total > 0:
                    porcentaje = f"{int((hechas/total)*100)}%"
                
                if total == 0: iconos = "—"

                texto += f"| **{i}** | {r.get('Tarea')} | {iconos} | **{porcentaje}** |\n"
            return texto

        elif modo == "AGREGAR":
            # datos: [Tarea, (n subtareas...), Fecha]
            # Creamos fila con 15 espacios para subtareas
            tarea = datos[0]
            fecha = datos[-1]
            cantidad_subs = len(datos) - 2 # Restamos Tarea y Fecha
            
            fila_subs = []
            for k in range(15):
                if k < cantidad_subs:
                    fila_subs.append("FALSE") # Activa para contar
                else:
                    fila_subs.append("") # Vacía para ignorar

            # Armamos la fila completa: Tarea + 15 Subs + Extras
            fila = [tarea] + fila_subs + ["", "Pendiente", fecha]
            sheet.append_row(fila)
            return f"Tarea agregada con {cantidad_subs} subtareas."

        elif modo == "CHECK":
            # datos[0] = Fila, datos[1] = Número de subtarea visual (1, 2, 3...)
            fila_idx = int(datos[0])
            sub_num = int(datos[1])
            
            # La columna 1 es Tarea, la 2 es Subtarea 1. 
            # Por tanto: Columna = 1 + sub_num
            col_idx = 1 + sub_num
            
            sheet.update_cell(fila_idx, col_idx, True)
            return "Avance actualizado."
            
        elif modo == "ADD_SUB":
            # Agrega una subtarea extra a una fila existente
            fila_idx = int(datos[0])
            row_vals = sheet.row_values(fila_idx)
            
            # Buscamos la primera columna vacía entre la 2 y la 16 (Subtareas)
            col_destino = -1
            for c in range(2, 17):
                # Si la longitud de row_vals es menor que c, es que está vacío al final
                if c > len(row_vals) or row_vals[c-1] == "":
                    col_destino = c
                    break
            
            if col_destino != -1:
                sheet.update_cell(fila_idx, col_destino, "FALSE")
                return "Subtarea adicional agregada."
            else:
                return "Máximo de 15 subtareas alcanzado."

    except Exception as e:
        return f"Error: {str(e)}"

# --- 5. CEREBRO Y AUTODETECCIÓN ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
except:
    st.error("Falta API Key")
    st.stop()


@st.cache_data
def detectar_modelo_real(key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for m in data.get('models', []):
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    return m['name']
    except:
        pass
    return "models/gemini-1.5-flash"


modelo_activo = detectar_modelo_real(api_key)


def get_hora_peru():
    # Hora de Lima (UTC-5)
    return datetime.datetime.utcnow() - datetime.timedelta(hours=5)


# --- 6. INICIALIZACIÓN Y CARGA DE DATOS ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "id_conv_actual" not in st.session_state:
    st.session_state.id_conv_actual = None
if "num_mensajes" not in st.session_state:
    st.session_state.num_mensajes = 40  # Recuperamos el contador

creds = obtener_credenciales()
hoja_chat, hoja_perfil = None, None
estado_memoria = "Desconectada"
perfil_texto = ""

if creds:
    h1, h2 = conectar_memoria(creds)
    if h1:
        hoja_chat = h1
        hoja_perfil = h2
        estado_memoria = "Conectada"

        # Cargar Chat
        if not st.session_state.messages:
            try:
                todas_las_filas = hoja_chat.get_all_values()
                if len(todas_las_filas) > 1:
                    # 1. Detectar IDs existentes
                    ids_existentes = sorted(
                        list(set(f[0] for f in todas_las_filas[1:] if f[0].strip().isdigit())), key=int)

                    if st.session_state.id_conv_actual is None:
                        if ids_existentes:
                            st.session_state.id_conv_actual = ids_existentes[-1]
                        else:
                            st.session_state.id_conv_actual = "1"

                    target_id = str(st.session_state.id_conv_actual)

                    # 2. FILTRAR primero solo las filas de esta conversación
                    filas_de_esta_conv = []
                    for fila in todas_las_filas[1:]:
                        if len(fila) >= 4 and fila[0] == target_id:
                            filas_de_esta_conv.append(fila)

                    # 3. APLICAR EL LÍMITE (Cargar solo los últimos 'num_mensajes')
                    limite = st.session_state.num_mensajes
                    for fila in filas_de_esta_conv[-limite:]:
                        rol_leido = fila[2].strip()
                        msg_leido = fila[3].strip()
                        if msg_leido:
                            role = "user" if rol_leido.lower() == "user" else "assistant"
                            st.session_state.messages.append(
                                {"role": role, "content": msg_leido, "mode": "personal"})

            except Exception as e:
                st.error(f"Error recuperando historial: {e}")

        # Cargar Perfil
        if hoja_perfil:
            try:
                vals = hoja_perfil.get_all_values()
                for fila in vals:
                    perfil_texto += " ".join(fila) + "\n"
            except:
                pass

# --- 7. BARRA LATERAL Y UI ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])

    st.write("---")
    uploaded_file = st.file_uploader("📸 Subir archivo", type=[
                                     "png", "jpg", "jpeg", "pdf"])

    st.write("---")
    st.header("🗂️ Conversaciones")

    # 1. Leer IDs desde la hoja
    lista_ids = ["1"]
    if hoja_chat:
        try:
            raw_data = hoja_chat.get_all_values()
            encontrados = sorted(
                list(set(f[0] for f in raw_data[1:] if f[0].strip().isdigit())), key=int)
            if encontrados:
                lista_ids = encontrados
        except:
            pass

    # 2. Determinar ID actual
    actual = str(
        st.session_state.id_conv_actual) if st.session_state.id_conv_actual else lista_ids[-1]

    if actual not in lista_ids:
        lista_ids.append(actual)

    # 3. Selector
    id_seleccionado = st.selectbox(
        "Elige una conversación:",
        options=lista_ids,
        index=lista_ids.index(actual)
    )

    if id_seleccionado != actual:
        st.session_state.id_conv_actual = id_seleccionado
        st.session_state.num_mensajes = 40  # Resetea vista al cambiar
        st.session_state.messages = []
        st.rerun()

    # 4. Botón Nueva Conversación
    if st.button("➕ Nueva Conversación"):
        max_id = int(lista_ids[-1])
        nuevo = str(max_id + 1)
        st.session_state.id_conv_actual = nuevo
        st.session_state.num_mensajes = 40  # Resetea vista al crear
        st.session_state.messages = []
        st.rerun()

    # 5. Botón Cargar Más (RECUPERADO)
    st.write("---")
    if st.button("🔄 Cargar más antiguos"):
        st.session_state.num_mensajes += 40
        st.session_state.messages = []
        st.rerun()

    st.write("---")
    if estado_memoria == "Conectada":
        st.success(f"🧠 Memoria: Conv. {st.session_state.id_conv_actual}")
    else:
        st.error("⚠️ Memoria Desconectada")

st.title("Tu Espacio")

# --- MOSTRAR HISTORIAL ---
for message in st.session_state.messages:
    if message["role"] != "system":
        av = "👤" if message["role"] == "user" else "🟣"
        with st.chat_message(message["role"], avatar=av):
            st.markdown(message["content"])

# --- 8. INPUT UNIFICADO (VOZ Y TEXTO) ---
audio_wav = st.audio_input("🎙️ Toca para hablar")
prompt_texto = st.chat_input("Escribe aquí...")
input_usuario = None
es_audio = False

if prompt_texto:
    input_usuario = prompt_texto
elif audio_wav:
    es_audio = True
    input_usuario = "🎤 [Audio enviado]"

if input_usuario:

    # Preparamos el mensaje para el historial (se mostrará)
    st.session_state.messages.append(
        {"role": "user", "content": input_usuario, "mode": "personal"})
    with st.chat_message("user", avatar="👤"):
        st.markdown(input_usuario)

# --- 9. LÓGICA DE PROCESAMIENTO Y RESPUESTA ---
    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    respuesta_texto = ""

    with st.spinner("Pensando..."):
        # Contexto
        historial = ""
        for m in st.session_state.messages[-40:]:
            historial += f"{m['role']}: {m['content']}\n"

        hora_peru_str = get_hora_peru().strftime("%A %d de %B del %Y, %H:%M:%S")

        if es_personal:
            sys_context = f"""
            INSTRUCCIONES: Eres un asistente personal leal y eficiente. NO menciones limitaciones de IA.
            HORA OFICIAL PERÚ (UTC-5): {hora_peru_str}
            PERFIL USUARIO: {perfil_texto}
            MEMORIA RECIENTE: {historial}

            TUS HERRAMIENTAS (TIENES PERMISO TOTAL PARA USARLAS):

            1. TAREAS Y PROYECTOS (PRIORIDAD):
            PROTOCOLO OBLIGATORIO DE GUARDADO:
            PASO 1 (El Borrador):
            Cuando te pidan una tarea, NO uses el comando todavía. Muestra el borrador EXACTAMENTE con este formato visual:
            
            📂 **Borrador de Tarea:**
            * Tarea: [Nombre]
            * Subtareas:
              1. [Sub1]
              2. [Sub2]
              ...
            
            📅 Fecha: [YYYY-MM-DD]
            
            ¿Es correcto?

            PASO 2 (La Ejecución):
            Si confirman, lanza el comando LIMPIO. 
            CUIDADO: El último dato del comando es la fecha. NO escribas nada después de la fecha en la misma línea del comando.
            Correcto: "TAREA_CMD: AGREGAR | ... | 2025-12-09"
            Incorrecto: "TAREA_CMD: AGREGAR | ... | 2025-12-09 ✅ Listo" (Esto corrompe la hoja).
            HERRAMIENTA TAREAS:
            1. Para ver tareas: "TAREA_CMD: LISTAR"
            2. Para crear tarea (soporta hasta 15 subtareas): "TAREA_CMD: AGREGAR | Título Tarea | Subtarea 1 | Subtarea 2 | ... | Fecha"
               (Ejemplo: "TAREA_CMD: AGREGAR | Informe | Buscar datos | Redactar | Revisar | 2025-12-07")
            3. Para marcar una casilla: "TAREA_CMD: CHECK | ID_Fila | N_Subtarea"
               (Ejemplo: "TAREA_CMD: CHECK | 2 | 1" marca la primera casilla de la fila 2).
            4. Para agregar una subtarea extra a una tarea ya creada: "TAREA_CMD: EXTENDER | ID_Fila"
               (Esto agrega una casilla vacía al final de esa tarea y recalcula el porcentaje).
              
            2. PARA AGENDAR EN CALENDARIO:
            CALENDAR_CMD: Título | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM | Nota | RRULE
            * RRULE Ejemplos: 
              - Todos los días: FREQ=DAILY
              - Cada mes día 5: FREQ=MONTHLY;BYMONTHDAY=5
              - Fin de mes: FREQ=MONTHLY;BYMONTHDAY=-1

            3. PARA GUARDAR EN MEMORIA:
            MEMORIA_CMD: Dato a guardar

            4. PARA ENVIAR CORREOS GMAIL:
            Si te piden enviar un correo, responde con este formato al final:
            EMAIL_CMD: Destinatario | Asunto | Cuerpo del mensaje

            NOTA: Si te preguntan "¿Qué tengo pendiente?", SIEMPRE ejecuta primero TAREA_CMD: LISTAR.
            """
        else:
            sys_context = "Responde como Gemini."

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}

            # --- CONSTRUCCIÓN DEL PAYLOAD (CON IMAGEN) ---
            payload_parts = [{"text": sys_context}]

            # 1. Agregar Imagen (si existe)
            if uploaded_file is not None:
                bytes_img = uploaded_file.getvalue()
                b64_img = base64.b64encode(bytes_img).decode('utf-8')
                payload_parts.append({
                    "inline_data": {
                        "mime_type": uploaded_file.type,
                        "data": b64_img
                    }
                })
                payload_parts.append(
                    {"text": "\n(El usuario adjuntó una imagen. Úsala si es relevante)."})

            # 2. Agregar Audio o Texto
            if es_audio:
                bytes_audio = audio_wav.getvalue()
                b64_audio = base64.b64encode(bytes_audio).decode('utf-8')
                payload_parts.append({
                    "inline_data": {
                        "mime_type": "audio/wav",
                        "data": b64_audio
                    }
                })
                payload_parts.append(
                    {"text": "\n---\nTranscribe el audio y responde."})
            else:
                payload_parts.append({"text": "USUARIO: " + prompt_texto})

            payload = {"contents": [{"parts": payload_parts}]}

            # Llamada a la API
            resp = requests.post(url, headers=headers,
                                 data=json.dumps(payload))

            if resp.status_code == 200:
                respuesta_texto = resp.json(
                )['candidates'][0]['content']['parts'][0]['text']
            else:
                respuesta_texto = f"Error {resp.status_code}: {resp.text}"
                if "quota" in resp.text:
                    respuesta_texto += "\n(Puede ser un problema temporal de cuota de API.)"
        except Exception as e:
            respuesta_texto = f"Error inesperado: {e}"

# --- LOGICA CALENDARIO (CON REPETICIÓN) ---
    if "CALENDAR_CMD:" in respuesta_texto:
        try:
            parts = respuesta_texto.split("CALENDAR_CMD:")
            respuesta_texto = parts[0].strip()

            # Ahora esperamos hasta 5 partes: Título | Inicio | Fin | Nota | RRULE
            datos = parts[1].strip().split("|")

            if len(datos) >= 3:
                resumen = datos[0].strip()

                # 1. Formato ISO
                ini_raw = datos[1].strip().replace(" ", "T")
                fin_raw = datos[2].strip().replace(" ", "T")
                if len(ini_raw) == 16:
                    ini_raw += ":00"
                if len(fin_raw) == 16:
                    fin_raw += ":00"

                # 2. Nota (Opcional)
                nota = datos[3].strip() if len(datos) > 3 else ""

                # 3. Regla de Repetición (RRULE) - Opcional
                rule = None
                if len(datos) > 4:
                    rule_raw = datos[4].strip()
                    if "FREQ=" in rule_raw:  # Solo si parece una regla válida
                        rule = "RRULE:" + \
                            rule_raw if not rule_raw.startswith(
                                "RRULE:") else rule_raw

                ok, link = crear_evento_calendario(
                    creds, resumen, ini_raw, fin_raw, nota, rule)

                tipo = "repetitivo" if rule else "único"
                respuesta_texto += f"\n\n{'✅ Evento ' + tipo + ' creado' if ok else '❌ Error'}: {link}"
        except:
            pass

# --- LOGICA MEMORIA (PERFIL) CON FECHA ---
    if "MEMORIA_CMD:" in respuesta_texto:
        try:
            parts = respuesta_texto.split("MEMORIA_CMD:")
            respuesta_texto = parts[0].strip()
            dato_nuevo = parts[1].strip()

            if hoja_perfil:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                hoja_perfil.append_row([timestamp, dato_nuevo])
                respuesta_texto += "\n(💾 Guardado en perfil)"
        except:
            pass

# --- LOGICA EMAIL ---
    if "EMAIL_CMD:" in respuesta_texto:
        try:
            parts = respuesta_texto.split("EMAIL_CMD:")
            respuesta_texto = parts[0].strip()
            datos = parts[1].strip().split("|")

            if len(datos) >= 3:
                dest = datos[0].strip()
                asunto = datos[1].strip()
                cuerpo = datos[2].strip()

                ok, msg = enviar_correo_gmail(dest, asunto, cuerpo)
                respuesta_texto += f"\n\n{'✅ Correo enviado' if ok else '❌ Error correo'}: {msg}"
        except:
            pass

# --- LOGICA TAREAS ---
    if "TAREA_CMD:" in respuesta_texto:
        try:
            parts = respuesta_texto.split("TAREA_CMD:")
            respuesta_texto = parts[0].strip()
            cmd_full = parts[1].strip().split("|")
            accion = cmd_full[0].strip()

            if accion == "LISTAR":
                res = gestionar_tareas("LISTAR")
                respuesta_texto += f"\n\n📋 {res}"

            elif accion == "AGREGAR":
                # Captura dinámicamente: Tarea | Sub1 | ... | Fecha
                datos_tarea = [x.strip() for x in cmd_full[1:]]
                res = gestionar_tareas("AGREGAR", datos_tarea)
                respuesta_texto += f"\n\n✅ {res}"

            elif accion == "CHECK" and len(cmd_full) >= 3:
                # CHECK | ID_Fila | N_Subtarea
                res = gestionar_tareas("CHECK", [cmd_full[1], cmd_full[2]])
                respuesta_texto += f"\n\n📈 {res}"

            elif accion == "EXTENDER" and len(cmd_full) >= 2:
                # EXTENDER | ID_Fila (Agrega una casilla vacía extra al final)
                res = gestionar_tareas("ADD_SUB", [cmd_full[1]])
                respuesta_texto += f"\n\n➕ {res}"

        except Exception as e:
            respuesta_texto += f"\n\n❌ Error procesando tarea: {str(e)}"
  
    # C. RESPUESTA FINAL
    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)

        # LOGICA DE AUDIO INTELIGENTE: (Solo responde con audio si se le habló con audio)
        if es_audio:
            audio_fp = texto_a_audio(respuesta_texto)
            if audio_fp:
                st.audio(audio_fp, format='audio/mp3')

        st.session_state.messages.append(
            {"role": "model", "content": respuesta_texto, "mode": tag_modo})

# D. GUARDAR EN MEMORIA
        if hoja_chat:
            try:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                id_actual = st.session_state.id_conv_actual

                # Guardamos 4 columnas: ID, Fecha, Rol, Mensaje
                hoja_chat.append_row(
                    [id_actual, timestamp, "user", input_usuario])
                hoja_chat.append_row(
                    [id_actual, timestamp, "assistant", respuesta_texto])
            except:
                pass







