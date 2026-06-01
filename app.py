from flask import Flask, render_template, request, jsonify
from SPARQLWrapper import SPARQLWrapper, JSON
import re
import requests

app = Flask(__name__)

FUSEKI_URL  = "http://localhost:3030/ws_buscador_so/sparql"
PREFIX_URI  = "http://www.semanticweb.org/administrator/ontologies/2026/2/untitled-ontology-2#"
DBP_SPARQL  = "https://dbpedia.org/sparql"
DBP_LOOKUP  = "https://lookup.dbpedia.org/api/search"

fuseki = SPARQLWrapper(FUSEKI_URL)
fuseki.setReturnFormat(JSON)

STOP_WORDS = {
    "el","la","los","las","un","una","unos","unas","es","de","para","que",
    "con","su","tiene","usa","como","sistema","operativo","sistemas","a",
    "son","lo","sobre","busco","quiero","dame","cuales","cuáles","me",
    "muestra","hay","tienen","pueden","operativos","al","del","en",
    "por","más","mas","entre","cuando","donde","cómo","cuándo","dónde",
    "qué","información","info","sobre","define","explica","cuéntame",
    "dime","háblame","habla","explícame","significa","significado"
}

PREFIX_STR = (
    f"PREFIX onto: <{PREFIX_URI}>\n"
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"
)

CLASE_FILTRO = "FILTER (?tipo IN (onto:Sistema_Operativo, onto:Distribucion))"

PROP_MAP = {
    "open_source":"es_open_source","abierto":"es_open_source","libre":"es_open_source",
    "gratuito":"es_gratuito_freeware","gratis":"es_gratuito_freeware","freeware":"es_gratuito_freeware",
    "pago":"es_comercial_de_pago","comercial":"es_comercial_de_pago","privativo":"es_comercial_de_pago",
    "posix":"cumple_estandar_posix","modificable":"permite_modificacion",
    "sandboxing":"tiene_sandboxing_nativo","principiantes":"orientado_a_principiantes",
    "principiante":"orientado_a_principiantes","movil":"proposito","móvil":"proposito",
    "servidor":"proposito","escritorio":"proposito","multiplataforma":"arquitectura_soportada",
    "kernel_modificado":"es_kernel_modificado","cifrado":"cifrado_disco_por_defecto",
    "kernel":"se_basa_en_kernel","nucleo":"se_basa_en_kernel","núcleo":"se_basa_en_kernel",
    "licencia":"utiliza_licencia","arquitectura":"arquitectura_soportada",
    "entorno":"entorno_escritorio_default","gestor":"gestor_paquetes_default",
    "paquetes":"gestor_paquetes_default","desarrollador":"desarrollador","empresa":"desarrollador",
    "version":"version_so","versión":"version_so","familia":"familia_base",
    "proposito":"proposito","propósito":"proposito",
}

DBP_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "BuscadorSO/1.0 (proyecto educativo; contacto@ejemplo.com)"
}

_dbp_cache = {}

def run_fuseki(query):
    fuseki.setQuery(query)
    return fuseki.query().convert()["results"]["bindings"]


# ─── Mapeos Flexibles para DBpedia ────────────────────────────────────────────

def _uri_candidatos(nombre):
    n = nombre.lower().strip()
    clean = nombre.strip().replace(" ", "_")
    if "windows" in n:
        m = re.search(r"windows\s*([\w\s]+)", n)
        ver = m.group(1).strip().replace(" ", "_") if m else ""
        return ([f"Windows_{ver}", "Microsoft_Windows", "Windows_NT"]
                if ver else ["Microsoft_Windows", "Windows_NT"])
    if "ubuntu"  in n: return ["Ubuntu", "Ubuntu_(operating_system)"]
    if "macos"   in n or "mac os" in n: return ["MacOS", "macOS", "Mac_OS_X"]
    if "android" in n: return ["Android_(operating_system)", "Android"]
    if "ios"     in n and "mac" not in n: return ["iOS", "IOS_(Apple)"]
    if "arch"    in n: return ["Arch_Linux"]
    if "debian"  in n: return ["Debian"]
    if "fedora"  in n: return ["Fedora_Linux", "Fedora_(operating_system)"]
    if "mint"    in n: return ["Linux_Mint"]
    if "centos"  in n: return ["CentOS"]
    if "red hat" in n or "redhat" in n: return ["Red_Hat_Enterprise_Linux"]
    if "freebsd" in n: return ["FreeBSD"]
    if "openbsd" in n: return ["OpenBSD"]
    if "chrome"  in n: return ["ChromeOS", "Chrome_OS"]
    if "haiku"   in n: return ["Haiku_(operating_system)"]
    if "solaris" in n: return ["Oracle_Solaris", "Solaris_(operating_system)", "Solaris"]
    if "dos"     in n: return ["MS-DOS", "DOS"]
    if "linux"   in n: return ["Linux"]
    return [clean, f"{clean}_(operating_system)", clean.split("_")[0]]


