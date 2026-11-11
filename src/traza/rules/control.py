"""Control de las instalaciones (docs/modules/control.md).

Usuario (11-11-2026): «el control sí es importante»; TRAZA «debe proponer cosas en caso de no
existir». Fuente normativa: RITE (RD 1027/2007, texto consolidado del BOE), IT 1.2.4.3:

- IT 1.2.4.3.1: control de las instalaciones de climatización (regulación por espacio,
  todo-nada solo en casos tasados, válvulas de control entre 0,6 y 1,3 veces la pérdida del
  elemento controlado, presión diferencial estabilizada con caudal variable y más de 70 kW,
  impulsión de frío constante, secuencia de generadores, medición y control del caudal en
  ventiladores de más de 5 m³/s).
- IT 1.2.4.3.2, tabla 2.4.3.1: categorías THM-C0 a C5 (control termohigrométrico).
- IT 1.2.4.3.3, tabla 2.4.3.2: categorías IDA-C1 a C6 (calidad del aire interior); IDA-C6 en
  locales de ocupación variable (apartado 4); IDA-C2, C3 o C4 en locales no diseñados para
  ocupación humana permanente (apartado 3).

Lo que el RITE no fija (qué señales lleva cada equipo) se propone como práctica habitual y
se dice así: el usuario lo confirma o lo cambia.
"""

from __future__ import annotations

#: Tabla 2.4.3.1 del RITE: qué controla el sistema en el local.
THM = {
    "THM-C0": "Ventilación",
    "THM-C1": "Ventilación y calentamiento",
    "THM-C2": "Ventilación, calentamiento y humectación",
    "THM-C3": "Ventilación, calentamiento y refrigeración (deshumectación no controlada)",
    "THM-C4": "Como THM-C3, con control de la humedad relativa media o del local más "
    "representativo",
    "THM-C5": "Como THM-C3, con control de la humedad relativa en los locales",
}
#: Tabla 2.4.3.2 del RITE.
IDA = {
    "IDA-C1": "Funcionamiento continuo",
    "IDA-C2": "Control manual (interruptor)",
    "IDA-C3": "Control por tiempo (horario)",
    "IDA-C4": "Control por presencia",
    "IDA-C5": "Control por ocupación (número de personas)",
    "IDA-C6": "Control directo por sensores de calidad del aire (CO₂ o COV)",
}
CON_HUMEDAD = ("THM-C2", "THM-C4", "THM-C5")
#: Solo en locales no diseñados para ocupación humana permanente (IT 1.2.4.3.3.3).
SIN_OCUPACION_PERMANENTE = ("IDA-C2", "IDA-C3", "IDA-C4")

#: Usos de ocupación variable: IDA-C6 obligatorio (IT 1.2.4.3.3.4: «teatros, cines, salones de
#: actos, aulas, recintos para el deporte y similares»). Elección de TRAZA de los usos del
#: catálogo que son «similares» (docs/modules/control.md).
OCUPACION_VARIABLE = (
    "reuniones",
    "salon_eventos",
    "gimnasio",
    "comedor",
    "restaurante_hotel",
    "espera_hospital",
    "piscina",
)
#: Usos con la humedad del local controlada por norma: quirófano, UNE 100713 (humedad
#: relativa entre 45 y 55 %) → THM-C5.
HUMEDAD_POR_NORMA = {"quirofano": "UNE 100713 (humedad relativa de 45 a 55 %)"}

#: Por encima de 5 m³/s (18 000 m³/h), medición y control del caudal (IT 1.2.4.3.1.10).
CAUDAL_MEDICION_M3H = 18_000.0
#: Caudal variable y más de 70 kW: presión diferencial estabilizada (IT 1.2.4.3.1.5).
POTENCIA_PRESION_DIFERENCIAL_KW = 70.0

TIPOS_PUNTO = {
    "ED": "Entrada digital",
    "SD": "Salida digital",
    "EA": "Entrada analógica",
    "SA": "Salida analógica",
}
PROPUESTA = "Propuesta (práctica habitual)"
