# Fuentes oficiales de la prueba real

La prueba de integración usa dos decretos del Diario Oficial de la Federación sobre modificación de la Tarifa de la Ley de los Impuestos Generales de Importación y de Exportación. Ambos son documentos oficiales comparables por materia, aunque no representan una versión consolidada de la misma tabla.

| Fecha DOF | Identificador | Fuente oficial | Observación de formato |
|---|---|---|---|
| 15 de agosto de 2023 | `5698661` | https://dof.gob.mx/nota_detalle.php?codigo=5698661&fecha=15/08/2023 | La página advierte que los documentos con tablas que exceden el ancho pueden mostrarse incompletos y ofrece una vista alternativa. |
| 22 de abril de 2024 | `5724207` | https://dof.gob.mx/nota_detalle.php?codigo=5724207&fecha=22/04/2024 | La página contiene el decreto posterior del mismo tipo y la misma advertencia sobre tablas amplias. |

La comparación se limita a contenido descargado desde estas publicaciones oficiales. Sus resultados muestran diferencias textuales y de formato; no determinan vigencia, clasificación o arancel aplicable. [1] [2]

## Referencias

[1]: https://dof.gob.mx/nota_detalle.php?codigo=5698661&fecha=15/08/2023 "DOF — Decreto de 15 de agosto de 2023"
[2]: https://dof.gob.mx/nota_detalle.php?codigo=5724207&fecha=22/04/2024 "DOF — Decreto de 22 de abril de 2024"

La revisión directa de ambas páginas confirmó una advertencia idéntica: el documento puede presentarse incompleto en el margen derecho cuando contiene tablas que rebasan el ancho predeterminado, con acceso a una visualización alternativa. Esta es una fuente real de diferencias de formato que el diff por líneas no corrige por sí solo; el informe debe leerse como evidencia textual y no como reconstrucción fiable de columnas.[1] [2]

## Resultado de la ejecución local

La ejecución local produjo `informe-dof-2023-2024.html` y `evidencia-dof-2023-2024.json`. El manifiesto registró las huellas SHA-256 de ambos textos y no incluyó contenido normativo. Antes de la corrección, `HtmlDiff(wrapcolumn=100)` agotó la recursión al intentar partir una fila documental muy extensa. El comparador ahora conserva la línea original con `wrapcolumn=None`, por lo que la ejecución finalizó sin excepción.

| Métrica | Publicación 2023 | Publicación 2024 | Lectura |
|---|---:|---:|---|
| Líneas extraídas | 18 | 18 | La estructura HTML del DOF agrupa grandes secciones en pocos nodos de texto. |
| Longitud máxima de línea | 211,711 caracteres | 254,574 caracteres | Las tablas y bloques extensos quedan concentrados en líneas anchas. |
| Filas que comienzan con `|` | 5 | 5 | La extracción conserva algunos límites, pero no descompone todas las filas normativas. |
| Marcadores de cambio en el informe | 1 agregado y 1 eliminado | — | El diff identifica un bloque grande, no modificaciones granulares por fracción. |

El resultado confirma que la herramienta **maneja** los cambios de formato sin caer, conserva los hashes y genera evidencia; pero la comparación por líneas no puede reconstruir columnas o distinguir cambios individuales cuando la fuente agrupa una tabla extensa en una única línea. No se implementó un normalizador de tablas en este incremento: sería una mejora separada que debe partir de una muestra mayor y reglas verificables, no de heurísticas generales.

## Patrón adicional verificado en Chrome: decreto de 2025

La página oficial del DOF para el decreto de 29 de diciembre de 2025 conserva la misma advertencia sobre tablas que rebasan el ancho y enlaza a una vista alternativa. Sin embargo, Chrome extrajo su contenido arancelario como una secuencia de elementos con viñetas —código, descripción, unidad y cuota—, en lugar de las filas Markdown observadas en 2023 y 2024. Esto confirma que la estructura visible y extraíble puede variar aun en decretos del mismo tema.[3]

La fuente se verificó directamente en Chrome. El intento posterior de abrir la vista alternativa oficial agotó el tiempo de respuesta de la extensión de Chrome, por lo que no se infiere que la vista alternativa mejore la estructura hasta poder verificarla de forma directa.

[3]: https://dof.gob.mx/nota_detalle.php?codigo=5777376&fecha=29/12/2025 "DOF — Decreto de 29 de diciembre de 2025"

## Patrón histórico verificado en Chrome: decreto de 2020

La publicación oficial de 30 de junio de 2020 sobre la tasa aplicable para mercancías originarias de América del Norte presenta artículos normativos seguidos de tablas de **dos columnas** (`Fracción` y `Descripción`). Chrome las extrajo como una tabla legible, con cada código y descripción en líneas separadas. Este patrón contrasta con los decretos de 2023–2024, que agregan unidad y cuotas, y con la extracción de 2025 en formato de secuencia. Por tanto, la forma de la tabla depende tanto de la época como del instrumento, no solo de su origen DOF.[4]

[4]: https://dof.gob.mx/nota_detalle.php?codigo=5595803&fecha=30/06/2020&print=true "DOF — Decreto de 30 de junio de 2020"

## Decisión de alcance a partir de los patrones

| Patrón verificado en Chrome | Decisión | Motivo |
|---|---|---|
| El mismo aviso de tabla ancha aparece en 2023, 2024 y 2025 | Mantener el diff textual como evidencia, no como reproducción de columnas | La vista ordinaria reconoce que hay una limitación de presentación; inferir columnas desde texto sería una transformación no verificable. |
| Las tablas cambian entre dos columnas (2020), código–descripción–unidad–cuota (2023–2024) y secuencia extraída (2025) | No crear un parser universal de filas arancelarias | Una expresión regular o un esquema fijo perdería información o produciría filas falsas según el documento. |
| Las publicaciones contienen bloques extremadamente largos | Conservar `wrapcolumn=None` y la regresión correspondiente | Evita el fallo de recursión sin alterar evidencia; el costo aceptado es scroll horizontal. |
| La vista alternativa existe, pero no se pudo verificar en Chrome por un agotamiento de tiempo | No automatizar ni asumir que la vista alternativa es canónica | Debe compararse directamente en Chrome antes de integrarla como fuente de extracción. |

La siguiente mejora que sí tiene una relación clara con estos hallazgos es permitir añadir, de forma opcional, la **URL oficial de origen** al manifiesto. Eso no interpreta tablas ni toca el texto, pero conecta la huella del archivo local con la publicación que el usuario verificó. Se debe implementar únicamente cuando la entrada se entregue explícitamente, sin descargar o consultar la URL desde la herramienta.


## Revalidación de 2025

En una revalidación posterior se intentó abrir la publicación de 2025 en Chrome; la extensión volvió a agotar el tiempo. La extracción alternativa de la misma URL oficial confirmó la advertencia de tabla ancha y la presencia de una tabla de código, descripción, unidad y cuota. Esta confirmación no sustituye la verificación visual: mantiene vigente la decisión de no automatizar la vista alternativa hasta poder inspeccionarla en Chrome.
