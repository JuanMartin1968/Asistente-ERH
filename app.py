import streamlit as st
import requests
import json

# Configuración
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO CORREGIDO (LADO DERECHO CLARO / LADO IZQUIERDO OSCURO) ---
st.markdown("""
<style>
    /* 1. LADO DERECHO (Área Principal) - Morado MUY pálido, casi blanco */
    .stApp {
        background-color: #FAF5FF; /* Morado súper bajo */
        color: #000000;            /* Letras NEGRAS */
    }

    /* 2. LADO IZQUIERDO (Barra Lateral) - Oscuro */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e; /* Fondo Oscuro */
    }
    /* Letras del lado izquierdo BLANCAS */
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    
    /* 3. INPUTS Y BOTONES */
    /* Caja de texto del usuario (Fondo blanco, letras negras) */
    .stTextInput > div > div > input {
        background-color: #FFFFFF;
        color: #000000;
        border: 1px solid #D1C4E9;
    }
    
    /* Botón de envío */
    .stButton > button {
        background-color: #6A1B9A;
        color: white;
        border: none;
    }

    /* Títulos en negro para el fondo claro */
    h1, h2, h3 { color: #000000 !important; }
    
    /* Burbujas de chat */
    .stChatMessage {
        background-color: rgba(255,255,255,0.7);
        border: 1px solid #E1BEE7;
        color: #000000;
    }
    /* Texto dentro de las burbujas */
    .stMarkdown p { color: #000000 !important; }
</style>
""", unsafe_allow_html=True)

# --- RECUPERAR CLAVE ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = None

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    if not api_key:
        st.error("⚠️ Falta API Key en Secrets")

# --- ÁREA PRINCIPAL ---
st.title("Tu Espacio")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar historial
for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- LÓGICA DE CONEXIÓN DIRECTA (SIN LIBRERÍA CON ERROR) ---
if prompt := st.chat_input("Escribe aquí..."):
    if not api_key:
        st.warning("Por favor configura tu API Key.")
        st.stop()

    # 1. Mostrar mensaje usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # 2. Configurar modo
    es_personal = ("Asistente" in modo)
    avatar_bot = "🟣" if es_personal else "✨"
    tag_modo = "personal" if es_personal else "gemini"

    # 3. Preparar Prompt
    if es_personal:
        sistema = "Eres un asistente personal útil y directo. Tu estética es morada."
        texto_final = f"{sistema}\n\nUsuario: {prompt}"
    else:
        texto_final = f"Responde como Gemini.\n\nUsuario: {prompt}"

    # 4. LLAMADA DIRECTA A LA API (Bypassea el error de librería)
    with st.chat_message("assistant", avatar=avatar_bot):
        placeholder = st.empty()
        placeholder.markdown("...")
        
        try:
            # Usamos el endpoint REST directo para evitar errores de versión de Python
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{"parts": [{"text": texto_final}]}]
            }
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                respuesta_json = response.json()
                try:
                    bot_reply = respuesta_json['candidates'][0]['content']['parts'][0]['text']
                    placeholder.markdown(bot_reply)
                    
                    st.session_state.messages.append({
                        "role": "model", 
                        "content": bot_reply, 
                        "mode": tag_modo
                    })
                except:
                    placeholder.error("Error interpretando respuesta.")
            else:
                placeholder.error(f"Error de Google: {response.text}")

        except Exception as e:
            placeholder.error(f"Error de conexión: {e}")
