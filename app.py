import streamlit as st
import requests
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistente Personal", page_icon="🟣", layout="wide")

# --- DISEÑO (TUS COLORES) ---
st.markdown("""
<style>
    /* DERECHA: Fondo claro, letras NEGRAS */
    .stApp { background-color: #FAF5FF !important; color: #000000 !important; }
    .stMarkdown p, h1, h2, h3, div, span, li, label { color: #000000 !important; }
    
    /* IZQUIERDA: Fondo Oscuro, letras BLANCAS */
    [data-testid="stSidebar"] { background-color: #1a0b2e !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* INPUTS */
    .stTextInput > div > div > input { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #D1C4E9 !important; }
    .stButton > button { background-color: #6A1B9A !important; color: white !important; border: none !important; }
    
    /* CHAT */
    .stChatMessage { background-color: #FFFFFF !important; border: 1px solid #E1BEE7 !important; color: #000000 !important; }
</style>
""", unsafe_allow_html=True)

# --- 1. CONEXIÓN A GOOGLE SHEETS (MEMORIA) ---
def conectar_memoria():
    try:
        # Busca las credenciales en los Secrets
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Arreglo común: a veces la private_key en secrets pierde los saltos de línea
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Abre la hoja por su nombre EXACTO
        sheet = client.open("Memoria_Asistente").sheet1
        return sheet
    except Exception as e:
        return None

# --- 2. RECUPERAR LLAVE GEMINI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
except:
    st.error("⚠️ Error: Falta GEMINI_API_KEY en Secrets.")
    st.stop()

# --- 3. DETECTOR DE MODELO (SILENCIOSO) ---
@st.cache_data
def obtener_mejor_modelo(key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            modelos = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            return modelos[0] if modelos else "models/gemini-1.5-flash"
    except:
        pass
    return "models/gemini-1.5-flash"

modelo_actual = obtener_mejor_modelo(api_key)

# --- INICIALIZACIÓN DE MEMORIA ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    
    # Intentar cargar historial antiguo desde Sheets
    hoja = conectar_memoria()
    if hoja:
        try:
            # Leemos todos los registros (excepto encabezado)
            registros = hoja.get_all_records()
            for r in registros:
                # Solo cargamos si hay contenido
                if r.get("mensaje"):
                    role = "user" if r.get("rol") == "user" else "model"
                    # Reconstruimos el formato de chat
                    st.session_state.messages.append({
                        "role": role,
                        "content": r.get("mensaje"),
                        "mode": "personal" # Asumimos histórico como personal por defecto
                    })
        except Exception as e:
            st.warning(f"No pude leer la memoria antigua: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    modo = st.radio("Modo:", ["🟣 Asistente Personal", "✨ Gemini General"])
    
    # Indicador de estado de memoria
    hoja_prueba = conectar_memoria()
    if hoja_prueba:
        st.success("🧠 Memoria conectada")
    else:
        st.error("🧠 Memoria desconectada (Revisa Secrets)")

# --- ÁREA DE CHAT ---
st.title("Tu Espacio")

# Mostrar historial
for message in st.session_state.messages:
    role = message["role"]
    avatar = "👤" if role == "user" else ("🟣" if message.get("mode") == "personal" else "✨")
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])

# --- LÓGICA DE ENVÍO Y GUARDADO ---
if prompt := st.chat_input("Escribe aquí..."):
    # 1. Guardar mensaje usuario en Session State
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # 2. Guardar mensaje usuario en Google Sheets (Memoria)
    hoja = conectar_memoria()
    if hoja:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            hoja.append_row([timestamp, "user", prompt])
        except:
            pass # Si falla guardar, seguimos funcionando

    # 3. Preparar respuesta IA
    es_personal = ("Asistente" in modo)
    tag_modo = "personal" if es_personal else "gemini"
    avatar_bot = "🟣" if es_personal else "✨"

    if es_personal:
        sistema = "Eres un asistente personal útil y directo. Tu estética es morada."
        texto_final = f"{sistema}\n\nUsuario: {prompt}"
    else:
        texto_final = f"Responde como Gemini.\n\nUsuario: {prompt}"

    # 4. Generar respuesta
    with st.chat_message("assistant", avatar=avatar_bot):
        placeholder = st.empty()
        placeholder.markdown("...")
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_actual}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = { "contents": [{"parts": [{"text": texto_final}]}] }
            
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                respuesta = response.json()
                if 'candidates' in respuesta:
                    texto_bot = respuesta['candidates'][0]['content']['parts'][0]['text']
                    placeholder.markdown(texto_bot)
                    
                    # Guardar en Session State
                    st.session_state.messages.append({"role": "model", "content": texto_bot, "mode": tag_modo})
                    
                    # Guardar en Google Sheets (Memoria)
                    if hoja:
                        try:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            hoja.append_row([timestamp, "assistant", texto_bot])
                        except:
                            pass
                else:
                    placeholder.error("Sin respuesta.")
            else:
                placeholder.error(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            placeholder.error(f"Error de conexión: {e}")
