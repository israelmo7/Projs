import streamlit as st
import json
import os
from PIL import Image
import cv2

# הגדרות נתיבים
EDL_FILE = "edit_decision_list.json"
OUTPUT_RESOLUTION = (1920, 1080)

st.set_page_config(page_title="AI Video Editor - GUI", layout="wide")

def load_edl():
    if os.path.exists(EDL_FILE):
        with open(EDL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_edl(data):
    with open(EDL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_thumbnail(path, media_type):
    """מחלץ פריים מייצג עבור התצוגה בממשק"""
    try:
        if media_type == "video":
            cap = cv2.VideoCapture(path)
            ret, frame = cap.read()
            cap.release()
            if ret:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        elif media_type == "image":
            img = Image.open(path)
            return img
    except:
        pass
    return None

def main():
    st.title("🎥 עורך ה-JSON האינטראקטיבי")
    st.write("כאן ניתן לערוך כתוביות, לשנות סדר ולראות את המדיה לפני הרינדור.")

    data = load_edl()
    if not data:
        st.error(f"לא נמצא קובץ {EDL_FILE}. וודא שהרצת את Stage 2.")
        return

    decisions = data.get("edit_decisions", [])
    
    # תפריט עליון
    col_save, col_info = st.columns([1, 4])
    if col_save.button("💾 שמור שינויים ל-JSON"):
        save_edl(data)
        st.success("השינויים נשמרו בהצלחה!")

    st.divider()

    # תצוגת רשימת הקליפים
    for i, item in enumerate(decisions):
        m_type = item.get("media_type")
        path = item.get("file_path", "Intro/Outro Block")
        
        with st.container():
            c1, c2, c3 = st.columns([1, 2, 1])
            
            # עמודה 1: תצוגה מקדימה
            if m_type in ["image", "video"]:
                thumb = get_thumbnail(path, m_type)
                if thumb is not None:
                    c1.image(thumb, use_container_width=True)
                c1.caption(os.path.basename(path))
            else:
                c1.info(f"🧱 {m_type.upper()}")

            # עמודה 2: עריכת תוכן
            if m_type in ["intro", "outro"]:
                new_caption = c2.text_area(f"טקסט {m_type}", item.get("caption", ""), key=f"cap_{i}")
                item["caption"] = new_caption
            else:
                profile = item.get("transition_profile", {})
                current_cap = profile.get("caption", "")
                
                # אם השדה ריק, המשתמש יראה סימון TODO
                label = "✍️ הוסף כתובית (Highlight)" if "caption" in profile else "מידע כללי"
                new_cap = c2.text_input(label, current_cap, key=f"cap_{i}", placeholder="השאר ריק אם לא נדרש טקסט")
                
                if "caption" in profile or new_cap:
                    item.setdefault("transition_profile", {})["caption"] = new_cap

            # עמודה 3: שליטה ובקרה
            c3.write(f"⏱️ משך: {item.get('duration')} שניות")
            
            # כפתורי הזזה (לוגיקה פשוטה להחלפת מיקומים ברשימה)
            col_up, col_down = c3.columns(2)
            if i > 0 and col_up.button("⬆️", key=f"up_{i}"):
                decisions[i], decisions[i-1] = decisions[i-1], decisions[i]
                save_edl(data)
                st.rerun()
            if i < len(decisions) - 1 and col_down.button("⬇️", key=f"down_{i}"):
                decisions[i], decisions[i+1] = decisions[i+1], decisions[i]
                save_edl(data)
                st.rerun()

        st.divider()

if __name__ == "__main__":
    main()