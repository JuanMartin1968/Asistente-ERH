import streamlit as st
import google.generativeai as genai

# --- CONFIGURACIÓN DE PÁGINA Y DISEÑO MINIMALISTA CÁLIDO ---
st.set_page_config(page_title="Mi Espacio Personal", page_icon="🟣", layout="wide")

# CSS PROFESIONAL Y MINIMALISTA
st.markdown("""
<style>
    /* --- ÁREA PRINCIPAL (DERECHA) - MORADO CÁLIDO --- */
    .stApp {
        background-color: #dac7ed; /* Morado cálido profundo */
        color: #ECDAEF; /* Texto claro y cálido */
    }

    /* --- BARRA LATERAL (IZQUIERDA) - OSCURO --- */
    [data-testid="stSidebar"] {
        background-color: #5D3A68; /* El tono oscuro original */
        border-right: 1px solid rgba(255,255,255,0.1); /* Separador sutil */
    }
    /* Texto sutil en sidebar */
    [data-testid="stSidebar"] .stMarkdown {
        color: #BFA5CC;
    }

    /* --- ELEMENTOS DE INTERFAZ --- */
    /* Títulos minimalistas (más finos) */
    h1, h2, h3 {
        color: #F3E5F5 !important;
        font-family: sans-serif;
        font-weight: 300 !important; /* Letra fina moderna */
    }

    /* Inputs (Cajas de texto) */
    .stTextInput > div > div > input {
        background-color: rgba(255,255,255,0.08); /* Translúcido */
        color: white;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
    }

    /* Botones minimalistas */
    .stButton > button {
        background-color: #9E47C1; /* Morado cálido vibrante */
        color: white;
        border: none;
        border-radius: 20px; /* Más redondeado */
        padding: 0.5rem 1.2rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #B96BD6; /* Más brillante al tocar */
        box-shadow: 0 4px 12px rgba(158, 71, 193, 0.3);
    }
    
    /* Radio Buttons (Selector de modo) */
    [data-testid="stRadio"] label {
        font-weight: 500;
        color: #ECDAEF !important;
    }

    /* Burbujas de chat */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        padding: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- AUTENTICACIÓN AUTOMÁTICA (Lee el secreto) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = None

# --- MENÚ LATERAL ---
with st.sidebar:
    st.title("⚙️ Panel")
    st.write("---")
    modo = st.radio("Selecciona tu modo:", ["🟣 Asistente Personal", "✨ Gemini (General)"])
    st.write("---")
    
    if not api_key:
        st.error("⚠️ No se encontró la llave en Secrets.")
        st.info("Por favor, configúrala en el panel de Streamlit Cloud.")

# --- LÓGICA PRINCIPAL ---
st.header("Tu Espacio Creativo")
st.caption("Conversa en un entorno cálido y minimalista.")

if api_key:
    genai.configure(api_key=api_key)
    
    # Historial
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        role = "user" if message["role"] == "user" else "assistant"
        # Iconos personalizados según el modo en que se generó el mensaje
        msg_mode = message.get("mode", "gemini")
        avatar = "👤" if role == "user" else ("🟣" if msg_mode == "personal" else "✨")
        
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # Input
    if prompt := st.chat_input("Escribe tu idea aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        current_mode_tag = "personal" if "Asistente" in modo else "gemini"
        avatar_bot = "🟣" if current_mode_tag == "personal" else "✨"

        with st.chat_message("assistant", avatar=avatar_bot):
            message_placeholder = st.empty()
            message_placeholder.markdown("Thinking...")
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                if current_mode_tag == "personal":
                    # Prompt del Asistente Cálido
                    sys_prompt = """Eres un asistente personal avanzado, con una personalidad cálida, amable y eficiente, similar a la estética minimalista y morada de tu interfaz. 
                    Usa emojis morados o cálidos (🟣, 👾, ✨, 💡) ocasionalmente. Tu objetivo es aprender del usuario y asistirle de forma cercana."""
                    full_prompt = f"{sys_prompt}\n\nUsuario: {prompt}"
                else:
                    # Prompt de Gemini General
                    full_prompt = f"Responde objetiva y útilmente como la IA Gemini de Google.\n\nUsuario: {prompt}"
                
                response = model.generate_content(full_prompt)
                bot_reply = response.text
                message_placeholder.markdown(bot_reply)
                
                st.session_state.messages.append({
                    "role": "model", 
                    "content": bot_reply, 
                    "mode": current_mode_tag
                })
            except Exception as e:
                message_placeholder.error(f"Error de conexión: {e}")
else:
    st.info("👈 Esperando configuración de API Key en la barra lateral.")

