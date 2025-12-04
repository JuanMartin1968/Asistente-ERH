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
    [data-testid="stAudioInput"] { margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 2. FUNCIONES DE AUDIO Y CONEXIÓN ---
def limpiar_texto_para_audio(texto):
    t = re.sub(r'[*_#]', '', texto)
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
    return t

def texto_a_audio(texto):
    try:
        if not texto or len(texto) < 2: return None
        limpio = limpiar_texto_para_audio(texto)
        tts = gTTS(text=limpio, lang='es')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except: return None

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
        wb = client.open("Memoria_Asistente")
        return wb.sheet1, wb.worksheet("Perfil")
    except: return None, None

def crear_evento_calendario(creds, resumen, inicio_iso, fin_iso, nota_alerta=""):
    try:
        service = build('calendar', 'v3', credentials=creds)
        reminders = {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 10}]}
        
        description = f"Agendado por Asistente.\n{nota_alerta}"
        evento = {
            'summary': resumen,
            'description': description,
            'start': {'dateTime': inicio_iso, 'timeZone': 'America/Lima'}, 
            'end': {'dateTime': fin_iso, 'timeZone': 'America/Lima'},
            'reminders': reminders 
        }
        creado = service.events().insert(calendarId=TU_EMAIL_GMAIL, body=evento).execute()
        return True, creado.get('htmlLink')
    except Exception as e:
        return False, str(e)

# --- 3. CEREBRO Y AUTODETECCIÓN ---
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

# --- 5. INTERFAZ ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    st.write("---")
    if estado_memoria == "Conectada":
        st.success("🧠 Memoria Conectada")
    else:
        st.error("⚠️ Memoria Desconectada")

st.title("Tu Espacio")

# --- 6. INPUT UNIFICADO ---
audio_wav = st.audio_input("🎙️ Toca para hablar")
prompt_texto = st.chat_input("Escribe aquí...")
input_usuario = None
es_audio = False

if prompt_texto:
    input_usuario = prompt_texto
    es_audio = False 
elif audio_wav:
    es_audio = True
    input_usuario = "🎤 [Procesando Audio...]" # Placeholder para el historial

if input_usuario:
    # Preparar el payload para la IA
    contenido_usuario = []
    
    if es_audio:
        # FIX: Pedimos transcripción y respuesta separadas por |||
        bytes_data = audio_wav.getvalue()
        b64_audio = base64.b64encode(bytes_data).decode('utf-8')
        
        sys_audio_inst = "Transcribe el audio EXACTAMENTE, devuelve el texto de la transcripción inmediatamente, separado de tu respuesta por el símbolo: |||."
        
        # Multimodal payload: [Instrucción], [Audio]
        payload_parts = [
            {"text": sys_audio_inst},
            {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
        ]
        
        # Asignamos el input del usuario como el texto de la instrucción
        contenido_usuario = [{"parts": payload_parts}]
    else:
        # Texto input
        contenido_usuario = [{"parts": [{"text": input_usuario}]}]

    # Mostrar mensaje usuario (se usa el placeholder si es audio)
    st.session_state.messages.append({"role": "user", "content": input_usuario, "mode": "personal"})
    with st.chat_message("user", avatar="👤"):
        st.markdown(input_usuario)

    # Contexto
    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    respuesta_texto = ""
    
    # --- 7. PROCESAMIENTO Y RESPUESTA ---
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        
        # Construimos el prompt de contexto
        historial = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-40:]])
        fecha_humana = get_hora_peru().strftime("%A %d de %B del %Y, %H:%M")
        
        sys_context = f"""
        INSTRUCCIONES: Eres un asistente personal leal. NO digas que eres IA.
        TIEMPO EN LIMA: {fecha_humana}
        PERFIL: {perfil_texto}
        MEMORIA: {historial}
        """

        # Prependemos el contexto al payload
        payload_final = {
            "contents": [
                {"parts": [{"text": sys_context}]}
            ]
        }
        
        # Añadimos el turno del usuario (que contiene el audio/texto y las instrucciones de agenda)
        # NOTA: Simplificamos el payload agregando el input a la lista de contenidos como el siguiente turno.
        
        # Simplificación de payload para evitar errores de anidamiento
        payload = {
            "contents": [
                {"parts": [{"text": sys_context}]},
                {"parts": contenido_usuario[0]['parts'] if es_audio else [{"text": input_usuario}]}
            ]
        }
        
        resp = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if resp.status_code == 200:
            full_response = resp.json()['candidates'][0]['content']['parts'][0]['text']
            transcripcion_final = None

            # 8. PARSING PARA AUDIO/TRANSCRIPCIÓN (EL FIX DEL ECO)
            if es_audio and '|||' in full_response:
                partes = full_response.split('|||', 1)
                transcripcion_final = partes[0].strip()
                respuesta_texto = partes[1].strip()
            else:
                respuesta_texto = full_response
            
            # Si hay transcripción, actualizamos el historial y el input_usuario para guardar
            if transcripcion_final:
                # Actualiza el historial visible
                st.session_state.messages[-1]['content'] = transcripcion_final 
                input_usuario = transcripcion_final
            
        else:
            respuesta_texto = f"Error {resp.status_code}: {resp.text}"

    except Exception as e:
        respuesta_texto = f"Error inesperado: {e}"

    # C. RESPUESTA FINAL
    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)
        
        # LOGICA DE AUDIO INTELIGENTE: (Solo responde con audio si se le habló con audio)
        if es_audio:
            audio_fp = texto_a_audio(respuesta_texto)
            if audio_fp:
                st.audio(audio_fp, format='audio/mp3')
            
        st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
        
        # D. GUARDAR EN MEMORIA
        if hoja_chat:
            try:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                # Guardamos la transcripción o el texto plano
                hoja_chat.append_row([timestamp, "user", input_usuario]) 
                hoja_chat.append_row([timestamp, "assistant", respuesta_texto])
            except: pass