def _lookup_uri(nombre):
    try:
        resp = requests.get(
            DBP_LOOKUP,
            params={"query": nombre + " operating system", "format": "json", "maxResults": 8},
            headers={"Accept": "application/json"},
            timeout=6
        )
        if not resp.ok:
            return None
        docs = resp.json().get("docs", [])
        nl = nombre.lower()
        for doc in docs:
            label = " ".join(doc.get("label", [])).lower()
            cats  = " ".join(doc.get("category", [])).lower()
            res   = (doc.get("resource") or [None])[0]
            if res and (
                any(w for w in nl.split() if len(w) > 2 and w in label)
                or "operating" in cats or "linux" in cats or "solaris" in label
            ):
                return res
        return (docs[0].get("resource") or [None])[0] if docs else None
    except Exception as e:
        app.logger.warning(f"[Lookup] {e}")
        return None


def _sparql_basico(bind_clause):
    """Query semántica robusta que extrae propiedades unificando namespaces ontológicos y literales."""
    return f"""
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX dbp:  <http://dbpedia.org/property/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT
  (SAMPLE(?absEs) AS ?resumen)
  (SAMPLE(?absEn) AS ?resumenEn)
  (SAMPLE(?lblFinal) AS ?nombre)
  (GROUP_CONCAT(DISTINCT ?devFinal; separator="||") AS ?desarrolladores)
  (SAMPLE(?fecha) AS ?anio)
  (GROUP_CONCAT(DISTINCT ?licFinal; separator="||") AS ?licencias)
  (SAMPLE(?page)  AS ?web)
  (SAMPLE(?logoV) AS ?logo)
  (SAMPLE(?r)     AS ?uri)
WHERE {{
  {bind_clause}
  OPTIONAL {{ 
    ?r rdfs:label ?lblRaw . 
    BIND(LANG(?lblRaw) AS ?lblLang)
    FILTER(?lblLang = "es" || ?lblLang = "en" || ?lblLang = "")
  }}
  BIND(COALESCE(?lblRaw, STR(?r)) AS ?lblFinal)
  
  OPTIONAL {{ ?r dbo:abstract ?absEs . FILTER(LANG(?absEs)="es") }}
  OPTIONAL {{ ?r dbo:abstract ?absEn . FILTER(LANG(?absEn)="en") }}
  
  OPTIONAL {{ 
    ?r dbo:developer|dbp:developer|dbo:company|dbp:company ?dev . 
    OPTIONAL {{ ?dev rdfs:label ?devL . FILTER(LANG(?devL)="en" || LANG(?devL)="es") }}
    BIND(COALESCE(?devL, STR(?dev)) AS ?devFinal)
  }}
  OPTIONAL {{ ?r dbo:releaseDate|dbp:releaseDate|dbo:introductionDate|dbp:introductionDate ?fecha }}
  OPTIONAL {{ 
    ?r dbo:license|dbp:license ?lic . 
    OPTIONAL {{ ?lic rdfs:label ?licL . FILTER(LANG(?licL)="en" || LANG(?licL)="es") }}
    BIND(COALESCE(?licL, STR(?lic)) AS ?licFinal)
  }}
  OPTIONAL {{ ?r foaf:homepage|dbp:website|dbo:website ?page }}
  OPTIONAL {{ ?r dbp:logo|dbo:logo ?logoV }}
}}"""


