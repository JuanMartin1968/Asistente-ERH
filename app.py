import streamlit as st
import google.generativeai as genai

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="Mi Asistente", page_icon="🟣", layout="wide")

# --- DISEÑO DE COLORES (TUS PREFERENCIAS) ---
st.markdown("""
<style>
    /* 1. LADO DERECHO (Área Principal) - Morado Cálido Minimalista */
    .stApp {
        background-color: #4A2C5A; /* Un morado cálido, tipo ciruela suave */
        color: #F3E5F5;             /* Texto lila muy claro para contraste */
    }

    /* 2. LADO IZQUIERDO (Menú) - El color oscuro que te gustaba */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e; /* Morado casi negro (el que estaba antes a la derecha) */
        border-right: 1px solid rgba(255,255,255,0.1);
    }

    /* 3. BOTONES Y DETALLES */
    .stButton > button {
        background-color: #8E44AD; /* Un lila vibrante para destacar */
        color: white;
        border-radius: 20px;
        border: none;
    }
    
    /* Cajas de texto más limpias */
    .stTextInput > div > div > input {
        background-color: rgba(0, 0, 0, 0.2); 
        color: white;
        border: 1px solid rgba(255,255,255,0.2);
    }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN AUTOMÁTICA ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = None

# --- BARRA LATERAL (IZQUIERDA) ---
with st.sidebar:
    st.header("Panel de Control")
    modo = st.radio("Elige tu modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    
    if not api_key:
        st.error("⚠️ Falta la API Key en Secrets.")

# --- CHAT PRINCIPAL (DERECHA) ---
st.title("Tu Espacio Personal")

if api_key:
    genai.configure(api_key=api_key)
    
    # Historial
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostrar mensajes
    for message in st.session_state.messages:
        role = message["role"]
        # Iconos: Usuario vs Asistente (según el modo guardado)
        if role == "user":
            avatar = "👤"
        else:
            avatar = "🟣" if message.get("mode") == "personal" else "✨"
            
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # Input Usuario
    if prompt := st.chat_input("Escribe algo..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # Determinar modo actual
        es_personal = ("Asistente" in modo)
        avatar_bot = "🟣" if es_personal else "✨"
        tag_modo = "personal" if es_personal else "gemini"

        with st.chat_message("assistant", avatar=avatar_bot):
            placeholder = st.empty()
            try:
                # CAMBIO IMPORTANTE: Usamos 'gemini-pro' que es 100% compatible
                model = genai.GenerativeModel('gemini-pro')
                
                if es_personal:
                    sys = "Eres un asistente personal cálido, leal y servicial. Tu color es el morado. Responde de forma cercana."
                    full_prompt = f"{sys}\n\nUsuario: {prompt}"
                else:
                    full_prompt = f"Responde como la IA Gemini de Google de forma objetiva.\n\nUsuario: {prompt}"
                
                response = model.generate_content(full_prompt)
                bot_reply = response.text
                
                placeholder.markdown(bot_reply)
                
                # Guardar respuesta
                st.session_state.messages.append({
                    "role": "model", 
                    "content": bot_reply, 
                    "mode": tag_modo
                })
            except Exception as e:
                placeholder.error(f"Error: {e}")
else:
    st.info("Configura tu llave secreta para empezar.")
