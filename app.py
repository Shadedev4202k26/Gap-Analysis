import streamlit as st
import pandas as pd
import base64
import os
import json
import requests
from weasyprint import HTML

# Set up Page Config
st.set_page_config(page_title="Smilez Operational Hub", page_icon="⚡", layout="wide")

# 1. PREMIUM INJECTED DESIGN UI
st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
    
    <style>
    /* Global Styles */
    .stApp { background-color: #0F172A; color: #F9FAFB; }
    body, p, span, div { font-family: 'DM Sans', sans-serif; }

    /* Header Banner */
    .brand-banner {
        background-color: #111827;
        padding: 40px;
        border-radius: 12px;
        border-left: 6px solid #FDD835;
        margin-bottom: 30px;
        display: flex;
        align-items: center;
    }
    .brand-text h1 {
        font-family: 'Urbanist', sans-serif;
        color: #FDD835 !important;
        font-size: 42px;
        margin: 0;
        letter-spacing: -1px;
    }
    .brand-text p { color: #94A3B8; margin: 5px 0 0 0; font-size: 16px; }

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        background-color: #1F2937 !important;
        border-radius: 8px 8px 0px 0px !important;
        padding: 10px 25px !important;
        color: #94A3B8 !important;
        font-family: 'Urbanist', sans-serif;
        font-weight: 600;
        border: none !important;
    }
    .stTabs [aria-selected="true"] { background-color: #FDD835 !important; color: #0F172A !important; }

    /* Metric Tiles */
    .metric-tile { background-color: #1F2937; padding: 30px; border-radius: 12px; border: 1px solid rgba(253, 216, 53, 0.1); text-align: center; }
    .metric-label { color: #FDD835; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-family: 'Urbanist', sans-serif; font-size: 48px; font-weight: 700; color: #F9FAFB; margin-top: 10px; }

    /* Strain Card */
    .strain-card {
        background-color: #1F2937;
        padding: 35px;
        border-radius: 15px;
        border-top: 4px solid #FDD835;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        margin-top: 15px;
    }
    .strain-title { font-family: 'Urbanist', sans-serif; font-size: 32px; color: #FDD835; margin-bottom: 5px; text-transform: uppercase; }
    
    .badge-class { background: #10B981; color: #FFF; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 12px; text-transform: uppercase; }
    .section-head { color: #94A3B8; font-weight: 700; text-transform: uppercase; font-size: 13px; margin-top: 20px; }
    .section-data { font-size: 18px; color: #F9FAFB; margin-top: 5px; }

    .stDownloadButton button {
        background-color: #FDD835 !important;
        color: #0F172A !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 15px 30px !important;
        width: 100%;
    }
    [data-testid="stDataFrame"] { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; }
    </style>
""", unsafe_allow_html=True)

# 2. BRAND LOGO HANDLER
logo_path = 'image.png'
logo_html = ""
if os.path.exists(logo_
