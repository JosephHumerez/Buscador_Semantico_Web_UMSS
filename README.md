# 🔍 Buscador de Sistemas Operativos - Web Semántica

Aplicación web interactiva que permite buscar y explorar información sobre sistemas operativos utilizando tecnologías de web semántica. Combina una **ontología personalizada** almacenada en Apache Jena Fuseki con datos de **DBpedia** para proporcionar información completa y contextualizada.

## 📋 Características

- 🔎 Búsqueda semántica de sistemas operativos
- 📊 Base de conocimiento en RDF/OWL con ontología personalizada
- 🌐 Integración con DBpedia para información adicional
- 🎨 Interfaz web responsiva y amigable
- 🚀 Backend desarrollado con Flask
- 💾 Gestión de datos mediante SPARQL queries

---

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

- **Python 3.8 o superior** → [Descargar Python](https://www.python.org/downloads/)
- **Java 11 o superior** (necesario para Fuseki) → [Descargar Java](https://www.oracle.com/java/technologies/downloads/)
- **Git** (para clonar el repositorio)

Verifica que tengas instalados correctamente:
```bash
python --version
java -version
```

---

## 🚀 Instalación y Configuración

### Paso 1: Clonar el Repositorio

```bash
git clone <URL-del-repositorio>
cd Proyecto Semestral
```

### Paso 2: Instalar las Dependencias de Python

Abre una terminal en la carpeta del proyecto (`Ctrl + Ñ` en VS Code) e instala las librerías necesarias:

```bash
pip install flask flask-cors SPARQLWrapper requests
```

### Paso 3: Configurar Apache Jena Fuseki

Fuseki es el servidor que almacena la ontología RDF. Aquí están los pasos para configurarlo:

#### Windows:

1. **Abre una terminal PowerShell** como administrador
2. **Navega a la carpeta de Fuseki**:
   ```bash
   cd "apache-jena-fuseki-6.1.0"
   ```

3. **Ejecuta el servidor Fuseki**:
   ```bash
   .\fuseki-server.bat
   ```

#### macOS/Linux:

1. **Abre una terminal**
2. **Navega a la carpeta de Fuseki**:
   ```bash
   cd apache-jena-fuseki-6.1.0
   ```

3. **Ejecuta el servidor Fuseki**:
   ```bash
   ./fuseki-server
   ```

4. Espera hasta ver en la consola: `Server started on port 3030`

### Paso 4: Verificar que Fuseki está funcionando

Abre tu navegador y ve a: **http://localhost:3030**

Deberías ver la interfaz de administración de Fuseki. Verifica que exista el dataset `ws_buscador_so` en la lista de datasets.

### Paso 5: Cargar la Ontología (si es necesario)

Si el dataset `ws_buscador_so` no contiene datos:

1. Ve a http://localhost:3030/control-panel.html
2. En la sección "Upload RDF Data", carga el archivo `sistemas_operativos_FINAL (2).rdf`
3. Selecciona el dataset `ws_buscador_so` como destino

---

## ▶️ Ejecutar la Aplicación

### En una Terminal NUEVA (mantén Fuseki ejecutándose):

1. **Navega a la carpeta del proyecto**:
   ```bash
   cd "ruta/al/Proyecto Semestral"
   ```

2. **Ejecuta la aplicación Flask**:
   ```bash
   python app.py
   ```

3. **Espera a ver en la consola**:
   ```
   * Running on http://127.0.0.1:5000
   ```

4. **Abre tu navegador** e ingresa a: **http://localhost:5000**

¡La aplicación debería estar funcionando! 🎉

---

## 📁 Estructura del Proyecto

```
Proyecto Semestral/
├── app.py                              # Backend Flask principal
├── README.md                           # Este archivo
├── sistemas_operativos_FINAL (2).rdf   # Ontología RDF/OWL
├── apache-jena-fuseki-6.1.0/           # Servidor SPARQL
│   ├── fuseki-server.bat               # Ejecutor en Windows
│   ├── fuseki-server                   # Ejecutor en Linux/macOS
│   └── run/                            # Configuración y datos
│       ├── config.ttl
│       ├── configuration/
│       │   └── ws_buscador_so.ttl     # Config del dataset
│       └── databases/                 # Base de datos RDF
└── templates/
    └── index.html                      # Interfaz web del frontend
```

---

## 🔧 Solución de Problemas Comunes dentro del sistema

### ❌ Error: "No se ha podido resolver la importación de flask"
**Solución**: Instala las dependencias:
```bash
pip install flask flask-cors SPARQLWrapper requests
```

### ❌ Error: "Unable to connect to Fuseki"
**Solución**: Asegúrate de que:
1. Fuseki esté ejecutándose en otra terminal
2. El URL sea correcto: `http://localhost:3030`
3. El dataset `ws_buscador_so` exista

### ❌ Error: "Port 5000 already in use"
**Solución**: O detén la aplicación anterior o ejecuta en otro puerto:
```bash
python -c "from app import app; app.run(port=5001)"
```

### ❌ Error: "Java not found" en Fuseki
**Solución**: Instala Java desde https://www.oracle.com/java/technologies/downloads/ y reinicia la terminal

---

## 📚 Tecnologías Utilizadas

| Tecnología | Versión | Propósito |
|-----------|---------|----------|
| Python | 3.8+ | Lenguaje base |
| Flask | 2.0+ | Framework web |
| SPARQLWrapper | - | Cliente SPARQL |
| Apache Jena Fuseki | 6.1.0 | Servidor RDF/SPARQL |
| RDF/OWL | - | Formato de ontología |
| HTML/CSS/JS | - | Frontend |

---

## 💡 Cómo Funciona la Aplicación

1. **Usuario ingresa una búsqueda** en la interfaz web
2. **Flask procesa la consulta** y la convierte en una query SPARQL
3. **Fuseki ejecuta la query** contra la ontología local
4. **Se enriquecen los resultados** con información de DBpedia
5. **Los resultados se muestran** en la interfaz web

---

## 📝 Notas Importantes

- ⚠️ Asegúrate de que **Fuseki esté ejecutándose antes** de iniciar Flask
- ⚠️ La aplicación se conecta a Fuseki en: `http://localhost:3030/ws_buscador_so/sparql`
- ⚠️ También se conecta a DBpedia en: `https://dbpedia.org/sparql`
- ⚠️ Requiere conexión a Internet para las consultas a DBpedia

---

## 🤝 Contribuciones

Este es un proyecto educativo del curso de Web Semántica. Las sugerencias y mejoras son bienvenidas.

---

## 📄 Licencia

Proyecto académico - UMSS 2026