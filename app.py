import streamlit as st
import requests
import json
import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

# --- 1. DATOS DE USUARIO ---
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
</style>
""", unsafe_allow_html=True)

# --- 3. FUNCIONES DE CONEXIÓN ---
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
        return client.open("Memoria_Asistente").sheet1
    except: return None

def crear_evento_calendario(creds, resumen, inicio_iso, fin_iso):
    try:
        service = build('calendar', 'v3', credentials=creds)
        evento = {
            'summary': resumen,
            'start': {'dateTime': inicio_iso, 'timeZone': 'America/Lima'}, 
            'end': {'dateTime': fin_iso, 'timeZone': 'America/Lima'},
        }
        service.events().insert(calendarId=TU_EMAIL_GMAIL, body=evento).execute()
        return True, "Agendado"
    except Exception as e:
        return False, str(e)

# --- 4. FUNCIÓN ROBUSTA ANTI-ERROR 404 ---
# Esta función prueba múltiples modelos si uno falla
def llamar_gemini_seguro(prompt_texto, api_key):
    # Lista de modelos a probar en orden de preferencia
    modelos = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
        "gemini-pro"
    ]
    
    ultimo_error = ""
    
    for modelo in modelos:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": prompt_texto}]}] }
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                # Si funciona, devolvemos el texto y salimos del bucle
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                ultimo_error = f"{modelo} dio error {response.status_code}"
                continue # Si falla, intenta el siguiente modelo de la lista
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    # Si llega aquí, fallaron todos
    return f"Error de conexión: {ultimo_error}"

# --- 5. INICIALIZACIÓN ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
except:
    st.error("Falta API Key")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
    creds = obtener_credenciales()
    if creds:
        hoja = conectar_memoria(creds)
        if hoja:
            try:
                registros = hoja.get_all_records()
                for r in registros:
                    msg = str(r.get("mensaje", "")).strip()
                    if msg:
                        role = "user" if r.get("rol") == "user" else "model"
                        st.session_state.messages.append({"role": role, "content": msg, "mode": "personal"})
            except: pass

# --- 6. UI ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])

st.title("Tu Espacio")

for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- 7. PROCESAMIENTO ---
if prompt := st.chat_input("Escribe aquí..."):
    # Guardar usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    creds = obtener_credenciales()
    hoja = None
    if creds: hoja = conectar_memoria(creds)
    
    if hoja:
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hoja.append_row([timestamp, "user", prompt])
        except: pass

    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    respuesta_texto = ""
    evento_creado = False

    # A. INTENTO DE AGENDAR
    if es_personal:
        prompt_analisis = f"""
        Fecha actual: {datetime.datetime.now().isoformat()}
        Usuario dice: "{prompt}"
        Responde SOLO JSON: {{"agendar": true/false, "titulo": "...", "inicio": "YYYY-MM-DDTHH:MM:SS", "fin": "YYYY-MM-DDTHH:MM:SS"}}
        """
        # Usamos la función segura que prueba varios modelos
        texto_analisis = llamar_gemini_seguro(prompt_analisis, api_key)
        
        if "Error" not in texto_analisis:
            try:
                texto_analisis = texto_analisis.replace("```json", "").replace("```", "").strip()
                datos = json.loads(texto_analisis)

                if datos.get("agendar"):
                    with st.spinner("Agendando..."):
                        exito, info = crear_evento_calendario(creds, datos["titulo"], datos["inicio"], datos["fin"])
                        if exito:
                            respuesta_texto = f"✅ Agendado: **{datos['titulo']}**"
                        else:
                            respuesta_texto = f"❌ Error calendario: {info}"
                        evento_creado = True
            except: pass

    # B. RESPUESTA NORMAL
    if not evento_creado:
        historial = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]])
        if es_personal:
            final = f"Eres un asistente personal útil. Memoria reciente:\n{historial}\n\nUsuario: {prompt}"
        else:
            final = f"Responde como Gemini.\n\nUsuario: {prompt}"
            
        respuesta_texto = llamar_gemini_seguro(final, api_key)

    # Mostrar y Guardar
    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)
        st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
        if hoja:
            try:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                hoja.append_row([timestamp, "assistant", respuesta_texto])
            except: pass
