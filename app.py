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
    /* DERECHA */
    .stApp { background-color: #FAF5FF !important; color: #000000 !important; }
    .stMarkdown p, h1, h2, h3, div, span, li, label { color: #000000 !important; }
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


def crear_evento_calendario(creds, resumen, inicio_iso, fin_iso, nota_alerta=""):
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
        creado = service.events().insert(calendarId=TU_EMAIL_GMAIL, body=evento).execute()
        return True, creado.get('htmlLink')
    except Exception as e:
        return False, str(e)


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
        # Cargar Chat y Perfil
        if not st.session_state.messages:
            try:
                registros = hoja_chat.get_all_records()
                for r in registros[-40:]:
                    r_low = {k.lower(): v for k, v in r.items()}
                    msg = str(r_low.get("mensaje", "")).strip()
                    if msg:
                        role = "user" if r_low.get(
                            "rol", "model").lower() == "user" else "model"
                        st.session_state.messages.append(
                            {"role": role, "content": msg, "mode": "personal"})
            except:
                pass
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
    if estado_memoria == "Conectada":
        st.success("🧠 Memoria Conectada")
    else:
        st.error("⚠️ Memoria Desconectada")

st.title("Tu Espacio")

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
            INSTRUCCIONES: Eres un asistente personal leal. NO digas que eres IA.
            HORA OFICIAL PERÚ (UTC-5): {hora_peru_str}
            PERFIL USUARIO: {perfil_texto}
            MEMORIA RECIENTE: {historial}
            """
        else:
            sys_context = "Responde como Gemini."

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}

            # --- CONSTRUCCIÓN DEL PAYLOAD CORREGIDO ---
            if es_audio:
                # Caso Audio: Multi-part (Instrucción de texto + Audio binario)
                bytes_data = audio_wav.getvalue()
                b64_audio = base64.b64encode(bytes_data).decode('utf-8')

                payload_parts = [
                    {"text": sys_context +
                        "\n---\nTranscribe el audio EXACTAMENTE, luego procede con la respuesta."},
                    {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
                ]
                payload = {"contents": [{"parts": payload_parts}]}

            else:
                # Caso Texto: Single-part (Instrucción de texto + Texto del usuario)
                payload_parts = [
                    {"text": sys_context},
                    {"text": "USUARIO: " + prompt_texto}
                ]
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
                # Guardamos el mensaje que se mostró en el historial
                hoja_chat.append_row([timestamp, "user", input_usuario])
                hoja_chat.append_row([timestamp, "assistant", respuesta_texto])
            except:
                pass
