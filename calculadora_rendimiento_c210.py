import math
import os
import streamlit as st
from fpdf import FPDF
from datetime import datetime

# ==========================================
# 0. CONFIGURACIÓN GENERAL
# ==========================================
IMG_PATH = "Cessna 210 FAB-411.jpg"
PESO_MAX_LBS = 3800

# Ajuste altimétrico estándar (inHg)
QNH_ESTANDAR_INHG = 29.92

# Texto de configuración de aeronave para cada fase.
# El de "Aterrizaje" viene de tu script original (app_landing_c210.py).
# El de "Despegue" queda como PLACEHOLDER porque tu script de consola
# (cessna210_takeoff.py) no incluía esta configuración explícita:
# complétalo con flaps / potencia / Vr según el POH antes de usarlo
# en vuelo real.
CONFIG_TEXT_DISPLAY = {
    "Despegue": "[COMPLETAR SEGÚN POH] Flaps ___°, Potencia Máxima, Vr ___ KIAS.",
    "Aterrizaje": "Flaps 30°, Motor Cortado, Frenado Máximo, App 71 KIAS.",
}

# ==========================================
# 1. BASES DE DATOS (Tablas del Manual)
# ==========================================
ALTITUDES = [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000]
TEMPERATURAS = [0, 10, 20, 30, 40]

# --- DESPEGUE (de cessna210_takeoff.py) ---
DESPEGUE_GROUND_ROLL = [
    [341.4, 367.3, 394.7, 423.7, 455.7],
    [373.4, 402.3, 432.8, 464.8, 499.9],
    [410.0, 440.4, 474.0, 510.5, 548.6],
    [449.6, 483.1, 521.2, 560.8, 603.5],
    [493.8, 531.9, 573.0, 617.2, 664.5],
    [544.1, 586.7, 632.5, 681.2, 734.6],
    [600.5, 647.7, 698.0, 752.9, 812.3],
    [664.5, 716.3, 774.2, 835.2, None],
    [736.1, 795.5, None, None, None],
]

DESPEGUE_TOTAL_50FT = [
    [554.7, 597.4, 641.6, 690.4, 743.7],
    [611.1, 656.8, 707.1, 763.5, 824.5],
    [673.6, 725.4, 783.3, 848.9, 920.5],
    [746.8, 806.2, 873.3, 947.9, 1033.3],
    [830.6, 900.7, 978.4, 1068.3, 1170.4],
    [931.2, 1013.5, 1106.4, 1216.2, 1345.7],
    [1053.1, 1152.1, 1268.0, 1406.7, 1580.4],
    [1204.0, 1330.5, 1481.3, 1671.8, None],
    [1400.6, 1571.2, None, None, None],
]

# --- ATERRIZAJE (de app_landing_c210.py) ---
ATERRIZAJE_GROUND_ROLL = [
    [221.0, 228.6, 237.7, 245.4, 253.0],
    [228.6, 237.7, 245.4, 254.5, 262.1],
    [237.7, 246.9, 254.5, 263.7, 272.8],
    [246.9, 256.0, 265.2, 274.3, 283.5],
    [256.0, 265.2, 274.3, 283.5, 294.1],
    [265.2, 275.8, 285.0, 294.1, 304.8],
    [275.8, 286.5, 295.7, 306.3, 315.5],
    [286.5, 297.2, 307.8, 318.5, 327.7],
    [297.2, 307.8, 320.0, 330.7, 341.4],
]

ATERRIZAJE_TOTAL_50FT = [
    [438.9, 451.1, 463.3, 475.5, 487.7],
    [451.1, 463.3, 475.5, 489.2, 501.4],
    [464.8, 477.0, 489.2, 502.9, 516.6],
    [477.0, 490.7, 506.0, 519.7, 533.4],
    [492.3, 506.0, 519.7, 533.4, 548.6],
    [506.0, 521.2, 534.9, 550.2, 565.4],
    [521.2, 538.0, 551.7, 566.9, 582.2],
    [538.0, 553.2, 570.0, 585.2, 600.5],
    [553.2, 570.0, 588.3, 603.5, 620.3],
]

