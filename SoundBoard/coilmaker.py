import math

def generate_perfect_stator_coil(filename="wedge_coil_45mm.dxf"):
    # ==========================================
    # הגדרות הנדסיות מנעלות ללוח 180x180 ודיסק 110
    # ==========================================
    hole_radius = 5.5       # רדיוס החור הפנימי (קוטר 11 מ"מ לסליל הקנוי)
    D = 45.0                # מרכז הסליל ממוקם ב-45 מ"מ ממרכז הלוח
    
    coil_outer_x = 15.0     # נמתח 15 מ"מ החוצה (מגיע לרדיוס 60 מ"מ בלוח)
    coil_inner_x = -15.0    # נמתח 15 מ"מ פנימה (מגיע לרדיוס 30 מ"מ בלוח)
    
    gap = 0.6               # מרווח בידוד ממוחשב בין סלילים שכנים (ייצור מפעל)
    turns = 24              # מספר כריכות מנצח לניצול שטח
    alpha = math.radians(15) # 30 מעלות לגזרת פיצה (15 לכל צד)
    
    steps_per_turn = 360
    total_steps = turns * steps_per_turn
    points = []
    
    def get_max_r(phi):
        ray_dx = math.cos(phi)
        ray_dy = math.sin(phi)
        min_r = 999.0
        
        if ray_dx > 0:
            r = coil_outer_x / ray_dx
            if 0 < r < min_r: min_r = r
        if ray_dx < 0:
            r = coil_inner_x / ray_dx
            if 0 < r < min_r: min_r = r
            
        denominator_top = ray_dy - ray_dx * math.tan(alpha)
        if denominator_top > 0.0001:
            r = (D * math.tan(alpha) - gap) / denominator_top
            if 0 < r < min_r: min_r = r
            
        denominator_bottom = -ray_dy - ray_dx * math.tan(alpha)
        if denominator_bottom > 0.0001:
            r = (D * math.tan(alpha) - gap) / denominator_bottom
            if 0 < r < min_r: min_r = r
            
        return min_r

    for i in range(total_steps + 1):
        p = i / total_steps
        phi = (i / steps_per_turn) * 2 * math.pi
        R_max = get_max_r(phi)
        
        # מורפינג: מעיגול מושלם בחור הפנימי לטרפז פיצה זוויתי בחוץ
        r_current = hole_radius + p * (R_max - hole_radius)
        
        x = r_current * math.cos(phi)
        y = r_current * math.sin(phi)
        points.append((x, y))
        
    with open(filename, "w") as f:
        f.write("0\nSECTION\n2\nENTITIES\n")
        for j in range(len(points) - 1):
            x1, y1 = points[j]
            x2, y2 = points[j + 1]
            f.write("0\nLINE\n8\nF_Cu\n")
            f.write(f"10\n{x1:.4f}\n20\n{y1:.4f}\n30\n0.0\n")
            f.write(f"11\n{x2:.4f}\n21\n{y2:.4f}\n31\n0.0\n")
        f.write("0\nENDSEC\n0\nEOF\n")
        
    print(f"✅ קובץ ה-DXF המעודכן '{filename}' נוצר בהצלחה!")
    print(f"טבעת הסלילים תתפוס בלוח את הרדיוס מ-30 מ\"מ עד 60 מ\"מ.")

if __name__ == "__main__":
    generate_perfect_stator_coil()