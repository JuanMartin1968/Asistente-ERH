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
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

st.markdown("""
<style>
    /* DERECHA */
    .stApp { background-color: #FAF5FF !important; color: #000000 !important; }
    .stMarkdown p, h1, h2, h3, div, span, li, label { color: #000000 !important; }
    /* IZQUIERDA */
    [data-testid="stSidebar"] { background-color: #1a0b2e !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    /* INPUTS */
    .stTextInput > div > div > input { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #D1C4E9 !important; }
    .stButton > button { background-color: #6A1B9A !important; color: white !important; border: none !important; }
    /* CHAT */
    .stChatMessage { background-color: #FFFFFF !important; border: 1px solid #E1BEE7 !important; color: #000000 !important; }
    /* Estilo para el input de audio */
    [data-testid="stAudioInput"] { margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNCIONES DE AUDIO Y LIMPIEZA ---
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
    except: return None

def conectar_memoria(creds):
    try:
        client = gspread.authorize(creds)
        wb = client.open("Memoria_Asistente")
        # Intentamos conectar hoja chat y perfil
        try:
            hoja_perfil = wb.worksheet("Perfil")
        except:
            hoja_perfil = None
        return wb.sheet1, hoja_perfil
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

# --- 5. CEREBRO ---
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

# --- 6. INICIALIZACIÓN ---
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
        
        # Cargar Historial
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
            
        # Cargar Perfil (Para que la IA sepa qué ya sabe)
        if hoja_perfil:
            try:
                vals = hoja_perfil.get_all_values()
                for fila in vals:
                    perfil_texto += " ".join(fila) + "\n"
            except: pass

# --- 7. UI ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    st.write("---")
    if estado_memoria == "Conectada":
        st.success("🧠 Memoria Conectada")
    else:
        st.error("⚠️ Memoria Desconectada")

st.title("Tu Espacio")

# Input Unificado
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
    # Preparar payload
    contenido_usuario = []
    
    if es_audio:
        bytes_data = audio_wav.getvalue()
        b64_audio = base64.b64encode(bytes_data).decode('utf-8')
        sys_audio_inst = "Transcribe el audio EXACTAMENTE, luego procede. Si pides agendar, extrae JSON."
        contenido_usuario = [
            {"text": sys_audio_inst},
            {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
        ]
    else:
        contenido_usuario = [{"text": input_usuario}]

    # Mostrar mensaje usuario
    st.session_state.messages.append({"role": "user", "content": input_usuario, "mode": "personal"})
    with st.chat_message("user", avatar="👤"):
        st.markdown(input_usuario)

    # Contexto
    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    respuesta_texto = ""
    evento_creado = False
    
    # URL y Headers para llamadas
    url_gen = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
    headers_gen = {'Content-Type': 'application/json'}

    # --- A. AGENDA ---
    if es_personal:
        ahora_peru = get_hora_peru().isoformat()
        sys_agenda = f"""
        Fecha Lima: {ahora_peru}
        Analiza input. Si quiere agendar: {{"agendar": true, "titulo": "...", "inicio": "ISO", "fin": "ISO", "nota_alerta": "..."}}
        Si no: {{"agendar": false}}
        """
        try:
            payload = { "contents": [{"parts": [{"text": sys_agenda}] + (contenido_usuario[0]['parts'] if es_audio else contenido_usuario) }] }
            resp = requests.post(url_gen, headers=headers_gen, data=json.dumps(payload))
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

    # --- B. PERFIL (ESTA ES LA PARTE QUE FALTABA) ---
    if es_personal and not evento_creado and hoja_perfil:
        try:
            sys_perfil = f"""
            Analiza si el usuario dio un dato PERMANENTE nuevo (nombre, gusto, trabajo).
            PERFIL EXISTENTE: "{perfil_texto}"
            Si es nuevo y NO está en el perfil existente, responde SOLO con el dato.
            Si no hay nada nuevo, responde NO.
            """
            payload_p = { "contents": [{"parts": [{"text": sys_perfil}] + (contenido_usuario[0]['parts'] if es_audio else contenido_usuario) }] }
            resp_p = requests.post(url_gen, headers=headers_gen, data=json.dumps(payload_p))
            
            if resp_p.status_code == 200:
                dato_nuevo = resp_p.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                if dato_nuevo and "NO" not in dato_nuevo and len(dato_nuevo) < 200:
                    hoja_perfil.append_row([get_hora_peru().strftime("%Y-%m-%d"), dato_nuevo])
        except: pass

    # --- C. RESPUESTA ---
    if not evento_creado:
        historial = ""
        for m in st.session_state.messages[-40:]:
            historial += f"{m['role']}: {m['content']}\n"
        
        fecha_hum = get_hora_peru().strftime("%A %d de %B del %Y, %H:%M")
        
        if es_personal:
            sys_msg = f"""
            Eres asistente personal leal. NO digas que eres IA.
            PERFIL: {perfil_texto}
            FECHA LIMA: {fecha_hum}
            MEMORIA: {historial}
            """
        else:
            sys_msg = "Responde como Gemini."

        try:
            payload = { "contents": [{"parts": [{"text": sys_msg}] + (contenido_usuario[0]['parts'] if es_audio else contenido_usuario) }] }
            resp = requests.post(url_gen, headers=headers_gen, data=json.dumps(payload))
            if resp.status_code == 200:
                respuesta_texto = resp.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                respuesta_texto = f"Error {resp.status_code}"
        except Exception as e:
            respuesta_texto = f"Error: {e}"

    # --- D. MOSTRAR ---
    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)
        
        if es_audio:
            audio_fp = texto_a_audio(respuesta_texto)
            if audio_fp:
                st.audio(audio_fp, format='audio/mp3')
            
        st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
        
        if hoja_chat:
            try:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                guardar_input = "[Audio]" if es_audio else input_usuario
                hoja_chat.append_row([timestamp, "user", guardar_input]) 
                hoja_chat.append_row([timestamp, "assistant", respuesta_texto])
            except: pass
