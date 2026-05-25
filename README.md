# Proyecto Semestre - Guía de Configuración y Solución de Errores

Este repositorio contiene el backend desarrollado en Python utilizando **Flask**. Si al abrir el proyecto en tu editor de código (como VS Code) te aparecen errores de importación (*"No se ha podido resolver la importación..."*), sigue los pasos descritos a continuación para configurar correctamente tu entorno.

---

## Requisitos e Instalación

El error principal ocurre debido a la falta de las librerías `flask` y `flask_cors` en el entorno de ejecución actual.

### Paso 1: Abrir la Terminal
En VS Code, abre una nueva terminal presionando `Ctrl + Ñ` (o `Ctrl + ~` según tu distribución de teclado), o dirígete al menú superior:
> **Terminal ➔ Nueva terminal**

### Paso 2: Instalar las Dependencias
Ejecuta el siguiente comando en la terminal para instalar los paquetes necesarios:

```bash
pip install flask flask-cors