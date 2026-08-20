# Diseño de la primera versión

## Suposiciones explícitas

Esta versión no descarga documentos ni extrae PDF. Recibe dos textos UTF-8 que el usuario ya obtuvo legalmente y escribe un único informe HTML local. Se prefiere este alcance porque valida la trazabilidad del diff sin introducir red, OCR, dependencias Python o reglas arancelarias.

## Contrato

| Parte | Decisión |
|---|---|
| Entrada | Dos rutas de archivo existentes, distintos entre sí y decodificables como UTF-8. |
| Identidad | Cada entrada se registra con nombre, SHA-256 y número de líneas. |
| Comparación | `difflib.HtmlDiff`, biblioteca estándar de Python, genera un diff por líneas. |
| Salida | Un HTML con metadatos escapados y una tabla de diferencias. |
| Fallos | Las rutas ausentes, directorios, entradas no UTF-8, entradas idénticas y salida igual a una entrada terminan con un mensaje de error y código distinto de cero. |

## Fuera de alcance

La versión no infiere fracciones, tasas, vigencias ni consecuencias. Tampoco invoca una IA, no conserva datos fuera del HTML que el usuario indica y no consulta internet. La comparación conserva el contenido de entrada por ser la evidencia mostrada; el usuario es responsable de no entregar datos sensibles.

## Éxito verificable

Una ejecución con dos archivos de muestra debe producir un HTML que contenga ambos hashes, los nombres de entrada y una sección de cambios. Una prueba estándar debe demostrar esa salida y otra debe rechazar entradas idénticas. Si estas condiciones se cumplen, la siguiente mejora candidata es una suborden `extract` que use `pdftotext` ya disponible, sin cambiar el comparador.

> ponytail: el diff por líneas no entiende tablas que cambian de columna. La mejora se justifica solo si dos documentos reales muestran ese límite; entonces se añadirá un normalizador acotado y probado para tablas seleccionadas.

## Extensión PDF confirmada

La extensión conserva el mismo comando de comparación: cada entrada puede ser un `.txt` UTF-8 o un `.pdf`. Para un PDF, el programa usa exclusivamente `pdftotext -layout -enc UTF-8`, una utilidad local ya disponible; no sube el archivo ni instala una biblioteca. El informe registra la huella SHA-256 de los bytes del archivo original y el tipo de entrada, mientras que el diff compara el texto extraído.

| Caso | Resultado esperado |
|---|---|
| PDF con capa textual | Se extrae texto local y se genera el mismo informe HTML. |
| PDF sin texto extraíble | Error explícito; no se fabrica contenido con OCR. |
| Falta `pdftotext` o la extracción falla | Error explícito con código distinto de cero. |
| Entradas con el mismo texto extraído | Se rechazan como antes, aunque los archivos sean distintos. |

> ponytail: no se integra OCR en esta fase. El límite es que un PDF escaneado se rechaza; se añadirá OCR solo si un corpus real demuestra que esa limitación impide revisar documentos y se puede probar sin enviar archivos a un tercero.

## Incremento de reproducibilidad

La siguiente mejora es un manifiesto JSON opcional mediante `--manifest evidencia.json`. No cambia el informe HTML ni guarda texto extraído. Registra el instante UTC, rutas de salida, y por cada entrada el nombre, tipo, SHA-256 del archivo original y número de líneas extraídas. Con eso una revisión puede comprobar que el informe corresponde a los mismos binarios sin exponer su contenido fuera del equipo.