def _sparql_extra(uri):
    """Recupera la totalidad de especificaciones técnicas estructurales cruzando ontologías."""
    return f"""
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX dbp:  <http://dbpedia.org/property/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT
  (GROUP_CONCAT(DISTINCT ?famFinal;  separator="||") AS ?familias)
  (GROUP_CONCAT(DISTINCT ?kernelFinal; separator="||") AS ?kernels)
  (SAMPLE(?verFinal)                                   AS ?version)
  (GROUP_CONCAT(DISTINCT ?ktFinal;   separator="||") AS ?tiposKernel)
  (GROUP_CONCAT(DISTINCT ?predFinal; separator="||") AS ?predecesores)
  (GROUP_CONCAT(DISTINCT ?sucFinal;  separator="||") AS ?sucesores)
WHERE {{
  BIND(<{uri}> AS ?r)
  OPTIONAL {{ 
    ?r dbo:family|dbp:family ?fam . 
    OPTIONAL {{ ?fam rdfs:label ?famL . FILTER(LANG(?famL)="en" || LANG(?famL)="es") }}
    BIND(COALESCE(?famL, STR(?fam)) AS ?famFinal)
  }}
  OPTIONAL {{ 
    ?r dbo:kernel|dbp:kernel ?kv . 
    OPTIONAL {{ ?kv rdfs:label ?kvL . FILTER(LANG(?kvL)="en" || LANG(?kvL)="es") }}
    BIND(COALESCE(?kvL, STR(?kv)) AS ?kernelFinal)
  }}
  OPTIONAL {{ ?r dbo:latestReleaseVersion|dbp:latestReleaseVersion|dbp:version|dbo:version ?verRaw . BIND(STR(?verRaw) AS ?verFinal) }}
  OPTIONAL {{ 
    ?r dbo:kernelType|dbp:kernelType ?kt . 
    OPTIONAL {{ ?kt rdfs:label ?ktL . FILTER(LANG(?ktL)="en" || LANG(?ktL)="es") }}
    BIND(COALESCE(?ktL, STR(?kt)) AS ?ktFinal)
  }}
  OPTIONAL {{ 
    ?r dbo:predecessor|dbp:predecessor ?pred. 
    OPTIONAL {{ ?pred rdfs:label ?predL. FILTER(LANG(?predL)="en" || LANG(?predL)="es") }}
    BIND(COALESCE(?predL, STR(?pred)) AS ?predFinal)
  }}
  OPTIONAL {{ 
    ?r dbo:successor|dbp:successor ?suc . 
    OPTIONAL {{ ?suc rdfs:label ?sucL. FILTER(LANG(?sucL)="en" || LANG(?sucL)="es") }}
    BIND(COALESCE(?sucL, STR(?suc)) AS ?sucFinal)
  }}
}}"""


def _run_dbpedia_sparql(query, timeout=25):
    try:
        resp = requests.get(
            DBP_SPARQL,
            params={"query": query, "format": "application/sparql-results+json"},
            headers=DBP_HEADERS,
            timeout=timeout
        )
        if not resp.ok:
            return None
        bindings = resp.json().get("results", {}).get("bindings", [])
        return bindings[0] if bindings else None
    except Exception as e:
        app.logger.warning(f"[SPARQL] {e}")
        return None


