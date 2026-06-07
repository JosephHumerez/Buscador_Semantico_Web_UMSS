from flask import Flask, render_template, request, jsonify
from SPARQLWrapper import SPARQLWrapper, JSON
import re
import requests
from translation_dict import TRANSLATION_DICT_EXPANDED as TRANSLATION_DICT

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
    "dime","háblame","habla","explícame","significa","significado",
    "sirven","sirve","usado","usados","usadas","usada","pensado","pensados",
    "diseñado","diseñados","orientado","orientados","hecho","hechos",
    "funciona","funcionan","corre","corren","ejecuta","ejecutan",
    "instala","instalan","existe","existen","puedo","puedes",
    # EN
    "what","is","are","the","a","an","of","for","and","or","in","on","at",
    "tell","me","about","explain","define","show","find","search","how",
    "serve","served","used","designed","made","built","meant","which","can","do",
    "run","runs","work","works","install","installed",
    # PT
    "o","a","os","as","um","uma","de","para","que","com","é","são","me",
    "qual","quais","mostrar","buscar","encontrar","sobre","explica","define",
    # FR
    "le","la","les","un","une","des","est","sont","de","du","pour","que",
    "quoi","quel","quelle","montre","cherche","trouve","sur","explique","définit",
}

PREFIX_STR = (
    f"PREFIX onto: <{PREFIX_URI}>\n"
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"
)

CLASE_FILTRO = "FILTER (?tipo IN (onto:Sistema_Operativo, onto:Distribucion))"

PROP_MAP = {
    # ── Booleanos (true/false) ──────────────────────────────────────────────────
    "open_source":"es_open_source","abierto":"es_open_source","libre":"es_open_source","open":"es_open_source",
    "gratuito":"es_gratuito_freeware","gratis":"es_gratuito_freeware","freeware":"es_gratuito_freeware",
    "free":"es_gratuito_freeware","gratuit":"es_gratuito_freeware",
    "pago":"es_comercial_de_pago","comercial":"es_comercial_de_pago","privativo":"es_comercial_de_pago",
    "paid":"es_comercial_de_pago","commercial":"es_comercial_de_pago","proprietary":"es_comercial_de_pago",
    "posix":"cumple_estandar_posix","modificable":"permite_modificacion",
    "sandboxing":"tiene_sandboxing_nativo","sandbox":"tiene_sandboxing_nativo",
    "principiantes":"orientado_a_principiantes","principiante":"orientado_a_principiantes",
    "beginner":"orientado_a_principiantes","beginners":"orientado_a_principiantes",
    "iniciante":"orientado_a_principiantes","débutant":"orientado_a_principiantes",
    "kernel_modificado":"es_kernel_modificado","cifrado":"cifrado_disco_por_defecto",
    "encryption":"cifrado_disco_por_defecto","chiffrement":"cifrado_disco_por_defecto",
    "multiusuario":"es_multiusuario","multitarea":"es_multitarea",
    # ── Propiedades de valor (no booleanas) ─────────────────────────────────────
    "kernel":"se_basa_en_kernel","nucleo":"se_basa_en_kernel","núcleo":"se_basa_en_kernel",
    "licencia":"utiliza_licencia","license":"utiliza_licencia","licence":"utiliza_licencia",
    "arquitectura":"arquitectura_soportada","architecture":"arquitectura_soportada",
    "entorno":"entorno_escritorio_default","gestor":"gestor_paquetes_default",
    "paquetes":"gestor_paquetes_default","packages":"gestor_paquetes_default",
    "desarrollador":"desarrollador","developer":"desarrollador","développeur":"desarrollador",
    "version":"version_so","versión":"version_so",
    "familia":"familia_base","family":"familia_base","famille":"familia_base",
    "proposito":"proposito","propósito":"proposito","purpose":"proposito",
    "multiplataforma":"arquitectura_soportada","multiplatform":"arquitectura_soportada",
}

# Propiedades cuyo valor en la ontología NO es booleano sino texto (ej. "Movil", "x86_64").
# Para estas se usa query_filtro_valor en vez de query_booleano.
PROP_VALOR_MAP = {
    "movil":"proposito","moviles":"proposito","móvil":"proposito","móviles":"proposito",
    "mobile":"proposito","móvel":"proposito",
    "celular":"proposito","celulares":"proposito",
    "smartphone":"proposito","smartphones":"proposito",
    "telefono":"proposito","teléfono":"proposito","telefonos":"proposito","teléfonos":"proposito",
    "phone":"proposito","phones":"proposito","handheld":"proposito",
    "servidor":"proposito","servidores":"proposito","server":"proposito","servers":"proposito","serveur":"proposito",
    "escritorio":"proposito","escritorios":"proposito","desktop":"proposito","desktops":"proposito","bureau":"proposito",
    "embebido":"proposito","embebidos":"proposito","embedded":"proposito","iot":"proposito",
    "x86":"arquitectura_soportada","x64":"arquitectura_soportada",
    "arm":"arquitectura_soportada","aarch64":"arquitectura_soportada","mips":"arquitectura_soportada",
    "linux":"se_basa_en_kernel","unix":"se_basa_en_kernel","xnu":"se_basa_en_kernel",
    "nt":"se_basa_en_kernel","bsd":"se_basa_en_kernel","monolitico":"se_basa_en_kernel",
    "debian":"familia_base","arch":"familia_base","fedora":"familia_base",
    "rpm":"gestor_paquetes_default","apt":"gestor_paquetes_default",
    "pacman":"gestor_paquetes_default","dnf":"gestor_paquetes_default",
    "gnome":"entorno_escritorio_default","kde":"entorno_escritorio_default",
    "xfce":"entorno_escritorio_default","mate":"entorno_escritorio_default",
}