TABLAS = {
    "Despegue": (DESPEGUE_GROUND_ROLL, DESPEGUE_TOTAL_50FT),
    "Aterrizaje": (ATERRIZAJE_GROUND_ROLL, ATERRIZAJE_TOTAL_50FT),
}

# ==========================================
# 2. FUNCIONES COMUNES DE CÁLCULO Y FORMATO
# (idénticas en ambos scripts originales)
# ==========================================
def interpolar_bilineal(alt, temp, matriz_datos):
    """Realiza la interpolación cruzando altitud y temperatura."""
    if alt < 0 or alt > 8000 or temp < 0 or temp > 40:
        return "Fuera de los límites de la tabla."

    alt_inf_idx = max([i for i, a in enumerate(ALTITUDES) if a <= alt])
    alt_sup_idx = min(len(ALTITUDES) - 1, alt_inf_idx + 1)

    temp_inf_idx = max([i for i, t in enumerate(TEMPERATURAS) if t <= temp])
    temp_sup_idx = min(len(TEMPERATURAS) - 1, temp_inf_idx + 1)

    q11 = matriz_datos[alt_inf_idx][temp_inf_idx]
    q21 = matriz_datos[alt_sup_idx][temp_inf_idx]
    q12 = matriz_datos[alt_inf_idx][temp_sup_idx]
    q22 = matriz_datos[alt_sup_idx][temp_sup_idx]

    if None in (q11, q21, q12, q22):
        return "Rendimiento de ascenso insuficiente (< 150 fpm)."

    x, x1, x2 = alt, ALTITUDES[alt_inf_idx], ALTITUDES[alt_sup_idx]
    y, y1, y2 = temp, TEMPERATURAS[temp_inf_idx], TEMPERATURAS[temp_sup_idx]

    if x1 == x2 and y1 == y2:
        return q11
    if x1 == x2:
        return q11 + (y - y1) * (q12 - q11) / (y2 - y1)
    if y1 == y2:
        return q11 + (x - x1) * (q21 - q11) / (x2 - x1)

    r1 = ((x2 - x) / (x2 - x1)) * q11 + ((x - x1) / (x2 - x1)) * q21
    r2 = ((x2 - x) / (x2 - x1)) * q12 + ((x - x1) / (x2 - x1)) * q22
    return ((y2 - y) / (y2 - y1)) * r1 + ((y - y1) / (y2 - y1)) * r2


def calcular_viento(direccion_viento, intensidad, rumbo_pista):
    """Devuelve la componente de viento en cara (positivo) o en cola (negativo)."""
    angulo_pista = rumbo_pista * 10
    diferencia = math.radians(direccion_viento - angulo_pista)
    headwind = intensidad * math.cos(diferencia)
    crosswind = intensidad * math.sin(diferencia)
    return headwind, crosswind


def calcular_altitud_presion(elevacion_campo, qnh_inhg):
    """Convierte elevación de campo + ajuste altimétrico QNH (inHg) a altitud de presión (ft).

    Fórmula estándar de altímetro: PA = Elevación + (29.92 - QNH) x 1000
    """
    return elevacion_campo + (QNH_ESTANDAR_INHG - qnh_inhg) * 1000


