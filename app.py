"""Point d'entrée : configuration, navigation par sections et filtres communs."""

import streamlit as st

from src import utils as u

st.set_page_config(page_title="Observatoire du logement IDF", page_icon=u.ICONS["app"], layout="wide")

st.logo(str(u.ROOT / "assets" / "logo_efrei.png"), size="large")
st.html("<style>[data-testid='stSidebarHeader'] img, [data-testid='stLogo'] {height: 4.5rem !important; max-width: 100% !important;}</style>")

sections: dict[str, list] = {}
for i, (section, path, title, icon, _) in enumerate(u.existing_pages()):
    sections.setdefault(section, []).append(
        st.Page(path, title=title, icon=icon, default=(i == 0))
    )
nav = st.navigation(sections)

# Filtres dans la sidebar, sous la navigation, partagés par toutes les pages
u.sidebar_filters()

nav.run()
