import uuid

import api_client
import streamlit as st
from i18n import t
from views import benchmark, chat, sidebar

# ==============================================================================
# CONFIGURACIÓN GENERAL Y ESTILOS
# ==============================================================================
st.set_page_config(
    page_title=t("page_title"),
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Re-exported for backwards compatibility with code that imported them from app.py
API_URL = api_client.API_URL
API_HEADERS = api_client.API_HEADERS

st.markdown(
    """
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1.05rem; color: #4B5563; margin-bottom: 1.5rem; }
    .tool-badge {
        display: inline-block; background-color: #E0E7FF; color: #3730A3; padding: 0.2rem 0.5rem;
        border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin-right: 0.4rem; margin-bottom: 0.4rem;
    }
    .citation-box {
        background-color: #F3F4F6; border-left: 4px solid #3B82F6; padding: 0.6rem 0.8rem;
        border-radius: 4px; margin-bottom: 0.5rem; font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Stable option ids (language independent); the visible label comes from `VIEW_LABELS`.
VIEW_CHAT = "Chat"
VIEW_SEARCH = "Búsqueda RAG"
VIEW_BENCHMARK = "Benchmark Lab"
VIEW_LABELS = {VIEW_CHAT: "view_chat", VIEW_SEARCH: "view_search", VIEW_BENCHMARK: "view_benchmark"}

# ==============================================================================
# INICIALIZACIÓN DEL ESTADO DE SESIÓN
# ==============================================================================
st.session_state.setdefault("session_id", str(uuid.uuid4()))
st.session_state.setdefault("cached_docs", [])
st.session_state.setdefault("flash", None)

if not st.session_state.cached_docs:
    st.session_state.cached_docs = api_client.fetch_documents()

# ==============================================================================
# PANEL LATERAL (SIDEBAR)
# ==============================================================================
with st.sidebar:
    sidebar.render_language_selector()
    st.title(t("sidebar_title"))
    st.caption(t("sidebar_caption"))

    health = api_client.check_api_health()
    if health.get("status") == "ok":
        st.success(t("api_ok", environment=health.get("environment", "dev")))
    else:
        st.error(t("api_down"))

    st.divider()
    sidebar.render_sessions()
    st.divider()
    chat_options = sidebar.render_hyperparameters(st.session_state.cached_docs)
    st.divider()
    sidebar.render_golden_corpus()
    st.divider()
    sidebar.render_ingestion()
    st.divider()
    sidebar.render_catalog()

# Mensajes generados por callbacks (eliminar sesión, feedback, restaurar corpus)
flash = st.session_state.flash
if flash:
    level, text = flash
    (st.success if level == "success" else st.error)(text)
    st.session_state.flash = None

# ==============================================================================
# ÁREA PRINCIPAL
# ==============================================================================
st.markdown(f'<div class="main-title">{t("main_title")}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">{t("main_subtitle")}</div>', unsafe_allow_html=True)

view = st.segmented_control(
    t("view_label"),
    [VIEW_CHAT, VIEW_SEARCH, VIEW_BENCHMARK],
    format_func={option: t(label_key) for option, label_key in VIEW_LABELS.items()}.__getitem__,
    default=VIEW_CHAT,
    required=True,
    key="main_view",
    label_visibility="collapsed",
)

if view == VIEW_BENCHMARK:
    benchmark.render_benchmark_lab()
elif view == VIEW_SEARCH:
    chat.render_search_lab(chat_options)
else:
    with st.expander(t("examples_title"), expanded=False):
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            st.info(t("example_data"))
        with col_e2:
            st.info(t("example_report"))
        with col_e3:
            st.info(t("example_webhook"))

    chat.render_history(st.session_state.session_id)
    chat.render_last_turn()

    user_input = st.chat_input(t("chat_placeholder"))
    if user_input:
        chat.handle_user_input(user_input, st.session_state.session_id, chat_options)