def obtener_matriz_respaldo(alt, temp, matriz):
    alt_inf_idx = max([i for i, a in enumerate(ALTITUDES) if a <= alt])
    alt_sup_idx = min(len(ALTITUDES) - 1, alt_inf_idx + 1)
    temp_inf_idx = max([i for i, t in enumerate(TEMPERATURAS) if t <= temp])
    temp_sup_idx = min(len(TEMPERATURAS) - 1, temp_inf_idx + 1)

    t_vals = [TEMPERATURAS[temp_inf_idx]]
    if temp_inf_idx != temp_sup_idx:
        if temp not in TEMPERATURAS:
            t_vals.append(temp)
        t_vals.append(TEMPERATURAS[temp_sup_idx])

    a_vals = [ALTITUDES[alt_inf_idx]]
    if alt_inf_idx != alt_sup_idx:
        if alt not in ALTITUDES:
            a_vals.append(alt)
        a_vals.append(ALTITUDES[alt_sup_idx])

    encabezado = ["Alt / Temp"] + [f"{t}°C" for t in t_vals]

    filas = []
    for a in a_vals:
        fila = [f"{a} ft"]
        for t in t_vals:
            val = interpolar_bilineal(a, t, matriz)
            if a == alt and t == temp:
                fila.append(f"<span style='color:red; font-weight:bold;'>{val:.1f}</span>")
            else:
                fila.append(f"{val:.1f}")
        filas.append(fila)

    return encabezado, filas


def render_html_table(encabezado, filas):
    html = "<table style='width:100%; text-align:center; border-collapse: collapse;'>"
    html += "<tr style='background-color: #f0f2f6;'>"
    for h in encabezado:
        html += f"<th style='border: 1px solid #d3d3d3; padding: 6px;'>{h}</th>"
    html += "</tr>"
    for fila in filas:
        html += "<tr>"
        for val in fila:
            html += f"<td style='border: 1px solid #d3d3d3; padding: 6px;'>{val}</td>"
        html += "</tr>"
    html += "</table>"
    return html


def pdf_agregar_tabla(pdf, titulo, encabezado, filas):
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, titulo, ln=True)
    pdf.set_font("Arial", 'B', 9)
    w = [35] + [30] * (len(encabezado) - 1)
    for i, header in enumerate(encabezado):
        pdf.cell(w[i], 8, header, border=1, align='C')
    pdf.ln()
    pdf.set_font("Arial", '', 9)
    for fila in filas:
        for i, val in enumerate(fila):
            clean_val = val.replace("<span style='color:red; font-weight:bold;'>", "").replace("</span>", "")
            if "color:red" in val:
                pdf.set_text_color(200, 0, 0)
                pdf.set_font("Arial", 'B', 9)
            else:
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Arial", '', 9)
            pdf.cell(w[i], 8, clean_val, border=1, align='C')
        pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    pdf.ln(5)


# ==========================================
# 3. LÓGICA DE CÁLCULO POR FASE (Despegue / Aterrizaje)
# ==========================================
def calcular_resultado(fase, altitud, temperatura, dir_viento, vel_viento, rumbo_pista, superficie):
    """Interpola, aplica corrección de viento y de superficie según la fase elegida."""
    tabla_gr, tabla_tot = TABLAS[fase]

    gr_base = interpolar_bilineal(altitud, temperatura, tabla_gr)
    total_base = interpolar_bilineal(altitud, temperatura, tabla_tot)

    if isinstance(gr_base, str):
        return {"error": gr_base}

    headwind, crosswind = calcular_viento(dir_viento, vel_viento, rumbo_pista)
    factor_viento = 1.0
    porc_v_gr = 0.0
    advertencia_viento = None

    if headwind > 0:
        # Disminuye 10% por cada 10 nudos en cara
        porc_v_gr = (headwind / 10) * 10.0
        factor_viento -= porc_v_gr / 100.0
        porc_v_gr = -porc_v_gr
    elif headwind < 0:
        # Aumenta 10% por cada 2.5 nudos en cola (límite manual: 10 kt)
        viento_cola = abs(headwind)
        if viento_cola > 10:
            advertencia_viento = "Viento de cola excede el límite del manual (10 kt). Calculado a 10 kt."
            viento_cola = 10
        porc_v_gr = (viento_cola / 2.5) * 10.0
        factor_viento += porc_v_gr / 100.0

    porc_v_tot = porc_v_gr
    val_v_gr = gr_base * (abs(porc_v_gr) / 100.0)
    val_v_tot = total_base * (abs(porc_v_tot) / 100.0)

    gr_viento = gr_base * factor_viento
    total_viento = total_base * factor_viento

    diff_pasto = 0.0
    gr_final = gr_viento
    total_final = total_viento

    if superficie == "Pasto Seco":
        if fase == "Despegue":
            # cessna210_takeoff.py: +15% multiplicativo, solo sobre la carrera en tierra
            gr_final = gr_viento * 1.15
            total_final = total_viento
        else:
            # app_landing_c210.py: +40% de la carrera base, aditivo a ambas distancias
            diff_pasto = gr_base * 0.40
            gr_final = gr_viento + diff_pasto
            total_final = total_viento + diff_pasto

    matriz_gr = obtener_matriz_respaldo(altitud, temperatura, tabla_gr)
    matriz_tot = obtener_matriz_respaldo(altitud, temperatura, tabla_tot)

    return {
        'gr_base': gr_base, 'total_base': total_base,
        'gr_viento': gr_viento, 'total_viento': total_viento,
        'gr_final': gr_final, 'total_final': total_final,
        'headwind': headwind, 'crosswind': crosswind,
        'porc_v_gr': porc_v_gr, 'porc_v_tot': porc_v_tot,
        'val_v_gr': val_v_gr, 'val_v_tot': val_v_tot,
        'diff_pasto': diff_pasto,
        'm_gr': matriz_gr, 'm_tot': matriz_tot,
        'advertencia_viento': advertencia_viento,
        'alt': altitud, 'temp': temperatura, 'dir_v': dir_viento,
        'vel_v': vel_viento, 'rwy': rumbo_pista, 'sup': superficie,
    }


