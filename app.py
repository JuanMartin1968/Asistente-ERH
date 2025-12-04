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
import streamlit_audiorecorder as st_audiorecorder

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
    [data-testid="stSidebar"] div.stAudioRecorder { padding-top: 10px; } 
</style>
""", unsafe_allow_html=True)

# --- 2. FUNCIONES DE CONEXIÓN ---
def obtener_credenciales():
    try:
        json_text = st.secrets["GOOGLE_CREDENTIALS"]
        creds_dict = json.loads(json_text, strict=False)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/calendar']
        return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except: return None

def conectar_memoria(creds):
    try:
        client = gspread.authorize(creds)
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

# --- 3. AUDIO Y CEREBRO ---
def texto_a_audio(texto):
    try:
        if not texto or len(texto) < 2: return None
        # Limpieza de caracteres para que no lea asteriscos
        t = re.sub(r'[*_#]', '', texto)
        t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
        tts = gTTS(text=t, lang='es')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except: return None

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

# --- 4. INICIALIZACIÓN ---
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
        if hoja_perfil:
            try:
                vals = hoja_perfil.get_all_values()
                for fila in vals:
                    perfil_texto += " ".join(fila) + "\n"
            except: pass

# --- 5. UI ---
with st.sidebar:
    st.header("Configuración")
    # Micrófono estable
    audio_bytes = st_audiorecorder.audiorecorder("🔴 Grabar", "⏹️ Parar")
    
    st.write("---")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    st.write("---")
    if estado_memoria == "Conectada":
        st.success("🧠 Memoria Conectada")
    else:
        st.error("⚠️ Memoria Desconectada")

st.title("Tu Espacio")

prompt_texto = st.chat_input("Escribe aquí...")

# Historial
for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- 6. PROCESAMIENTO UNIFICADO ---
input_final = None
es_audio = False
payload_parts = []

# Detectar origen (Audio o Texto)
if prompt_texto:
    input_final = prompt_texto
    # Parte de texto simple para la API
    payload_parts = [{"text": input_final}]
    
elif len(audio_bytes) > 0:
    es_audio = True
    input_final = "🎤 [Audio]"
    b64_audio = base64.b64encode(audio_bytes).decode('utf-8')
    # Parte multimodal para la API
    payload_parts = [
        {"text": "Transcribe este audio y responde a él."}, 
        {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
    ]

if input_final:
    # Mostrar mensaje usuario
    st.session_state.messages.append({"role": "user", "content": input_final, "mode": "personal"})
    with st.chat_message("user", avatar="👤"):
        st.markdown(input_final)

    # Variables Contexto
    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    # Contexto Sistema
    historial = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-40:]])
    fecha_humana = get_hora_peru().strftime("%A %d de %B del %Y, %H:%M")
    
    if es_personal:
        sys_msg = f"""
        ERES UN ASISTENTE PERSONAL. NO DIGAS QUE ERES UNA IA.
        TU PERFIL DE USUARIO (MEMORIA PERMANENTE): {perfil_texto}
        FECHA Y HORA ACTUAL (LIMA): {fecha_humana}
        HISTORIAL RECIENTE: {historial}
        """
    else:
        sys_msg = "Responde como Gemini."

    # Función auxiliar para llamar a Gemini
    def llamar_gemini(system_prompt, user_parts):
        url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        # Estructura JSON corregida para evitar Error 400
        final_contents = [{"parts": [{"text": system_prompt}] + user_parts}]
        data = {"contents": final_contents}
        return requests.post(url, headers=headers, data=json.dumps(data))

    respuesta_texto = ""
    evento_creado = False

    # A. ANÁLISIS AGENDA (Solo si es personal)
    if es_personal:
        prompt_agenda = sys_msg + "\n\nAnaliza la última entrada. Si quiere agendar, responde SOLO JSON: {\"agendar\": true, \"titulo\": \"...\", \"inicio\": \"ISO\", \"fin\": \"ISO\", \"nota_alerta\": \"...\"}. Si no, {\"agendar\": false}"
        try:
            # Reutilizamos los parts del usuario (sea audio o texto)
            resp = llamar_gemini(prompt_agenda, payload_parts)
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

    # B. ANÁLISIS PERFIL (Guardar datos nuevos)
    if es_personal and not evento_creado and hoja_perfil:
        try:
            prompt_perfil = sys_msg + f"\n\nAnaliza la última entrada. Si hay un dato PERMANENTE nuevo sobre el usuario que NO esté ya en el perfil: '{perfil_texto}', responde SOLO con el dato. Si no, responde NO."
            resp = llamar_gemini(prompt_perfil, payload_parts)
            if resp.status_code == 200:
                nuevo_dato = resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                if nuevo_dato and "NO" not in nuevo_dato and len(nuevo_dato) < 200:
                    hoja_perfil.append_row([get_hora_peru().strftime("%Y-%m-%d"), nuevo_dato])
        except: pass

    # C. RESPUESTA CONVERSACIONAL
    if not evento_creado:
        try:
            resp = llamar_gemini(sys_msg, payload_parts)
            if resp.status_code == 200:
                respuesta_texto = resp.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                respuesta_texto = f"Error API {resp.status_code}: {resp.text}"
        except Exception as e:
            respuesta_texto = f"Error: {e}"

    # D. MOSTRAR Y GUARDAR
    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)
        
        # Audio solo si el usuario usó micrófono
        if es_audio:
            audio_fp = texto_a_audio(respuesta_texto)
            if audio_fp:
                st.audio(audio_fp, format='audio/mp3')
            
        st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
        
        if hoja_chat:
            try:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                # Guardamos lo que se mostró en pantalla
                hoja_chat.append_row([timestamp, "user", input_final]) 
                hoja_chat.append_row([timestamp, "assistant", respuesta_texto])
            except: pass
