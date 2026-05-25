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
                
                # 1. Armamos el diccionario de propiedades del SO
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

                # =======================================================
                # 🧠 NUEVO MOTOR DE EVALUACIÓN ESTRUCTURAL (EL DEFINITIVO)
                # =======================================================
                
                # Ignoramos los booleanos literales en las palabras a buscar, 
                # porque la lógica ya evaluará los "true" o "false" internamente.
                palabras_utiles = [kw for kw in palabras_clave if kw not in ["true", "false"]]
                
                puntuacion = 0
                descartado = False
                nombre_so = subj.replace('_', ' ').lower()
                
                for kw in palabras_utiles:
                    kw_encontrada = False
                    
                    # A) ¿La palabra buscada es parte del nombre del SO? (ej: "ubuntu")
                    if kw in nombre_so:
                        kw_encontrada = True
                        
                    # B) Analizar Propiedades y sus Valores Reales
                    for p_name, vals in atributos_os.items():
                        nombre_propiedad = p_name.replace('_', ' ').lower()
                        
                        # CASO 1: La palabra hace referencia a una propiedad (ej: "posix" en "cumple_estandar_posix")
                        if kw in nombre_propiedad:
                            for v in vals:
                                val_str = str(v).lower()
                                
                                if val_str == "false":
                                    # Si es FALSE, evaluamos si el usuario preguntó en negativo (ej: "que NO sea posix")
                                    if "no" in palabras_clave or "cerrado" in palabras_clave:
                                        kw_encontrada = True # Gana punto porque buscaba algo que NO lo tuviera
                                    else:
                                        descartado = True # 🛑 VETO LETAL: Lo descarta por completo
                                        break
                                elif val_str == "true":
                                    kw_encontrada = True # Gana punto porque lo cumple
                                    
                        if descartado: break
                        
                        # CASO 2: La palabra hace referencia a un Valor Técnico (ej: "ext4", "amd64", "apple")
                        for v in vals:
                            val_str = str(v).replace('_', ' ').lower()
                            if val_str not in ["true", "false"]: # Ignoramos booleanos aquí
                                if kw in val_str:
                                    kw_encontrada = True
                                # Tolerancia a pequeños errores de tipeo (ej: 'androit' -> 'android')
                                elif difflib.SequenceMatcher(None, kw, val_str).ratio() > 0.85:
                                    kw_encontrada = True
                                    
                    if descartado: break
                    if kw_encontrada: puntuacion += 1
                        
                if descartado:
                    continue # ⛔ Salta al siguiente SO inmediatamente (Adiós MS-DOS)
                    
                # C) Calcular la nota final
                porcentaje_match = puntuacion / len(palabras_utiles) if len(palabras_utiles) > 0 else 0
                
                # Si cumple más del 40% de lo que pidió, lo mostramos
                if porcentaje_match >= 0.40:
                    resultados.append({
                        "id_instancia": subj,
                        "atributos": {k: list(v) for k, v in atributos_os.items()},
                        "relevancia": round(porcentaje_match * 100, 1)
                    })
                # =======================================================
                    
        # Ordenamos del mejor puntaje al peor
        resultados.sort(key=lambda x: (-x["relevancia"], x["id_instancia"]))
        return jsonify(resultados)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)