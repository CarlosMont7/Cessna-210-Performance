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

# Texto de configuración de aeronave para cada fase, según el POH.
# Sin velocidades (Vr / velocidad de aterrizaje): varían con viento y peso,
# así que no se muestran como un valor fijo.
CONFIG_TEXT_DISPLAY = {
    "Despegue": "Flaps 10°, Potencia Máxima.",
    "Aterrizaje": "Flaps 30°, Potencia Idle (Ralentí), Frenado Máximo.",
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
        fila = [f"{a:.0f} ft"]
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


def pdf_agregar_tabla(pdf, x, ancho_total, titulo, encabezado, filas, alto_fila=5):
    """Dibuja una mini-tabla de respaldo (interpolación) posicionada en x, con ancho fijo.
    Pensada para caber dentro de media hoja horizontal (columna de una fase)."""
    n_cols = len(encabezado)
    w_label = ancho_total * 0.30
    w_col = (ancho_total - w_label) / (n_cols - 1)
    anchos = [w_label] + [w_col] * (n_cols - 1)

    pdf.set_x(x)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(ancho_total, 5, titulo, ln=True)

    pdf.set_x(x)
    pdf.set_font("Arial", 'B', 7)
    for i, header in enumerate(encabezado):
        pdf.cell(anchos[i], alto_fila, header, border=1, align='C')
    pdf.ln()

    for fila in filas:
        pdf.set_x(x)
        for i, val in enumerate(fila):
            clean_val = val.replace("<span style='color:red; font-weight:bold;'>", "").replace("</span>", "")
            if "color:red" in val:
                pdf.set_text_color(200, 0, 0)
                pdf.set_font("Arial", 'B', 7)
            else:
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Arial", '', 7)
            pdf.cell(anchos[i], alto_fila, clean_val, border=1, align='C')
        pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 8)


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
# 4. GENERACIÓN DE PDF COMBINADO (Despegue + Aterrizaje en una sola hoja horizontal)
# ==========================================
ALTURA_BLOQUE_VACIO = 154  # mm — alto de referencia para la caja "NO CALCULADO" (incluye tablas de respaldo)


def _cell_texto_ajustado(pdf, ancho, alto, texto, tam_max=7.5, tam_min=5.5):
    """Escribe una celda de texto reduciendo el tamaño de letra si no entra en el ancho dado,
    para evitar que el texto se desborde hacia la columna vecina."""
    tam = tam_max
    pdf.set_font("Arial", '', tam)
    while pdf.get_string_width(texto) > ancho - 2 and tam > tam_min:
        tam -= 0.5
        pdf.set_font("Arial", '', tam)
    pdf.cell(ancho, alto, texto, border=1, ln=True)