# Valor canónico a buscar en la ontología para cada palabra clave de PROP_VALOR_MAP
PROP_VALOR_VALOR = {
    "movil":"Movil","móvil":"Movil","moviles":"Movil","móviles":"Movil",
    "mobile":"Movil","móvel":"Movil",
    "celular":"Movil","celulares":"Movil",
    "smartphone":"Movil","smartphones":"Movil",
    "telefono":"Movil","teléfono":"Movil","telefonos":"Movil","teléfonos":"Movil",
    "phone":"Movil","phones":"Movil","handheld":"Movil",
    "servidor":"Servidor","servidores":"Servidor","server":"Servidor","servers":"Servidor","serveur":"Servidor",
    "escritorio":"Escritorio","escritorios":"Escritorio","desktop":"Escritorio","desktops":"Escritorio","bureau":"Escritorio",
    "embebido":"Embebido","embebidos":"Embebido","embedded":"Embebido","iot":"Embebido",
}

# TRANSLATION_DICT está importado desde translation_dict.py


def traducir_resultado(resultado, lang="es"):
    """Traduce los atributos y valores de un resultado según el idioma especificado."""
    if lang not in TRANSLATION_DICT:
        lang = "es"
    
    dict_traducciones = TRANSLATION_DICT[lang]
    atributos_traducidos = []
    
    for attr in resultado.get("atributos", []):
        attr_original = attr["Atributo"]
        valor_original = attr["Valor"]
        
        # Traducir el atributo
        attr_traducido = dict_traducciones["atributos"].get(attr_original, attr_original)
        
        # Traducir el valor
        valor_traducido = dict_traducciones["valores"].get(valor_original, valor_original)
        
        atributos_traducidos.append({
            "Atributo": attr_traducido,
            "Valor": valor_traducido
        })
    
    resultado["atributos"] = atributos_traducidos
    return resultado


# ─── DBpedia headers ──────────────────────────────────────────────────────

DBP_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "BuscadorSO/1.0 (proyecto educativo; contacto@ejemplo.com)"
}

_dbp_cache = {}

def run_fuseki(query):
    fuseki.setQuery(query)
    return fuseki.query().convert()["results"]["bindings"]


# ─── Detección de idioma ───────────────────────────────────────────────────────

def detectar_idioma(texto):
    tl = texto.lower()
    if re.search(r'\b(what is|what are|how|explain|tell me|compare|vs|versus|show|find|search|which)\b', tl):
        return "en"
    if re.search(r'\b(qu[eé] [eé]|como|qual|quais|mostrar|buscar|comparar|versus|explica)\b', tl):
        if re.search(r'\b(qual|quais|buscar|mostrar|sistema operacional)\b', tl):
            return "pt"
        return "es"
    if re.search(r'\b(qu\'est|c\'est|quoi|quel|quelle|montre|cherche|compare|versus|expliquer)\b', tl):
        return "fr"
    return "es"


# ─── Normalización multilingüe de intención ───────────────────────────────────

CMP_PATTERNS = re.compile(
    r'(.+?)\s+(?:vs\.?|versus|contra|vs\.?\s|'
    r'comparar\s+con|comparado\s+con|diferencia\s+entre|'
    r'compare\s+with|compared\s+to|difference\s+between|'
    r'comparar\s+com|diferença\s+entre|'
    r'comparer\s+avec|comparé\s+à|différence\s+entre)\s+(.+)',
    re.IGNORECASE
)

COUNT_PATTERNS = re.compile(
    r'cu[aá]ntos|cu[aá]ntas|cantidad\s+de|total\s+de|n[uú]mero\s+de|'
    r'how\s+many|count\s+of|total\s+of|number\s+of|'
    r'quantos|quantas|quantidade\s+de|total\s+de|n[uú]mero\s+de|'
    r'combien|nombre\s+de|total\s+de',
    re.IGNORECASE
)

DEF_PATTERNS = re.compile(
    r'qu[eé]\s+es|qu[eé]\s+son|define|definici[oó]n\s+de|explic|cu[eé]ntame|h[aá]blame|significa|'
    r'what\s+is|what\s+are|explain|definition\s+of|tell\s+me\s+about|describe|'
    r'o\s+que\s+[eé]|o\s+que\s+s[aã]o|explica|defini[çc][aã]o\s+de|fala\s+sobre|'
    r"qu'est.ce\s+que|c'est\s+quoi|expliquer|définition\s+de|parle\s+de|qu'est",
    re.IGNORECASE
)

RANK_PATTERNS = re.compile(
    r'\b(m[aá]s|menos|menor|mayor)\b.{0,40}\b(ram|memoria|consumo|r[aá]pido|ligero|seguro|popular)\b|'
    r'\b(most|least|lightest|fastest|lowest|highest)\b.{0,40}\b(ram|memory|usage|fast|light)|'
    r'\b(mais|menos|menor|maior)\b.{0,40}\b(ram|mem[oó]ria|consumo|r[aá]pido|leve)|'
    r'\b(plus|moins|le\s+plus|le\s+moins)\b.{0,40}\b(ram|mémoire|consommation|rapide|léger)',
    re.IGNORECASE
)


