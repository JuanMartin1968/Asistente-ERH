import streamlit as st
import requests
import json

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO DE COLORES (CORREGIDO Y FORZADO) ---
st.markdown("""
<style>
    /* 1. LADO DERECHO (Área Principal) */
    /* Fondo morado casi blanco (#FAF5FF) y Letras NEGRAS */
    .stApp {
        background-color: #FAF5FF !important;
        color: #000000 !important;
    }
    
    /* Forzar texto negro en párrafos y títulos del lado derecho */
    .stMarkdown p, h1, h2, h3, .stMarkdown, div {
        color: #000000 !important;
    }

    /* 2. LADO IZQUIERDO (Barra Lateral) */
    /* Fondo Oscuro (#1a0b2e) y Letras BLANCAS */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e !important;
    }
    /* Todo el texto de la izquierda en Blanco */
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {
        color: #FFFFFF !important;
    }

    /* 3. INPUTS Y BOTONES */
    /* Caja de texto (Fondo blanco, Letra negra) */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #D1C4E9 !important;
    }
    
    /* Botón (Morado) */
    .stButton > button {
        background-color: #6A1B9A !important;
        color: white !important;
        border: none !important;
    }
    
    /* Burbujas del Chat */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.8) !important;
        border: 1px solid #E1BEE7 !important;
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- RECUPERAR Y LIMPIAR CLAVE ---
try:
    # .strip() elimina espacios invisibles que causan errores 404
    api_key = st.secrets["GEMINI_API_KEY"].strip()
except:
    api_key = None

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])

# --- ÁREA PRINCIPAL ---
st.title("Tu Espacio")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- LÓGICA DE ENVÍO ---
if prompt := st.chat_input("Escribe aquí..."):
    if not api_key:
        st.error("Falta la API Key en Secrets.")
        st.stop()

    # Mostrar usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"

    if es_personal:
        sistema = "Eres un asistente personal útil y directo. Tu estética es morada."
        texto_final = f"{sistema}\n\nUsuario: {prompt}"
    else:
        texto_final = f"Responde como Gemini.\n\nUsuario: {prompt}"

    with st.chat_message("assistant", avatar=avatar_bot):
        placeholder = st.empty()
        placeholder.markdown("...")
        
        try:
            # CAMBIO CRÍTICO: Usamos 'gemini-1.5-flash-latest' que es más robusto
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
            
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": texto_final}]}] }
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                respuesta = response.json()
                if 'candidates' in respuesta:
                    texto = respuesta['candidates'][0]['content']['parts'][0]['text']
                    placeholder.markdown(texto)
                    st.session_state.messages.append({"role": "model", "content": texto, "mode": tag_modo})
                else:
                    placeholder.error("Google respondió vacío. Intenta de nuevo.")
            else:
                placeholder.error(f"Error {response.status_code}: {response.text}")

        except Exception as e:
            placeholder.error(f"Error de conexión: {e}")
