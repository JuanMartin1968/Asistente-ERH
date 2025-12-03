import streamlit as st
import google.generativeai as genai

# --- CONFIGURACIÓN DE PÁGINA Y DISEÑO MORADO ---
st.set_page_config(page_title="Mi Asistente Personal", page_icon="💜")

# CSS personalizado para forzar el modo oscuro/morado
st.markdown("""
<style>
    /* Fondo principal */
    .stApp {
        background-color: #1a0b2e;
        color: #e0d4fc;
    }
    /* Barras laterales */
    [data-testid="stSidebar"] {
        background-color: #110022;
    }
    /* Botones y inputs */
    .stTextInput > div > div > input {
        background-color: #2d1b4e;
        color: white;
    }
    .stButton > button {
        background-color: #7b2cbf;
        color: white;
        border: none;
        border-radius: 10px;
    }
    /* Títulos */
    h1, h2, h3 {
        color: #9d4edd !important;
    }
</style>
""", unsafe_allow_html=True)

# --- MENÚ LATERAL: EL BOTÓN DE MODO ---
with st.sidebar:
    st.header("⚙️ Configuración")
    st.write("Elige con quién quieres hablar:")
    # Aquí está el botón dual que pediste
    modo = st.radio(
        "Modo de consulta:",
        ["💜 Mi Asistente (Aprende de mí)", "✨ Gemini (Consulta General)"]
    )

    # Campo para poner la clave (esto lo haremos automático después)
    api_key = st.text_input("Pega tu API Key de Gemini aquí:", type="password")

# --- LÓGICA DEL CEREBRO ---
st.title("💜 Tu Espacio Personal")

if api_key:
    # Conectamos con Gemini
    genai.configure(api_key=api_key)

    # Inicializar el historial del chat si no existe
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostrar mensajes anteriores en pantalla
    for message in st.session_state.messages:
        role = "user" if message["role"] == "user" else "assistant"
        avatar = "👤" if role == "user" else (
            "💜" if message.get("mode") == "personal" else "✨")
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # --- CAPTURAR TU MENSAJE ---
    if prompt := st.chat_input("Escribe aquí..."):
        # 1. Guardar y mostrar tu mensaje
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # 2. Preparar la respuesta según el botón que elegiste
        with st.chat_message("assistant", avatar="💜" if modo == "💜 Mi Asistente (Aprende de mí)" else "✨"):
            message_placeholder = st.empty()

            try:
                model = genai.GenerativeModel('gemini-1.5-flash')

                if "Asistente" in modo:
                    # Lógica de Personalización
                    # Aquí le decimos que actúe como TU asistente
                    instruccion_sistema = f"""
                    Eres un asistente personal altamente inteligente y cariñoso.
                    Tu diseño es de tonos morados, así que usa emojis morados (💜, 🟣, 👾) frecuentemente.
                    Tu objetivo es aprender del usuario. Si el usuario te cuenta algo sobre su vida, guárdalo mentalmente para usarlo en el futuro.
                    """
                    full_prompt = f"{instruccion_sistema}\n\nUsuario dice: {prompt}"
                    response = model.generate_content(full_prompt)
                    bot_reply = response.text

                    # (Más adelante aquí agregaremos el código para guardar en Google Sheets)

                else:
                    # Lógica de Gemini Puro
                    full_prompt = f"Responde como una IA útil y objetiva de Google llamada Gemini.\n\nUsuario: {prompt}"
                    response = model.generate_content(full_prompt)
                    bot_reply = response.text

                # Mostrar respuesta
                message_placeholder.markdown(bot_reply)

                # Guardar en historial
                st.session_state.messages.append({
                    "role": "model",
                    "content": bot_reply,
                    "mode": "personal" if "Asistente" in modo else "gemini"
                })

            except Exception as e:
                st.error(f"Error: {e}")
else:
    st.warning(
        "⚠️ Por favor, introduce tu API Key en el menú lateral para comenzar.")