# ==========================================
# 4. GENERACIÓN DE PDF
# ==========================================
def generar_pdf(fase, alt, temp, dir_v, vel_v, rwy, sup, r):
    gr_b, tot_b = r['gr_base'], r['total_base']
    gr_v, tot_v = r['gr_viento'], r['total_viento']
    gr_f, tot_f = r['gr_final'], r['total_final']
    hw, cw = r['headwind'], r['crosswind']
    porc_v_gr, porc_v_tot = r['porc_v_gr'], r['porc_v_tot']
    val_v_gr, val_v_tot = r['val_v_gr'], r['val_v_tot']
    diff_pasto = r['diff_pasto']
    m_gr, m_tot = r['m_gr'], r['m_tot']
    elevacion_campo, qnh = r['elevacion_campo'], r['qnh']

    tipo_viento_txt = "Viento frontal" if hw >= 0 else "Viento de cola"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)

    if os.path.exists(IMG_PATH):
        pdf.image(IMG_PATH, x=20, y=10, w=40)
        pdf.set_xy(65, 12)
        pdf.set_font("Arial", 'B', 15)
        pdf.cell(0, 8, f"PLANILLA DE {fase.upper()} - CESSNA 210", ln=True)
        pdf.set_x(65)
        pdf.set_font("Arial", '', 10)
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
        pdf.cell(0, 6, f"| Fecha de emision: {fecha_actual}", ln=True)
        pdf.ln(12)
    else:
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"PLANILLA DE {fase.upper()} - CESSNA 210", ln=True, align='C')
        pdf.set_font("Arial", '', 10)
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
        pdf.cell(0, 10, f"Fecha de emision: {fecha_actual}", ln=True, align='C')
        pdf.ln(10)

    # 1. Condiciones
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"1. CONDICIONES APLICADAS (PESO MAX. {PESO_MAX_LBS} LBS)", ln=True)
    pdf.set_font("Arial", '', 9)
    texto_condiciones = (
        f"- Configuración: {CONFIG_TEXT_DISPLAY[fase]}\n"
        f"- Elevación de Campo: {elevacion_campo:.0f} ft | QNH: {qnh:.2f} inHg "
        f"-> Altitud de Presión calculada: {alt:.0f} pies.\n"
        f"- Temperatura OAT: {temp} °C.\n"
        f"- Pista en uso: {rwy} (Eje {int(rwy*10)}°) | Superficie: {sup}.\n"
        f"- Viento: {tipo_viento_txt} de {abs(hw):.1f} kt (Dir: {dir_v}°, Vel: {vel_v} kt, Cruzado: {abs(cw):.1f} kt)."
    )
    pdf.multi_cell(0, 5, texto_condiciones)
    pdf.ln(5)

    # 2. Interpolación Base
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, "2. INTERPOLACION BASE (Temperatura y Elevación)", ln=True)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, "Valores base extraídos de la tabla. El valor señalado en rojo indica el punto exacto interpolado.", ln=True)
    pdf.ln(3)
    enc_gr, fil_gr = m_gr
    pdf_agregar_tabla(pdf, "Carrera en Tierra Base (m)", enc_gr, fil_gr)
    enc_tot, fil_tot = m_tot
    pdf_agregar_tabla(pdf, "Distancia Total 50FT Base (m)", enc_tot, fil_tot)

    # 3. Efecto del Viento
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, "3. CORRECCION ARITMETICA POR EFECTO DE VIENTO", ln=True)
    pdf.set_font("Arial", '', 9)
    operador = "-" if hw >= 0 else "+"
    txt_v_gr = f"Carrera en Tierra: {gr_b:.1f} {operador} ({abs(porc_v_gr):.1f}% de {gr_b:.1f} = {abs(val_v_gr):.1f}) = {gr_v:.1f} m"
    txt_v_tot = f"Distancia Total 50FT: {tot_b:.1f} {operador} ({abs(porc_v_tot):.1f}% de {tot_b:.1f} = {abs(val_v_tot):.1f}) = {tot_v:.1f} m"
    pdf.multi_cell(0, 5, f"- Componente: {tipo_viento_txt} de {abs(hw):.1f} kt.\n- {txt_v_gr}\n- {txt_v_tot}")
    pdf.ln(5)

    # 4. Efecto de Superficie
    if sup == "Pasto Seco":
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, "4. CORRECCION ARITMETICA POR TIPO DE SUPERFICIE (PASTO SECO)", ln=True)
        pdf.set_font("Arial", '', 9)
        if fase == "Despegue":
            txt_pasto = (
                f"- Carrera en tierra con viento aplicado: {gr_v:.1f} m\n"
                f"- Incremento reglamentario (+15% multiplicativo sobre Ground Roll): {gr_v:.1f} x 1.15 = {gr_f:.1f} m\n"
                f"- Distancia Total 50FT: sin corrección por superficie según el manual = {tot_f:.1f} m"
            )
        else:
            txt_pasto = (
                f"- Carrera en tierra base obtenida de la tabla: {gr_b:.1f} m\n"
                f"- Incremento reglamentario (40% de la carrera en tierra): 40% de {gr_b:.1f} = +{diff_pasto:.1f} m\n"
                f"- Carrera en Tierra final: {gr_v:.1f} + {diff_pasto:.1f} = {gr_f:.1f} m\n"
                f"- Distancia Total final: {tot_v:.1f} + {diff_pasto:.1f} = {tot_f:.1f} m"
            )
        pdf.multi_cell(0, 5, txt_pasto)
        pdf.ln(5)

    # 5. Resultados Finales
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"5. RESULTADOS FINALES DE {fase.upper()}", ln=True)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"CARRERA EN TIERRA (Ground Roll): {gr_f:.1f} metros", ln=True)
    pdf.cell(0, 8, f"DISTANCIA TOTAL (Franqueo 50FT): {tot_f:.1f} metros", ln=True)

    return pdf.output(dest="S").encode("latin-1")


