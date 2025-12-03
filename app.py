import streamlit as st
import requests
import json
import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

# --- 1. DATOS DEL USUARIO ---
TU_EMAIL_GMAIL = "juanjesusmartinsr@gmail.com"

# --- 2. CONFIGURACIÓN VISUAL ---
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
</style>
""", unsafe_allow_html=True)

# --- 3. CONEXIÓN SEGURA ---
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

# --- FUNCIÓN CALENDARIO "AGRESIVA" ---
def crear_evento_calendario(creds, resumen, inicio_iso, fin_iso, minutos_alerta):
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        # Lógica reforzada: Siempre forzamos el override si hay minutos
        reminders = {
            'useDefault': False, # OBLIGAMOS a ignorar el default de 30 min
            'overrides': [
                {'method': 'popup', 'minutes': int(minutos_alerta)}
            ]
        }

        evento = {
            'summary': resumen,
            'start': {'dateTime': inicio_iso, 'timeZone': 'America/Lima'}, 
            'end': {'dateTime': fin_iso, 'timeZone': 'America/Lima'},
            'reminders': reminders
        }
        service.events().insert(calendarId=TU_EMAIL_GMAIL, body=evento).execute()
        return True, "Agendado"
    except Exception as e:
        return False, str(e)

# --- 4. CEREBRO Y AUTODETECCIÓN ---
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
hoja = None
estado_memoria = "Desconectada"

if creds:
    hoja = conectar_memoria(creds)
    if hoja:
        estado_memoria = "Conectada"
        if not st.session_state.messages:
            try:
                registros = hoja.get_all_records()
                for r in registros:
                    r_low = {k.lower(): v for k, v in r.items()}
                    msg = str(r_low.get("mensaje", "")).strip()
                    if msg:
                        rol_orig = r_low.get("rol", "model").lower()
                        role = "user" if rol_orig == "user" else "model"
                        st.session_state.messages.append({"role": role, "content": msg, "mode": "personal"})
            except: pass

# --- 6. BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    st.write("---")
    if estado_memoria == "Conectada":
        st.success("🧠 Memoria Conectada")
    else:
        st.error("⚠️ Memoria Desconectada")

# --- 7. CHAT UI ---
st.title("Tu Espacio")

for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- 8. PROCESAMIENTO ---
if prompt := st.chat_input("Escribe aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    if hoja:
        try:
            timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
            hoja.append_row([timestamp, "user", prompt])
        except: pass

    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    respuesta_texto = ""
    evento_creado = False

    # A. INTENTO DE AGENDAR
    if es_personal:
        ahora_peru = get_hora_peru().isoformat()
        
        prompt_analisis = f"""
        Fecha/Hora actual en Lima, Perú: {ahora_peru}
        Usuario dice: "{prompt}"
        
        Analiza si quiere agendar.
        Si menciona alerta (ej: "avísame 10 min antes"), pon el NÚMERO entero en "alerta_minutos".
        Si no dice alerta, pon 15.
        
        Responde SOLO JSON: 
        {{"agendar": true/false, "titulo": "...", "inicio": "ISO", "fin": "ISO", "alerta_minutos": 15}}
        """
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": prompt_analisis}]}] }
            resp = requests.post(url, headers=headers, data=json.dumps(data))
            
            if resp.status_code == 200:
                texto_json = resp.json()['candidates'][0]['content']['parts'][0]['text']
                texto_json = texto_json.replace("```json", "").replace("```", "").strip()
                datos = json.loads(texto_json)

                if datos.get("agendar"):
                    with st.spinner("Agendando..."):
                        # Convertimos a entero y usamos valor absoluto para evitar negativos
                        minutos = abs(int(datos.get("alerta_minutos", 15)))
                        exito, info = crear_evento_calendario(creds, datos["titulo"], datos["inicio"], datos["fin"], minutos)
                        if exito:
                            respuesta_texto = f"✅ Agendado: **{datos['titulo']}**\n🔔 Alerta configurada: **{minutos} minutos antes**"
                        else:
                            respuesta_texto = f"❌ Error calendario: {info}"
                        evento_creado = True
        except: pass

    # B. RESPUESTA NORMAL
    if not evento_creado:
        historial = ""
        for m in st.session_state.messages[-40:]:
            historial += f"{m['role']}: {m['content']}\n"
        
        fecha_humana = get_hora_peru().strftime("%A %d de %B del %Y, %H:%M")
        
        if es_personal:
            final = f"""
            INSTRUCCIONES: Eres un asistente personal leal.
            NO digas que eres un modelo de lenguaje.
            
            TIEMPO EN LIMA: {fecha_humana}
            MEMORIA: {historial}
            USUARIO: {prompt}
            """
        else:
            final = f"Responde como Gemini.\n\nUsuario: {prompt}"
            
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": final}]}] }
            resp = requests.post(url, headers=headers, data=json.dumps(data))
            
            if resp.status_code == 200:
                respuesta_texto = resp.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                respuesta_texto = f"Error {resp.status_code}: {resp.text}"
        except Exception as e:
            respuesta_texto = f"Error: {e}"

    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)
        st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
        if hoja:
            try:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                hoja.append_row([timestamp, "assistant", respuesta_texto])
            except: pass
