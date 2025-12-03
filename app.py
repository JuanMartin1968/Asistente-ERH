import streamlit as st
import google.generativeai as genai

# Configuración básica
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO EXACTO SEGÚN TUS INSTRUCCIONES ---
st.markdown("""
<style>
    /* 1. LADO DERECHO (Área Principal) */
    /* Fondo: Morado súper bajo (casi blanco) */
    .stApp {
        background-color: #F8F0FC; 
        color: #000000; /* Letras Negras */
    }

    /* 2. LADO IZQUIERDO (Barra Lateral) */
    /* Fondo: Oscuro (el que te gustaba antes) */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e;
    }
    /* Letras del lado izquierdo: Blancas */
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    /* 3. CAJAS DE TEXTO Y BOTONES */
    /* Input del usuario (Fondo blanco para que resalte en el fondo claro, letras negras) */
    .stTextInput > div > div > input {
        background-color: #FFFFFF;
        color: #000000;
        border: 1px solid #D1C4E9;
    }
    
    /* Botón */
    .stButton > button {
        background-color: #6A1B9A; /* Morado fuerte para destacar */
        color: white;
        border: none;
        border-radius: 8px;
    }

    /* Títulos en el lado derecho (Negros) */
    h1, h2, h3 {
        color: #000000 !important;
    }
    
    /* Burbujas de chat */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.5); /* Sutil transparencia */
        border: 1px solid #E1BEE7;
        border-radius: 10px;
        color: #000000; /* Texto negro en el chat */
    }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = None

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Elige modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    if not api_key:
        st.error("⚠️ Falta API Key en Secrets")

# --- ÁREA PRINCIPAL ---
st.title("Tu Espacio")

if api_key:
    genai.configure(api_key=api_key)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostrar historial
    for message in st.session_state.messages:
        role = message["role"]
        avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # Input
    if prompt := st.chat_input("Escribe aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        es_personal = ("Asistente" in modo)
        avatar_bot = "🟣" if es_personal else "✨"
        tag_modo = "personal" if es_personal else "gemini"

        with st.chat_message("assistant", avatar=avatar_bot):
            placeholder = st.empty()
            placeholder.markdown("...")
            try:
                # Usamos el modelo Flash con la librería actualizada
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                if es_personal:
                    sys = "Eres un asistente personal útil. Responde de forma directa."
                    full_prompt = f"{sys}\n\nUsuario: {prompt}"
                else:
                    full_prompt = f"Responde como Gemini.\n\nUsuario: {prompt}"
                
                response = model.generate_content(full_prompt)
                text_reply = response.text
                placeholder.markdown(text_reply)
                
                st.session_state.messages.append({
                    "role": "model", 
                    "content": text_reply, 
                    "mode": tag_modo
                })
            except Exception as e:
                placeholder.error(f"Error: {e}")
else:
    st.info("Configurando...")