# ─── DBpedia helpers ──────────────────────────────────────────────────────────

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
    if "raspberry" in n: return ["Raspberry_Pi_OS", "Raspbian"]
    if "kali"    in n: return ["Kali_Linux"]
    if "manjaro" in n: return ["Manjaro_Linux"]
    if "opensuse" in n or "suse" in n: return ["OpenSUSE", "SUSE_Linux"]
    if "alpine"  in n: return ["Alpine_Linux"]
    if "gentoo"  in n: return ["Gentoo_Linux"]
    if "nixos"   in n: return ["NixOS"]
    if "void"    in n: return ["Void_Linux"]
    if "tails"   in n: return ["Tails_(operating_system)"]
    if "qubes"   in n: return ["Qubes_OS"]
    if "plan 9"  in n: return ["Plan_9_from_Bell_Labs"]
    if "minix"   in n: return ["MINIX"]
    if "reactos" in n: return ["ReactOS"]
    if "beos"    in n or "be os" in n: return ["BeOS"]
    if "amiga"   in n: return ["AmigaOS"]
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
                or "operating" in cats or "linux" in cats
            ):
                return res
        return (docs[0].get("resource") or [None])[0] if docs else None
    except Exception as e:
        app.logger.warning(f"[Lookup] {e}")
        return None


def _sparql_basico(bind_clause, lang="es"):
    lang2 = "en" if lang != "en" else "es" 
    return f"""
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX dbp:  <http://dbpedia.org/property/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT
  (SAMPLE(?absLang) AS ?resumen)
  (SAMPLE(?absEn)   AS ?resumenEn)
  (SAMPLE(?lbl)     AS ?nombre)
  (GROUP_CONCAT(DISTINCT ?devFinal; separator="||") AS ?desarrolladores)
  (SAMPLE(?fecha)   AS ?anio)
  (GROUP_CONCAT(DISTINCT ?licFinal; separator="||") AS ?licencias)
  (SAMPLE(?page)    AS ?web)
  (SAMPLE(?logoV)   AS ?logo)
  (SAMPLE(?r)       AS ?uri)
WHERE {{
  {bind_clause}
  OPTIONAL {{ ?r rdfs:label ?lbl . FILTER(LANG(?lbl)="{lang}" || LANG(?lbl)="en") }}
  OPTIONAL {{ ?r dbo:abstract ?absLang . FILTER(LANG(?absLang)="{lang}") }}
  OPTIONAL {{ ?r dbo:abstract ?absEn   . FILTER(LANG(?absEn)="en") }}
  OPTIONAL {{
    ?r dbo:developer|dbp:developer ?dev .
    OPTIONAL {{ ?dev rdfs:label ?devL . FILTER(LANG(?devL)="en" || LANG(?devL)="{lang}") }}
    BIND(COALESCE(?devL, STR(?dev)) AS ?devFinal)
  }}
  OPTIONAL {{ ?r dbo:releaseDate|dbp:releaseDate ?fecha }}
  OPTIONAL {{
    ?r dbo:license|dbp:license ?lic .
    OPTIONAL {{ ?lic rdfs:label ?licL . FILTER(LANG(?licL)="en" || LANG(?licL)="{lang}") }}
    BIND(COALESCE(?licL, STR(?lic)) AS ?licFinal)
  }}
  OPTIONAL {{ ?r foaf:homepage|dbp:website ?page }}
  OPTIONAL {{ ?r dbp:logo|dbo:logo ?logoV }}
}}"""


