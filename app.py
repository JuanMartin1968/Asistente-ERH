import streamlit as st
import requests
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO ---
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

# --- 1. CONEXIÓN A MEMORIA (NUEVO MÉTODO) ---
def conectar_memoria():
    try:
        # AQUI ESTA LA CLAVE: Leemos el bloque de texto que pegaste
        json_text = st.secrets["GOOGLE_CREDENTIALS"]
        creds_dict = json.loads(json_text)
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # IMPORTANTE: El nombre de la hoja debe ser EXACTO
        sheet = client.open("Memoria_Asistente").sheet1
        return sheet
    except Exception as e:
        # Si falla, guardamos el error exacto para mostrártelo
        st.session_state.error_memoria = str(e)
        return None

# --- 2. RECUPERAR LLAVE GEMINI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
except:
    st.error("⚠️ Error: Falta GEMINI_API_KEY en Secrets.")
    st.stop()

# --- 3. DETECTOR DE MODELO ---
@st.cache_data
def obtener_mejor_modelo(key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            modelos = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            return modelos[0] if modelos else "models/gemini-1.5-flash"
    except:
        pass
    return "models/gemini-1.5-flash"

modelo_actual = obtener_mejor_modelo(api_key)

# --- INICIALIZACIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.error_memoria = None
    
    # Cargar historial
    hoja = conectar_memoria()
    if hoja:
        try:
            registros = hoja.get_all_records()
            for r in registros:
                if r.get("mensaje"):
                    role = "user" if r.get("rol") == "user" else "model"
                    st.session_state.messages.append({
                        "role": role,
                        "content": str(r.get("mensaje")),
                        "mode": "personal"
                    })
        except:
            pass

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    
    st.write("---")
    # Diagnóstico
    if st.session_state.get("error_memoria"):
        st.error(f"❌ Error: {st.session_state.error_memoria}")
    else:
        st.success("🧠 Memoria Conectada")

# --- ÁREA DE CHAT ---
st.title("Tu Espacio")

for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- ENVÍO ---
if prompt := st.chat_input("Escribe aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Guardar en Memoria
    hoja = conectar_memoria()
    if hoja:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hoja.append_row([timestamp, "user", prompt])
        except:
            pass

    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"
    
    texto_final = f"Eres un asistente personal útil. Usuario: {prompt}" if es_personal else f"Responde como Gemini. Usuario: {prompt}"

    with st.chat_message("assistant", avatar=avatar_bot):
        placeholder = st.empty()
        placeholder.markdown("...")
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_actual}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": texto_final}]}] }
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                texto = response.json()['candidates'][0]['content']['parts'][0]['text']
                placeholder.markdown(texto)
                st.session_state.messages.append({"role": "model", "content": texto, "mode": tag_modo})
                
                if hoja:
                    try:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        hoja.append_row([timestamp, "assistant", texto])
                    except:
                        pass
            else:
                placeholder.error(f"Error {response.status_code}")
        except Exception as e:
            placeholder.error(f"Error: {e}")