def _parsear_row(row):
    if not row:
        return None

    def g(k):
        return row[k]["value"] if k in row else None

    def clean_val(v):
        """Limpia URIs crudas de recursos transformándolas en etiquetas legibles."""
        if not v: return None
        if "http" in v:
            if "#" in v: return v.split("#")[-1].replace("_", " ")
            return v.split("/")[-1].replace("_", " ")
        return v.replace("_", " ")

    def gsplit(k, lim=6):
        v = g(k)
        if not v:
            return None
        parts = list(dict.fromkeys(clean_val(x.strip()) for x in v.split("||") if x.strip()))
        return ", ".join(parts[:lim]) or None

    anio = g("anio")
    result = {
        "resumen":      g("resumen") or g("resumenEn"),
        "nombre":       g("nombre"),
        "uri":          g("uri"),
        "desarrollador":gsplit("desarrolladores"),
        "anio":         anio[:4] if anio else None,
        "licencia":     gsplit("licencias"),
        "web":          g("web"),
        "familia":      gsplit("familias"),
        "kernel":       gsplit("kernels"),
        "version":      g("version"),
        "plataformas":  gsplit("plataformas"),
        "lenguaje":     gsplit("lenguajes"),
        "tipoKernel":   gsplit("tiposKernel"),
        "predecesores": gsplit("predecesores"),
        "sucesores":    gsplit("sucesores"),
        "influencias":  gsplit("influencias"),
        "logo":         g("logo"),
    }
    clean = {k: v for k, v in result.items() if v}
    return clean if clean else None


def consultar_dbpedia(nombre):
    global _dbp_cache
    clave = nombre.lower().strip()
    if clave in _dbp_cache:
        return _dbp_cache[clave]

    datos = _consultar_dbpedia_interno(nombre)
    _dbp_cache[clave] = datos 
    return datos


def _consultar_dbpedia_interno(nombre):
    # ── Estrategia 1: Lookup Directo ──────────────────────────────────────────
    uri_lookup = _lookup_uri(nombre)
    if uri_lookup:
        row = _run_dbpedia_sparql(_sparql_basico(f"BIND(<{uri_lookup}> AS ?r)"))
        datos = _parsear_row(row)
        if datos:
            datos["uri"] = datos.get("uri") or uri_lookup
            _enriquecer_con_extra(datos)
            return datos

    # ── Estrategia 2: URIs Candidatas Estructurales ───────────────────────────
    for cand in _uri_candidatos(nombre)[:4]:
        uri = f"http://dbpedia.org/resource/{requests.utils.quote(cand, safe='')}"
        row = _run_dbpedia_sparql(_sparql_basico(f"BIND(<{uri}> AS ?r)"))
        datos = _parsear_row(row)
        if datos:
            datos["uri"] = datos.get("uri") or uri
            _enriquecer_con_extra(datos)
            return datos

    # ── Estrategia 3: Indexación Difusa en Software ───────────────────────────
    nom_clean = re.sub(r"[^\w\s]", "", nombre)
    query_tl = f"""
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbp:  <http://dbpedia.org/property/>
SELECT DISTINCT ?r
  (SAMPLE(?lbl)   AS ?nombre)
  (SAMPLE(?absEs) AS ?resumen)
  (SAMPLE(?absEn) AS ?resumenEn)
  (GROUP_CONCAT(DISTINCT ?devLbl; separator="||") AS ?desarrolladores)
  (SAMPLE(?fecha) AS ?anio)
  (GROUP_CONCAT(DISTINCT ?licLbl; separator="||") AS ?licencias)
  (SAMPLE(?page)  AS ?web)
  (SAMPLE(?logoV) AS ?logo)
WHERE {{
  ?r rdf:type ?type .
  FILTER(?type IN (dbo:OperatingSystem, dbo:Software))
  ?r rdfs:label ?lbl . FILTER(regex(?lbl, "{nom_clean}", "i"))
  OPTIONAL {{ ?r dbo:abstract ?absEs . FILTER(LANG(?absEs)="es") }}
  OPTIONAL {{ ?r dbo:abstract ?absEn . FILTER(LANG(?absEn)="en") }}
  OPTIONAL {{ ?r dbo:developer|dbp:developer ?dev . ?dev rdfs:label ?devLbl . }}
  OPTIONAL {{ ?r dbo:releaseDate|dbp:releaseDate ?fecha }}
  OPTIONAL {{ ?r dbo:license|dbp:license ?lic . ?lic rdfs:label ?licLbl . }}
  OPTIONAL {{ ?r foaf:homepage ?page }}
  OPTIONAL {{ ?r dbp:logo ?logoV }}
}} GROUP BY ?r LIMIT 1"""

    row2 = _run_dbpedia_sparql(query_tl)
    datos2 = _parsear_row(row2)
    if datos2:
        if not datos2.get("uri") and row2 and "r" in row2:
            datos2["uri"] = row2["r"]["value"]
        _enriquecer_con_extra(datos2)
        return datos2

    return None


