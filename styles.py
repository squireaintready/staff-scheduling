"""Custom CSS for layout and mobile responsiveness.

The stylesheet is static (no interpolation of user data), so injecting it with
``unsafe_allow_html`` is safe.
"""

import streamlit as st

CUSTOM_CSS = """
<style>
    /* Remove top padding to bring content to very top */
    .main .block-container {
        padding-top: 0;
        margin-top: 0;
    }

    /* Remove any extra spacing at top */
    .main > div:first-child {
        padding-top: 0;
    }

    /* Make Streamlit header minimal but keep hamburger menu visible */
    header[data-testid="stHeader"] {
        background: transparent;
        height: 2.5rem;
    }

    /* Narrow sidebar - wide enough for "Shift Templates" */
    [data-testid="stSidebar"] {
        min-width: 180px;
        max-width: 200px;
    }

    /* Prevent text wrapping/vertical text */
    .stSelectbox label, .stSelectbox div[data-baseweb="select"] {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Make selectbox dropdown text not wrap */
    [data-baseweb="select"] span {
        white-space: nowrap;
    }

    /* Compact the schedule grid */
    [data-testid="column"] {
        padding: 0 4px;
    }

    /* Smaller captions */
    .stCaption {
        font-size: 0.75rem;
        white-space: nowrap;
    }

    /* Ensure metric values don't wrap */
    [data-testid="stMetricValue"] {
        white-space: nowrap;
    }

    /* Compact buttons */
    .stButton button {
        padding: 0.25rem 0.5rem;
        font-size: 0.75rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }

    /* ===== MOBILE RESPONSIVE ===== */
    @media (max-width: 768px) {
        /* Make main content full width */
        .main .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
            max-width: 100%;
        }

        /* Allow horizontal scroll for schedule grid */
        [data-testid="stHorizontalBlock"] {
            overflow-x: auto;
            flex-wrap: nowrap !important;
            -webkit-overflow-scrolling: touch;
            padding-bottom: 0.5rem;
        }

        /* Minimum width for day columns on mobile */
        [data-testid="column"] {
            min-width: 55px;
            flex-shrink: 0;
        }

        /* Employee name column wider on mobile */
        [data-testid="column"]:first-child {
            min-width: 90px;
        }

        /* Stack form elements better on mobile */
        .stSelectbox, .stCheckbox {
            margin-bottom: 0.25rem;
        }

        /* Smaller text on mobile */
        .stMarkdown {
            font-size: 0.85rem;
        }

        .stMarkdown h3 {
            font-size: 1.1rem;
        }

        /* Smaller captions on mobile */
        .stCaption {
            font-size: 0.65rem;
        }

        /* Touch-friendly buttons on mobile */
        .stButton button {
            padding: 0.4rem 0.6rem;
            font-size: 0.8rem;
            min-height: 38px;
        }

        /* Touch-friendly checkboxes */
        .stCheckbox {
            padding: 0.25rem 0;
        }

        /* Compact progress bar */
        .stProgress {
            margin: 0.25rem 0;
        }

        /* Hide sidebar by default on mobile (user can open) */
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 200px;
        }
    }

    /* Tablet adjustments */
    @media (max-width: 1200px) and (min-width: 769px) {
        [data-testid="stSidebar"] {
            min-width: 160px;
            max-width: 180px;
        }

        [data-testid="column"] {
            min-width: 70px;
        }
    }
</style>
"""


def inject_styles() -> None:
    """Apply the custom stylesheet to the current page."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
