# etapa3_reporte_retrasos.py
import streamlit as st
import pandas as pd # Necesitarás pandas: pip install pandas

def display_reporte_retrasos():
    st.header("3. Reporte de Tareas Calificadas con Retraso (+7 días)")

    if 'analisis_completos' not in st.session_state or not st.session_state.analisis_completos:
        st.info("Realiza un análisis de tiempos de calificación en la Pestaña 2 para ver este reporte.")
        return

    # st.session_state.analisis_completos es un diccionario {assign_id: [lista_de_resultados_analisis]}
    
    tareas_con_retraso_general = {} # {assign_id: contador_retrasos}
    estudiantes_con_retraso_detalle = [] # Lista de diccionarios para tabla detallada

    # Definir el umbral de retraso (7 días en segundos)
    RETRASO_UMBRAL_DIAS = 7
    RETRASO_UMBRAL_SEGUNDOS = RETRASO_UMBRAL_DIAS * 24 * 60 * 60

    for assign_id, resultados_analisis in st.session_state.analisis_completos.items():
        if not resultados_analisis: # Si no hay resultados para esta tarea
            continue

        # Obtener nombre de la tarea para el reporte
        # Asumimos que 'tasks_for_analysis_options_display' tiene la info
        task_display_name = st.session_state.get('tasks_for_analysis_options_display', {}).get(assign_id, f"Tarea ID: {assign_id}")
        
        contador_retrasos_tarea = 0
        for res in resultados_analisis:
            # Necesitamos la diferencia en segundos o días numéricamente.
            # La función calculate_time_difference devuelve un string.
            # Deberíamos modificar analizar_tiempos_calificacion_tarea para que también devuelva la diferencia numérica.
            # Por ahora, vamos a *asumir* que tenemos acceso a los timestamps.
            
            submission_ts = res.get('submission_date_ts')
            graded_ts = res.get('graded_date_ts')

            if submission_ts and graded_ts and submission_ts > 0 and graded_ts > 0:
                diferencia_segundos = graded_ts - submission_ts
                if graded_ts > submission_ts and diferencia_segundos > RETRASO_UMBRAL_SEGUNDOS:
                    contador_retrasos_tarea += 1
                    dias_retraso = diferencia_segundos / (24 * 60 * 60)
                    estudiantes_con_retraso_detalle.append({
                        "Tarea": task_display_name,
                        "Estudiante": res.get('student_name', 'N/A'),
                        "Fecha Envío": res.get('submission_date_str', 'N/A'),
                        "Fecha Calificación": res.get('graded_date_str', 'N/A'),
                        "Días de Retraso (Profesor)": f"{dias_retraso:.1f}"
                    })
        
        if contador_retrasos_tarea > 0:
            tareas_con_retraso_general[task_display_name] = contador_retrasos_tarea

    if not tareas_con_retraso_general and not estudiantes_con_retraso_detalle:
        st.success(f"¡Excelente! Ningún profesor tardó más de {RETRASO_UMBRAL_DIAS} días en calificar las tareas analizadas.")
        return

    st.subheader("Resumen de Tareas con Calificaciones Retrasadas")
    if tareas_con_retraso_general:
        for tarea, count in tareas_con_retraso_general.items():
            st.write(f"- **{tarea}**: {count} estudiante(s) calificado(s) con más de {RETRASO_UMBRAL_DIAS} días de retraso.")
    else:
        st.write(f"No hay tareas con más de {RETRASO_UMBRAL_DIAS} días de retraso en la calificación de los estudiantes analizados.")

    st.subheader("Detalle de Estudiantes Calificados con Retraso")
    if estudiantes_con_retraso_detalle:
        df_retrasos = pd.DataFrame(estudiantes_con_retraso_detalle)
        st.dataframe(df_retrasos, use_container_width=True)
    else:
        st.write("No hay detalles de estudiantes calificados con retraso para mostrar.")