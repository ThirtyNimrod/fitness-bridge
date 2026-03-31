import streamlit as st


def inject_css():
    """Inject custom CSS for visual polish across the app."""
    st.markdown("""
    <style>
    /* ── Chat Bubbles ──────────────────────────────────────────────────── */
    .stChatMessage[data-testid="stChatMessage"] {
        border-radius: 12px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
    }

    /* ── Metric Cards ──────────────────────────────────────────────────── */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 1rem;
    }

    div[data-testid="stMetric"] label {
        font-size: 0.85rem;
        color: #94a3b8;
    }

    /* ── Sidebar Branding ──────────────────────────────────────────────── */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }

    /* ── Connection Status Pills ───────────────────────────────────────── */
    .status-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-connected {
        background: #166534;
        color: #bbf7d0;
    }
    .status-disconnected {
        background: #7f1d1d;
        color: #fecaca;
    }

    /* ── Source Badges ──────────────────────────────────────────────────── */
    .source-strava {
        color: #fb923c;
        font-weight: 600;
    }
    .source-fitbit {
        color: #60a5fa;
        font-weight: 600;
    }

    /* ── Containers / Expanders ─────────────────────────────────────────── */
    div[data-testid="stExpander"] {
        border: 1px solid #334155;
        border-radius: 8px;
    }

    /* ── Buttons ────────────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15);
    }

    /* ── Loading Skeleton ──────────────────────────────────────────────── */
    .skeleton {
        background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 4px;
        height: 1.2rem;
    }
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    /* ── Dividers ──────────────────────────────────────────────────────── */
    hr {
        border-color: #334155;
    }

    /* ── Readiness Zone Highlights ──────────────────────────────────────── */
    .readiness-green { border-left: 4px solid #22c55e !important; }
    .readiness-amber { border-left: 4px solid #f59e0b !important; }
    .readiness-red   { border-left: 4px solid #ef4444 !important; }
    </style>
    """, unsafe_allow_html=True)