| Decisión | Justificación |
|---|---|
| Manifiesto JSON opcional | La biblioteca estándar cubre serialización y mantiene el CLI actual. |
| Sin contenido de entrada | Reduce duplicación y el riesgo de persistir información no necesaria. |
| Sin dependencia `pdf-diff` | [JoshData/pdf-diff](https://github.com/JoshData/pdf-diff) es un proyecto activo y relevante, pero persigue diferencias visuales de PDF. El objetivo actual es trazabilidad textual con la extracción local existente, por lo que añadirlo no justifica otra dependencia. |

La verificación mínima debe comprobar que el manifiesto es JSON válido, que contiene las huellas de ambos archivos y que no incluye frases del contenido de entrada.

## URLs de origen opcionales

`--source-url` se repite dos veces, en el orden de las entradas: primero para `before` y después para `after`. El programa no descarga, no resuelve y no afirma que una URL coincida con un archivo; solo preserva el vínculo que el usuario verificó previamente. Para reducir entradas ambiguas, se aceptan únicamente URL `https` sin usuario ni contraseña cuyo host sea `gob.mx` o termine en `.gob.mx`.

| Caso | Resultado |
|---|---|
| Dos URL DOF HTTPS válidas | Cada una se guarda como `source_url` junto al metadato de su entrada. |
| Sin opción | El manifiesto conserva el contrato actual, sin `source_url`. |
| Una sola URL o más de dos | Error local y no se escribe informe ni manifiesto. |
| `http`, host no gubernamental, usuario/contraseña o URL incompleta | Error local y no se escribe informe ni manifiesto. |

La prueba debe comprobar que las URLs DOF se conservan exactamente, que el orden se respeta, que una URL no válida o una cantidad incorrecta se rechaza y que la herramienta no invoca ninguna red.

## Controles de fiabilidad mínimos

El CLI no sobrescribe resultados existentes. Si `--output` o `--manifest` apunta a un archivo ya existente, aborta antes de escribir cualquier salida. Este comportamiento favorece evidencia reproducible: el usuario elige una ruta nueva o elimina/archiva conscientemente la evidencia anterior.

La comprobación automatizada debe confirmar que ambos rechazos dejan intactos el archivo previo y no crean el otro artefacto. GitHub Actions ejecutará la misma comprobación con Python 3.12 y `poppler-utils`; no instala paquetes Python ni crea un segundo runner.

## Modo OCR local explícito

El flag `--ocr` habilita un único fallback para un PDF cuya extracción nativa no devuelve texto. El programa invoca localmente `ocrmypdf -l spa --rotate-pages --deskew --output-type pdf` sobre una copia temporal, nunca modifica la entrada original y vuelve a extraer el texto del PDF derivado mediante `pdftotext`. Si la entrada ya contiene texto nativo, `--ocr` no la reprocesa.

| Caso | Resultado esperado |
|---|---|
| PDF escaneado sin `--ocr` | Error explícito; no se generan artefactos. |
| PDF escaneado con `--ocr` | Se genera el informe y el manifiesto identifica la entrada como `PDF_OCR`. |
| OCR no disponible o falla | Error explícito; no se generan artefactos. |
| PDF con texto nativo y `--ocr` | Se conserva `PDF`; no se invoca OCR. |

El manifiesto conserva la huella del PDF original y no persiste la copia temporal. El tipo `PDF_OCR` indica que la comparación usa texto reconocido, que puede contener errores de lectura y no debe interpretarse como transcripción normativa exacta.

## Marcadores de página para PDF

El extractor de Poppler separa páginas mediante caracteres de avance de página. DOF Diff Lab los convierte en líneas visibles `--- Página N ---` antes de generar el diff. Esto permite ubicar un cambio de PDF por página dentro del informe sin inferir columnas, coordenadas ni celdas de una tabla.

| Caso | Resultado esperado |
|---|---|
| PDF de una página con cambios | El diff contiene `--- Página 1 ---`. |
| PDF de varias páginas | El diff contiene el marcador de la página afectada y su contexto; omite páginas sin cambios. |
| PDF OCR | Los marcadores se aplican al PDF temporal OCR y se conserva `PDF_OCR` como tipo de origen. |
| TXT | No se inventan páginas. |

La comprobación debe combinar dos PDFs mínimos de dos páginas y confirmar que los marcadores aparecen en el informe junto con el cambio de la segunda página.
