# Biblioteca documental local

## 1. Descripción

GestionIREKS utiliza una biblioteca documental externa y de solo lectura. Los
documentos originales no se copian a la base de datos ni se modifican. Los
catálogos e índices son datos derivados que pueden reconstruirse.

```text
IREKS-Servidor
    ↓
Catálogo SQLite local
    ↓
Índice de contenido FTS5
    ↓
Índice semántico Ollama
    ↓
Búsqueda híbrida
    ↓
Asistente documental con fuentes
```

La extracción, la indexación y las consultas a la IA se ejecutan localmente.

## 2. Ubicación

La variable `GESTION_IREKS_DOCUMENTS_DIR` tiene prioridad. Si no se define, la
aplicación busca `IREKS-Servidor` como carpeta hermana del repositorio.

Ejemplo genérico para una sesión de PowerShell:

```powershell
$env:GESTION_IREKS_DOCUMENTS_DIR = "C:\ruta\IREKS-Servidor"
python run.py
```

No es necesario mover ni copiar la biblioteca dentro de GestionIREKS.

## 3. Datos generados

El índice local se guarda en:

```text
data/document_library.sqlite
```

Contiene metadatos del catálogo, texto extraído, el índice FTS5, fragmentos,
embeddings y estados de indexación. No contiene los PDF ni los demás documentos
originales. Está ignorado por Git, no debe commitearse y puede eliminarse para
reconstruir todos los índices desde la biblioteca externa.

## 4. Formatos

El catálogo reconoce PDF, XLS, XLSX, DOCX y Markdown (`.md` y `.markdown`). La
extracción de contenido admite PDF con texto y Markdown. La vista previa interna
admite PDF; el resto de formatos se abre con la aplicación predeterminada del
sistema.

Un PDF sin texto extraíble queda registrado como `sin texto`. Puede ser candidato
para OCR en el futuro, pero el MVP no ejecuta OCR.

## 5. Primer uso

El orden desde la aplicación PySide6 es:

1. Abrir **Documentos**.
2. Pulsar **Actualizar catálogo**.
3. Abrir **Buscar en contenido**.
4. Actualizar el índice de contenido.
5. Abrir la configuración y activar la IA local.
6. Configurar el modelo de embeddings.
7. Probar el modelo conversacional.
8. Probar los embeddings.
9. Actualizar el índice semántico.
10. Usar la búsqueda documental.
11. Usar **Preguntar a la IA**.

El catálogo de archivos, la extracción de contenido y los embeddings son procesos
distintos. Completar uno no inicia automáticamente el siguiente.

## 6. Configuración de Ollama

En la configuración de IA local deben indicarse:

- activación de la IA local;
- una URL HTTP loopback, por ejemplo `http://127.0.0.1:11434`;
- el modelo conversacional;
- el modelo de embeddings.

El modelo de embeddings predeterminado es `embeddinggemma` y puede sobrescribirse
con `GESTION_IREKS_EMBEDDING_MODEL`. Los modelos conversacional y de embeddings son
independientes y deben estar instalados previamente en Ollama. La aplicación no
descarga modelos. Solo se aceptan `127.0.0.1`, `localhost` o `::1`; Ollama local no
requiere claves.

## 7. Búsqueda

La pantalla Documentos permite buscar por nombre o ruta relativa. **Buscar en
contenido** ofrece búsqueda textual FTS5 sobre páginas extraídas, búsqueda
semántica mediante embeddings y recuperación híbrida cuando ambos índices están
disponibles.

Si el índice semántico no está disponible o no es compatible con el modelo
configurado, la recuperación utiliza fallback léxico y lo indica como modo de
búsqueda. Los filtros de área y categoría se aplican a las consultas. Cada
resultado identifica el documento y la página recuperada.

## 8. Asistente documental

El asistente construye la respuesta a partir de páginas recuperadas y limita las
citas a fuentes reales entregadas al modelo. Rechaza respuestas sin citas válidas
y puede responder que no existe información suficiente. Los documentos se tratan
como datos no confiables, nunca como instrucciones que deban ejecutarse.