def _sparql_extra(uri, lang="es"):
    return f"""
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX dbp:  <http://dbpedia.org/property/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT
  (GROUP_CONCAT(DISTINCT ?famFinal;  separator="||") AS ?familias)
  (GROUP_CONCAT(DISTINCT ?kFinal;    separator="||") AS ?kernels)
  (SAMPLE(?verFinal)                                 AS ?version)
  (GROUP_CONCAT(DISTINCT ?ktFinal;   separator="||") AS ?tiposKernel)
  (GROUP_CONCAT(DISTINCT ?predFinal; separator="||") AS ?predecesores)
  (GROUP_CONCAT(DISTINCT ?sucFinal;  separator="||") AS ?sucesores)
  (GROUP_CONCAT(DISTINCT ?platFinal; separator="||") AS ?plataformas)
  (GROUP_CONCAT(DISTINCT ?langFinal; separator="||") AS ?lenguajes)
WHERE {{
  BIND(<{uri}> AS ?r)
  OPTIONAL {{
    ?r dbo:family|dbp:family ?fam .
    OPTIONAL {{ ?fam rdfs:label ?famL . FILTER(LANG(?famL)="en" || LANG(?famL)="{lang}") }}
    BIND(COALESCE(?famL, STR(?fam)) AS ?famFinal)
  }}
  OPTIONAL {{
    ?r dbo:kernel|dbp:kernel ?kv .
    OPTIONAL {{ ?kv rdfs:label ?kvL . FILTER(LANG(?kvL)="en" || LANG(?kvL)="{lang}") }}
    BIND(COALESCE(?kvL, STR(?kv)) AS ?kFinal)
  }}
  OPTIONAL {{ ?r dbo:latestReleaseVersion|dbp:latestReleaseVersion|dbp:version ?verRaw . BIND(STR(?verRaw) AS ?verFinal) }}
  OPTIONAL {{
    ?r dbo:kernelType|dbp:kernelType ?kt .
    OPTIONAL {{ ?kt rdfs:label ?ktL . FILTER(LANG(?ktL)="en" || LANG(?ktL)="{lang}") }}
    BIND(COALESCE(?ktL, STR(?kt)) AS ?ktFinal)
  }}
  OPTIONAL {{
    ?r dbo:predecessor|dbp:predecessor ?pred .
    OPTIONAL {{ ?pred rdfs:label ?predL . FILTER(LANG(?predL)="en" || LANG(?predL)="{lang}") }}
    BIND(COALESCE(?predL, STR(?pred)) AS ?predFinal)
  }}
  OPTIONAL {{
    ?r dbo:successor|dbp:successor ?suc .
    OPTIONAL {{ ?suc rdfs:label ?sucL . FILTER(LANG(?sucL)="en" || LANG(?sucL)="{lang}") }}
    BIND(COALESCE(?sucL, STR(?suc)) AS ?sucFinal)
  }}
  OPTIONAL {{ ?r dbp:supportedPlatforms ?plat . BIND(STR(?plat) AS ?platFinal) }}
  OPTIONAL {{ ?r dbp:programmingLanguage ?lang . BIND(STR(?lang) AS ?langFinal) }}
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
            app.logger.warning(f"[SPARQL] HTTP {resp.status_code}")
            return None
        bindings = resp.json().get("results", {}).get("bindings", [])
        return bindings[0] if bindings else None
    except Exception as e:
        app.logger.warning(f"[SPARQL] {e}")
        return None


def _clean_val(v):
    if not v: return None
    if v.startswith("http"):
        v = v.split("#")[-1] if "#" in v else v.split("/")[-1]
    return v.replace("_", " ").strip()


def _parsear_row(row):
    if not row:
        return None

    def g(k):
        return row[k]["value"] if k in row else None

    def gsplit(k, lim=6):
        v = g(k)
        if not v: return None
        parts = list(dict.fromkeys(_clean_val(x) for x in v.split("||") if x.strip()))
        return ", ".join(p for p in parts if p)[:200] or None

    anio = g("anio")
    result = {
        "resumen":       g("resumen") or g("resumenEn"),
        "nombre":        g("nombre"),
        "uri":           g("uri"),
        "desarrollador": gsplit("desarrolladores"),
        "anio":          anio[:4] if anio else None,
        "licencia":      gsplit("licencias"),
        "web":           g("web"),
        "familia":       gsplit("familias"),
        "kernel":        gsplit("kernels"),
        "version":       g("version"),
        "plataformas":   gsplit("plataformas"),
        "lenguaje":      gsplit("lenguajes"),
        "tipoKernel":    gsplit("tiposKernel"),
        "predecesores":  gsplit("predecesores"),
        "sucesores":     gsplit("sucesores"),
        "logo":          g("logo"),
    }
    clean = {k: v for k, v in result.items() if v}
    return clean if clean else None


def _enriquecer_con_extra(datos, lang="es"):
    uri = datos.get("uri")
    if not uri:
        return
    try:
        row = _run_dbpedia_sparql(_sparql_extra(uri, lang), timeout=20)
        if not row:
            return

        def gsplit_row(k, lim=6):
            v = row[k]["value"] if k in row else None
            if not v: return None
            parts = list(dict.fromkeys(_clean_val(x) for x in v.split("||") if x.strip()))
            return ", ".join(p for p in parts if p)[:200] or None

        extras = {
            "familia":      gsplit_row("familias"),
            "kernel":       gsplit_row("kernels"),
            "version":      row["version"]["value"] if "version" in row else None,
            "tipoKernel":   gsplit_row("tiposKernel"),
            "predecesores": gsplit_row("predecesores"),
            "sucesores":    gsplit_row("sucesores"),
            "plataformas":  gsplit_row("plataformas"),
            "lenguaje":     gsplit_row("lenguajes"),
        }
        for k, v in extras.items():
            if v and not datos.get(k):
                datos[k] = v
    except Exception as e:
        app.logger.warning(f"[extra] {e}")


def consultar_dbpedia(nombre, lang="es"):
    clave = f"{lang}:{nombre.lower().strip()}"
    if clave in _dbp_cache:
        return _dbp_cache[clave]
    datos = _consultar_dbpedia_interno(nombre, lang)
    _dbp_cache[clave] = datos
    return datos


def _consultar_dbpedia_interno(nombre, lang="es"):
    uri_lookup = _lookup_uri(nombre)
    if uri_lookup:
        row = _run_dbpedia_sparql(_sparql_basico(f"BIND(<{uri_lookup}> AS ?r)", lang))
        datos = _parsear_row(row)
        if datos:
            datos["uri"] = datos.get("uri") or uri_lookup
            _enriquecer_con_extra(datos, lang)
            return datos

    for cand in _uri_candidatos(nombre)[:5]:
        uri = f"http://dbpedia.org/resource/{requests.utils.quote(cand, safe='')}"
        row = _run_dbpedia_sparql(_sparql_basico(f"BIND(<{uri}> AS ?r)", lang))
        datos = _parsear_row(row)
        if datos:
            datos["uri"] = datos.get("uri") or uri
            _enriquecer_con_extra(datos, lang)
            return datos

    nom_clean = re.sub(r"[^\w\s]", "", nombre)
    query_tl = f"""
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbp:  <http://dbpedia.org/property/>
SELECT DISTINCT ?r
  (SAMPLE(?lbl)   AS ?nombre)
  (SAMPLE(?absLang) AS ?resumen)
  (SAMPLE(?absEn)   AS ?resumenEn)
  (GROUP_CONCAT(DISTINCT ?devFinal; separator="||") AS ?desarrolladores)
  (SAMPLE(?fecha) AS ?anio)
  (GROUP_CONCAT(DISTINCT ?licFinal; separator="||") AS ?licencias)
  (SAMPLE(?page)  AS ?web)
  (SAMPLE(?logoV) AS ?logo)
