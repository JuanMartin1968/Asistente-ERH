import streamlit as st
import requests
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO EXACTO (TU PEDIDO: DERECHA CLARA / IZQUIERDA OSCURA) ---
st.markdown("""
<style>
    /* 1. LADO DERECHO: Fondo claro, letras NEGRAS */
    .stApp {
        background-color: #FAF5FF !important;
        color: #000000 !important;
    }
    .stMarkdown p, h1, h2, h3, div, span, li {
        color: #000000 !important;
    }

    /* 2. LADO IZQUIERDO: Fondo Oscuro, letras BLANCAS */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e !important;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    /* 3. INPUTS */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #D1C4E9 !important;
    }
    .stButton > button {
        background-color: #6A1B9A !important;
        color: white !important;
        border: none !important;
    }
    
    /* 4. BURBUJAS */
    .stChatMessage {
        background-color: #FFFFFF !important;
        border: 1px solid #E1BEE7 !important;
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- RECUPERAR LLAVE ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
except:
    st.error("⚠️ Error: No encuentro la API Key en Secrets.")
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])

# --- CHAT ---
st.title("Tu Espacio")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- CONEXIÓN DIRECTA ---
if prompt := st.chat_input("Escribe aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"

    if es_personal:
        final_prompt = f"Eres un asistente personal útil, directo y amable.\n\nUsuario: {prompt}"
    else:
        final_prompt = f"Responde como Gemini.\n\nUsuario: {prompt}"

    with st.chat_message("assistant", avatar=avatar_bot):
        placeholder = st.empty()
        placeholder.markdown("...")
        
        try:
            # URL DEL MODELO
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": final_prompt}]}] }
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                texto = response.json()['candidates'][0]['content']['parts'][0]['text']
                placeholder.markdown(texto)
                st.session_state.messages.append({"role": "model", "content": texto, "mode": tag_modo})
            else:
                # AQUÍ ESTÁ EL CAMBIO: Muestra el mensaje REAL de Google
                error_msg = response.text
                placeholder.error(f"Error {response.status_code} de Google: {error_msg}")
                st.error("👇 Pista: Si dice 'API not enabled', copia el enlace que sale ahí y pégalo en tu navegador.")
        except Exception as e:
            placeholder.error(f"Error de conexión: {e}")