def _enriquecer_con_extra(datos):
    uri = datos.get("uri")
    if not uri:
        return
    try:
        row = _run_dbpedia_sparql(_sparql_extra(uri), timeout=20)
        if not row:
            return
        
        def clean_val(v):
            if not v: return None
            if "http" in v:
                if "#" in v: return v.split("#")[-1].replace("_", " ")
                return v.split("/")[-1].replace("_", " ")
            return v.replace("_", " ")

        def gsplit_row(k, lim=6):
            v = row[k]["value"] if k in row else None
            if not v:
                return None
            parts = list(dict.fromkeys(clean_val(x.strip()) for x in v.split("||") if x.strip()))
            return ", ".join(parts[:lim]) or None
            
        extras = {
            "familia":      gsplit_row("familias"),
            "kernel":       gsplit_row("kernels"),
            "version":      row["version"]["value"] if "version" in row else None,
            "tipoKernel":   gsplit_row("tiposKernel"),
            "predecesores": gsplit_row("predecesores"),
            "sucesores":    gsplit_row("sucesores"),
        }
        for k, v in extras.items():
            if v and not datos.get(k):
                datos[k] = v
    except Exception as e:
        app.logger.warning(f"[extra] {e}")


# ─── Detección de intención ────────────────────────────────────────────────────

def detectar_intencion(texto):
    tl = texto.lower().strip()
    palabras_raw = set(re.sub(r'[^\w\s]', '', tl).split())
    palabras = palabras_raw - STOP_WORDS

    m = re.search(
        r'(.+?)\s+(?:vs\.?|versus|contra|comparar\s+con|comparado\s+con|diferencia\s+entre)\s+(.+)', tl)
    if m:
        return "comparar", {"a": m.group(1).strip(), "b": m.group(2).strip()}

    if re.search(r'cu[aá]ntos|cu[aá]ntas|cantidad\s+de|total\s+de|n[uú]mero\s+de', tl):
        return "contar", {"palabras": list(palabras)}

    m_def = re.search(
        r'(?:qu[eé]\s+es|qu[eé]\s+son|define\s+(?:el|la|los|las)?\s*|'
        r'definici[oó]n\s+(?:de|del)?\s*|'
        r'explic[aa]\s+(?:me\s+)?(?:qu[eé]\s+es\s+)?|'
        r'cu[eé]ntame\s+(?:sobre\s+|(?:qu[eé]\s+es\s+))?|'
        r'h[aá]blame\s+(?:de|sobre)\s+|'
        r'qu[eé]\s+significa\s+|'
        r'significado\s+de\s+)',
        tl
    )
    if m_def:
        termino_def = tl[m_def.end():].strip()
        termino_def = re.sub(r'^(?:el|la|los|las|un|una)\s+', '', termino_def).strip()
        if termino_def:
            return "definicion", {"termino": termino_def}

    m_rank = re.search(
        r'\b(m[aá]s|menos|menor|mayor)\b.{0,40}\b(ram|memoria|consumo|r[aá]pido|ligero|seguro|popular)\b|'
        r'\b(m[aá]s\s+ligero|m[aá]s\s+seguro|m[aá]s\s+r[aá]pido|menos\s+ram)',
        tl
    )
    if m_rank:
        direccion = "ASC" if re.search(r'\bmenos\b|\bmenor\b|\bm[aá]s\s+ligero\b', tl) else "DESC"
        campo = "ram_en_reposo_mb" if re.search(r'ram|memoria|ligero|consumo', tl) else "version_so"
        return "ranking", {"campo": campo, "orden": direccion, "palabras": list(palabras)}

    m_k = re.search(r'kernel\s+(\w[\w\s]*?)(?:\s+(?:en|de|para|que)|\s*$)', tl)
    if m_k:
        return "filtro_kernel", {"kernel": m_k.group(1).strip()}

    m_prop = re.search(
        r'qu[eé]\s+(?:so|sistemas?)(?:\s+\w+)?\s+(?:tienen?|usan?|soportan?|incluyen?|permiten?)\s+(.+)|'
        r'(?:so|sistemas?)\s+(?:con|que\s+tengan?|que\s+usen?)\s+(.+)',
        tl
    )
    if m_prop:
        obj = (m_prop.group(1) or m_prop.group(2) or "").strip()
        palabras_obj = set(re.sub(r'[^\w\s]', '', obj.lower()).split()) - STOP_WORDS
        return "filtro_propiedad", {"palabras": list(palabras_obj), "objeto": obj}

    if re.search(r'\bno\s+(?:son|es|libre|gratuito)|privativo|cerrado|de\s+pago|sin\s+costo', tl):
        return "booleano_false", {"palabras": list(palabras)}

    bool_kw = {"abierto","open","gratuito","gratis","libre","multiplataforma",
               "multiusuario","multitarea","movil","móvil","escritorio","servidor",
               "posix","sandboxing","principiantes","principiante","cifrado","freeware"}
    if palabras & bool_kw:
        return "booleano_true", {"palabras": list(palabras)}

    return "nombre", {"palabras": list(palabras), "termino": texto}


