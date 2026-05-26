import streamlit as st

st.set_page_config(
    page_title="SnapMeal AI",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded",
)

import google.generativeai as genai
from PIL import Image
import json
import re
import os
from gtts import gTTS
import tempfile
from dotenv import load_dotenv

from services.spark_service import SparkFoodService
from services.nutrition_service import enrich_analysis

load_dotenv()


@st.cache_resource
def get_spark_service():
    return SparkFoodService.get_instance()


spark_service = get_spark_service()

LANGUAGE_CODES = {
    "English": "en",
    "Hindi": "hi",
    "Japanese": "ja",
    "French": "fr"
}

# ----------------------------
# STEP 1: Add Your API Key Here
# ----------------------------
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-flash")

# Theme Toggle
if 'theme' not in st.session_state:
    st.session_state.theme = "light"

def generate_speech_summary(food_data, language):
    try:
        summary_prompt = f"""
Give a short, friendly, spoken-style summary (4-5 sentences)
of this food item based on the following data.

The summary must be in {language}.

Food Data:
{json.dumps(food_data, indent=2)}

Make it natural and conversational.
Do NOT return JSON.
Return plain text only.
"""

        response = model.generate_content(summary_prompt)

        if response and hasattr(response, "text") and response.text:
            return response.text.strip()
        else:
            return "⚠ AI returned empty summary."

    except Exception as e:
        return f"❌ Speech Error: {str(e)}"
    

    
def text_to_speech(text, lang_code):
    try:
        tts = gTTS(text=text, lang=lang_code)
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp_file.name)
        
        return temp_file.name

    except Exception as e:
        return None
    

def toggle_theme():
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"

# Initialize session state variables
if 'history' not in st.session_state:
    st.session_state.history = []
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'calorie_log' not in st.session_state:
    st.session_state.calorie_log = []
if 'dietary_preference' not in st.session_state:
    st.session_state.dietary_preference = "None"

