import streamlit as st
import requests
import json

# Configuración
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO: LADO DERECHO CLARO (LETRAS NEGRAS) / LADO IZQUIERDO OSCURO (LETRAS BLANCAS) ---
st.markdown("""
<style>
    /* 1. LADO DERECHO (Principal) - Morado casi blanco */
    .stApp {
        background-color: #FAF5FF; 
        color: #000000; /* NEGRO OBLIGATORIO */
    }

    /* 2. LADO IZQUIERDO (Menú) - Oscuro */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e;
    }
    /* Forzar letras blancas en TODO el menú izquierdo */
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    /* 3. INPUTS Y BOTONES */
    /* Caja de texto donde escribes (Fondo blanco, letra negra) */
    .stTextInput > div > div > input {
        background-color: #FFFFFF;
        color: #000000;
        border: 1px solid #D1C4E9;
    }
    
    /* Botón enviar */
    .stButton > button {
        background-color: #6A1B9A;
        color: white;
        border: none;
    }

    /* Títulos y textos del lado derecho en negro */
    h1, h2, h3, p { color: #000000 !important; }
    
    /* Burbujas del chat (Fondo claro, texto negro) */
    .stChatMessage {
        background-color: rgba(255,255,255,0.8);
        border: 1px solid #E1BEE7;
    }
</style>
""", unsafe_allow_html=True)

# --- RECUPERAR CLAVE ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = None

# --- MENÚ IZQUIERDO ---
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

# --- LÓGICA (CONECTADA A GEMINI 1.5 FLASH) ---
if prompt := st.chat_input("Escribe aquí..."):
    if not api_key:
        st.error("Falta la API Key.")
        st.stop()

    # Guardar mensaje usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"

    if es_personal:
        sistema = "Eres un asistente personal útil y directo."
        texto_final = f"{sistema}\n\nUsuario: {prompt}"
    else:
        texto_final = f"Responde como Gemini.\n\nUsuario: {prompt}"

    with st.chat_message("assistant", avatar=avatar_bot):
        placeholder = st.empty()
        placeholder.markdown("...")
        
        try:
            # URL DEL MODELO CORRECTO (1.5 Flash)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": texto_final}]}] }
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                respuesta = response.json()
                texto = respuesta['candidates'][0]['content']['parts'][0]['text']
                placeholder.markdown(texto)
                st.session_state.messages.append({"role": "model", "content": texto, "mode": tag_modo})
            else:
                placeholder.error(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            placeholder.error(f"Error: {e}")