No hay memoria entre preguntas ni streaming. La recuperación semántica puede
mejorar consultas conceptuales, pero no garantiza por sí sola que todas las
respuestas sean correctas; deben revisarse las fuentes mostradas.

## 9. Seguridad

- La biblioteca de origen se usa en modo solo lectura.
- La base guarda rutas relativas y la resolución se hace mediante identificadores.
- Se impide resolver documentos fuera de la raíz configurada.
- La UI y los resultados controlados no muestran rutas absolutas.
- Los documentos originales y los índices locales permanecen fuera de Git.
- La extracción, los embeddings y el asistente documental se ejecutan localmente.
- No se descargan modelos automáticamente.
- Las respuestas documentales no modifican la base funcional de GestionIREKS.

## 10. Actualización y mantenimiento

Ejecutar **Actualizar catálogo** cuando se añadan, cambien o retiren archivos.
Actualizar después el índice de contenido y, por último, el semántico. También es
necesario actualizar el índice semántico cuando cambie el modelo de embeddings.

La cancelación es cooperativa: no fuerza la terminación del hilo, conserva los
documentos ya completados y permite continuar posteriormente. Los índices son
incrementales, por lo que una segunda ejecución omite documentos sin cambios.

## 11. Solución de problemas

| Situación | Comprobación o acción |
| --- | --- |
| Biblioteca no disponible | Revisar `GESTION_IREKS_DOCUMENTS_DIR` y que la carpeta exista. |
| Catálogo vacío | Confirmar que hay formatos admitidos y actualizar el catálogo. |
| PDF corrupto o protegido | Sustituir o reparar el original fuera de GestionIREKS; no borrar otros datos. |
| PDF sin texto | Se marca como `sin texto`; el MVP no incorpora OCR. |
| SQLite sin FTS5 | Usar una distribución de Python/SQLite con FTS5 habilitado. |
| IA local desactivada | Activarla en Configuración y volver a probar. |
| Ollama no disponible | Iniciar Ollama y comprobar la URL loopback configurada. |
| Modelo conversacional ausente | Instalar previamente el modelo configurado en Ollama. |
| Modelo de embeddings ausente | Instalar previamente el modelo; la aplicación no lo descarga. |
| Índice creado con otro modelo | Actualizar el índice semántico con el modelo actual. |
| Solo aparece búsqueda léxica | Es un fallback válido; revisar el estado del índice semántico. |
| Indexación lenta | Mantener la ventana abierta o cancelar cooperativamente y reanudar después. |
| Documento desaparecido | Actualizar el catálogo; el registro quedará inactivo sin borrar el original. |

No se recomienda borrar, mover o renombrar documentos originales para resolver un
problema de índices.

## 12. Limitaciones del MVP

- Sin OCR.
- Sin extracción de contenido XLS, XLSX o DOCX.
- Sin historial conversacional ni streaming.
- Sin actualización o reindexación automática.
- Sin endpoints documentales FastAPI nuevos.
- Sin asociación automática con productos o fórmulas.
- Índice vectorial local en SQLite, sin servidor vectorial externo.

## Validación operativa del MVP

El checkpoint del 29 de agosto de 2026 catalogó 2.587 documentos admitidos, de los
que 2.570 eran PDF, sin modificar la biblioteca. El piloto textual procesó 25
documentos: 24 indexados, 1 sin texto y 0 fallidos; almacenó 83 páginas con texto.
La búsqueda FTS5, el fallback léxico y el smoke PySide6 fueron correctos.

La validación semántica quedó pendiente porque el modelo `embeddinggemma` no
estaba instalado en Ollama. Es un requisito operativo, no un fallo funcional del
catálogo o de la búsqueda textual. La suite Python completa terminó con 784 tests
correctos y 151 warnings conocidos no bloqueantes.