def _dibujar_bloque_fase(pdf, nombre_fase, fase, r, x, y, ancho):
    """Dibuja la caja de una fase (DESPEGUE/ATERRIZAJE) en la posición x,y del PDF combinado.
    Si r es None, dibuja una caja con 'NO CALCULADO' en rojo en su lugar.
    """
    pdf.set_xy(x, y)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_x(x)
    pdf.cell(ancho, 8, f"CONDICIONES DE {nombre_fase}", border=1, align='C', ln=True)

    if r is None:
        pdf.set_x(x)
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(ancho, ALTURA_BLOQUE_VACIO - 8, "NO CALCULADO", border=1, align='C')
        pdf.set_text_color(0, 0, 0)
        return

    hw, cw = r['headwind'], r['crosswind']
    tipo_viento_txt = "Viento frontal" if hw >= 0 else "Viento de cola"
    operador = "-" if hw >= 0 else "+"

    campos = [
        ("Configuración", CONFIG_TEXT_DISPLAY[fase]),
        ("Peso Bruto", f"{PESO_MAX_LBS} lbs (MAX)"),
        ("Elev. Campo / QNH", f"{r['elevacion_campo']:.0f} ft  /  {r['qnh']:.2f} inHg"),
        ("Altitud de Presión", f"{r['alt']:.0f} ft"),
        ("Temperatura OAT", f"{r['temp']} °C"),
        ("Pista en Uso", f"{r['rwy']:.0f}  (Eje {int(r['rwy']*10)}°)"),
        ("Superficie", r['sup']),
        ("Viento", f"{tipo_viento_txt} {abs(hw):.1f} kt | Cruzado {abs(cw):.1f} kt (Dir {r['dir_v']:.0f}° / {r['vel_v']:.0f} kt)"),
    ]

    pdf.set_font("Arial", '', 7.5)
    for etiqueta, valor in campos:
        pdf.set_x(x)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(ancho * 0.34, 6, etiqueta, border=1)
        _cell_texto_ajustado(pdf, ancho * 0.66, 6, str(valor))

    # Interpolación base (respaldo): valores reales de la tabla del manual usados para interpolar
    pdf.set_x(x)
    pdf.set_font("Arial", 'BI', 7)
    pdf.cell(ancho, 4, "Respaldo: interpolación sobre la tabla del manual (valor exacto en rojo)", ln=True)
    enc_gr, fil_gr = r['m_gr']
    enc_tot, fil_tot = r['m_tot']
    pdf_agregar_tabla(pdf, x, ancho, "Carrera en Tierra Base (m)", enc_gr, fil_gr)
    pdf.set_x(x)
    pdf.ln(1)
    pdf_agregar_tabla(pdf, x, ancho, "Distancia Total 50FT Base (m)", enc_tot, fil_tot)
    pdf.set_x(x)
    pdf.ln(2)

    # Desglose condensado de correcciones aplicadas
    pdf.set_x(x)
    pdf.set_font("Arial", 'I', 7)
    desglose = (
        f"Base interpolada: GR {r['gr_base']:.1f} m / Total {r['total_base']:.1f} m.  "
        f"Viento: GR {r['gr_base']:.1f} {operador} {abs(r['val_v_gr']):.1f} = {r['gr_viento']:.1f} m."
    )
    if r['sup'] == "Pasto Seco":
        if fase == "Despegue":
            desglose += f"  Pasto seco: GR x1.15 = {r['gr_final']:.1f} m (Total sin corrección)."
        else:
            desglose += f"  Pasto seco: +{r['diff_pasto']:.1f} m a ambas distancias."
    pdf.multi_cell(ancho, 4, desglose, border=1)

    pdf.set_x(x)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(ancho, 7, f"DIST. DE {nombre_fase} / LONG. DE PISTA", border=1, align='C', ln=True)

    pdf.set_x(x)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(ancho * 0.5, 7, "Carrera en Tierra", border=1, align='C')
    pdf.cell(ancho * 0.5, 7, "Total (Franqueo 50 FT)", border=1, align='C', ln=True)

    pdf.set_x(x)
    pdf.set_font("Arial", 'B', 15)
    pdf.cell(ancho * 0.5, 12, f"{r['gr_final']:.0f} m", border=1, align='C')
    pdf.cell(ancho * 0.5, 12, f"{r['total_final']:.0f} m", border=1, align='C', ln=True)