# ─── Constructores SPARQL (Fuseki) ────────────────────────────────────────────

def query_todos():
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto ?propiedad ?valor .
}} LIMIT 3000"""

def query_nombre(termino, palabras):
    tf = termino.replace(" ", "_")
    filtros = " || ".join(
        [f'regex(str(?v), "{p}", "i") || regex(str(?sujeto), "{p}", "i")' for p in palabras]
    ) if palabras else f'regex(str(?sujeto), "{tf}", "i")'
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto ?p_match ?v .
    FILTER ( {filtros} )
    ?sujeto ?propiedad ?valor .
}} LIMIT 2000"""

def query_booleano(palabras, valor_bool):
    prop_onto = None
    for p in palabras:
        if p in PROP_MAP:
            prop_onto = f"onto:{PROP_MAP[p]}"
            break
    if prop_onto:
        return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto {prop_onto} ?vm .
    FILTER ( str(?vm) = "{valor_bool}" )
    ?sujeto ?propiedad ?valor .
}} LIMIT 2000"""
    filtros = " || ".join([f'regex(str(?vm), "{p}", "i")' for p in palabras]) if palabras else "false"
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto ?prop_any ?vm .
    FILTER ( str(?vm) = "{valor_bool}" && ({filtros}) )
    ?sujeto ?propiedad ?valor .
}} LIMIT 2000"""

def query_filtro_propiedad(palabras, objeto):
    filtros_valor = " || ".join(
        [f'regex(str(?objVal), "{p}", "i") || regex(str(?obj), "{p}", "i")' for p in palabras]
    ) if palabras else f'regex(str(?obj), "{objeto}", "i")'
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto ?prop_any ?obj .
    FILTER ( {filtros_valor} )
    ?sujeto ?propiedad ?valor .
}} LIMIT 2000"""

def query_filtro_kernel(kernel_nombre):
    kn = kernel_nombre.replace(" ", "_")
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto onto:se_basa_en_kernel ?k .
    FILTER ( regex(str(?k), "{kn}", "i") || regex(str(?k), "{kernel_nombre}", "i") )
    ?sujeto ?propiedad ?valor .
}} LIMIT 2000"""

