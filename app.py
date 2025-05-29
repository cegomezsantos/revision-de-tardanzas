import streamlit as st
from moodle_services import (
    obtener_tareas_por_curso,
    analizar_tiempos_calificacion_tarea,
    MOODLE_URL_BASE,
)
from datetime import datetime
from etapa3_reporte_retrasos import display_reporte_retrasos

# --- Configuración de la Página Streamlit ---
st.set_page_config(page_title="Verificador de Calificaciones Moodle", layout="wide")

# --- INICIALIZACIÓN DE st.session_state (MOVER TODO AQUÍ ARRIBA) ---
if 'all_assignments_from_courses' not in st.session_state:
    st.session_state.all_assignments_from_courses = []
if 'tasks_for_analysis_options_display' not in st.session_state:
    st.session_state.tasks_for_analysis_options_display = {}
if 'analisis_completos' not in st.session_state:
    st.session_state.analisis_completos = {}
# 'selected_assignment_info_for_dates' ya no se usa directamente si el multiselect
# itera sobre los IDs seleccionados para mostrar la info. Si aún lo usas para
# alguna lógica interna, inicialízalo también. Por ahora, lo omito si no es esencial.

st.title("📝 Verificador de Tiempos de Calificación en Moodle")
# st.markdown(f"Conectado a: `{MOODLE_URL_BASE}`")

# --- CREACIÓN DE PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["1. Consultar Tareas y Fechas", "2. Analizar Tiempos", "3. Reporte de Retrasos"])

with tab1:
    st.header("Consultar Tareas por Curso(s) y Ver Fechas de Configuración")
    
    course_ids_str_input = st.text_input(
        "Ingresa el ID del CURSO (o IDs separados por coma):",
        key="course_ids_text_input_tab1",
        placeholder="Ej: 33538, 33539, 12345"
    )

    if st.button("📚 Consultar Tareas de Curso(s)", key="btn_consultar_cursos_tab1"):
        print("DEBUG APP.PY: Botón 'Consultar Tareas de Curso(s)' PRESIONADO")
        st.session_state.all_assignments_from_courses = []
        st.session_state.tasks_for_analysis_options_display = {}
        st.session_state.analisis_completos = {} 

        if not course_ids_str_input:
            print("DEBUG APP.PY: IDs de curso no ingresados.")
            st.warning("Por favor, ingresa al menos un ID de curso.")
        else:
            course_ids_list_str = [id_str.strip() for id_str in course_ids_str_input.split(',')]
            valid_course_ids_to_query = []
            for id_str in course_ids_list_str:
                if id_str.isdigit():
                    valid_course_ids_to_query.append(int(id_str))
                else:
                    st.error(f"El ID '{id_str}' no es un número válido y será ignorado.")
            
            if not valid_course_ids_to_query:
                st.warning("No se ingresaron IDs de curso numéricos válidos.")
            else:
                all_retrieved_assignments_temp = []
                has_errors_during_fetch = False
                total_courses_to_query = len(valid_course_ids_to_query)
                progress_bar = st.progress(0.0) # st.progress(0) si prefieres empezar en 0 entero
                progress_text_area = st.empty()
                
                for i, course_id in enumerate(valid_course_ids_to_query):
                    current_progress = (i + 1) / total_courses_to_query
                    progress_text_area.text(f"Consultando curso ID: {course_id} ({i+1}/{total_courses_to_query})...")
                    assignments_from_api_for_this_course = obtener_tareas_por_curso(course_id)
                    if assignments_from_api_for_this_course is not None:
                        if assignments_from_api_for_this_course:
                             all_retrieved_assignments_temp.extend(assignments_from_api_for_this_course)
                    else:
                        st.error(f"Error crítico al consultar el curso ID {course_id}.")
                        has_errors_during_fetch = True
                    progress_bar.progress(current_progress)
                progress_text_area.text("¡Consulta de cursos completada!")
                progress_bar.empty()

                if all_retrieved_assignments_temp:
                    st.success(f"Se encontraron {len(all_retrieved_assignments_temp)} tareas.")
                    st.session_state.all_assignments_from_courses = all_retrieved_assignments_temp
                    for task in st.session_state.all_assignments_from_courses:
                        course_id_of_task = task.get('courseid_original_request', 'Desconocido')
                        display_str = f"{task.get('name', 'Tarea s/n')} (Curso ID: {course_id_of_task}, Tarea ID: {task.get('id', 'N/A')})"
                        st.session_state.tasks_for_analysis_options_display[task['id']] = display_str
                
                if not all_retrieved_assignments_temp and not has_errors_during_fetch:
                     st.info("No se encontraron tareas en los cursos especificados o los cursos no tienen tareas.")
                elif not all_retrieved_assignments_temp and has_errors_during_fetch:
                     st.warning("No se pudieron recuperar tareas de ningún curso debido a errores. Revise la consola del servidor.")

    # Esta es la línea 91 del error original, ahora debería funcionar
    if st.session_state.all_assignments_from_courses: 
        task_options_for_dates_view = {
            task['id']: task.get('name', f"Tarea ID: {task['id']}")
            for task in st.session_state.all_assignments_from_courses
        }
        if task_options_for_dates_view:
            selected_task_ids_for_dates_view = st.multiselect(
                "Selecciona UNA O MÁS tareas para ver sus fechas de configuración:",
                options=list(task_options_for_dates_view.keys()),
                format_func=lambda task_id: task_options_for_dates_view.get(task_id, f"ID: {task_id}"),
                key="multiselect_view_assignment_dates_tab1"
            )
            if selected_task_ids_for_dates_view:
                for task_id_to_show in selected_task_ids_for_dates_view:
                    tarea_info = next((task for task in st.session_state.all_assignments_from_courses if task['id'] == task_id_to_show), None)
                    if tarea_info:
                        st.subheader(f"Fechas para Tarea: {tarea_info['name']} (ID: {tarea_info['id']})")
                        def format_short_date(timestamp_str_long):
                            if timestamp_str_long == "N/A" or not timestamp_str_long: return "N/A"
                            try: return datetime.strptime(timestamp_str_long.split(" ")[0], '%Y-%m-%d').strftime('%Y-%m-%d')
                            except ValueError: return timestamp_str_long
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Envíos desde", format_short_date(tarea_info.get('allowsubmissionsfromdate_str', "N/A")))
                        col2.metric("Entrega", format_short_date(tarea_info.get('duedate_str', "N/A")))
                        col3.metric("Límite", format_short_date(tarea_info.get('cutoffdate_str', "N/A")))
                        col4.metric("Calificación esperada", format_short_date(tarea_info.get('gradingduedate_str', "N/A")))
                        st.markdown("---")