WHERE {{
  ?r rdf:type ?type . FILTER(?type IN (dbo:OperatingSystem, dbo:Software))
  ?r rdfs:label ?lbl . FILTER(regex(?lbl, "{nom_clean}", "i"))
  OPTIONAL {{ ?r dbo:abstract ?absLang . FILTER(LANG(?absLang)="{lang}") }}
  OPTIONAL {{ ?r dbo:abstract ?absEn   . FILTER(LANG(?absEn)="en") }}
  OPTIONAL {{
    ?r dbo:developer|dbp:developer ?dev .
    OPTIONAL {{ ?dev rdfs:label ?devL . FILTER(LANG(?devL)="en") }}
    BIND(COALESCE(?devL, STR(?dev)) AS ?devFinal)
  }}
  OPTIONAL {{ ?r dbo:releaseDate ?fecha }}
  OPTIONAL {{
    ?r dbo:license ?lic .
    OPTIONAL {{ ?lic rdfs:label ?licL . FILTER(LANG(?licL)="en") }}
    BIND(COALESCE(?licL, STR(?lic)) AS ?licFinal)
  }}
  OPTIONAL {{ ?r foaf:homepage ?page }}
  OPTIONAL {{ ?r dbp:logo ?logoV }}
}} GROUP BY ?r LIMIT 1"""

    row2 = _run_dbpedia_sparql(query_tl)
    datos2 = _parsear_row(row2)
    if datos2:
        if not datos2.get("uri") and row2 and "r" in row2:
            datos2["uri"] = row2["r"]["value"]
        _enriquecer_con_extra(datos2, lang)
        return datos2

    return None


# ─── Detección de intención (multilingüe) ─────────────────────────────────────

def detectar_intencion(texto):
    tl = texto.lower().strip()
    palabras_raw = set(re.sub(r'[^\w\s]', '', tl).split())
    palabras = palabras_raw - STOP_WORDS
    lang = detectar_idioma(tl)

    m = CMP_PATTERNS.search(tl)
    if m:
        return "comparar", {"a": m.group(1).strip(), "b": m.group(2).strip(), "lang": lang}

    if COUNT_PATTERNS.search(tl):
        return "contar", {"palabras": list(palabras), "lang": lang}

    m_def = DEF_PATTERNS.search(tl)
    if m_def:
        termino_def = tl[m_def.end():].strip()
        termino_def = re.sub(r'^(?:el|la|los|las|un|una|the|a|an|o|a|os|as|le|la|les|un|une)\s+', '', termino_def).strip()
        if termino_def:
            return "definicion", {"termino": termino_def, "lang": lang}

    m_rank = RANK_PATTERNS.search(tl)
    if m_rank:
        es_asc = bool(re.search(r'\b(menos|menor|lightest|least|lowest|menos|menor|plus\s+l[eé]ger|moins)\b', tl))
        direccion = "ASC" if es_asc else "DESC"
        campo = "ram_en_reposo_mb" if re.search(r'ram|mem[oó]ria|memory|mémoire|ligero|light|leve|léger', tl) else "version_so"
        return "ranking", {"campo": campo, "orden": direccion, "palabras": list(palabras), "lang": lang}

    m_k = re.search(r'kernel\s+(\w[\w\s]*?)(?:\s+(?:en|de|para|que|in|on|for|with|com|sur|avec)|\s*$)', tl)
    if m_k:
        return "filtro_kernel", {"kernel": m_k.group(1).strip(), "lang": lang}

    # ── Preguntas de PROPÓSITO/USO: "sirven para X", "usados en X", "para celulares", etc. ──
    PATRON_PROPOSITO = re.compile(
        r'(?:sirven|usado[s]?|pensado[s]?|dise[nñ]ado[s]?|orientado[s]?|enfocado[s]?|hecho[s]?|'
        r'serve[sd]?|used|designed|made|built|meant)\s+'
        r'(?:para|en|for|on|in)?\s*'
        r'(?:celulares?|smartphones?|tel[eé]fonos?\s*m[oó]viles?|dispositivos?\s*m[oó]viles?|'
        r'm[oó]viles?|mobile\s*devices?|phones?|handheld|'
        r'servidores?|servers?|'
        r'escritorio[s]?|desktops?|pcs?|'
        r'embebido[s]?|embedded|iot)',
        re.IGNORECASE
    )
    PATRON_PARA_TIPO = re.compile(
        r'(?:^|\s)para\s+'
        r'(?:celulares?|smartphones?|tel[eé]fonos?\s*m[oó]viles?|dispositivos?\s*m[oó]viles?|'
        r'm[oó]viles?|mobile\s*devices?|phones?|handheld|'
        r'servidores?|servers?|'
        r'escritorio[s]?|desktops?|pcs?|'
        r'embebido[s]?|embedded|iot)',
        re.IGNORECASE
    )
    PATRON_FUNCIONA_EN = re.compile(
        r'(?:funciona[n]?|corre[n]?|corren|ejecuta[n]?|run[s]?|work[s]?|instala[n]?)\s+'
        r'(?:en|on|in)\s+'
        r'(?:celulares?|smartphones?|tel[eé]fonos?|dispositivos?\s*m[oó]viles?|'
        r'm[oó]viles?|mobile|phones?|handheld|'
        r'servidores?|servers?|escritorio[s]?|desktops?)',
        re.IGNORECASE
    )

    for pat in (PATRON_PROPOSITO, PATRON_PARA_TIPO, PATRON_FUNCIONA_EN):
        m_p = pat.search(tl)
        if m_p:
            fragmento = m_p.group(0).lower()
            # Determinar el valor canónico de propósito
            val_proposito = None
            for kw, val in PROP_VALOR_VALOR.items():
                if re.search(kw, fragmento):
                    val_proposito = val
                    break
            if val_proposito:
                return "filtro_valor", {
                    "propiedad": "proposito",
                    "valor": val_proposito,
                    "lang": lang,
                    "palabras": list(palabras),
                }

    m_prop = re.search(
        r'qu[eé]\s+(?:so|sistemas?)(?:\s+\w+)?\s+(?:tienen?|usan?|soportan?|incluyen?|permiten?)\s+(.+)|'
        r'(?:so|sistemas?)\s+(?:con|que\s+tengan?|que\s+usen?)\s+(.+)|'
        r'which\s+(?:os|systems?)\s+(?:have|use|support|include)\s+(.+)|'
        r'(?:os|systems?)\s+(?:with|that\s+have|that\s+use)\s+(.+)',
        tl
    )
    if m_prop:
        obj = next((g for g in m_prop.groups() if g), "").strip()
        palabras_obj = set(re.sub(r'[^\w\s]', '', obj.lower()).split()) - STOP_WORDS
        return "filtro_propiedad", {"palabras": list(palabras_obj), "objeto": obj, "lang": lang}

    if re.search(r'\bno\s+(?:son|es|libre|gratuito)|privativo|cerrado|de\s+pago|'
                 r'not\s+(?:free|open)|proprietary|closed|paid|'
                 r'não\s+(?:livre|gratuito)|propriét', tl):
        return "booleano_false", {"palabras": list(palabras), "lang": lang}

    # ── Palabras clave de propiedades con valor de texto ─────────────────────────
    for kw in palabras:
        if kw in PROP_VALOR_MAP:
            prop = PROP_VALOR_MAP[kw]
            val  = PROP_VALOR_VALOR.get(kw)       # puede ser None para arm, apt, etc.
            if val:
                return "filtro_valor", {
                    "propiedad": prop,
                    "valor": val,
                    "lang": lang,
                    "palabras": list(palabras),
                }
            # Sin valor canónico → buscar la palabra literalmente
            return "filtro_valor", {
                "propiedad": prop,
                "valor": kw,
                "lang": lang,
                "palabras": list(palabras),
            }

    bool_kw = {"abierto","open","gratuito","gratis","libre","free","multiplataforma",
               "multiusuario","multitarea","posix","sandboxing","sandbox","principiantes","beginner",
               "cifrado","encryption","freeware","gratuit","débutant","aberto","iniciante",
               "multiusuario","multitarea","kernel_modificado"}
    if palabras & bool_kw:
        return "booleano_true", {"palabras": list(palabras), "lang": lang}

    return "nombre", {"palabras": list(palabras), "termino": texto, "lang": lang}


# ─── Constructores SPARQL (Fuseki) ──────────────────────────────────────────────

def query_todos():
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    ?sujeto ?propiedad ?valor .
}} LIMIT 3000"""