def query_comparar(a, b):
    a_f, b_f = a.replace(" ", "_"), b.replace(" ", "_")
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto ?p_match ?v .
    FILTER (
        regex(str(?v), "{a}", "i") || regex(str(?sujeto), "{a_f}", "i") ||
        regex(str(?v), "{b}", "i") || regex(str(?sujeto), "{b_f}", "i")
    )
    ?sujeto ?propiedad ?valor .
}} LIMIT 2000"""

def query_contar(palabras):
    if palabras:
        filtros = " || ".join(
            [f'regex(str(?v), "{p}", "i") || regex(str(?s), "{p}", "i")' for p in palabras]
        )
        bloque_filtro = f"\n    ?sujeto ?pm ?v .\n    BIND(?sujeto AS ?s)\n    FILTER ( {filtros} )"
    else:
        bloque_filtro = ""
    return f"""
{PREFIX_STR}
SELECT (COUNT(DISTINCT ?sujeto) AS ?total) WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}{bloque_filtro}
}}"""

def query_ranking(campo, orden, palabras):
    onto_campo = f"onto:{campo}"
    filtros_extra = ""
    if palabras:
        filtros_extra = " || ".join(
            [f'regex(str(?v), "{p}", "i") || regex(str(?sujeto), "{p}", "i")' for p in palabras]
        )
        filtros_extra = f"\n    ?sujeto ?pm ?v .\n    FILTER ( {filtros_extra} )"
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor ?campoVal WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto {onto_campo} ?campoVal .{filtros_extra}
    ?sujeto ?propiedad ?valor .
}}
ORDER BY {orden}(xsd:decimal(?campoVal))
LIMIT 1000"""


# ─── Procesamiento de resultados Fuseki ───────────────────────────────────────

def agrupar_bindings(bindings):
    datos = {}
    for r in bindings:
        if not ("sujeto" in r and "propiedad" in r and "valor" in r):
            continue
        suj  = r["sujeto"]["value"].split('#')[-1]
        prop = r["propiedad"]["value"].split('#')[-1]
        val  = r["valor"]["value"].split('#')[-1]
        if prop in ("type", "rdf-schema#label"):
            continue
        prop_l = prop.replace("_", " ").title()
        val_l  = val.replace("_", " ")
        if val_l.lower() == "true":  val_l = "Sí"
        elif val_l.lower() == "false": val_l = "No"
        datos.setdefault(suj, [])
        atr = {"Atributo": prop_l, "Valor": val_l}
        if atr not in datos[suj]:
            datos[suj].append(atr)
    return datos

def nombre_exacto(titulo, atributos):
    for a in atributos:
        if a["Atributo"].lower() == "nombre":
            return a["Valor"]
    return titulo.replace("_", " ")

def armar_resultado(titulo, attrs, modo):
    return {
        "titulo":         titulo.replace("_", " "),
        "atributos":      attrs,
        "nombre_dbpedia": nombre_exacto(titulo, attrs),
        "modo":           modo
    }


