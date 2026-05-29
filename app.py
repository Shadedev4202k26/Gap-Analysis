import streamlit as st
import pandas as pd
import base64
import os
from weasyprint import HTML

# Set up Page Config
st.set_page_config(page_title="Smilez Operational Hub", page_icon="⚡", layout="wide")

# 1. PREMIUM INDUSTRIAL-TIER CSS INJECTION
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
    .brand-text p {
        color: #94A3B8;
        margin: 5px 0 0 0;
        font-size: 16px;
    }

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

    /* Strain Reference Card */
    .strain-card {
        background-color: #1F2937;
        padding: 35px;
        border-radius: 15px;
        border-top: 4px solid #FDD835;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        margin-top: 15px;
    }
    .strain-title { font-family: 'Urbanist', sans-serif; font-size: 32px; color: #FDD835; margin-bottom: 10px; text-transform: uppercase; }
    
    /* Classification Badges */
    .badge-indica { background: #8B5CF6; color: #FFF; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 12px; text-transform: uppercase; }
    .badge-sativa; { background: #F59E0B; color: #111; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 12px; text-transform: uppercase; }
    .badge-hybrid { background: #10B981; color: #FFF; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 12px; text-transform: uppercase; }
    
    .section-head { color: #94A3B8; font-weight: 700; text-transform: uppercase; font-size: 13px; margin-top: 20px; }
    .section-data { font-size: 18px; color: #F9FAFB; margin-top: 5px; }

    /* Buttons */
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

# 2. LOGO HEADER INTEGRATION
logo_path = 'image.png'
logo_html = ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="height: 80px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f"""
    <div class="brand-banner">
        {logo_html}
        <div class="brand-text">
            <h1>SMILEZ OPERATIONAL HUB</h1>
            <p>Intelligence Engine for Inventory Logistics & Knowledge Management</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# 3. CONTROL CENTER TABS
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 KNOWLEDGE BASE"])

# --- TAB 1: INVENTORY FLOW ENGINE ---
with tab1:
    st.markdown("### 📥 Live Data Ingestion")
    uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv", key="dutchie_uploader")

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [str(col).strip('="').strip() for col in df.columns]
            qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col][0]
            
            df['Product'] = df['Product'].apply(lambda x: str(x).strip('="').strip())
            df['Room'] = df['Room'].apply(lambda x: str(x).strip('="').strip())
            df['Qty'] = pd.to_numeric(df[qty_col].apply(lambda x: str(x).strip('="').strip()), errors='coerce').fillna(0)
            
            pivot = df.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
            results = []
            for product, row in pivot.iterrows():
                present = row[row > 0].index.tolist()
                absent = row[row == 0].index.tolist()
                if absent and present:
                    for r in present:
                        if row[r] >= 15:
                            results.append({"Product Name": product, "Location": r, "Available Qty": int(row[r])})
            
            final_df = pd.DataFrame(results).sort_values("Product Name")

            if not final_df.empty:
                m1, m2, m3 = st.columns(3)
                with m1: st.markdown(f'<div class="metric-tile"><div class="metric-label">High-Impact Gaps</div><div class="metric-value">{len(final_df)}</div></div>', unsafe_allow_html=True)
                with m2: st.markdown(f'<div class="metric-tile"><div class="metric-label">Units to Move</div><div class="metric-value">{final_df["Available Qty"].sum()}</div></div>', unsafe_allow_html=True)
                with m3: st.markdown(f'<div class="metric-tile"><div class="metric-label">Min Threshold</div><div class="metric-value">15+</div></div>', unsafe_allow_html=True)

                st.write("---")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                html_pdf = f"<html><body style='font-family:sans-serif;'><h2>Smilez Gap Report</h2>{final_df.to_html()}</body></html>"
                pdf_out = HTML(string=html_pdf).write_pdf()
                st.download_button("📥 DOWNLOAD MERCHANDISING PDF", pdf_out, "Smilez_Report.pdf", "application/pdf")
            else:
                st.info("No gaps found matching the 15+ unit threshold.")
            
        except Exception as e:
            st.error(f"Analysis Error: {e}")

# --- TAB 2: MASSIFIED STRAIN DICTIONARY (100+ PROFILES) ---
with tab2:
    st.markdown("### 🔍 Enterprise Strain Reference Search")
    
    db = [
        {"name": "Acapulco Gold", "type": "Sativa", "terps": "Myrcene, Caryophyllene", "flav": "Earthy, Sweet, Woody, Chestnut", "eff": "Uplifting, High-Energy, Creative Motivation"},
        {"name": "Afghani", "type": "Indica", "terps": "Myrcene, Caryophyllene, Pinene", "flav": "Heavy Earth, Sweet Hash, Spicy Pine", "eff": "Deep Body Sedation, Relaxation, Sleep Inducing"},
        {"name": "Alien OG", "type": "Hybrid", "terps": "Myrcene, Limonene, Caryophyllene", "flav": "Sour Citrus, Pungent Pine, Heavy Fuel", "eff": "Intense Cerebral Buzz, Heavy Body Relaxation"},
        {"name": "Amnesia Haze", "type": "Sativa", "terps": "Terpinolene, Myrcene", "flav": "Sharp Citrus, Sweet Lemon, Fresh Earth", "eff": "Energetic, Uplifting, Cerebral Focus"},
        {"name": "Animal Cookies", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Sweet Sour Cherry, Nutty Vanilla, Doughy", "eff": "Heavy Physical Relaxation, Calming, Sleepy"},
        {"name": "Animal Mints", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sweet Mint, Pungent Earth, Piney Gas", "eff": "Full Body Stone, Relaxed Mind, Stress Relief"},
        {"name": "Apples and Bananas", "type": "Hybrid", "terps": "Myrcene, Caryophyllene, Pinene", "flav": "Sour Apple, Sweet Banana, Sharp Gas", "eff": "Euphoric Head High, Creative, Deeply Relaxed"},
        {"name": "Apple Fritter", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sweet Apple, Cake Pastry, Cheesy Funk", "eff": "Balanced Body High, Euphoric, Tingly"},
        {"name": "Ayahuasca Purple", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Rich Hazelnut, Papaya, Sweet Earth", "eff": "Highly Sedative, Relaxing, Peacefully Calming"},
        {"name": "Banana Candy", "type": "Indica", "terps": "Myrcene, Limonene", "flav": "Sweet Artificial Banana, Sugary Candy", "eff": "Relaxed Body, Mood Elevation, Mild Sedation"},
        {"name": "Banana Runtz", "type": "Hybrid", "terps": "Limonene, Myrcene", "flav": "Ripe Banana, Fruity Sweet Candy, Creamy", "eff": "Happy, Uplifted Spirit, Gentle Body Melt"},
        {"name": "Berry White", "type": "Indica", "terps": "Caryophyllene, Myrcene", "flav": "Sweet Blueberry, Sour Pine, Herbal Cake", "eff": "Balanced Relaxation, Euphoric Mood, Calming"},
        {"name": "Biscotti", "type": "Indica", "terps": "Caryophyllene, Limonene", "flav": "Sweet Cookie Dough, Spicy Diesel, Vanilla", "eff": "Cerebral Creative Lift, Total Body Relaxation"},
        {"name": "Blackberry Kush", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Sweet Wild Berry, Jet Fuel, Rich Earth", "eff": "Physical Couchlock, Heavy Sleep Aid, Hungry"},
        {"name": "Block Berry", "type": "Hybrid", "terps": "Limonene, Myrcene, Caryophyllene", "flav": "Sweet Berry, Crushed Orange, Tart Zest", "eff": "Laser Focused, Intense Euphoria, Active Day-Use"},
        {"name": "Blue Cheese", "type": "Indica", "terps": "Myrcene, Caryophyllene, Limonene", "flav": "Sharp Cheese, Sweet Blueberry, Savory Funk", "eff": "Heavy Physical Calm, Relaxed Mind, Muscle Relief"},
        {"name": "Blue Dream", "type": "Hybrid", "terps": "Myrcene, Pinene, Caryophyllene", "flav": "Sweet Blueberry, Fresh Berry, Herbal Earth", "eff": "Gentle Functional Uplift, Full-Body Ease, Creative"},
        {"name": "Blueberry", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Sweet Berry, Vanilla Cream, Tart Fruit", "eff": "Classic Couchlock, Sedative Relaxation, Deep Peace"},
        {"name": "Blueberry Cruffin", "type": "Indica", "terps": "Myrcene, Caryophyllene, Limonene", "flav": "Blueberry Pastry, Brown Sugar, Creamy Gas", "eff": "Cozy Physical Melting, Cerebral Bliss, Euphoria"},
        {"name": "Blueberry Muffin", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Fresh Baked Blueberry Muffin, Sweet Batter", "eff": "Calming Soothing Mind, Approachable Body Ease"},
        {"name": "Brain Stew", "type": "Indica", "terps": "Caryophyllene, Myrcene, Limonene", "flav": "Chemical Fuel, Heavy Garlic, Dank Earth", "eff": "Mind Eraser, Intense Physical Couchlock"},
        {"name": "Bubba Kush", "type": "Indica", "terps": "Caryophyllene, Linalool, Myrcene", "flav": "Roasted Coffee, Dark Chocolate, Spicy Kush", "eff": "Deep Physical Sedation, Ultimate Sleep Prep"},
        {"name": "Bubble Gum", "type": "Hybrid", "terps": "Caryophyllene, Myrcene", "flav": "Sweet Pink Bubblegum, Sugary Fruit, Floral", "eff": "Creative Focused Mind, Soft Calming Undertones"},
        {"name": "Candy Runtz", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sugary Sweet Tarts, Rainbow Candy, Gas", "eff": "Playful Euphoric Mind, Uplifting, Anti-Stress"},
        {"name": "Candy Sherb", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Sugared Citrus, Creamy Sherbet, Soft Gas", "eff": "Social Energy, Joyful Head High, Soft Relaxation"},
        {"name": "Cereal Milk", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sweet Sugary Milk, Creamy Fruit, Light Dough", "eff": "Calm Creative Focus, High Mental Clarity, Friendly"},
        {"name": "Chemdawg", "type": "Hybrid", "terps": "Caryophyllene, Myrcene, Limonene", "flav": "Chemical Fuel, Sour Industrial Diesel, Pine", "eff": "Heavy Striking Euphoria, Loud Mind High"},
        {"name": "Cherry Pie", "type": "Hybrid", "terps": "Caryophyllene, Myrcene", "flav": "Sweet Tart Cherry, Baked Crust, Earthy Spice", "eff": "Relaxed Muscles, Giggly, Socially Approachable"},
        {"name": "Chiquita Banana", "type": "Hybrid", "terps": "Limonene, Myrcene", "flav": "Ripe Tropical Banana, Clean Sweet Earth", "eff": "High Potency Cerebral Rush, Euphoria, Active"},
        {"name": "Cinderella 99", "type": "Sativa", "terps": "Terpinolene, Myrcene", "flav": "Pineapple, Sweet Tropical Citrus, Skunk", "eff": "Vibrant Cerebral Energy, Creative Drive"},
        {"name": "Cookies and Cream", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sweet Vanilla Ice Cream, Nutty Cookie Dough", "eff": "Balanced Euphoria, Physical Comfort, Sleepy"},
        {"name": "Death Star", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Skunky Diesel, Heavy Fuel, Rubber Pungent", "eff": "Creeping Heavy Stone, Mind Numbing, Sleepy"},
        {"name": "Dolce de Fresa", "type": "Sativa", "terps": "Limonene, Myrcene", "flav": "Sweet Strawberry Cream, Candy, Tart Fruit", "eff": "High Energy Lift, Socially Motivated, Euphoric"},
        {"name": "Durban Poison", "type": "Sativa", "terps": "Terpinolene, Myrcene, Ocimene", "flav": "Sweet Clean Pine, Spicy Anise, Clear Wood", "eff": "Pure Unmatched Day Energy, Creative Focus"},
        {"name": "G13", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Dank Earth, Woody Pine, Classic Skunk", "eff": "Heavy Medicating Sedation, Mind Eraser, Sleep"},
        {"name": "Galactic Warheads", "type": "Hybrid", "terps": "Limonene, Caryophyllene", "flav": "Extreme Sour Candy, Chemical Fruit, Citrus", "eff": "Uplifting Mental Lightning, Creative Energy"},
        {"name": "Garlic Cookies", "type": "Indica", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Garlic, Fuel, Pungent Onion, Roasted Coffee", "eff": "Heavy Physical Locking, Euphoric Dream state"},
        {"name": "Garlic Drip", "type": "Indica", "terps": "Caryophyllene, Limonene", "flav": "Heavy GMO Funk, Savory Spice, Rotten Fuel", "eff": "Intense Physical Comfort, Anti-Anxiety Melting"},
        {"name": "Gary Payton", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Nutty Burnt Rubber, Spicy Diesel, Herb Kush", "eff": "Long Lasting Active High, Social, Focus Flow"},
        {"name": "Gelato 33", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sweet Citrus Sherbet, Creamy Earth, Minty", "eff": "Uplifting Happy Headspace, Functional Body Calm"},
        {"name": "Gelato 41", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Linalool", "flav": "Heavy Lavender Cream, Sweet Berry, Sweet Gas", "eff": "Deep Sensory Elevation, Relaxed Body, Peaceful"},
        {"name": "Gelato 45", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sweet Sugared Fruit, Soft Marshmallow Cream", "eff": "Balanced Relaxed Mood, Ideal Afternoon Day-Use"},
        {"name": "Georgia Pie", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Savory Peach Pie, Baked Nutty Crust, Gas", "eff": "Heavy Stoney Body Load, High Appetite, Relaxed"},
        {"name": "GG4", "type": "Hybrid", "terps": "Caryophyllene, Myrcene, Limonene", "flav": "Heavy Pungent Pine, Sour Chemical Diesel, Glue", "eff": "True Couchlock, Muscle Numbing, Mind Obliteration"},
        {"name": "GNS (Ghost OG)", "type": "Hybrid", "terps": "Myrcene, Limonene", "flav": "Sour Crisp Citrus, Sweet Piney Earth, Gas", "eff": "Balanced Euphoric Head, Smooth Body Relief"},
        {"name": "GMO", "type": "Indica", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Garlic, Heavy Onion, Mushroom, Fuel Skunk", "eff": "Extreme Sedation, Sleepy, Heavy Mental Bliss"},
        {"name": "Gogurtz", "type": "Hybrid", "terps": "Limonene, Caryophyllene", "flav": "Creamy Artificial Yogurt, Sweet Berry Gas", "eff": "Dreamy Carefree Headspace, Calming Relaxation"},
        {"name": "Granddaddy Purple", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Sweet Artificial Grape, Deep Musky Berry", "eff": "Classic Heavy Body Stone, Restful Sleep Aid"},
        {"name": "Grape Gasoline", "type": "Indica", "terps": "Caryophyllene, Myrcene", "flav": "Fermented Grape, Pungent Petroleum, Pepper", "eff": "Fast Calming Body Melt, Stress Wipe, Sleepy"},
        {"name": "Green Crack", "type": "Sativa", "terps": "Myrcene, Caryophyllene, Limonene", "flav": "Sharp Mango Fruit, Sweet Citrus Punch", "eff": "Vibrant Clean Focus, Racing Energy, Daytime Activity"},
        {"name": "Harlequin", "type": "Sativa", "terps": "Myrcene, Pinene", "flav": "Musky Rich Earth, Mango Sweetness, Herbal", "eff": "Clear-Headed, High-Functioning, Therapeutic (High CBD)"},
        {"name": "Hash Bee OG", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Spicy Pure Hashish, Earthy Pine, Heavy Funk", "eff": "Deep Body Blanket, Sedative Calm, Restful"},
        {"name": "Headband", "type": "Hybrid", "terps": "Myrcene, Limonene", "flav": "Creamy Sour Diesel, Lemon Zing, Earthy Kush", "eff": "Warm Creative Head Halo Feeling, Long Lasting Relax"},
        {"name": "Headstash", "type": "Indica", "terps": "Caryophyllene, Myrcene, Linalool", "flav": "Sweet Clean Earth, Creamy Berry, Spicy Gas", "eff": "Luxury Cognitive Calming, Pure Blissful Rest"},
        {"name": "Honey Banana", "type": "Hybrid", "terps": "Limonene, Myrcene", "flav": "Baked Banana Bread, Sweet Strawberries, Honey", "eff": "Intensely Flavorful Euphoria, Giggly, Creative"},
        {"name": "Ice Cream Cake", "type": "Indica", "terps": "Caryophyllene, Limonene, Linalool", "flav": "Sugary Vanilla Frosting, Creamy Nutty Dough", "eff": "Deep Physical Sedation, Muscle Melter, Blissful Sleep"},
        {"name": "Ice Cream Mints", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Creamy Vanilla Sweet Mint, Sharp Herb Gas", "eff": "Highly Balanced Buzz, Mood Booster, Calm Physical"},
        {"name": "Inzane in the Membrane", "type": "Sativa", "terps": "Terpinolene, Limonene", "flav": "Spicy Lemon Chemical, Industrial Cleaner", "eff": "Intense Racing Cerebral Lightning, Extreme Energy"},
        {"name": "Jack Herer", "type": "Sativa", "terps": "Terpinolene, Pinene, Caryophyllene", "flav": "Spicy Haze Pine, Crisp Wood, Lemon Rind", "eff": "High Executive Focus, Creative Day Production"},
        {"name": "Jealousy", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Dark Sweet Plum, Candy Fuel, Pepper Cream", "eff": "Anti-Anxiety Mind Relief, Creative Flow, Cozy"},
        {"name": "L.A. Confidential", "type": "Indica", "terps": "Myrcene, Caryophyllene, Pinene", "flav": "Crisp Spicy Pine, Earthy Skunk, Classic Kush", "eff": "Psychedelic Body Sedation, Deep Physical Relief"},
        {"name": "Lantz", "type": "Hybrid", "terps": "Limonene, Caryophyllene, Myrcene", "flav": "Sweet Exotic Citrus, Creamy Candy, Clean Gas", "eff": "Award-Winning Euphoria, Massive Sensory Lift, Social"},
        {"name": "Lemon Cherry Gelato", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Tart Lemon, Sweet Black Cherry, Rich Cream Gas", "eff": "Top-Tier Premium Euphoria, Carefree Happy Mind"},
        {"name": "Lemon Haze", "type": "Sativa", "terps": "Limonene, Terpinolene", "flav": "Fresh Zesty Lemon, Sweet Sugared Citrus", "eff": "Uplifted Mood, Social Talkative Energy, Motivated"},
        {"name": "Limon Mandarina", "type": "Sativa", "terps": "Limonene, Terpinolene", "flav": "Squeezed Tangerine peel, Lime Zest, Funk", "eff": "Refreshing Daytime Cognitive Lift, Bright Energy"},
        {"name": "Los Muertos", "type": "Hybrid", "terps": "Pinene, Caryophyllene", "flav": "Spicy Herbal Citrus, Dark Floral Gas, Musk", "eff": "Structured Creative Focus, Clear Thinking Mind"},
        {"name": "Mac 1", "type": "Hybrid", "terps": "Limonene, Caryophyllene, Pinene", "flav": "Dank Sour Diesel, Creamy Orange, Spicy Herb", "eff": "Heavy Balanced Euphoria, High Technical Creativity"},
        {"name": "Mandarin Z", "type": "Hybrid", "terps": "Limonene, Myrcene", "flav": "Sweet Sugared Mandarin Orange, Tropical Zkittlez", "eff": "Joyful Carefree Mind, Socially Animated, Uplifted"},
        {"name": "Maui Wowie", "type": "Sativa", "terps": "Myrcene, Pinene", "flav": "Sweet Pineapple Chunks, Tropical Hibiscus", "eff": "Happy Vacation Headspace, Light Day Motivation"},
        {"name": "Motorbreath", "type": "Indica", "terps": "Myrcene, Caryophyllene, Limonene", "flav": "Industrial Chemical Diesel, Heavy Garlic Gas", "eff": "Unrivaled Knockout Potency, Instant Couchlock"},
        {"name": "Northern Lights", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Pungent Forest Pine, Sweet Herbal Woodiness", "eff": "Dreamy Sedative Floating, Total Mind Eraser"},
        {"name": "OG Kush", "type": "Hybrid", "terps": "Myrcene, Limonene, Caryophyllene", "flav": "Skunky Chemical Fuel, Sour Lemon, Heavy Pine", "eff": "Classic Stoney Mind Melter, Heavy Body Cushion"},
        {"name": "Orange Yuzu", "type": "Sativa", "terps": "Limonene, Terpinolene", "flav": "Sharp Sour Yuzu, Sweet Orange, Musk Funk", "eff": "Crisp Morning Wake and Bake, Energizing Mind Lift"},
        {"name": "Pancakes", "type": "Indica", "terps": "Caryophyllene, Limonene", "flav": "Warm Sweet Buttered Dough, Maple Syrup, Gas", "eff": "Comforting Physical Warmth, Calming, Sleepy"},
        {"name": "Papaya", "type": "Indica", "terps": "Myrcene, Limonene", "flav": "Sweet Rotting Papaya, Tropical Mango, Pepper", "eff": "Soothing Muscle Relief, Warm Euphoria, Anti-Stress"},
        {"name": "Papaya Juice", "type": "Indica", "terps": "Myrcene, Limonene, Linalool", "flav": "Fresh Pressed Papaya, Sweet Tropical Nectar", "eff": "Heavy Physical Melting, Creative Day Dreaming"},
        {"name": "Party Runtz", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Fruit Punch Candy, Fizzy Sugar, Light Gas", "eff": "Excited Social Energy, Uplifting Mood Enhancer"},
        {"name": "Permanent Marker", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Industrial Permanent Marker Ink, Sour Candy, Gas", "eff": "Extreme Potency, Euphoric Mind Daze, Heavy Relaxation"},
        {"name": "Pineapple Express", "type": "Hybrid", "terps": "Myrcene, Limonene", "flav": "Sweet Glazed Pineapple, Cedar Wood, Tropics", "eff": "Happy Energetic Focus, Clean Day Motivation"},
        {"name": "Pink Certz", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Fizzy Pink Mint, Chemical Fuel, Grape Tart", "eff": "Highly Creative, Balanced Head-Body Stimulation"},
        {"name": "Pink Runtz", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sugary Sweet Strawberry, Creamy Candy Tart", "eff": "Playful Giggly Headspace, Long-Lasting Delight"},
        {"name": "Pink Zoap", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sweet Perfumed Soap, Pink Guava, Sharp Fuel", "eff": "Instant Mood Elevation, Chatty, Mind Stimulating"},
        {"name": "Plan Z", "type": "Hybrid", "terps": "Limonene, Caryophyllene", "flav": "Tropical Candy Skittles, Sweet Orange Zest", "eff": "Uplifting Daytime Focus, Carefree Euphoria"},
        {"name": "Pluto Kush", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Heavy Pungent Skunk, Spice, Pure Black Pepper", "eff": "Deep Outer-Space Couchlock, Insomnia Relief"},
        {"name": "Project Z", "type": "Hybrid", "terps": "Limonene, Caryophyllene, Myrcene", "flav": "Complex Exotic Candy, Sweet Fuel, Grape", "eff": "Mind Warping Euphoria, Heavy Body Relief"},
        {"name": "Purple Drank", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Sweet Grape Syrup, Berry Fizz, Earthy Gas", "eff": "Heavy Eyelid Relaxation, Calming, Sleep Aid"},
        {"name": "Purple Haze", "type": "Sativa", "terps": "Myrcene, Caryophyllene", "flav": "Sweet Berry Candy, Earthy Exotic Spice, Wine", "eff": "Dreamy Cerebral Activation, Trippy Creative Drive"},
        {"name": "Purple Punch", "type": "Indica", "terps": "Caryophyllene, Limonene", "flav": "Sweet Grape Dimetapp, Blueberry Candy, Cake", "eff": "Cozy Warm Body Relaxation, Ideal Sleepy Dessert"},
        {"name": "Rainbow Belts", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Linalool", "flav": "Zesty Lime Skittles, Fizzy Sweet Candy, Gas", "eff": "Pure Unadulterated Mental Happiness, Total Calm"},
        {"name": "Rainbow Guava", "type": "Hybrid", "terps": "Limonene, Caryophyllene", "flav": "Sweet Rotten Guava, Passionfruit, Tropical Gas", "eff": "Exotic Sensory Heightening, Creative Focus"},
        {"name": "RS-11 (Rainbow Sherbert)", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Sour Cherry Candy, Creamy Tropical Sherbet", "eff": "Elite Mentally Relaxed High, Clear Sensory Focus"},
        {"name": "Runtz", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Linalool", "flav": "Pure Sugared Candy bag, Tropical Fruit Skunky", "eff": "Imaginative Playful Headspace, Deep Joy, Chatty"},
        {"name": "Sex Panther", "type": "Indica", "terps": "Caryophyllene, Myrcene, Linalool", "flav": "Heavy Musky Petroleum, Spiced Wood, Earth", "eff": "Thick Heavy Body Lock, Instant Shoulder Drop"},
        {"name": "SFV OG", "type": "Hybrid", "terps": "Myrcene, Limonene", "flav": "Lemon Sol-Jan, Pine Needle, Chemical Fuel", "eff": "Fast Striking Cognitive Euphoria, Joint Comfort"},
        {"name": "Sherb Cream Pie", "type": "Indica", "terps": "Caryophyllene, Limonene, Linalool", "flav": "Creamy Nutty Pastry, Sunset Sherbet, Gas", "eff": "Deep Intoxicating Calm, Mind Eraser, Sleepy"},
        {"name": "Skywalker OG", "type": "Indica", "terps": "Myrcene, Caryophyllene", "flav": "Heavy Jet Fuel, Pungent Spice, Pine Forest", "eff": "Immediate Numbing Couchlock, Heavy Sleep Aid"},
        {"name": "Slurricane", "type": "Indica", "terps": "Caryophyllene, Limonene", "flav": "Sugared Dark Berry, Sweet Grapes, Spice Herb", "eff": "Deep Body Tingles, Calm Peaceful Mental state"},
        {"name": "Speaker Knockerz", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Doughy Animal Mints, Raw Sweet Fruit, Earth", "eff": "Heavy Balanced Blast, Highly Photogenic High"},
        {"name": "Sour Diesel", "type": "Sativa", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Skunky Commercial Diesel, Heavy Fuel, Citric", "eff": "Fast Acting Cerebral Energy, High Social Flow"},
        {"name": "Spritzer", "type": "Hybrid", "terps": "Limonene, Caryophyllene", "flav": "Fizzy Raspberry Soda, Red Wine, Sharp Gas", "eff": "Effervescent Mood Boost, Creative Brainstorming"},
        {"name": "Strawberry Cough", "type": "Sativa", "terps": "Myrcene, Pinene", "flav": "Fresh Red Strawberries, Sweet Skunk, Herbal", "eff": "Uplifting Clean Focus, Powerful Anti-Social Anxiety"},
        {"name": "Superboof", "type": "Hybrid", "terps": "Limonene, Myrcene, Caryophyllene", "flav": "Explosive Ruby Red Grapefruit, Heavy Musky Gas", "eff": "Unmatched Daytime Euphoria, Social, Joyful Focus"},
        {"name": "Super Lemon Haze", "type": "Sativa", "terps": "Terpinolene, Limonene", "flav": "Zesty Lemon Head Candy, Sweet Tart Citrus", "eff": "Electric Clean Mind Energy, Motivation Drive"},
        {"name": "Super Silver Haze", "type": "Sativa", "terps": "Myrcene, Terpinolene", "flav": "Earthy Musk, Old School Skunk, Sweet Citrus", "eff": "Clear Headed Functional High, All-Day Production"},
        {"name": "Swamp Water Fumez", "type": "Hybrid", "terps": "Caryophyllene, Myrcene", "flav": "Rotten Onion Funk, Swamp Gas, Sugared Chemical", "eff": "Intense Spacey Cerebral High, Ultimate Relaxation"},
        {"name": "Tangie", "type": "Sativa", "terps": "Myrcene, Limonene, Terpinolene", "flav": "Fresh Peel Tangerine, Sweet Concentrated Orange", "eff": "Happy Focused Energy, Uplifting Creative Flow"},
        {"name": "Tropicana Cookies", "type": "Sativa", "terps": "Caryophyllene, Limonene", "flav": "Fresh Blood Orange Juice, Baked Warm Cookie", "eff": "Productive Bright Focus, Happy Active Cerebral"},
        {"name": "Wedding Cake", "type": "Indica", "terps": "Limonene, Caryophyllene, Myrcene", "flav": "Rich Sugared Vanilla, Cake Batter, Pepper Spice", "eff": "Deep Muscle Relaxation, Calming, High Appetite"},
        {"name": "White Runtz", "type": "Hybrid", "terps": "Limonene, Caryophyllene", "flav": "Sweet Creamy Fruit, White Powder Candy, Gas", "eff": "Long Lasting Happy Tingly Body Buzz, Delight"},
        {"name": "White Truffle", "type": "Hybrid", "terps": "Caryophyllene, Humulene", "flav": "Savory Musky Earth, White Truffle Mushroom", "eff": "Elite Calming Serenity, Stress Melt, Deep Peace"},
        {"name": "White Widow", "type": "Hybrid", "terps": "Myrcene, Caryophyllene, Pinene", "flav": "Spicy Crisp Wood, Sharp Black Pepper, Earth", "eff": "Highly Conversational Social Energy, Creative Burst"},
        {"name": "Zaza", "type": "Hybrid", "terps": "Myrcene, Limonene, Caryophyllene", "flav": "Heavy Fuel Overload, Sweet Pungent Chem Skunk", "eff": "Hit Like A Freight Train, Heavy Euphoric Daze"},
        {"name": "Zkittlez", "type": "Indica", "terps": "Caryophyllene, Humulene, Linalool", "flav": "Mouthwatering Rainbow Candy, Grape, Sour Lime", "eff": "Peaceful Focused Headspace, Calming Stress Melt"}
    ]
    
    # Fuzzy string searching input
    query = st.text_input("Search Engine Input", placeholder="Type strain name here (e.g. Lantz, Permanent, Superboof, Runtz, Kush)...", key="strain_search_box", label_visibility="collapsed").lower().strip()
    
    if query:
        matches = [s for s in db if query in s['name'].lower()]
        
        if matches:
            if len(matches) > 1:
                options = [s['name'] for s in matches]
                options = list(dict.fromkeys(options))  # Deduplicate
                selected_name = st.selectbox(f"💡 Found {len(options)} matching profiles. Select exact variant:", options)
                display_matches = [s for s in matches if s['name'] == selected_name][:1]
            else:
                display_matches = matches
                
            for s in display_matches:
                # Dynamic badge assignment based on genetic categorization
                b_type = s['type'].lower()
                badge_style = "badge-indica" if "indica" in b_type else ("badge-sativa" if "sativa" in b_type else "badge-hybrid")
                
                st.markdown(f"""
                    <div class="strain-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                            <div class="strain-title">✨ {s['name']}</div>
                            <span class="{badge_style}">{s['type'].upper()}</span>
                        </div>
                        <hr style="border: 0; border-top: 1px solid rgba(148, 163, 184, 0.2); margin-bottom: 15px;">
                        <div class="section-head">🧪 Dominant Terpenes</div>
                        <div class="section-data">{s['terps']}</div>
                        <div class="section-head">🍋 Flavor Profile</div>
                        <div class="section-data">{s['flav']}</div>
                        <div class="section-head">🧠 Reported Effects</div>
                        <div class="section-data">{s['eff']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No matching profile found in the corporate quick-cache database.")