with tab2:
    st.header("Analizar Tiempos de Calificación")
    
    selected_task_ids_for_analysis_input = []
    if st.session_state.tasks_for_analysis_options_display:
        selected_task_ids_for_analysis_input = st.multiselect(
            "Selecciona tareas para analizar sus tiempos de calificación:",
            options=list(st.session_state.tasks_for_analysis_options_display.keys()), 
            format_func=lambda task_id: st.session_state.tasks_for_analysis_options_display.get(task_id, f"ID Tarea: {task_id}"),
            key="multiselect_analyze_tasks_tab2"
        )
    else:
        st.info("Consulta tareas en la Pestaña 1 para poder seleccionarlas aquí para análisis.")

    if st.button("📊 Analizar Tiempos de Calificación Seleccionados", key="btn_analizar_tiempos_tab2"):
        if not selected_task_ids_for_analysis_input:
            st.warning("Por favor, selecciona al menos una tarea para analizar.")
        else:
            st.info(f"Analizando tareas (IDs): {selected_task_ids_for_analysis_input}")
            st.session_state.analisis_completos = {} 
            
            for assignid_to_analyze in selected_task_ids_for_analysis_input:
                task_name_display = st.session_state.tasks_for_analysis_options_display.get(assignid_to_analyze, f"ID Tarea: {assignid_to_analyze}")
                with st.expander(f"Resultados para Tarea: {task_name_display}", expanded=True):
                    with st.spinner(f"Obteniendo datos para tarea ID: {assignid_to_analyze}..."):
                        resultados_analisis = analizar_tiempos_calificacion_tarea(assignid_to_analyze) 
                    st.session_state.analisis_completos[assignid_to_analyze] = resultados_analisis

                    if resultados_analisis:
                        st.success(f"Análisis completo. {len(resultados_analisis)} participantes/envíos encontrados.")
                        data_for_df = [{"Estudiante": res['student_name'], "Estado Envío": res['submission_status'],
                                        "Fecha Envío": res['submission_date_str'], "Fecha Calificación": res['graded_date_str'],
                                        "Tiempo para Calificar": res['time_to_grade_str'], "Calificación": res['grade']}
                                       for res in resultados_analisis]
                        st.dataframe(data_for_df, use_container_width=True)
                    else:
                        st.warning(f"No se encontraron datos de calificación o participantes para la tarea ID: {assignid_to_analyze}, o no hubo envíos/calificaciones que analizar.")

with tab3:
    display_reporte_retrasos()


st.sidebar.info(
    """
    **Acerca de esta App:**
    Ayuda a verificar tiempos de calificación en Moodle.
    1. **Pestaña 1:** Consulta tareas por ID de curso y ve sus fechas.
    2. **Pestaña 2:** Analiza tiempos de calificación para tareas seleccionadas.
    3. **Pestaña 3:** Ve un reporte de calificaciones con retraso mayor a 7 días.
    """
)