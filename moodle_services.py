import streamlit as st # <--- IMPORTANTE: Añade esta línea
import requests
import json
import urllib3
from datetime import datetime, timedelta

# Suprimir warnings de SSL no verificado (NO RECOMENDADO PARA PRODUCCIÓN SIN VALIDACIÓN)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    # Intenta acceder a los secrets. Esto funcionará en Streamlit Cloud si están configurados,
    # o localmente si tienes un archivo .streamlit/secrets.toml
    MOODLE_URL_BASE = st.secrets["MOODLE_API_URL_BASE"]
    MOODLE_TOKEN    = st.secrets["MOODLE_API_TOKEN"]

except KeyError as e:
    # Este bloque se ejecuta si el archivo secrets.toml existe (o los secrets están configurados en la nube)
    # PERO una de las claves específicas (MOODLE_API_URL_BASE o MOODLE_API_TOKEN) no se encuentra.
    error_message = (
        f"ERROR CRÍTICO: La clave secreta '{e.args[0]}' no fue encontrada.\n"
        "Por favor, asegúrate de que MOODLE_API_URL_BASE y MOODLE_API_TOKEN estén definidos:\n"
        "- En Streamlit Community Cloud: En la configuración 'Secrets' de tu aplicación.\n"
        "- Para desarrollo local: En un archivo llamado '.streamlit/secrets.toml' en la raíz de tu proyecto."
    )
    print(error_message)
    # Detener la aplicación si faltan secretos cruciales
    # MOODLE_URL_BASE = "ERROR_URL_NO_CONFIGURADA" # Para evitar NameError más adelante
    # MOODLE_TOKEN = "ERROR_TOKEN_NO_CONFIGURADO" # Para evitar NameError más adelante
    st.error(error_message)
    st.stop() # Detiene la ejecución del script de Streamlit

# --- FUNCIONES AUXILIARES ---
# (tus funciones timestamp_to_datetime_str y calculate_time_difference se mantienen igual)
def timestamp_to_datetime_str(timestamp, short_format=False):
    if timestamp and isinstance(timestamp, (int, float)) and timestamp > 0:
        dt_object = datetime.fromtimestamp(timestamp)
        if short_format:
            return dt_object.strftime('%Y-%m-%d')
        else:
            return dt_object.strftime('%Y-%m-%d %H:%M:%S')
    return "N/A"

