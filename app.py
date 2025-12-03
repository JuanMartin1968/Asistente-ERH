import streamlit as st
import requests
import json
import gspread
import datetime
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

# MODIFICADO: Conecta a AMBAS hojas (Chat y Perfil)
def conectar_hojas(creds):
    try:
        client = gspread.authorize(creds)
        spreadsheet = client.open("Memoria_Asistente")
        # Hoja 1 para el chat diario
        hoja_chat = spreadsheet.sheet1
        # Hoja 'Perfil' para datos permanentes
        try:
            hoja_perfil = spreadsheet.worksheet("Perfil")
        except:
            hoja_perfil = None # Si no existe la pestaña, no fallamos, solo la ignoramos
        return hoja_chat, hoja_perfil
    except: return None, None

def crear_evento_calendario(creds, resumen, inicio_iso, fin_iso, nota_alerta=""):
    try:
        service = build('calendar', 'v3', credentials=creds)
        # Google suele ignorar overrides en cuentas gratuitas, pero lo intentamos
        reminders = {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 10}]}
        
        description = f"Agendado por tu Asistente.\n{nota_alerta}"
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

# --- 3. CEREBRO ---
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

def consultar_llm(prompt_txt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_activo}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        data = { "contents": [{"parts": [{"text": prompt_txt}]}] }
        resp = requests.post(url, headers=headers, data=json.dumps(data))
        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    return "Error de conexión."

# --- 4. INICIALIZACIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []

creds = obtener_credenciales()
hoja_chat, hoja_perfil = None, None
estado_memoria = "Desconectada"
datos_perfil_texto = ""

if creds:
    hoja_chat, hoja_perfil = conectar_hojas(creds)
    if hoja_chat:
        estado_memoria = "Conectada"
        # Cargar Chat Reciente
        if not st.session_state.messages:
            try:
                registros = hoja_chat.get_all_records()
                # Leemos los últimos 50 para no saturar
                for r in registros[-50:]:
                    r_low = {k.lower(): v for k, v in r.items()}
                    msg = str(r_low.get("mensaje", "")).strip()
                    if msg:
                        role = "user" if r_low.get("rol", "model").lower() == "user" else "model"
                        st.session_state.messages.append({"role": role, "content": msg, "mode": "personal"})
            except: pass
        
        # Cargar Perfil Permanente
        if hoja_perfil:
            try:
                # Leemos todo el perfil, son datos clave
                vals = hoja_perfil.get_all_values()
                # Convertimos la lista de listas en texto plano
                for fila in vals:
                    datos_perfil_texto += " ".join(fila) + "\n"
            except: pass

# --- 5. UI ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    st.write("---")
    if estado_memoria == "Conectada":
        st.success("🧠 Memoria Conectada")
    else:
        st.error("⚠️ Memoria Desconectada")

st.title("Tu Espacio")

for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- 6. PROCESAMIENTO ---
if prompt := st.chat_input("Escribe aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Guardar Chat en Hoja 1
    if hoja_chat:
        try:
            timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
            hoja_chat.append_row([timestamp, "user", prompt])
        except: pass

    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    respuesta_texto = ""
    evento_creado = False

    if es_personal:
        # 1. Análisis de Agenda
        ahora_peru = get_hora_peru().isoformat()
        prompt_agenda = f"""
        Fecha/Hora Lima: {ahora_peru}
        Usuario: "{prompt}"
        Si quiere agendar, responde SOLO JSON: {{"agendar": true, "titulo": "...", "inicio": "ISO", "fin": "ISO", "nota_alerta": "..."}}
        Si no, {{"agendar": false}}
        """
        resp_agenda = consultar_llm(prompt_agenda)
        if "agendar" in resp_agenda:
            try:
                resp_agenda = resp_agenda.replace("```json", "").replace("```", "").strip()
                datos = json.loads(resp_agenda)
                if datos.get("agendar"):
                    with st.spinner("Agendando..."):
                        exito, link = crear_evento_calendario(creds, datos["titulo"], datos["inicio"], datos["fin"], datos.get("nota_alerta", ""))
                        if exito:
                            respuesta_texto = f"✅ **{datos['titulo']}** agendado.\n[Editar evento o alerta]({link})"
                        else:
                            respuesta_texto = f"❌ Error calendario: {link}"
                        evento_creado = True
            except: pass

        # 2. Análisis de Perfil (Guardar datos nuevos)
        if hoja_perfil:
            # Pedimos a la IA que extraiga datos permanentes
            prompt_perfil = f"""
            Analiza si el usuario dijo algo permanente sobre sí mismo (nombre, gustos, trabajo, familia, preferencias).
            Usuario: "{prompt}"
            Si hay un dato nuevo, responde SOLO con el dato (ej: "Usuario prefiere Excel sobre Sheets"). 
            Si no hay datos nuevos importantes, responde "NO".
            """
            dato_nuevo = consultar_llm(prompt_perfil)
            if dato_nuevo and "NO" not in dato_nuevo and len(dato_nuevo) < 200:
                try:
                    hoja_perfil.append_row([get_hora_peru().strftime("%Y-%m-%d"), dato_nuevo])
                except: pass

    if not evento_creado:
        # 3. Respuesta Normal
        historial = ""
        for m in st.session_state.messages[-40:]:
            historial += f"{m['role']}: {m['content']}\n"
        
        fecha_humana = get_hora_peru().strftime("%A %d de %B del %Y, %H:%M")
        
        if es_personal:
            final = f"""
            Eres un asistente personal leal. NO eres una IA genérica.
            
            DATOS CLAVE DEL USUARIO (PERFIL):
            {datos_perfil_texto}
            
            CONTEXTO:
            Fecha: {fecha_humana} (Lima)
            
            MEMORIA RECIENTE:
            {historial}
            
            USUARIO: {prompt}
            """
        else:
            final = f"Responde como Gemini.\n\nUsuario: {prompt}"
            
        respuesta_texto = consultar_llm(final)

    with st.chat_message("assistant", avatar=avatar_bot):
        st.markdown(respuesta_texto)
        st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
        if hoja_chat:
            try:
                timestamp = get_hora_peru().strftime("%Y-%m-%d %H:%M:%S")
                hoja_chat.append_row([timestamp, "assistant", respuesta_texto])
            except: pass
