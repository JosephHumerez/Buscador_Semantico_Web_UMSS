from flask import Flask, request, jsonify
from flask_cors import CORS
import xml.etree.ElementTree as ET
import re
import unicodedata
import os
import difflib

app = Flask(__name__)
CORS(app) 

# --- 1. NLP y Traductor Semántico ---
def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')

def extraer_palabras_clave(frase):
    frase_min = frase.lower()
    
    # TRADUCTOR SEMÁNTICO: Convierte las preguntas de tu PDF a los atributos de la Ontología
    traducciones = {
        "gratuitos": "gratuito true",
        "gratis": "gratuito true",
        "comerciales": "comercial true",
        "codigo cerrado": "open source false",
        "propietario": "open source false",
        "privativa": "open source false",
        "principiantes": "principiantes true",
        "pago": "pago true",
        "32 bits": "16-bit", # MS-DOS en tu ontología dice 16-bit
        "64 bits": "amd64",
        "arm": "arm64",
        "placas de desarrollo": "placas desarrollo true",
        "raspberry": "placas desarrollo true",
        "infectados": "exe nativamente false",
        "tienda oficial": "tienda true",
        "asistentes": "asistente instalacion true",
        "gui": "asistente instalacion true",
        "marca de hardware": "hardware especifico true",
        "subsistemas": "subsistema compatibilidad true",
        "wsl": "subsistema compatibilidad true",
        "cifrar el disco": "cifrado disco true",
        "reemplazar completamente": "reemplazo entorno true",
        "nube": "servidor red empresarial",
        "hosting": "servidor web red",
        "programacion": "desarrollo compilador codigo",
        "apple": "macos ios mac",
        "microsoft": "windows ms dos",
        "celular": "movil smartphone android ios",
        "ligero": "rapido poco recursos ram",
        "viejo": "antiguo ms dos 16-bit",
        "seguro": "seguridad cifrado selinux apparmor"
    }
    
    # Reemplazamos las frases humanas por lógica de la ontología
    for humano, ontologia in traducciones.items():
        frase_min = frase_min.replace(humano, ontologia)
        
    frase_limpia = re.sub(r'[^\w\s]', ' ', frase_min)
    
    # STOP WORDS: Ignorar palabras de relleno de las preguntas de tu PDF
    stop_words = {
        "que", "cual", "cuales", "como", "tiene", "tienen", "usa", "usan", "utiliza", "utilizan", 
        "es", "son", "el", "la", "los", "las", "un", "una", "unos", "unas", 
        "sistema", "sistemas", "operativo", "operativos", "so", "con", "de", "para", "por", "y", "o", "en", "su", "sus", "si",
        "pc", "computadora", "computadoras", "escritorio", "pero", "requieren", "mantienen", 
        "actuales", "familia", "basadas", "ej", "distintos", "distintas", "incluyen", "nativamente", "directa", "archivos"
    }
    
    palabras = frase_limpia.split()
    keywords = [remover_acentos(p) for p in palabras if p not in stop_words and len(p) > 1]
    
    if not keywords:
        keywords = [remover_acentos(p) for p in palabras if len(p) > 1]
    return keywords

# --- 2. Parser NATIVO ---
def cargar_ontologia_owx():
    if not os.path.exists('TrabajoFinalSo.owx'):
        raise Exception("¡Falta el archivo TrabajoFinalSo.owx!")

    tree = ET.parse('TrabajoFinalSo.owx') 
    root = tree.getroot()
    
    def get_iri(element):
        return element.attrib.get('IRI', element.attrib.get('abbreviatedIRI', '')).replace('#', '')

    entidades = {}
    
    for child in root:
        tag = child.tag.split('}')[-1]
        hijos = list(child) 
        
        if tag == 'ClassAssertion' and len(hijos) >= 2:
            cls = get_iri(hijos[0])
            ind = get_iri(hijos[1])
            if ind not in entidades: entidades[ind] = {}
            if 'tipo_clase' not in entidades[ind]: entidades[ind]['tipo_clase'] = set()
            entidades[ind]['tipo_clase'].add(cls)
            
        elif tag == 'ObjectPropertyAssertion' and len(hijos) >= 3:
            prop = get_iri(hijos[0])
            subj = get_iri(hijos[1])
            obj = get_iri(hijos[2])
            if subj not in entidades: entidades[subj] = {}
            if prop not in entidades[subj]: entidades[subj][prop] = set()
            entidades[subj][prop].add(obj)
            
        elif tag == 'DataPropertyAssertion' and len(hijos) >= 3:
            prop = get_iri(hijos[0])
            subj = get_iri(hijos[1])
            val = hijos[2].text or ""
            if subj not in entidades: entidades[subj] = {}
            if prop not in entidades[subj]: entidades[subj][prop] = set()
            entidades[subj][prop].add(val)
                
    return entidades