def calculate_time_difference(start_ts, end_ts):
    if start_ts and end_ts and start_ts > 0 and end_ts > 0:
        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)
        if end_dt < start_dt: return "Calificado antes del envío" 
        difference = end_dt - start_dt
        days = difference.days
        hours, remainder = divmod(difference.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days > 0: parts.append(f"{days} día{'s' if days != 1 else ''}")
        if hours > 0: parts.append(f"{hours} hora{'s' if hours != 1 else ''}")
        if minutes > 0: parts.append(f"{minutes} minuto{'s' if minutes != 1 else ''}")
        if not parts and difference.total_seconds() < 60 : return "Menos de un minuto"
        elif not parts: return "Mismo instante"
        return ", ".join(parts)
    return "N/A"


# --- FUNCIONES WEB SERVICES MOODLE ---

def obtener_tareas_por_curso(course_id):
    """
    Obtiene todas las tareas (assignments) de un curso específico.
    """
    params = {
        "wstoken":                   MOODLE_TOKEN,
        "wsfunction":                "mod_assign_get_assignments",
        "moodlewsrestformat":        "json",
        "courseids[0]":              course_id,
        # "capabilities[0]":           "mod/assign:view", # Opcional
        "includenotenrolledcourses": 1 # Opcional
    }

    print(f"DEBUG: obtener_tareas_por_curso - Llamando a mod_assign_get_assignments con params: {params}")

    try:
        r = requests.post(MOODLE_URL_BASE, data=params, verify=False)
        print(f"DEBUG: obtener_tareas_por_curso - Respuesta HTTP Status Code: {r.status_code}")
        r.raise_for_status()
        data = r.json()

        if "exception" in data:
            print(f"MOODLE API EXCEPTION (obtener_tareas_por_curso): {data.get('message', 'Sin mensaje')}")
            print(f"MOODLE API EXCEPTION Detalle: errorcode='{data.get('errorcode', 'N/A')}', debuginfo='{data.get('debuginfo', 'N/A')}'")
            return []

        assignments_list = []
        courses_data = data.get("courses", [])
        print(f"DEBUG: obtener_tareas_por_curso - Cursos encontrados: {len(courses_data)}")

        if not courses_data:
            print("DEBUG: obtener_tareas_por_curso - No se devolvieron cursos en la respuesta.")
            return []

        for course_data in courses_data:
            # Asegurarse que el ID del curso procesado es el que se solicitó.
            # Si course_id es un string, convertirlo a int para la comparación.
            if course_data.get("id") == int(course_id): 
                for assign_data in course_data.get("assignments", []):
                    assignments_list.append({
                        "id": assign_data.get("id"), # Este es el assignmentid
                        "cmid": assign_data.get("cmid"),
                        "name": assign_data.get("name"),
                        "duedate_ts": assign_data.get("duedate"),
                        "allowsubmissionsfromdate_ts": assign_data.get("allowsubmissionsfromdate"),
                        "gradingduedate_ts": assign_data.get("gradingduedate"),
                        "cutoffdate_ts": assign_data.get("cutoffdate"),
                        "duedate_str": timestamp_to_datetime_str(assign_data.get("duedate")),
                        "allowsubmissionsfromdate_str": timestamp_to_datetime_str(assign_data.get("allowsubmissionsfromdate")),
                        "gradingduedate_str": timestamp_to_datetime_str(assign_data.get("gradingduedate")),
                        "cutoffdate_str": timestamp_to_datetime_str(assign_data.get("cutoffdate")),
                    })
                break 
        
        print(f"DEBUG: obtener_tareas_por_curso - Total tareas encontradas para curso {course_id}: {len(assignments_list)}")
        return assignments_list

    except requests.exceptions.HTTPError as e_http:
        print(f"CRITICAL ERROR: HTTPError en obtener_tareas_por_curso: {e_http}")
        if e_http.response is not None: print(f"CRITICAL ERROR: Respuesta del servidor (HTTPError): {e_http.response.text}")
        return []
    except requests.exceptions.RequestException as e_req:
        print(f"CRITICAL ERROR: RequestException en obtener_tareas_por_curso: {e_req}")
        return []
    except json.JSONDecodeError as e_json:
        print(f"CRITICAL ERROR: JSONDecodeError en obtener_tareas_por_curso. Error: {e_json}. Respuesta: {r.text if 'r' in locals() else 'No response object'}")
        return []
    except Exception as e_general:
        print(f"CRITICAL ERROR: Excepción general en obtener_tareas_por_curso: {e_general}")
        import traceback
        traceback.print_exc()
        return []

# EN moodle_services.py

# ... (MOODLE_URL_BASE, MOODLE_TOKEN, funciones auxiliares, obtener_tareas_por_curso se mantienen) ...

def obtener_participantes(assignid):
    """Obtiene los participantes de una tarea (assignment.id)."""
    print(f"DEBUG: obtener_participantes - Intentando obtener participantes para assignid: {assignid}")
    params = {
        "wstoken":            MOODLE_TOKEN,
        "wsfunction":         "mod_assign_list_participants",
        "moodlewsrestformat": "json",
        "assignid":           assignid,
        "groupid":            0,
        "filter":             "",
        "skip":               0,
        "limit":              0,
        "onlyids":            0,
        "includeenrolments":  1
    }
    try:
        r = requests.post(MOODLE_URL_BASE, data=params, verify=False)
        print(f"DEBUG: obtener_participantes - Status Code: {r.status_code} para assignid: {assignid}")
        # print(f"DEBUG: obtener_participantes - Respuesta cruda: {r.text[:300]}...") # Descomentar si es necesario
        r.raise_for_status()
        parts_data = r.json()
        if "exception" in parts_data:
            print(f"MOODLE API EXCEPTION (obtener_participantes) para assignid {assignid}: {parts_data.get('message', 'N/A')}, ErrorCode: {parts_data.get('errorcode', 'N/A')}")
            return None # Indicar error
        
        # Si parts_data es una lista (como se espera)
        if isinstance(parts_data, list):
            print(f"DEBUG: obtener_participantes - Número de participantes JSON crudos recibidos: {len(parts_data)}")
            participants_dict = {p["id"]: p.get("fullname", "Nombre Desconocido") for p in parts_data if "id" in p}
            print(f"DEBUG: obtener_participantes - Diccionario de participantes procesado (primeros 3): {dict(list(participants_dict.items())[:3])}")
            return participants_dict if participants_dict else {} # Devolver dict vacío si no hay participantes válidos
        else:
            # Si la respuesta no es una lista, es inesperado para mod_assign_list_participants
            print(f"CRITICAL ERROR: obtener_participantes - Respuesta inesperada, no es una lista. Tipo: {type(parts_data)}. Datos: {str(parts_data)[:300]}...")
            return None # Indicar error

    except requests.exceptions.HTTPError as e_http:
        print(f"CRITICAL ERROR (HTTPError) en obtener_participantes para assignid {assignid}: {e_http}")
        if e_http.response is not None: print(f"CRITICAL ERROR: Respuesta del servidor: {e_http.response.text}")
        return None
    except requests.exceptions.RequestException as e_req:
        print(f"CRITICAL ERROR (RequestException) en obtener_participantes para assignid {assignid}: {e_req}")
        return None
    except json.JSONDecodeError as e_json:
        print(f"CRITICAL ERROR (JSONDecodeError) en obtener_participantes para assignid {assignid}. Error: {e_json}. Respuesta: {r.text if 'r' in locals() else 'No response object'}")
        return None
    except Exception as e_general:
        print(f"CRITICAL ERROR (Excepción general) en obtener_participantes para assignid {assignid}: {e_general}")
        import traceback
        traceback.print_exc()
        return None

def obtener_submisiones(assignid):
    """Obtiene todas las submisiones para una tarea específica (assignment.id)."""
    print(f"DEBUG: obtener_submisiones - Intentando obtener submisiones para assignid: {assignid}")
    params = {
        "wstoken":            MOODLE_TOKEN,
        "wsfunction":         "mod_assign_get_submissions",
        "moodlewsrestformat": "json",
        "assignmentids[0]":   assignid,
        "status":             "", 
    }
    try:
        r = requests.post(MOODLE_URL_BASE, data=params, verify=False)
        print(f"DEBUG: obtener_submisiones - Status Code: {r.status_code} para assignid: {assignid}")
        r.raise_for_status()
        data = r.json()

        if "exception" in data:
            print(f"MOODLE API EXCEPTION (obtener_submisiones) para assignid {assignid}: {data.get('message', 'N/A')}, ErrorCode: {data.get('errorcode', 'N/A')}")
            return None # Indicar error
        
        if data.get("assignments") and len(data["assignments"]) > 0:
            submissions = data["assignments"][0].get("submissions", [])
            print(f"DEBUG: obtener_submisiones - Número de submisiones encontradas: {len(submissions)}")
            return submissions
        else:
            print(f"DEBUG: obtener_submisiones - No se encontró la estructura 'assignments' o estaba vacía para assignid {assignid}.")
            return [] # Devuelve lista vacía si la estructura no es la esperada pero no hay excepción
            
    except requests.exceptions.HTTPError as e_http:
        print(f"CRITICAL ERROR (HTTPError) en obtener_submisiones para assignid {assignid}: {e_http}")
        if e_http.response is not None: print(f"CRITICAL ERROR: Respuesta del servidor: {e_http.response.text}")
        return None
    # ... (resto de los except como antes, devolviendo None) ...
    except requests.exceptions.RequestException as e_req:
        print(f"CRITICAL ERROR (RequestException) en obtener_submisiones para assignid {assignid}: {e_req}")
        return None
    except json.JSONDecodeError as e_json:
        print(f"CRITICAL ERROR (JSONDecodeError) en obtener_submisiones para assignid {assignid}. Error: {e_json}. Respuesta: {r.text if 'r' in locals() else 'No response object'}")
        return None
    except Exception as e_general:
        print(f"CRITICAL ERROR (Excepción general) en obtener_submisiones para assignid {assignid}: {e_general}")
        import traceback
        traceback.print_exc()
        return None


def obtener_calificaciones_tarea(assignid):
    """Obtiene las calificaciones para una tarea específica (assignment.id)."""
    print(f"DEBUG: obtener_calificaciones_tarea - Intentando obtener calificaciones para assignid: {assignid}")
    params = {
        "wstoken":            MOODLE_TOKEN,
        "wsfunction":         "mod_assign_get_grades",
        "moodlewsrestformat": "json",
        "assignmentids[0]":   assignid,
        "since":              0 
    }
    try:
        r = requests.post(MOODLE_URL_BASE, data=params, verify=False)
        print(f"DEBUG: obtener_calificaciones_tarea - Status Code: {r.status_code} para assignid: {assignid}")
        r.raise_for_status()
        data = r.json()

        if "exception" in data:
            print(f"MOODLE API EXCEPTION (obtener_calificaciones_tarea) para assignid {assignid}: {data.get('message', 'N/A')}, ErrorCode: {data.get('errorcode', 'N/A')}")
            return None # Indicar error

        if data.get("assignments") and len(data["assignments"]) > 0:
            grades = data["assignments"][0].get("grades", [])
            print(f"DEBUG: obtener_calificaciones_tarea - Número de calificaciones encontradas: {len(grades)}")
            return grades
        else:
            print(f"DEBUG: obtener_calificaciones_tarea - No se encontró la estructura 'assignments' o estaba vacía para assignid {assignid}.")
            return [] # Devuelve lista vacía si la estructura no es la esperada pero no hay excepción
            
    except requests.exceptions.HTTPError as e_http:
        print(f"CRITICAL ERROR (HTTPError) en obtener_calificaciones_tarea para assignid {assignid}: {e_http}")
        if e_http.response is not None: print(f"CRITICAL ERROR: Respuesta del servidor: {e_http.response.text}")
        return None
    # ... (resto de los except como antes, devolviendo None) ...
    except requests.exceptions.RequestException as e_req:
        print(f"CRITICAL ERROR (RequestException) en obtener_calificaciones_tarea para assignid {assignid}: {e_req}")
        return None
    except json.JSONDecodeError as e_json:
        print(f"CRITICAL ERROR (JSONDecodeError) en obtener_calificaciones_tarea para assignid {assignid}. Error: {e_json}. Respuesta: {r.text if 'r' in locals() else 'No response object'}")
        return None
    except Exception as e_general:
        print(f"CRITICAL ERROR (Excepción general) en obtener_calificaciones_tarea para assignid {assignid}: {e_general}")
        import traceback
        traceback.print_exc()
        return None


def analizar_tiempos_calificacion_tarea(assignid):
    """
    Analiza los tiempos de calificación para una tarea específica (assignment.id).
    """
    print(f"\nDEBUG: analizar_tiempos_calificacion_tarea - INICIANDO ANÁLISIS para assignid: {assignid}")
    
    participantes = obtener_participantes(assignid)
    # Si obtener_participantes devuelve None (error) o un diccionario vacío (sin participantes)
    if participantes is None:
        print(f"ERROR: analizar_tiempos_calificacion_tarea - Falló la obtención de participantes para assignid {assignid}. No se puede continuar.")
        return [] 
    if not participantes: # Diccionario vacío
        print(f"INFO: analizar_tiempos_calificacion_tarea - No se encontraron participantes para assignid {assignid}. El análisis resultará vacío.")
        return []
        
    submisiones = obtener_submisiones(assignid)
    if submisiones is None: # Error en la llamada
        print(f"ERROR: analizar_tiempos_calificacion_tarea - Falló la obtención de submisiones para assignid {assignid}.")
        # Podrías decidir continuar sin submisiones o abortar. Por ahora, continuamos pero no habrá fechas de envío.
        submisiones = [] # Tratar como lista vacía para que el resto del código no falle
    
    calificaciones = obtener_calificaciones_tarea(assignid)
    if calificaciones is None: # Error en la llamada
        print(f"ERROR: analizar_tiempos_calificacion_tarea - Falló la obtención de calificaciones para assignid {assignid}.")
        calificaciones = [] # Tratar como lista vacía

    print(f"DEBUG: analizar_tiempos_calificacion_tarea - Participantes: {len(participantes)}, Submisiones: {len(submisiones)}, Calificaciones: {len(calificaciones)} para assignid {assignid}")

    submisiones_por_usuario = {}
    for sub in submisiones: # submisiones es una lista
        userid = sub.get("userid")
        if userid:
            submisiones_por_usuario[userid] = {
                "submission_time": sub.get("timemodified"), 
                "submission_status": sub.get("status"),
                "submitted": sub.get("status") == "submitted" or sub.get("status") == "graded"
            }

    calificaciones_por_usuario = {}
    for grade_info in calificaciones: # calificaciones es una lista
        userid = grade_info.get("userid")
        if userid:
            calificaciones_por_usuario[userid] = {
                "grade": grade_info.get("grade"),
                "timegraded": grade_info.get("timemodified") 
            }

    resultados_analisis = []
    # Iterar sobre los participantes (que es un dict) es la base
    for userid, fullname in participantes.items():
        # ... (resto de la lógica de cruce de datos y cálculo de tiempo se mantiene igual) ...
        info_sub = submisiones_por_usuario.get(userid, {})
        info_grade = calificaciones_por_usuario.get(userid, {})
        
        student_submission_ts = None
        if info_sub.get("submitted"): # Solo si realmente envió
             student_submission_ts = info_sub.get("submission_time")
        
        teacher_graded_ts = info_grade.get("timegraded")
        
        tiempo_calificacion = "N/A"
        if student_submission_ts and teacher_graded_ts:
            tiempo_calificacion = calculate_time_difference(student_submission_ts, teacher_graded_ts)
        elif student_submission_ts and not teacher_graded_ts:
             tiempo_calificacion = "Pendiente de calificar"
        elif not student_submission_ts: # Modificado para ser más general
            if info_grade.get("grade") is not None: # Si no envió pero tiene nota
                tiempo_calificacion = "Calificado sin envío"
            else: # No envió y no tiene nota
                tiempo_calificacion = "No ha enviado"
        else: # Otros casos (ej. no hay student_submission_ts pero sí teacher_graded_ts sin nota)
            tiempo_calificacion = "Situación de datos incompleta"


        resultados_analisis.append({
            "assignment_id": assignid,
            "user_id": userid,
            "student_name": fullname,
            "submission_status": info_sub.get("submission_status", "Sin información de envío"),
            "submission_date_ts": student_submission_ts,
            "submission_date_str": timestamp_to_datetime_str(student_submission_ts),
            "graded_date_ts": teacher_graded_ts,
            "graded_date_str": timestamp_to_datetime_str(teacher_graded_ts),
            "grade": info_grade.get("grade", "Sin calificar"),
            "time_to_grade_str": tiempo_calificacion
        })
    
    print(f"DEBUG: analizar_tiempos_calificacion_tarea - Total resultados generados: {len(resultados_analisis)}")
    return resultados_analisis

# El resto de moodle_services.py (obtener_tareas_por_curso) no cambia.