# Evaluación real del consultor técnico

Esta comprobación opcional ejecuta consultas conocidas contra el catálogo, el
índice FTS5 y el índice semántico locales. No modifica documentos, índices,
modelos ni la base de datos.

## Ejecución completa

~~~powershell
python .\scripts\evaluate_technical_consultant_corpus.py
~~~

La línea base está en:

~~~text
evaluation/technical_consultant_real_corpus.json
~~~

Cada caso fija los requisitos, el modo de recuperación, el orden de los
productos relevantes, su clasificación y los nombres de las fichas fuente.
Una lista vacía de resultados también es una expectativa válida: protege los
casos en los que el catálogo no contiene evidencia suficiente y el consultor
debe abstenerse de recomendar.

## Ejecución parcial

~~~powershell
python .\scripts\evaluate_technical_consultant_corpus.py --case high-hydration
~~~

La opción --case se puede repetir. Esto permite comprobar un escenario sin
esperar a que terminen todos los embeddings de consulta.

## Informe JSON

~~~powershell
python .\scripts\evaluate_technical_consultant_corpus.py --json
python .\scripts\evaluate_technical_consultant_corpus.py --output .\.tmp\technical-acceptance.json
~~~

Sin --output, la herramienta no escribe archivos. Los códigos de salida son:

- 0: todos los casos coinciden;
- 1: se detectaron desviaciones;
- 2: la línea base o la selección de casos no es válida.

Una desviación no actualiza automáticamente la línea base. Primero se debe
comprobar si cambió el catálogo, el modelo de embeddings o la calidad real de
la recuperación. Solo después de revisar las fichas se puede modificar el JSON
en un corte independiente.