# ==========================================
# 5. INTERFAZ DE USUARIO (STREAMLIT)
# ==========================================
st.set_page_config(page_title="Rendimiento C210", page_icon="✈️", layout="wide")

if 'calculado' not in st.session_state:
    st.session_state.calculado = False
    st.session_state.resultados = {}
    st.session_state.pdf_bytes = None
    st.session_state.fase_calculada = None

col_img, col_title = st.columns([1, 4])
with col_img:
    if os.path.exists(IMG_PATH):
        st.image(IMG_PATH, use_container_width=True)
with col_title:
    st.title("Calculadora de Rendimiento - Cessna 210")
    st.markdown("**Grupo Aéreo Mixto | Sección Operaciones**")

fase = st.radio(
    "¿Qué fase quieres planificar primero?",
    ["Despegue", "Aterrizaje"],
    horizontal=True,
)

with st.form("formulario_vuelo"):
    st.markdown(f"**Condiciones de Ingreso ({fase})**")
    col1, col2, col3 = st.columns(3)

    with col1:
        elevacion_campo = st.number_input("Elevación del Campo (pies)", min_value=0.0, max_value=9000.0, value=1371.0, step=10.0)
        qnh = st.number_input("Ajuste Altimétrico QNH (inHg)", min_value=27.50, max_value=31.50, value=29.92, step=0.01)

    with col2:
        temperatura = st.number_input("Temperatura Exterior (°C)", min_value=0.0, max_value=40.0, value=30.0, step=1.0)
        superficie = st.selectbox("Superficie de Pista", ["Asfalto / Pista Seca", "Pasto Seco"])

    with col3:
        dir_viento = st.number_input("Dirección del Viento (°)", min_value=0.0, max_value=360.0, value=330.0, step=10.0)
        vel_viento = st.number_input("Intensidad del Viento (kt)", min_value=0.0, max_value=50.0, value=12.0, step=1.0)
        rumbo_pista = st.number_input("Rumbo de Pista en uso (1-36)", min_value=1.0, max_value=36.0, value=34.0, step=1.0)

    submit = st.form_submit_button(f"Calcular Rendimiento de {fase}", use_container_width=True)