def query_nombre(termino, palabras):
    tf = termino.replace(" ", "_")
    # Primero buscar por nombre exacto o URI del SO (mayor precisión)
    # Luego como fallback en cualquier propiedad
    if palabras:
        filtros_nombre = " || ".join(
            [f'regex(str(?sujeto), "{p}", "i") || regex(str(?nom), "{p}", "i")' for p in palabras]
        )
        filtros_general = " || ".join(
            [f'regex(str(?v), "{p}", "i") || regex(str(?sujeto), "{p}", "i")' for p in palabras]
        )
    else:
        filtros_nombre  = f'regex(str(?sujeto), "{tf}", "i")'
        filtros_general = f'regex(str(?sujeto), "{tf}", "i")'
    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    {{
        # Prioridad 1: match en nombre o URI del SO
        OPTIONAL {{ ?sujeto onto:nombre ?nom }}
        FILTER ( {filtros_nombre} )
    }} UNION {{
        # Prioridad 2: match en cualquier propiedad
        ?sujeto ?p_match ?v .
        FILTER ( {filtros_general} )
        # Excluir SOs que solo matchean por familia_base o propiedades secundarias
        # cuando el término es corto (probable nombre de SO)
        FILTER NOT EXISTS {{
            ?sujeto onto:nombre ?n2 .
            FILTER ( !regex(str(?n2), "{tf.split('_')[0]}", "i") )
        }}
    }}
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
        [f'regex(str(?obj), "{p}", "i")' for p in palabras]
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

