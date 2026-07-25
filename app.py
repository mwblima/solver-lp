import streamlit as st

# Configuração da página deve ser a primeira chamada
st.set_page_config(
    page_title="Solver LP",
    page_icon="images/favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Configuração de Idioma ---
if "language" not in st.session_state:
    st.session_state["language"] = "pt"

import base64

# ... imports ...
from ui.home_page import home_page
from ui.library_page import library_page
from ui.history_page import history_page
from ui.simplex_page import simplex_ui
from ui.branch_and_bound_page import bab_ui
from ui.sensitivity_page import sensitivity_ui
from ui.duality_page import duality_ui
from ui.standard_form_page import standard_form_ui
from ui.lang import t, get_available_languages

# Obter idiomas disponíveis
available_langs = get_available_languages()
# Criar listas para o selectbox (Nome -> Código)
lang_names = list(available_langs.values())
lang_codes = list(available_langs.keys())

# Helper para carregar imagem
def get_img_as_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Seletor no topo da sidebar
with st.sidebar:
    # Header Personalizado (Logo + Texto)
    img_base64 = get_img_as_base64("images/logo.svg")
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 20px;">
            <img src="data:image/svg+xml;base64,{img_base64}" width="40">
            <h1 style="font-size: 1.8rem; margin: 0;">
                <span style="color: var(--text-color);">Solver</span> <span style="color: #4CAF50;">LP</span>
            </h1>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🌐 Idioma / Language")
    
    # Encontrar índice do idioma atual
    current_lang_code = st.session_state["language"]
    try:
        current_index = lang_codes.index(current_lang_code)
    except ValueError:
        current_index = 0
        if lang_codes:
            st.session_state["language"] = lang_codes[0]

    selected_lang_name = st.selectbox(
        "Selecione / Select", 
        lang_names, 
        index=current_index,
        label_visibility="collapsed"
    )
    
    # Mapear nome de volta para código
    # (Assumindo unicidade de nomes, o que é razoável para Display Names definidos)
    if selected_lang_name:
         # Encontrar código correspondente ao nome selecionado
         new_lang_code = next((code for code, name in available_langs.items() if name == selected_lang_name), "pt")
         
         if new_lang_code != st.session_state["language"]:
             st.session_state["language"] = new_lang_code
             st.rerun()

    st.divider()

    # Creator Badge
    st.markdown(
        """
        <div style="text-align: center; margin-top: 20px;">
            <p style="font-size: 0.8em; color: #888; margin-bottom: 5px;">Developed by</p>
            <p style="font-weight: bold; font-size: 1.1em; margin-bottom: 10px;">Marcos Winicyus</p>
            <div style="display: flex; justify-content: center; gap: 15px;">
                <a href="https://github.com/mwblima" target="_blank" title="GitHub" style="color: inherit; text-decoration: none;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                </a>
                <a href="https://www.linkedin.com/in/marcos-winicyus/" target="_blank" title="LinkedIn" style="color: inherit; text-decoration: none;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                    </svg>
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# CSS customizado Global
st.markdown("""
<style>
    /* Destacar botões principais */
    .stButton > button[kind="primary"] {
        background: linear-gradient(45deg, #1f77b4, #17a2b8);
        border: none;
        font-weight: bold;
        padding: 0.75rem 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Definição das Páginas (st.Page) ---

# Principal
p_home = st.Page(home_page, title=t("menu.home"), icon="🏠")
p_library = st.Page(library_page, title=t("menu.library"), icon="📚")
p_history = st.Page(history_page, title=t("menu.history"), icon="🕑")

# Solvers
p_simplex = st.Page(simplex_ui, title=t("menu.simplex"), icon="📐")
p_bab = st.Page(bab_ui, title=t("menu.bab"), icon="🌳")

# Ferramentas
p_duality = st.Page(duality_ui, title=t("menu.duality"), icon="🔄")
p_sensitivity = st.Page(sensitivity_ui, title=t("menu.sensitivity"), icon="📊")
p_std_form = st.Page(standard_form_ui, title=t("menu.std_form"), icon="📝")

# Navegação Organizada
pg = st.navigation({
    "": [p_home, p_library, p_history],
    t("menu.solvers"): [p_simplex, p_bab],
    t("menu.tools"): [p_duality, p_sensitivity, p_std_form],
}, position="top")

# --- Lógica de Redirecionamento (Compatibilidade) ---
# Mapeia as strings antigas usadas em library_page.py e duality_page.py para os objetos st.Page
REDIRECT_MAP = {
    "simplex": p_simplex,
    "bab": p_bab,
    "📐 Método Simplex": p_simplex,
    "🌳 Branch & Bound": p_bab,
    "Simplex": p_simplex,
    "Branch & Bound": p_bab,
    "duality": p_duality,
    "sensitivity": p_sensitivity,
    "std_form": p_std_form,
    "library": p_library,
    "history": p_history
}

if "pending_redirect" in st.session_state:
    target = st.session_state["pending_redirect"]
    del st.session_state["pending_redirect"]
    
    if target in REDIRECT_MAP:
        st.switch_page(REDIRECT_MAP[target])
    else:
        # Tenta achar por título exato se não estiver no mapa
        pass

# Executar a navegação
pg.run()