# ----------------------------
# Custom CSS for styling
# ----------------------------
st.markdown("""
<style>
.main-header {
    font-size: 100px !important;
    font-weight: 900 !important;
    text-align: left !important;
    margin-top: -30px;
    margin-bottom: 20px;
    background: linear-gradient(90deg, #FF4B4B, #FF9F1C);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

    .sub-header {
        font-size: 1.5rem;
        color: #4ECDC4;
        margin-top: 1rem;
    }
    .feature-card {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0f2f6;
        margin: 0.5rem 0;
    }
    .favorite-btn {
        background-color: #FFE66D;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        cursor: pointer;
    }
    .history-item {
        padding: 0.5rem;
        border-left: 3px solid #4ECDC4;
        margin: 0.5rem 0;
        background-color: #f9f9f9;
    }
    .metric-card {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 1rem;
        color: white;
    }
    .health-score {
        font-size: 3rem;
        font-weight: bold;
    }
    .stButton>button {
        width: 100%;
    }
    .comparison-container {
        display: flex;
        justify-content: space-around;
        padding: 1rem;
    }
    .lang-select {
        margin-bottom: 1rem;
            
    }
    .block-container {
        padding-right: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Sidebar - Settings & Features
# ----------------------------
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Theme Toggle
    st.subheader("🎨 Theme")
    theme_col1, theme_col2 = st.columns(2)
    with theme_col1:
        if st.button("☀️ Light"):
            st.session_state.theme = "light"
    with theme_col2:
        if st.button("🌙 Dark"):
            st.session_state.theme = "dark"
    
    # Language Selection
    st.subheader("🌐 Language")
    language = st.selectbox(
        "Select Language",
        ["English", "Hindi", "Japanese", "French"]
    )
    
    # Dietary Preferences
    st.subheader("🥗 Dietary Preferences")
    dietary = st.selectbox(
        "Select Diet",
        ["None", "Vegan", "Vegetarian", "Keto", "Gluten-Free", "Dairy-Free", "Low-Carb", "Paleo"]
    )
    st.session_state.dietary_preference = dietary
    
    # Quick Stats
    st.subheader("📊 Quick Stats")
    st.metric("Total Analyses", len(st.session_state.history))
    st.metric("Favorites", len(st.session_state.favorites))
    log_stats = spark_service.aggregate_calorie_log(st.session_state.calorie_log)
    st.metric(
        "Calories Logged",
        int(log_stats.get("total", 0)) if log_stats else 0,
    )
    if log_stats:
        st.caption(f"PySpark avg per entry: {log_stats.get('average', 0)} kcal")

# ----------------------------
# Main Header
# ----------------------------
st.markdown("""
<h1 class="main-header">
    🍔 SnapMeal AI
</h1>
""", unsafe_allow_html=True)
st.write("Upload a food image and get full details with advanced features!")

# ----------------------------
# Tabs for different features
# ----------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔍 Analyze Food",
    "📜 History",
    "⭐ Favorites",
    "📈 Compare",
    "🧮 Calorie Calculator",
    "⚡ Spark Analytics",
])

# ----------------------------
# Tab 1: Analyze Food
# ----------------------------
with tab1:
    col1, col2 = st.columns([0.9, 1.4])
    
    with col1:
        st.subheader("📤 Upload Image")
        uploaded_file = st.file_uploader("Upload Food Image", type=["jpg", "png", "jpeg"])
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)            
            if st.button("Analyze Food", type="primary"):
                with st.spinner("Analyzing..."):
                    prompt = f"""
You are a professional nutrition expert.

Analyze this food image.
User's dietary preference: {dietary}

IMPORTANT:
- Return ONLY valid JSON.
- Do not write explanations.
- Do not use markdown.
- Do not wrap in ```json.
- All TEXT VALUES must be written in {language}.
- Keep JSON keys in English.
- Only translate the values, NOT the keys.

Format:

{{
  "name": "",
  "short_description": "",
  "cuisine": "",
  "ingredients": [],
  "nutrients": {{
      "calories": "",
      "protein": "",
      "carbs": "",
      "fat": ""
  }},
  "allergens": [],
  "how_its_made": "",
  "health_score": "",
  "dietary_tags": [],
  "health_benefits": [],
  "health_concerns": []
}}
"""

                    response = model.generate_content([prompt, image])

                    try:
                        raw_text = response.text
                        start = raw_text.find("{")
                        end = raw_text.rfind("}") + 1
                        json_text = raw_text[start:end]
                        data = json.loads(json_text)
                        # PySpark RAG: verified nutrition from food database
                        data, enriched = enrich_analysis(data, spark_service)
                        if enriched:
                            st.info("📚 Verified nutrition data applied via PySpark lookup.")
                        
                        # Save to history
                        st.session_state.history.append({
                            "name": data["name"],
                            "image": uploaded_file,
                            "data": data,
                            "timestamp": str(st.session_state.get("analysis_count", 0) + 1)
                        })
                        
                        # Store current analysis
                        st.session_state.current_analysis = data
                        speech = generate_speech_summary(data, language)
                        st.session_state.current_speech = speech
                        
                        st.success("✅ Analysis Complete!")
                        
                    except Exception as e:
                        st.error(f"AI response format error: {str(e)}. Try again.")

    with col2:
        st.subheader("📋 Results")
        
        if 'current_analysis' in st.session_state and st.session_state.current_analysis:
            data = st.session_state.current_analysis
            
            # Food Name
            st.markdown(f"### 🍽 {data.get('name', 'Unknown Food')}")
            
            # Description
            st.write(data.get('short_description', ''))
            
            # Cuisine & Dietary Tags
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown(f"**🌍 Cuisine:** {data.get('cuisine', 'Unknown')}")
            with col_c2:
                dietary_tags = data.get('dietary_tags', [])
                if dietary_tags:
                    st.markdown(f"**🥗 Tags:** {', '.join(dietary_tags)}")
            
            st.divider()
            
            # Nutrients with Visual Metrics
            st.subheader("🔥 Nutrients")
            nutrients = data.get('nutrients', {})
            
            # Create metric columns
# Clean numeric extraction function
            import re

            def extract_number(value):
                if isinstance(value, str):
                    match = re.search(r"\d+", value.replace(",", ""))
                    if match:
                        return int(match.group())
                elif isinstance(value, (int, float)):
                    return int(value)
                return 0

            calories = extract_number(nutrients.get("calories"))
            protein = extract_number(nutrients.get("protein"))
            carbs = extract_number(nutrients.get("carbs"))
            fat = extract_number(nutrients.get("fat"))

            n_row1_col1, n_row1_col2 = st.columns(2)
            n_row2_col1, n_row2_col2 = st.columns(2)

            with n_row1_col1:
                st.metric("Calories", f"{calories} kcal")

            with n_row1_col2:
                st.metric("Protein", f"{protein} g")

            with n_row2_col1:
                st.metric("Carbs", f"{carbs} g")

            with n_row2_col2:
                st.metric("Fat", f"{fat} g")
                        
            # Nutrient Chart
            try:
                import pandas as pd
                nutrient_df = pd.DataFrame({
                    'Nutrient': ['Protein', 'Carbs', 'Fat'],
                    'Grams': [
                        float(nutrients.get('protein', '0').replace('g', '').strip()) if isinstance(nutrients.get('protein'), str) else nutrients.get('protein', 0),
                        float(nutrients.get('carbs', '0').replace('g', '').strip()) if isinstance(nutrients.get('carbs'), str) else nutrients.get('carbs', 0),
                        float(nutrients.get('fat', '0').replace('g', '').strip()) if isinstance(nutrients.get('fat'), str) else nutrients.get('fat', 0)
                    ]
                })
                st.bar_chart(nutrient_df.set_index('Nutrient'))
            except:
                pass
            
            # Ingredients
            st.subheader("🥕 Ingredients")
            ingredients = data.get('ingredients', [])
            if ingredients:
                st.write(", ".join(ingredients))
            
            # Allergens
            st.subheader("⚠️ Allergens")
            allergens = data.get('allergens', [])
            if allergens:
                st.error(", ".join(allergens))
            else:
                st.success("No common allergens detected")
            
            # How it's made
            st.subheader("👨‍🍳 How It's Made")
            st.write(data.get('how_its_made', ''))
            
            # Health Score
            st.subheader("💚 Health Score")
            health_score = data.get('health_score', 'N/A')
            st.markdown(f"""
            <div class="metric-card">
                <div class="health-score">{health_score}</div>
                <div>out of 10</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Health Benefits & Concerns
            benefits = data.get('health_benefits', [])
            concerns = data.get('health_concerns', [])
            
            if benefits or concerns:
                st.subheader("🏥 Health Insights")
                if benefits:
                    st.success("**Benefits:** " + ", ".join(benefits))
                if concerns:
                    st.warning("**Concerns:** " + ", ".join(concerns))

            # 🎙 AI Voice Summary
            st.divider()
            st.subheader("🎙 AI Voice Summary")

            if 'current_speech' in st.session_state:
                speech_text = st.session_state.current_speech
                st.info(speech_text)

                if st.button("▶ Play Audio"):
                    audio_file = text_to_speech(
                        speech_text,
                        LANGUAGE_CODES[language]
                    )
                    if audio_file:
                        audio_bytes = open(audio_file, "rb").read()
                        st.audio(audio_bytes, format="audio/mp3")
                    else:
                        st.error("Audio generation failed.")
            
            # Action Buttons
            st.divider()
            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            
            with action_col1:
                if st.button("❤️ Add to Favorites"):
                    if data not in st.session_state.favorites:
                        st.session_state.favorites.append(data)
                        st.success("Added to favorites!")
                    else:
                        st.info("Already in favorites")
            
            with action_col2:
                if st.button("➕ Log Calories"):
                    try:
                        cal = extract_number(nutrients.get("calories")) if isinstance(nutrients.get('calories'), str) else nutrients.get('calories', 0)
                        st.session_state.calorie_log.append(cal)
                        st.success(f"Logged {cal} calories!")
                    except:
                        st.error("Could not log calories")
            
            with action_col3:
                if st.button("📤 Share"):
                    share_text = f"🍔 **{data.get('name')}**\n\n🔥 Calories: {nutrients.get('calories')}\n💚 Health Score: {health_score}\n\nAnalyzed with SnapMeal AI!"
                    st.text_area("Copy to share:", share_text, height=80)
            
            with action_col4:
                if st.button("📋 View Full Details"):
                    st.json(data)
        else:
            st.info("👆 Upload an image and click Analyze to see results!")

# ----------------------------
# Tab 2: History
# ----------------------------
with tab2:
    st.subheader("📜 Analysis History")
    
    if st.session_state.history:
        for i, item in enumerate(reversed(st.session_state.history)):
            with st.expander(f"#{len(st.session_state.history) - i}: {item['name']}"):
                col_h1, col_h2 = st.columns([1, 2])
                with col_h1:
                    if item.get('image'):
                        st.image(item['image'], width=150)
                with col_h2:
                    st.write(f"**Name:** {item['data'].get('name')}")
                    st.write(f"**Calories:** {item['data'].get('nutrients', {}).get('calories')}")
                    st.write(f"**Health Score:** {item['data'].get('health_score')}")
                    if st.button(f"Load Analysis", key=f"load_{i}"):
                        st.session_state.current_analysis = item['data']
                        st.rerun()
        
        if st.button("🗑 Clear History"):
            st.session_state.history = []
            st.success("History cleared!")
    else:
        st.info("No analysis history yet!")

# ----------------------------
# Tab 3: Favorites
# ----------------------------
with tab3:
    st.subheader("⭐ Favorite Analyses")
    
    if st.session_state.favorites:
        for i, fav in enumerate(st.session_state.favorites):
            with st.expander(f"❤️ {fav.get('name', 'Unknown')}"):
                st.write(f"**Description:** {fav.get('short_description', '')}")
                st.write(f"**Cuisine:** {fav.get('cuisine', '')}")
                st.write(f"**Calories:** {fav.get('nutrients', {}).get('calories')}")
                st.write(f"**Health Score:** {fav.get('health_score')}")
                
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    if st.button(f"View Details", key=f"fav_view_{i}"):
                        st.session_state.current_analysis = fav
                        st.rerun()
                with f_col2:
                    if st.button(f"Remove", key=f"fav_remove_{i}"):
                        st.session_state.favorites.pop(i)
                        st.rerun()
        
        if st.button("🗑 Clear All Favorites"):
            st.session_state.favorites = []
            st.success("Favorites cleared!")
    else:
        st.info("No favorites yet! Add some from the analysis tab.")

# ----------------------------
# Tab 4: Compare Foods
# ----------------------------
with tab4:
    st.subheader("📈 Food Comparison")
    
    if len(st.session_state.history) >= 1:
        food_options = [item['name'] for item in st.session_state.history]
        
        col_comp1, col_comp2 = st.columns(2)
        
        with col_comp1:
            food1 = st.selectbox("Select Food 1", food_options, index=0)
        with col_comp2:
            food2 = st.selectbox("Select Food 2", food_options, index=min(1, len(food_options)-1))
        
        if food1 and food2:
            item1 = next((item for item in st.session_state.history if item['name'] == food1), None)
            item2 = next((item for item in st.session_state.history if item['name'] == food2), None)
            
            if item1 and item2:
                st.divider()
                
                # Comparison Header
                comp_col1, comp_col2 = st.columns(2)
                with comp_col1:
                    st.markdown(f"### 🍔 {item1['name']}")
                with comp_col2:
                    st.markdown(f"### 🍔 {item2['name']}")
                
                # Comparison Metrics
                n1 = item1['data'].get('nutrients', {})
                n2 = item2['data'].get('nutrients', {})
                
                st.subheader("🔥 Nutrient Comparison")
                
                comp_data = {
                    'Nutrient': ['Calories', 'Protein (g)', 'Carbs (g)', 'Fat (g)'],
                    item1['name']: [
                        n1.get('calories', '0'),
                        n1.get('protein', '0'),
                        n1.get('carbs', '0'),
                        n1.get('fat', '0')
                    ],
                    item2['name']: [
                        n2.get('calories', '0'),
                        n2.get('protein', '0'),
                        n2.get('carbs', '0'),
                        n2.get('fat', '0')
                    ]
                }
                
                # PySpark nutrient comparison
                spark_comparison = spark_service.compare_history_items(item1, item2)
                if spark_comparison:
                    st.dataframe(spark_comparison, use_container_width=True, hide_index=True)

                ccol1, ccol2, ccol3, ccol4 = st.columns(4)

                with ccol1:
                    st.metric("Calories", n1.get('calories', 'N/A'), delta=n2.get('calories', 'N/A'))
                with ccol2:
                    st.metric("Protein", n1.get('protein', 'N/A'), delta=n2.get('protein', 'N/A'))
                with ccol3:
                    st.metric("Carbs", n1.get('carbs', 'N/A'), delta=n2.get('carbs', 'N/A'))
                with ccol4:
                    st.metric("Fat", n1.get('fat', 'N/A'), delta=n2.get('fat', 'N/A'))
                
                # Health Score Comparison
                hs1 = item1['data'].get('health_score', '0')
                hs2 = item2['data'].get('health_score', '0')
                
                st.subheader("💚 Health Score Comparison")
                hs_col1, hs_col2 = st.columns(2)
                with hs_col1:
                    st.metric(item1['name'], hs1)
                with hs_col2:
                    st.metric(item2['name'], hs2)
                
                # Winner
                try:
                    if float(hs1) > float(hs2):
                        st.success(f"🏆 {item1['name']} is healthier!")
                    elif float(hs2) > float(hs1):
                        st.success(f"🏆 {item2['name']} is healthier!")
                    else:
                        st.info("Both foods have equal health scores!")
                except:
                    pass
    else:
        st.info("Need at least 1 analyzed food to compare! Go to Analyze Food tab first.")

# ----------------------------
# Tab 5: Calorie Calculator
# ----------------------------
with tab5:
    st.subheader("🧮 Daily Calorie Calculator")
    
    # User Profile
    with st.expander("👤 Your Profile", expanded=True):
        p_col1, p_col2, p_col3 = st.columns(3)
        
        with p_col1:
            weight = st.number_input("Weight (kg)", min_value=1.0, value=70.0)
        with p_col2:
            height = st.number_input("Height (cm)", min_value=1.0, value=170.0)
        with p_col3:
            age = st.number_input("Age", min_value=1, value=30)

        gender = st.selectbox(
            "Gender",
            ["Male", "Female"]
        )
        
        activity_level = st.select_slider(
            "Activity Level",
            options=["Sedentary", "Light", "Moderate", "Active", "Very Active"],
            value="Moderate"
        )
    
    # BMR (Mifflin-St Jeor)
    if gender == "Male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    activity_multipliers = {
        "Sedentary": 1.2,
        "Light": 1.375,
        "Moderate": 1.55,
        "Active": 1.725,
        "Very Active": 1.9,
    }

    tdee = bmr * activity_multipliers[activity_level]

    st.subheader("🎯 Your Daily Calorie Needs")
    d_col1, d_col2, d_col3, d_col4 = st.columns(4)

    with d_col1:
        st.metric("BMR", f"{int(bmr)} kcal")
    with d_col2:
        st.metric("Daily Need (TDEE)", f"{int(tdee)} kcal")
    with d_col3:
        st.metric("To Lose Weight", f"{int(tdee - 500)} kcal")
    with d_col4:
        st.metric("To Gain Weight", f"{int(tdee + 500)} kcal")

    st.divider()

    st.subheader("📝 Today's Food Log")

    if st.session_state.calorie_log:
        log_stats = spark_service.aggregate_calorie_log(st.session_state.calorie_log)
        total_today = log_stats.get("total", sum(st.session_state.calorie_log))
        remaining = tdee - total_today

        st.progress(min(total_today / tdee, 1.0), text=f"{int(total_today)} / {int(tdee)} kcal")
        st.caption(
            f"PySpark: {int(log_stats.get('entries', 0))} entries, "
            f"avg {log_stats.get('average', 0)} kcal, max {log_stats.get('max_entry', 0)} kcal"
        )

        if remaining > 0:
            st.success(f"✅ {int(remaining)} calories remaining")
        else:
            st.warning(f"⚠️ {int(abs(remaining))} calories over your daily limit!")

        st.write("**Logged Foods:**")
        for i, cal in enumerate(st.session_state.calorie_log):
            st.write(f"  {i+1}. {cal} kcal")

        if st.button("🗑 Clear Today's Log"):
            st.session_state.calorie_log = []
            st.rerun()
    else:
        st.info("No foods logged today. Analyze some foods and click 'Log Calories' to add them!")

    st.divider()
    st.subheader("⚡ Quick Add")
    quick_cal = st.number_input("Add custom calories", min_value=0, value=0)
    if st.button("Add to Log"):
        if quick_cal > 0:
            st.session_state.calorie_log.append(quick_cal)
            st.success(f"Added {quick_cal} calories!")
            st.rerun()

# ----------------------------
# Tab 6: Spark Analytics
# ----------------------------
with tab6:
    engine = getattr(spark_service, "engine", "unknown")
    st.subheader(f"⚡ Analytics ({engine})")

    overview = spark_service.get_database_overview()
    o_col1, o_col2, o_col3, o_col4 = st.columns(4)
    with o_col1:
        st.metric("Foods in DB", int(overview.get("total_foods", 0)))
    with o_col2:
        st.metric("Avg Calories", overview.get("avg_calories", 0))
    with o_col3:
        st.metric("Max Calories", overview.get("max_calories", 0))
    with o_col4:
        st.metric("Min Calories", overview.get("min_calories", 0))

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("🌍 Avg Nutrition by Cuisine")
        cuisine_stats = spark_service.get_cuisine_stats()
        if cuisine_stats:
            import pandas as pd
            st.dataframe(pd.DataFrame(cuisine_stats), use_container_width=True, hide_index=True)

    with right:
        st.subheader("🔥 Top Foods by Calories")
        top_foods = spark_service.top_foods_by_metric("calories", limit=8)
        if top_foods:
            import pandas as pd
            st.dataframe(pd.DataFrame(top_foods), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🔎 Search Food Database (PySpark)")
    search_query = st.text_input("Search by name", placeholder="e.g. pizza, biryani")
    if search_query:
        results = spark_service.search_foods(search_query)
        if results:
            import pandas as pd
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        else:
            st.warning("No matches in the verified database.")

    st.divider()
    st.subheader("📊 Your Analysis History (PySpark)")
    if st.session_state.history:
        history_stats = spark_service.get_history_stats(st.session_state.history)
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            st.metric("Analyses", int(history_stats.get("analyses", 0)))
        with h_col2:
            st.metric("Avg Calories", history_stats.get("avg_calories", 0))
        with h_col3:
            st.metric("Avg Health Score", history_stats.get("avg_health_score", 0))
    else:
        st.info("Analyze some foods first to see history analytics.")

# ----------------------------
# Footer
# ----------------------------
st.divider()
st.markdown("""
<div style="text-align: center; color: #888;">
    <p>🍔 SnapMeal AI - Your Personal Nutrition Assistant</p>
    <p>Powered by Google Gemini AI & Apache PySpark</p>
</div>
""", unsafe_allow_html=True)
