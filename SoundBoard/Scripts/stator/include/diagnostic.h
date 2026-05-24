#ifndef STATOR_DIAGNOSTIC_H
#define STATOR_DIAGNOSTIC_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief מפעיל את תפריט הדיאגנוסטיקה (CLI) ב-Serial Monitor.
 * הפונקציה הזו "חוטפת" את ה-Thread הראשי ולא חוזרת, 
 * ומאפשרת בדיקה פרטנית של כל רכיב חומרה על הלוח.
 */
void diagnostic_run_cli(void);

#ifdef __cplusplus
}
#endif

#endif // STATOR_DIAGNOSTIC_H