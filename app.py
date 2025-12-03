import streamlit as st
import requests
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO EXACTO (TU PEDIDO) ---
st.markdown("""
<style>
    /* 1. LADO DERECHO: Fondo claro (#FAF5FF), Letras NEGRAS */
    .stApp {
        background-color: #FAF5FF !important;
        color: #000000 !important;
    }
    /* Forzar negro en todos los textos de la derecha */
    .stMarkdown p, h1, h2, h3, div, span, li, label {
        color: #000000 !important;
    }

    /* 2. LADO IZQUIERDO: Fondo Oscuro (#1a0b2e), Letras BLANCAS */
    [data-testid="stSidebar"] {
        background-color: #1a0b2e !important;
    }
    /* Todo el texto de la izquierda en Blanco */
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div, [data-testid="stSidebar"] label {
        color: #FFFFFF !important;
    }

    /* 3. INPUTS Y BOTONES */
    /* Caja de texto (Fondo blanco, Letra negra) */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #D1C4E9 !important;
    }
    /* Selectbox (Lista desplegable) en el sidebar */
    .stSelectbox > div > div {
        background-color: #2d1b4e !important;
        color: white !important;
    }
    
    /* Botón (Morado) */
    .stButton > button {
        background-color: #6A1B9A !important;
        color: white !important;
        border: none !important;
    }
    
    /* Burbujas del Chat */
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

# --- FUNCIÓN: OBTENER MODELOS REALES DISPONIBLES ---
@st.cache_data
def obtener_modelos(key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Filtramos solo los que sirven para generar contenido (chat)
            modelos = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            return modelos
        else:
            return []
    except:
        return []

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    
    # 1. Selector de Modo
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    
    st.write("---")
    st.write("📡 **Modelos detectados en tu llave:**")
    
    # 2. Selector de Modelo Automático
    lista_modelos = obtener_modelos(api_key)
    
    if lista_modelos:
        # Si encontró modelos, deja que el usuario elija uno que SÍ exista
        modelo_seleccionado = st.selectbox("Usa este modelo:", lista_modelos, index=0)
    else:
        st.error("No se encontraron modelos. Tu llave podría estar bloqueada por Google.")
        modelo_seleccionado = "models/gemini-1.5-flash" # Fallback por si acaso

# --- ÁREA PRINCIPAL ---
st.title("Tu Espacio")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- CHAT CON EL MODELO SELECCIONADO ---
if prompt := st.chat_input("Escribe aquí..."):
    # Guardar usuario
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
            # USAMOS EL NOMBRE EXACTO QUE SELECCIONASTE EN LA LISTA
            # Ya no adivinamos. Usamos 'modelo_seleccionado' directamente.
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_seleccionado}:generateContent?key={api_key}"
            
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
                    placeholder.error("Respuesta vacía de Google.")
            else:
                placeholder.error(f"Error {response.status_code}: {response.text}")

        except Exception as e:
            placeholder.error(f"Error de conexión: {e}")
