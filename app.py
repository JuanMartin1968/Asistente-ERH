import streamlit as st
import requests
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- ESTÉTICA (Tus colores exactos) ---
st.markdown("""
<style>
    /* 1. DERECHA: Fondo casi blanco, Letras NEGRAS */
    .stApp {
        background-color: #FAF5FF !important;
        color: #000000 !important;
    }
    
    /* Forzar negro en todos los textos de la derecha */
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown li {
        color: #000000 !important;
    }

    /* 2. IZQUIERDA: Fondo Oscuro, Letras BLANCAS */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e !important;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    /* 3. INPUTS Y CHAT */
    /* Input: Fondo blanco, borde morado suave, letra negra */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #D1C4E9 !important;
    }
    
    /* Botón */
    .stButton > button {
        background-color: #6A1B9A !important;
        color: white !important;
        border: none !important;
    }
    
    /* Burbujas del chat: Fondo claro, texto negro */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.85) !important;
        border: 1px solid #E1BEE7 !important;
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- RECUPERAR LLAVE ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
except:
    api_key = None

# --- MENÚ LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])

# --- ÁREA DE CHAT ---
st.title("Tu Espacio")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- FUNCIÓN DE FUERZA BRUTA (La Solución) ---
def intentar_generar(prompt_texto, key):
    # Lista de modelos a probar en orden
    modelos = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    
    errores = []
    
    for modelo in modelos:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={key}"
            headers = {'Content-Type': 'application/json'}
            data = {"contents": [{"parts": [{"text": prompt_texto}]}]}
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                # ¡ÉXITO!
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                errores.append(f"{modelo}: {response.status_code}")
                continue # Intenta el siguiente modelo
        except:
            continue

    # Si llega aquí, fallaron los 3
    return f"Error total. Fallaron todos los modelos. Detalles: {', '.join(errores)}"

# --- INTERACCIÓN ---
if prompt := st.chat_input("Escribe aquí..."):
    if not api_key:
        st.error("Falta API Key.")
        st.stop()

    # Usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Preparar Prompt
    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"

    if es_personal:
        final_prompt = f"Eres un asistente personal útil y directo. Tu estética es morada.\n\nUsuario: {prompt}"
    else:
        final_prompt = f"Responde como Gemini.\n\nUsuario: {prompt}"

    # Asistente
    with st.chat_message("assistant", avatar=avatar_bot):
        placeholder = st.empty()
        placeholder.markdown("...")
        
        # Llamamos a la función que prueba todos los modelos
        respuesta_texto = intentar_generar(final_prompt, api_key)
        
        if "Error total" in respuesta_texto:
            placeholder.error(respuesta_texto)
        else:
            placeholder.markdown(respuesta_texto)
            st.session_state.messages.append({"role": "model", "content": respuesta_texto, "mode": tag_modo})