if submit:
    altitud_presion = calcular_altitud_presion(elevacion_campo, qnh)
    resultado = calcular_resultado(fase, altitud_presion, temperatura, dir_viento, vel_viento, rumbo_pista, superficie)

    if "error" in resultado:
        st.error(f"⚠️ {resultado['error']} (Altitud de presión calculada: {altitud_presion:.0f} ft)")
        st.session_state.calculado = False
    else:
        if resultado.get("advertencia_viento"):
            st.warning(f"⚠️ {resultado['advertencia_viento']}")

        resultado['elevacion_campo'] = elevacion_campo
        resultado['qnh'] = qnh

        st.session_state.resultados = resultado
        st.session_state.fase_calculada = fase
        st.session_state.pdf_bytes = generar_pdf(
            fase, altitud_presion, temperatura, dir_viento, vel_viento, rumbo_pista, superficie, resultado
        )
        st.session_state.calculado = True

# ==========================================
# 6. MOSTRAR RESULTADOS EN WEB
# ==========================================
if st.session_state.calculado:
    fase_r = st.session_state.fase_calculada
    res = st.session_state.resultados
    st.divider()

    # 1. CONDICIONES APLICADAS
    st.subheader(f"1. Condiciones Aplicadas al {fase_r}")
    hw_val = res['headwind']
    cw_val = res['crosswind']
    tipo_v_str = "Viento frontal" if hw_val >= 0 else "Viento de cola"

    st.info(f"""
    * **Configuración Aeronave:** {CONFIG_TEXT_DISPLAY[fase_r]}
    * **Elevación y QNH:** Elevación de campo **{res['elevacion_campo']:.0f} ft** con QNH **{res['qnh']:.2f} inHg** → Altitud de Presión calculada: **{res['alt']:.0f} pies**.
    * **Temperatura:** OAT de **{res['temp']} °C**.
    * **Pista y Superficie:** Pista en uso **{res['rwy']}** (Eje `{int(res['rwy']*10)}°`) con superficie de **{res['sup']}**.
    * **Viento Aplicado:** {tipo_v_str} de **{abs(hw_val):.1f} nudos** (Dirección: {res['dir_v']}°, Intensidad: {res['vel_v']} kt, Cruzado: {abs(cw_val):.1f} kt).
    """)

    st.divider()

    # 2. INTERPOLACIÓN BASE
    st.subheader("2. Interpolación Base (Temperatura y Elevación)")
    st.markdown("Valores base extraídos de la tabla. El valor resaltado en **rojo** indica el punto exacto interpolado:")

    t_col1, t_col2 = st.columns(2)
    enc_gr, fil_gr = res['m_gr']
    enc_tot, fil_tot = res['m_tot']

    with t_col1:
        st.markdown("**Carrera en Tierra Base (m)**")
        st.markdown(render_html_table(enc_gr, fil_gr), unsafe_allow_html=True)

    with t_col2:
        st.markdown("**Distancia Total 50FT Base (m)**")
        st.markdown(render_html_table(enc_tot, fil_tot), unsafe_allow_html=True)

    st.divider()

    # 3. EFECTO DEL VIENTO
    st.subheader("3. Corrección Aritmética por Efecto de Viento")
    operador = "-" if hw_val >= 0 else "+"
    st.markdown(f"""
    * **Componente aplicada:** {tipo_v_str} de `{abs(hw_val):.1f} kt`.
    * **Desglose en Carrera en Tierra:** `{res['gr_base']:.1f} m` {operador} (`{abs(res['porc_v_gr']):.1f}%` de `{res['gr_base']:.1f}` = `{abs(res['val_v_gr']):.1f} m`) = **`{res['gr_viento']:.1f} m`**
    * **Desglose en Distancia Total (50 ft):** `{res['total_base']:.1f} m` {operador} (`{abs(res['porc_v_tot']):.1f}%` de `{res['total_base']:.1f}` = `{abs(res['val_v_tot']):.1f} m`) = **`{res['total_viento']:.1f} m`**
    """)

    # 4. EFECTO DE SUPERFICIE
    if res['sup'] == "Pasto Seco":
        st.divider()
        st.subheader("4. Corrección Aritmética por Tipo de Superficie (Pasto Seco)")
        if fase_r == "Despegue":
            st.markdown(f"""
            * **Carrera en tierra con viento aplicado:** `{res['gr_viento']:.1f} m`.
            * **Incremento reglamentario (+15% multiplicativo sobre Ground Roll):** `{res['gr_viento']:.1f} x 1.15` = **`{res['gr_final']:.1f} m`**.
            * **Distancia Total (50FT):** sin corrección por superficie según el manual = **`{res['total_final']:.1f} m`**.
            """)
        else:
            st.markdown(f"""
            * **Carrera en tierra base obtenida de la tabla:** `{res['gr_base']:.1f} m`.
            * **Cálculo del 40% reglamentario (sobre Ground Roll):** `40% de {res['gr_base']:.1f} = +{res['diff_pasto']:.1f} m`.
            * **Operación final (Carrera en Tierra):** `{res['gr_viento']:.1f} + {res['diff_pasto']:.1f}` = **`{res['gr_final']:.1f} m`**.
            * **Operación final (Distancia Total):** `{res['total_viento']:.1f} + {res['diff_pasto']:.1f}` = **`{res['total_final']:.1f} m`**.
            """)

    st.divider()

    # 5. RESULTADOS FINALES
    st.subheader(f"5. Resultados Finales de {fase_r}")
    res_col1, res_col2 = st.columns(2)

    with res_col1:
        st.metric(f"Carrera de {fase_r} Final (Ground Roll)", f"{res['gr_final']:.1f} m")
    with res_col2:
        st.metric("Distancia Total Final (50 FT)", f"{res['total_final']:.1f} m")

    st.divider()

    # Botón de Descarga
    st.download_button(
        label="📥 Descargar Reporte Desglosado en PDF",
        data=st.session_state.pdf_bytes,
        file_name=f"{fase_r}_C210_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
