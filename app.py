import streamlit as st
import requests
import json
import gspread
import datetime
import base64
import io
from gtts import gTTS
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

# --- 1. CONFIGURACIÓN ---
TU_EMAIL_GMAIL = "juanjesusmartinsr@gmail.com"

st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FAF5FF !important; color: #000000 !important; }
    .stMarkdown p, h1, h2, h3, div, span, li, label { color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #1a0b2e !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stTextInput > div > div > input { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #D1C4E9 !important; }
    .stButton > button { background-color: #6A1B9A !important; color: white !important; border: none !important; }
    .stChatMessage { background-color: #FFFFFF !important; border: 1px solid #E1BEE7 !important; color: #000000 !important; }
    /* Ajuste para el reproductor de audio */
    audio { width: 100%; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. FUNCIONES DE CONEXIÓN ---
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
    except: return None

def conectar_memoria(creds):
    try:
        client = gspread.authorize(creds)
        # Intentamos conectar a las dos hojas
        wb = client.open("Memoria_Asistente")
        return wb.sheet1, wb.worksheet("Perfil")
    except: return None, None

def crear_evento_calendario(creds, resumen, inicio_iso, fin_iso, nota_alerta=""):
    try:
        service = build('calendar', 'v3', credentials=creds)
        reminders = {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 10}]}
        evento = {
            'summary': resumen,
            'description': f"Agendado por Asistente.\n{nota_alerta}",
            'start': {'dateTime': inicio_iso, 'timeZone': 'America/Lima'}, 
            'end': {'dateTime': fin_iso, 'timeZone': 'America/Lima'},
            'reminders': reminders 
        }
        creado = service.events().insert(calendarId=TU_EMAIL_GMAIL, body=evento).execute()
        return True, creado.get('htmlLink')
    except Exception as e:
        return False, str(e)

# --- 3. FUNCIONES DE AUDIO ---
def texto_a_audio(texto):
    try:
        if not texto or len(texto) < 2: return None
        tts = gTTS(text=texto, lang='es')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except: return None

# --- 4. CEREBRO ---
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
    except: pass
    return "models/gemini-1.5-flash"

modelo_activo = detectar_modelo_real(api_key)

def get_hora_peru():
    return datetime.datetime.utcnow() - datetime.timedelta(hours=5)

# --- 5. INICIALIZACIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []

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
                registros = hoja_chat.get_all_records()
                for r in registros[-40:]:
                    r_low = {k.lower(): v for k, v in r.items()}
                    msg = str(r_low.get("mensaje", "")).strip()
                    if msg:
                        role = "user" if r_low.get("rol", "model").lower() == "user" else "model"
                        st.session_state.messages.append({"role": role, "content": msg, "mode": "personal"})
            except: pass
        # Cargar Perfil
        if hoja_perfil:
            try:
                vals = hoja_perfil.get_all_values()
                for fila in vals:
                    perfil_texto += " ".join(fila) + "\n"
            except: pass

# --- 6. INTERFAZ ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    st.write("---")
    if estado_memoria == "Conectada":
        st.success("🧠 Memoria Conectada")
    else:
        st.error("⚠️ Memoria Desconectada")

st.title("Tu Espacio")

# Input de Audio (Walkie Talkie)
audio_wav = st.audio_input("🎙️ Toca para hablar")

# Historial Visual
for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- 7. LÓGICA UNIFICADA (TEXTO O AUDIO) ---
prompt_texto = st.chat_input("Escribe aquí...")
input_usuario = None
es_audio = False

if prompt_texto:
    input_usuario = prompt_texto
elif audio_wav:
    es_audio = True
    input_usuario = "[Audio enviado... procesando]"

if input_usuario:
    # Si es audio, preparamos el payload especial
    contenido_usuario = []
    if es_audio:
        bytes_data = audio_wav.getvalue()
        b64_audio = base64.b64encode(bytes_data).decode('utf-8')
        contenido_usuario = [
            {"text": "Por favor, transcribe lo que digo en este audio y luego respóndeme. Si pido agendar, extrae el JSON."},
            {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
        ]
    else:
        contenido_usuario = [{"text": input_usuario}]

    # Mostrar mensaje usuario (provisional si es audio)
    st.session_state.messages.append({"role": "user", "content": input_usuario})
    with st.chat_message("user", avatar="👤"):
        st.markdown(input_usuario)

    # Variables de contexto
    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    # --- A. INTENTO DE AGENDAR (Voz o Texto) ---
    respuesta_texto = ""
    evento_creado = False
    
    if es_personal:
        ahora_peru = get_hora_peru().isoformat()
        # Prompt de sistema para detectar agenda
        sys_agenda = f"""
        Fecha/Hora Lima: {ahora_peru}
        Analiza el input (texto o audio).
        Si quiere agendar, responde SOLO JSON: {{"agendar": true, "titulo": "...", "inicio": "ISO", "fin": "ISO", "nota_alerta": "..."}}
        Si no, {{"agendar": false}}
        """
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            # Combinamos la instrucción de sistema con el contenido del usuario
            payload_agenda = { "contents": [{"parts": [{"text": sys_agenda}] + contenido_usuario }] }
            
            resp = requests.post(url, headers=headers, data=json.dumps(payload_agenda))
            if resp.status_code == 200:
                txt = resp.json()['candidates'][0]['content']['parts'][0]['text']
                txt = txt.replace("```json", "").replace("```", "").strip()
                datos = json.loads(txt)
                if datos.get("agendar"):
                    with st.spinner("Agendando..."):
                        exito, link = crear_evento_calendario(creds, datos["titulo"], datos["inicio"], datos["fin"], datos.get("nota_alerta", ""))
                        if exito:
                            respuesta_texto = f"✅ **{datos['titulo']}** agendado.\n[Ver evento]({link})"
                        else:
                            respuesta_texto = f"❌ Error: {link}"
                        evento_creado = True
        except: pass

    # --- B. RESPUESTA CONVERSACIONAL ---
    if not evento_creado:
        # Contexto
        historial = ""
        for m in st.session_state.messages[-40:]:
            historial += f"{m['role']}: {m['content']}\n"
        
        fecha_humana = get_hora_peru().strftime("%A %d de %B del %Y, %H:%M")
        
        if es_personal:
            sys_msg = f"""
            Eres un asistente personal leal. NO digas que eres un modelo de lenguaje.
            PERFIL USUARIO: {perfil_texto}
            TIEMPO LIMA: {fecha_humana}
            MEMORIA: {historial}
            """
        else:
            sys_msg = "Responde como Gemini."

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            # Payload final: Sistema + (Audio o Texto)
            payload_chat = { "contents": [{"parts": [{"text": sys_msg}] + contenido_usuario }] }
            
            resp = requests.post(url, headers=headers, data=json.dumps(payload_chat))
            if resp.status_code == 200:
                respuesta_texto = resp.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                respuesta_texto = f"Error {resp.status_code}"
        except Exception as e:
            respuesta_texto = f"Error: {e}"

    # --- C. MOSTRAR, HABLAR Y GUARDAR ---
    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)
        
        # Generar audio de respuesta
        audio_fp = texto_a_audio(respuesta_texto)
        if audio_fp:
            st.audio(audio_fp, format='audio/mp3')
            
        # Guardar en sesión
        st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
        
        # Guardar en Sheet (Si fue audio, guardamos la respuesta, el input queda como [Audio])
        if hoja_chat:
            try:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                # Si era audio, idealmente guardaríamos la transcripción, 
                # pero para no complicar, guardamos la etiqueta o lo que el usuario escribió
                hoja_chat.append_row([timestamp, "user", input_usuario]) 
                hoja_chat.append_row([timestamp, "assistant", respuesta_texto])
            except: pass