def generar_pdf_combinado(res_despegue, res_aterrizaje):
    """Genera una sola hoja en horizontal con Despegue a la izquierda y Aterrizaje a la
    derecha. La fase que no haya sido calculada se marca con 'NO CALCULADO' en rojo.
    """
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_left_margin(12)
    pdf.set_right_margin(12)

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    titulo = f"PLANILLA DE RENDIMIENTO - CESSNA 210 (PESO MAX. {PESO_MAX_LBS} LBS)"

    ancho_util = pdf.w - pdf.l_margin - pdf.r_margin

    if os.path.exists(IMG_PATH):
        pdf.image(IMG_PATH, x=12, y=8, w=26)
        pdf.set_y(10)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", 'B', 15)
        pdf.cell(ancho_util, 8, titulo, align='C', ln=True)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", '', 9)
        pdf.cell(ancho_util, 6, f"Fecha de emision: {fecha_actual}", align='C', ln=True)
    else:
        pdf.set_font("Arial", 'B', 15)
        pdf.cell(ancho_util, 9, titulo, ln=True, align='C')
        pdf.set_font("Arial", '', 9)
        pdf.cell(ancho_util, 6, f"Fecha de emision: {fecha_actual}", ln=True, align='C')

    pdf.ln(4)
    y_inicio = pdf.get_y()

    ancho_pagina = pdf.w - pdf.l_margin - pdf.r_margin
    hueco = 8
    ancho_col = (ancho_pagina - hueco) / 2
    x_izq = pdf.l_margin
    x_der = pdf.l_margin + ancho_col + hueco

    _dibujar_bloque_fase(pdf, "DESPEGUE", "Despegue", res_despegue, x_izq, y_inicio, ancho_col)
    _dibujar_bloque_fase(pdf, "ATERRIZAJE", "Aterrizaje", res_aterrizaje, x_der, y_inicio, ancho_col)

    # Firma (centrada en la parte inferior de la hoja)
    pdf.set_y(-25)
    ancho_pagina_util = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Arial", '', 10)
    pdf.set_x(pdf.l_margin)
    pdf.cell(ancho_pagina_util, 8, "_" * 35, align='C', ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.cell(ancho_pagina_util, 6, "COMANDANTE DE NAVE", align='C', ln=True)

    salida_pdf = pdf.output(dest="S")
    # Compatibilidad: fpdf clásico devuelve str (requiere encode); fpdf2 reciente ya devuelve bytes/bytearray.
    if isinstance(salida_pdf, str):
        return salida_pdf.encode("latin-1")
    return bytes(salida_pdf)


# ==========================================
# 5. INTERFAZ DE USUARIO (STREAMLIT)
# ==========================================
st.set_page_config(page_title="Rendimiento C210", page_icon="✈️", layout="wide")

if 'res_despegue' not in st.session_state:
    st.session_state.res_despegue = None
    st.session_state.res_aterrizaje = None
    st.session_state.pdf_bytes = None

col_img, col_title = st.columns([1, 4])
with col_img:
    if os.path.exists(IMG_PATH):
        st.image(IMG_PATH, use_container_width=True)
with col_title:
    st.title("Calculadora de Rendimiento - Cessna 210")
    st.markdown("**Grupo Aéreo Mixto | Sección Operaciones**")

st.divider()


def renderizar_formulario_fase(fase, key_prefix):
    """Dibuja el formulario de una fase (con widgets de key propia) y devuelve
    (submit, elevacion_campo, qnh, temperatura, superficie, dir_viento, vel_viento, rumbo_pista)."""
    with st.form(f"formulario_{key_prefix}"):
        elevacion_campo = st.number_input(
            "Elevación del Campo (pies)", min_value=0.0, max_value=9000.0, value=1371.0, step=10.0,
            key=f"elev_{key_prefix}"
        )
        qnh = st.number_input(
            "Ajuste Altimétrico QNH (inHg)", min_value=27.50, max_value=31.50, value=29.92, step=0.01,
            key=f"qnh_{key_prefix}"
        )
        temperatura = st.number_input(
            "Temperatura Exterior (°C)", min_value=0.0, max_value=40.0, value=30.0, step=1.0,
            key=f"temp_{key_prefix}"
        )
        superficie = st.selectbox(
            "Superficie de Pista", ["Asfalto / Pista Seca", "Pasto Seco"],
            key=f"sup_{key_prefix}"
        )
        dir_viento = st.number_input(
            "Dirección del Viento (°)", min_value=0.0, max_value=360.0, value=330.0, step=10.0,
            key=f"dirv_{key_prefix}"
        )
        vel_viento = st.number_input(
            "Intensidad del Viento (kt)", min_value=0.0, max_value=50.0, value=12.0, step=1.0,
            key=f"velv_{key_prefix}"
        )
        rumbo_pista = st.number_input(
            "Rumbo de Pista en uso (1-36)", min_value=1.0, max_value=36.0, value=34.0, step=1.0,
            key=f"rwy_{key_prefix}"
        )
        submit = st.form_submit_button(f"Calcular {fase}", use_container_width=True)

    return submit, elevacion_campo, qnh, temperatura, superficie, dir_viento, vel_viento, rumbo_pista


def renderizar_resultados_fase(fase, res):
    """Muestra el desglose completo (condiciones, interpolación, correcciones, resultado final)
    de una fase ya calculada, en el ancho de la columna donde se invoque."""
    hw_val = res['headwind']
    cw_val = res['crosswind']
    tipo_v_str = "Viento frontal" if hw_val >= 0 else "Viento de cola"
    operador = "-" if hw_val >= 0 else "+"

    st.info(f"""
    * **Configuración:** {CONFIG_TEXT_DISPLAY[fase]}
    * **Elev. Campo / QNH:** {res['elevacion_campo']:.0f} ft / {res['qnh']:.2f} inHg → **Altitud de Presión: {res['alt']:.0f} ft**
    * **Temperatura:** {res['temp']} °C
    * **Pista / Superficie:** {res['rwy']:.0f} (Eje {int(res['rwy']*10)}°) / {res['sup']}
    * **Viento:** {tipo_v_str} {abs(hw_val):.1f} kt | Cruzado {abs(cw_val):.1f} kt (Dir {res['dir_v']:.0f}° / {res['vel_v']:.0f} kt)
    """)

    with st.expander("Ver interpolación base y desglose de correcciones"):
        enc_gr, fil_gr = res['m_gr']
        enc_tot, fil_tot = res['m_tot']

        st.markdown("**Carrera en Tierra Base (m)**")
        st.markdown(render_html_table(enc_gr, fil_gr), unsafe_allow_html=True)
        st.markdown("**Distancia Total 50FT Base (m)**")
        st.markdown(render_html_table(enc_tot, fil_tot), unsafe_allow_html=True)

        st.markdown(f"""
        **Corrección por Viento**
        * Carrera en Tierra: `{res['gr_base']:.1f}` {operador} `{abs(res['val_v_gr']):.1f}` = **`{res['gr_viento']:.1f} m`**
        * Distancia Total: `{res['total_base']:.1f}` {operador} `{abs(res['val_v_tot']):.1f}` = **`{res['total_viento']:.1f} m`**
        """)

        if res['sup'] == "Pasto Seco":
            if fase == "Despegue":
                st.markdown(f"""
                **Corrección por Superficie (Pasto Seco)**
                * Carrera en Tierra x1.15 = **`{res['gr_final']:.1f} m`** (Distancia Total sin corrección)
                """)
            else:
                st.markdown(f"""
                **Corrección por Superficie (Pasto Seco)**
                * +{res['diff_pasto']:.1f} m a ambas distancias → Carrera en Tierra **`{res['gr_final']:.1f} m`**, Total **`{res['total_final']:.1f} m`**
                """)

    m1, m2 = st.columns(2)
    with m1:
        st.metric("Carrera en Tierra", f"{res['gr_final']:.1f} m")
    with m2:
        st.metric("Total (50 FT)", f"{res['total_final']:.1f} m")


col_desp, col_ate = st.columns(2)

with col_desp:
    st.subheader("✈️ Despegue")
    submit_d, elev_d, qnh_d, temp_d, sup_d, dirv_d, velv_d, rwy_d = renderizar_formulario_fase("Despegue", "desp")

    if submit_d:
        pa_d = calcular_altitud_presion(elev_d, qnh_d)
        resultado_d = calcular_resultado("Despegue", pa_d, temp_d, dirv_d, velv_d, rwy_d, sup_d)

        if "error" in resultado_d:
            st.error(f"⚠️ {resultado_d['error']} (Altitud de presión calculada: {pa_d:.0f} ft)")
        else:
            if resultado_d.get("advertencia_viento"):
                st.warning(f"⚠️ {resultado_d['advertencia_viento']}")
            resultado_d['elevacion_campo'] = elev_d
            resultado_d['qnh'] = qnh_d
            st.session_state.res_despegue = resultado_d

    if st.session_state.res_despegue is not None:
        renderizar_resultados_fase("Despegue", st.session_state.res_despegue)

with col_ate:
    st.subheader("🛬 Aterrizaje")
    submit_a, elev_a, qnh_a, temp_a, sup_a, dirv_a, velv_a, rwy_a = renderizar_formulario_fase("Aterrizaje", "ate")

    if submit_a:
        pa_a = calcular_altitud_presion(elev_a, qnh_a)
        resultado_a = calcular_resultado("Aterrizaje", pa_a, temp_a, dirv_a, velv_a, rwy_a, sup_a)

        if "error" in resultado_a:
            st.error(f"⚠️ {resultado_a['error']} (Altitud de presión calculada: {pa_a:.0f} ft)")
        else:
            if resultado_a.get("advertencia_viento"):
                st.warning(f"⚠️ {resultado_a['advertencia_viento']}")
            resultado_a['elevacion_campo'] = elev_a
            resultado_a['qnh'] = qnh_a
            st.session_state.res_aterrizaje = resultado_a

    if st.session_state.res_aterrizaje is not None:
        renderizar_resultados_fase("Aterrizaje", st.session_state.res_aterrizaje)

# ==========================================
# 6. DESCARGA COMBINADA (PDF horizontal)
# ==========================================
st.divider()

despegue_ok = st.session_state.res_despegue is not None
aterrizaje_ok = st.session_state.res_aterrizaje is not None

if despegue_ok or aterrizaje_ok:
    st.session_state.pdf_bytes = generar_pdf_combinado(st.session_state.res_despegue, st.session_state.res_aterrizaje)

    st.caption(
        f"Estado de la planilla combinada — Despegue: {'✅ calculado' if despegue_ok else '❌ no calculado'} "
        f"| Aterrizaje: {'✅ calculado' if aterrizaje_ok else '❌ no calculado'}"
    )

    st.download_button(
        label="📥 Descargar Planilla Combinada (Despegue + Aterrizaje, PDF horizontal)",
        data=st.session_state.pdf_bytes,
        file_name=f"Rendimiento_C210_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
else:
    st.caption("Calcula al menos una fase (Despegue o Aterrizaje) para habilitar la descarga combinada.")