# ─── Rutas ─────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/dbpedia')
def dbpedia():
    nombre = request.args.get('nombre', '').strip()
    if not nombre:
        return jsonify({"error": "Falta el parámetro 'nombre'"}), 400
    try:
        datos = consultar_dbpedia(nombre)
        if datos:
            return jsonify({"ok": True, "datos": datos})
        return jsonify({"ok": False, "datos": None})
    except Exception as e:
        app.logger.error(f"[/dbpedia] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/dbpedia-test')
def dbpedia_test():
    import traceback
    resultados = {}

    try:
        import requests as req_test
        resultados["requests_instalado"] = True
        resultados["requests_version"] = req_test.__version__
    except ImportError as e:
        resultados["requests_instalado"] = False
        resultados["requests_error"] = str(e)
        return jsonify(resultados)

    try:
        r = req_test.get("https://httpbin.org/get", timeout=6)
        resultados["internet_ok"] = r.status_code == 200
    except Exception as e:
        resultados["internet_ok"] = False
        resultados["internet_error"] = str(e)

    try:
        r = req_test.get(
            "https://lookup.dbpedia.org/api/search",
            params={"query": "Linux operating system", "format": "json", "maxResults": 2},
            headers={"Accept": "application/json"},
            timeout=8
        )
        resultados["lookup_status"] = r.status_code
        resultados["lookup_ok"] = r.ok
        if r.ok:
            docs = r.json().get("docs", [])
            resultados["lookup_primer_recurso"] = docs[0].get("resource", [None])[0] if docs else None
    except Exception as e:
        resultados["lookup_ok"] = False
        resultados["lookup_error"] = str(e)
        resultados["lookup_traceback"] = traceback.format_exc()

    try:
        query = "SELECT ?s WHERE { <http://dbpedia.org/resource/Linux> ?p ?s } LIMIT 3"
        r = req_test.get(
            "https://dbpedia.org/sparql",
            params={"query": query, "format": "application/sparql-results+json"},
            headers={"Accept": "application/sparql-results+json",
                     "User-Agent": "BuscadorSO/1.0"},
            timeout=10
        )
        resultados["sparql_status"] = r.status_code
        resultados["sparql_ok"] = r.ok
        if r.ok:
            bindings = r.json().get("results", {}).get("bindings", [])
            resultados["sparql_bindings_count"] = len(bindings)
    except Exception as e:
        resultados["sparql_ok"] = False
        resultados["sparql_error"] = str(e)
        resultados["sparql_traceback"] = traceback.format_exc()

    try:
        datos = consultar_dbpedia("Linux")
        resultados["consultar_dbpedia_ok"] = datos is not None
        if datos:
            resultados["consultar_dbpedia_campos"] = list(datos.keys())
    except Exception as e:
        resultados["consultar_dbpedia_ok"] = False
        resultados["consultar_dbpedia_error"] = str(e)
        resultados["consultar_dbpedia_traceback"] = traceback.format_exc()

    return jsonify(resultados)


@app.route('/buscar')
def buscar():
    termino = request.args.get('q', '').strip().replace('"', '')
    if not termino:
        return jsonify({"error": "Escribe algo para buscar"})

    tl = termino.lower()
    palabras_router = set(re.sub(r'[^\w\s]', '', tl).split())

    if "todos" in palabras_router or (
        ("so" in palabras_router or "sistemas" in palabras_router)
        and len(palabras_router - STOP_WORDS) <= 3
    ):
        intencion, params = "todos", {}
    else:
        intencion, params = detectar_intencion(termino)

    try:
        if intencion == "contar":
            rows = run_fuseki(query_contar(params.get("palabras", [])))
            total = int(rows[0]["total"]["value"]) if rows and "total" in rows[0] else 0
            return jsonify({
                "tipo": "conteo", "total": total, "intencion": "contar",
                "mensaje": f"Se encontraron {total} sistemas operativos que coinciden con tu búsqueda."
            })

        if intencion == "definicion":
            termino_def = params.get("termino", termino)
            palabras_def = [
                p for p in re.sub(r'[^\w\s]', '', termino_def.lower()).split()
                if p not in STOP_WORDS and len(p) > 2
            ]
            bindings = run_fuseki(query_nombre(termino_def, palabras_def))
            agrupado = agrupar_bindings(bindings) if bindings else {}
            resultados = [armar_resultado(t, a, "definicion") for t, a in agrupado.items()]
            return jsonify({
                "tipo":           "definicion",
                "intencion":      "definicion",
                "termino_buscar": termino_def,
                "resultados":     resultados
            })

        if intencion == "todos":
            q = query_todos()
        elif intencion == "comparar":
            q = query_comparar(params["a"], params["b"])
        elif intencion == "ranking":
            q = query_ranking(params["campo"], params["orden"], params.get("palabras", []))
        elif intencion == "filtro_kernel":
            q = query_filtro_kernel(params.get("kernel", ""))
        elif intencion == "filtro_propiedad":
            q = query_filtro_propiedad(params.get("palabras", []), params.get("objeto", termino))
        elif intencion in ("booleano_true", "booleano_false"):
            valor = "true" if intencion == "booleano_true" else "false"
            q = query_booleano(params.get("palabras", []), valor)
        else:
            q = query_nombre(termino, params.get("palabras", []))

        bindings = run_fuseki(q)

        if not bindings and intencion not in ("todos",):
            bindings = run_fuseki(query_nombre(termino, params.get("palabras", [])))

        agrupado = agrupar_bindings(bindings) if bindings else {}
        resultados = [armar_resultado(t, a, intencion) for t, a in agrupado.items()]

        return jsonify({
            "tipo":           "resultados",
            "intencion":      "intencion",
            "params":         params,
            "termino_buscar": termino,
            "resultados":     resultados
        })

    except Exception as e:
        return jsonify({"error": f"Error del núcleo semántico: {str(e)}"})


if __name__ == '__main__':
    app.run(debug=True)