import math
import argparse
import sys

def write_kicad_module(filename, module_name, points, track_width):
    """פונקציית עזר לכתיבת הקובץ המשותפת לשני הסוגים"""
    with open(filename, "w") as f:
        f.write(f'(module "{module_name}" (layer "F.Cu")\n')
        for j in range(len(points) - 1):
            x1, y1 = points[j]
            x2, y2 = points[j + 1]
            f.write(f'  (fp_line (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) (layer "F.Cu") (width {track_width}))\n')
        f.write(')\n')
    print(f"✅ הצלחה! נוצר קובץ: {filename}")

def generate_main_coil(filename):
    hole_radius, D = 5.5, 52.0
    R_inner, R_outer = 37.0, 68.0
    gap, turns, track_width = 0.6, 12, 0.4
    alpha = math.radians(15)
    
    points = []
    total_steps = turns * 360
    
    def get_max_r(phi):
        ray_dx, ray_dy = math.cos(phi), math.sin(phi)
        min_r = 999.0
        
        # חיתוך זוויות
        den_top = ray_dy - ray_dx * math.tan(alpha)
        if den_top > 0.0001: min_r = min(min_r, (D * math.tan(alpha) - gap/2) / den_top)
        den_bot = -ray_dy - ray_dx * math.tan(alpha)
        if den_bot > 0.0001: min_r = min(min_r, (D * math.tan(alpha) - gap/2) / den_bot)
            
        # חיתוך מעגלי
        b = 2 * D * ray_dx
        for R_limit in [R_outer, R_inner]:
            c = D**2 - R_limit**2
            disc = b**2 - 4 * c
            if disc >= 0:
                # לוגיקה לבחירת קשת פנימית/חיצונית לפי סימן
                r_val = (-b + math.sqrt(disc)) / 2 if R_limit == R_outer else (-b - math.sqrt(disc)) / 2
                if 0 < r_val < min_r: min_r = r_val
        return min_r

    for i in range(total_steps + 1):
        p = i / total_steps
        phi = (i / 360) * 2 * math.pi
        r_current = hole_radius + p * (get_max_r(phi) - hole_radius)
        points.append((r_current * math.cos(phi), r_current * math.sin(phi)))
        
    write_kicad_module(filename, "Main_Coil_Perfect_Ring", points, track_width)

def generate_stab_coil(filename):
    inner_r, track_width, clearance = 3.2, 0.4, 0.2
    turns = 4
    outer_r = inner_r + turns * (track_width + clearance)
    points = []
    
    steps = turns * 120
    for i in range(steps + 1):
        theta = (i / 120) * 2 * math.pi
        r = inner_r + (i / steps) * (outer_r - inner_r)
        points.append((r * math.cos(theta), r * math.sin(theta)))
        
    write_kicad_module(filename, "Stabilization_Coil", points, track_width)

def main():
    parser = argparse.ArgumentParser(description="KiCad Coil Generator")
    parser.add_argument("--type", choices=["main", "stab"], required=True, help="סוג הסליל לייצור")
    parser.add_argument("--output", help="שם קובץ היעד", default=None)
    
    args = parser.parse_args()
    
    if args.type == "main":
        filename = args.output or "main_coil.kicad_mod"
        generate_main_coil(filename)
    elif args.type == "stab":
        filename = args.output or "stab_coil.kicad_mod"
        generate_stab_coil(filename)

if __name__ == "__main__":
    main()

"""
ליצירת סליל ראשי עם שם ברירת מחדל:
Bash
python coil_gen.py --type main
ליצירת סליל ייצוב עם שם קובץ מותאם אישית:
Bash
python coil_gen.py --type stab --output my_stabilizer_v1.kicad_mod
קבלת עזרה (אם שכחת את הפקודות):
Bash
python coil_gen.py --help
"""