@app.route('/buscar', methods=['GET'])
def buscar():
    raw_query = request.args.get('q', '').strip()
    palabras_clave = extraer_palabras_clave(raw_query)
    
    try:
        entidades = cargar_ontologia_owx()
        resultados = []
        
        for subj, props in entidades.items():
            clases = props.get('tipo_clase', set())
            
            if 'Sistema_Operativo' in clases or 'Distribucion' in clases:
                atributos_os = {}
                
                for p, valores in props.items():
                    if p == 'tipo_clase': continue
                    if p not in atributos_os: atributos_os[p] = set()
                    
                    for v in valores:
                        atributos_os[p].add(v)
                        
                        if v in entidades:
                            for sub_p, sub_vals in entidades[v].items():
                                if sub_p == 'tipo_clase': continue
                                if sub_p not in atributos_os: atributos_os[sub_p] = set()
                                for sub_v in sub_vals:
                                    atributos_os[sub_p].add(sub_v)
                
                texto_completo = subj.replace('_', ' ').lower() + " "
                
                for p_name, vals in atributos_os.items():
                    nombre_limpio = p_name.replace('_', ' ').lower()
                    
                    for v in vals:
                        v_str = str(v).replace('_', ' ').lower()
                        
                        # VALIDACIÓN ESTRICTA DE BOOLEANOS
                        if v_str == "false":
                            # Solo agregamos las propiedades 'false' al texto si el usuario
                            # buscó explícitamente la palabra 'false'
                            if "false" in palabras_clave:
                                texto_completo += f"{nombre_limpio} false "
                        elif v_str == "true":
                            # Las propiedades 'true' siempre se agregan
                            texto_completo += f"{nombre_limpio} true "
                        else:
                            # Valores normales (ej: ext4, amd64, google)
                            texto_completo += f"{nombre_limpio} {v_str} "
                            
                texto_completo = remover_acentos(texto_completo)
                
                # --- NUEVO SISTEMA DE PUNTUACIÓN (SCORING) ---
                puntuacion = 0
                palabras_del_so = texto_completo.split()
                
                for kw in palabras_clave:
                    # 1. Coincidencia exacta (Vale 1 punto entero)
                    if kw in texto_completo:
                        puntuacion += 1.0
                    else:
                        # 2. Coincidencia difusa / Inteligente
                        # Compara la palabra clave con todas las palabras del SO para ver si se parecen
                        # Ej: Si busca "ubunto", se parece un 85% a "ubuntu"
                        mejor_similitud = max([difflib.SequenceMatcher(None, kw, p).ratio() for p in palabras_del_so] + [0])
                        
                        # Si la palabra se parece al menos un 70%, le damos puntaje parcial
                        if mejor_similitud > 0.70:
                            puntuacion += mejor_similitud

                # 3. Calcular el porcentaje total de coincidencia
                porcentaje_match = 0
                if len(palabras_clave) > 0:
                    porcentaje_match = puntuacion / len(palabras_clave)
                
                # 4. Decisión más inteligente:
                # En lugar de exigir el 100%, si cumple al menos el 40% de lo que pidió el usuario, lo mostramos
                if porcentaje_match >= 0.40: 
                    resultados.append({
                        "id_instancia": subj,
                        "atributos": {k: list(v) for k, v in atributos_os.items()},
                        "relevancia": round(porcentaje_match * 100, 1) # Guardamos el % para mostrarlo luego
                    })
                    
        resultados.sort(key=lambda x: (-x["relevancia"], x["id_instancia"]))
        return jsonify(resultados)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)