def query_filtro_valor(propiedad, valor, palabras_extra=None):
    """Busca SO donde onto:<propiedad> coincide con <valor>.
    También busca en onto:descripcion como fallback para cubrir
    casos donde la propiedad no está definida pero la descripción la menciona."""
    onto_prop = f"onto:{propiedad}"

    # Variantes de búsqueda para manejar acentos y sinónimos
    VARIANTES = {
        "Movil":      ["m.vil", "mobile", "celular", "smartphone", "tel.fono"],
        "Móvil":      ["m.vil", "mobile", "celular", "smartphone", "tel.fono"],
        "movil":      ["m.vil", "mobile", "celular", "smartphone", "tel.fono"],
        "Servidor":   ["servidor", "server"],
        "servidor":   ["servidor", "server"],
        "Escritorio": ["escritorio", "desktop"],
        "escritorio": ["escritorio", "desktop"],
        "Embebido":   ["embebido", "embedded", "iot"],
        "embebido":   ["embebido", "embedded", "iot"],
        "Legado":     ["legado", "legacy"],
    }
    variantes_val = VARIANTES.get(valor, [valor.lower()])
    regex_val = "|".join(variantes_val)

    return f"""
{PREFIX_STR}
SELECT DISTINCT ?sujeto ?propiedad ?valor WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    {{
        # Búsqueda principal: en la propiedad exacta
        ?sujeto {onto_prop} ?obj_v .
        FILTER ( regex(str(?obj_v), "{regex_val}", "i") )
    }} UNION {{
        # Fallback: en la descripción del SO
        ?sujeto onto:descripcion ?desc_v .
        FILTER ( regex(str(?desc_v), "{regex_val}", "i") )
    }}
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

def query_filtro_valor_desde_palabras(palabras):
    """Dado un conjunto de palabras del query de conteo, devuelve la query SPARQL
    para listar los SOs correspondientes."""
    import unicodedata
    # Mapea palabra normalizada -> (propiedad, valor_canonico)
    VARIANTES_LISTA = {
        "movil":      ("proposito", "Movil"),
        "moviles":    ("proposito", "Movil"),
        "celular":    ("proposito", "Movil"),
        "celulares":  ("proposito", "Movil"),
        "smartphone": ("proposito", "Movil"),
        "smartphones":("proposito", "Movil"),
        "servidor":   ("proposito", "Servidor"),
        "servidores": ("proposito", "Servidor"),
        "server":     ("proposito", "Servidor"),
        "escritorio": ("proposito", "Escritorio"),
        "desktop":    ("proposito", "Escritorio"),
    }
    for p in (palabras or []):
        p_norm = unicodedata.normalize("NFKD", p).encode("ascii","ignore").decode().lower()
        if p_norm in VARIANTES_LISTA:
            prop, val = VARIANTES_LISTA[p_norm]
            return query_filtro_valor(prop, val, [])
    return None

def query_contar(palabras):
    # Si las palabras incluyen clave de propósito, filtrar semánticamente
    import unicodedata
    VARIANTES_CONTAR = {
        "movil":      ("proposito", "m.vil|mobile|celular|smartphone"),
        "moviles":    ("proposito", "m.vil|mobile|celular|smartphone"),
        "celular":    ("proposito", "m.vil|mobile|celular|smartphone"),
        "celulares":  ("proposito", "m.vil|mobile|celular|smartphone"),
        "smartphone": ("proposito", "m.vil|mobile|celular|smartphone"),
        "smartphones":("proposito", "m.vil|mobile|celular|smartphone"),
        "servidor":   ("proposito", "servidor|server"),
        "servidores": ("proposito", "servidor|server"),
        "escritorio": ("proposito", "escritorio|desktop"),
        "desktop":    ("proposito", "escritorio|desktop"),
    }
    for p in (palabras or []):
        p_norm = unicodedata.normalize("NFKD", p).encode("ascii","ignore").decode().lower()
        if p_norm in VARIANTES_CONTAR:
            prop, regex_val = VARIANTES_CONTAR[p_norm]
            return f"""
{PREFIX_STR}
SELECT (COUNT(DISTINCT ?sujeto) AS ?total) WHERE {{
    ?sujeto rdf:type ?tipo . {CLASE_FILTRO}
    {{
        ?sujeto onto:{prop} ?obj_v .
        FILTER ( regex(str(?obj_v), "{regex_val}", "i") )
    }} UNION {{
        ?sujeto onto:descripcion ?desc_v .
        FILTER ( regex(str(?desc_v), "{regex_val}", "i") )
    }}
}}"""

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


# ─── Procesamiento Fuseki ─────────────────────────────────────────────────────

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


# ─── Rutas ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    from flask import make_response
    resp = make_response(render_template('index.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/dbpedia')
def dbpedia_route():
    nombre = request.args.get('nombre', '').strip()
    lang   = request.args.get('lang', 'es').strip()
    if not nombre:
        return jsonify({"error": "Falta el parámetro 'nombre'"}), 400
    try:
        datos = consultar_dbpedia(nombre, lang)
        return jsonify({"ok": bool(datos), "datos": datos})
    except Exception as e:
        app.logger.error(f"[/dbpedia] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/dbpedia/comparar')
def dbpedia_comparar():
    a    = request.args.get('a', '').strip()
    b    = request.args.get('b', '').strip()
    lang = request.args.get('lang', 'es').strip()
    if not a or not b:
        return jsonify({"error": "Faltan parámetros 'a' y 'b'"}), 400
    try:
        datos_a = consultar_dbpedia(a, lang)
        datos_b = consultar_dbpedia(b, lang)
        return jsonify({
            "ok": bool(datos_a or datos_b),
            "a": {"nombre": a, "datos": datos_a},
            "b": {"nombre": b, "datos": datos_b},
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/buscar')
def buscar():
    termino = request.args.get('q', '').strip().replace('"', '')
    lang_param = request.args.get('lang', '').strip() # <-- Recibe el idioma del botón

    if not termino:
        return jsonify({"error": "Escribe algo para buscar"})

    tl = termino.lower()
    palabras_router = set(re.sub(r'[^\w\s]', '', tl).split())

    # 1. Definimos el idioma (usamos el del botón; si no hay, lo adivinamos)
    lang = lang_param if lang_param else detectar_idioma(tl)

    PALABRAS_INTENCION = {
        "sirven","sirve","movil","moviles","celular","celulares",
        "smartphone","smartphones","servidor","servidores",
        "escritorio","desktop","open","gratuito","gratis","libre","free",
        "sandboxing","sandbox","cifrado","principiantes","beginner","posix",
        "kernel","nucleo","comparar","vs","versus","cuantos",
        "mobile","server","embedded","embebido","iot","funciona","funcionan",
        "usado","usados","diseñado","diseñados","orientado",
    }
    import unicodedata
    palabras_norm = {unicodedata.normalize("NFKD", p).encode("ascii","ignore").decode() for p in palabras_router}
    tiene_intencion = bool(palabras_norm & PALABRAS_INTENCION)

    if not tiene_intencion and (
        "todos" in palabras_router or "all" in palabras_router or (
            re.search(r'\b(so|sistemas?|systems?|systèmes?)\b', tl)
            and len(palabras_router - STOP_WORDS) <= 3
        )
    ):
        intencion, params = "todos", {"lang": lang}
    else:
        intencion, params = detectar_intencion(termino)
        params["lang"] = lang # <-- ¡MAGIA! Forzamos a la intención a usar el idioma del botón

    try:
        if intencion == "contar":
            rows = run_fuseki(query_contar(params.get("palabras", [])))
            total = int(rows[0]["total"]["value"]) if rows and "total" in rows[0] else 0
            msgs = {
                "es": f"Se encontraron {total} sistemas operativos.",
                "en": f"Found {total} operating systems.",
                "pt": f"Foram encontrados {total} sistemas operacionais.",
                "fr": f"{total} systèmes d'exploitation trouvés.",
            }
            # También obtener la lista de SOs para mostrarlos bajo el conteo
            try:
                q_lista = query_filtro_valor_desde_palabras(params.get("palabras", []))
                if q_lista:
                    bindings_lista = run_fuseki(q_lista)
                    agrupado_lista = agrupar_bindings(bindings_lista) if bindings_lista else {}
                    resultados_lista = [armar_resultado(t, a, "contar") for t, a in agrupado_lista.items()]
                    resultados_lista = [traducir_resultado(r, lang) for r in resultados_lista]
                else:
                    resultados_lista = []
            except Exception:
                resultados_lista = []
            return jsonify({
                "tipo": "conteo", "total": total, "intencion": "contar",
                "mensaje": msgs.get(lang, msgs["es"]),
                "resultados": resultados_lista
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
            resultados = [traducir_resultado(r, lang) for r in resultados]
            return jsonify({
                "tipo":           "definicion",
                "intencion":      "definicion",
                "termino_buscar": termino_def,
                "lang":           lang,
                "resultados":     resultados
            })

        if intencion == "comparar":
            q = query_comparar(params["a"], params["b"])
            bindings = run_fuseki(q)
            agrupado = agrupar_bindings(bindings) if bindings else {}
            resultados = [armar_resultado(t, a, "comparar") for t, a in agrupado.items()]
            resultados = [traducir_resultado(r, lang) for r in resultados]
            return jsonify({
                "tipo":       "comparar",
                "intencion":  "comparar",
                "params":     params,
                "lang":       lang,
                "resultados": resultados,
                "termino_a":  params["a"],
                "termino_b":  params["b"],
            })

        if intencion == "todos":
            q = query_todos()
        elif intencion == "ranking":
            q = query_ranking(params["campo"], params["orden"], params.get("palabras", []))
        elif intencion == "filtro_kernel":
            q = query_filtro_kernel(params.get("kernel", ""))
        elif intencion == "filtro_valor":
            q = query_filtro_valor(params["propiedad"], params["valor"], params.get("palabras", []))
        elif intencion == "filtro_propiedad":
            q = query_filtro_propiedad(params.get("palabras", []), params.get("objeto", termino))
        elif intencion in ("booleano_true", "booleano_false"):
            valor = "true" if intencion == "booleano_true" else "false"
            q = query_booleano(params.get("palabras", []), valor)
        else:
            q = query_nombre(termino, params.get("palabras", []))

        bindings = run_fuseki(q)
        if not bindings and intencion not in ("todos", "filtro_valor", "filtro_kernel", "filtro_propiedad", "booleano_true", "booleano_false", "ranking"):
            bindings = run_fuseki(query_nombre(termino, params.get("palabras", [])))

        agrupado = agrupar_bindings(bindings) if bindings else {}
        resultados = [armar_resultado(t, a, intencion) for t, a in agrupado.items()]
        resultados = [traducir_resultado(r, lang) for r in resultados]

        return jsonify({
            "tipo":           "resultados",
            "intencion":      intencion,
            "params":         params,
            "lang":           lang,
            "termino_buscar": termino,
            "resultados":     resultados
        })

    except Exception as e:
        return jsonify({"error": f"Error del núcleo semántico: {str(e)}"})


if __name__ == '__main__':
    app.run(debug=True)