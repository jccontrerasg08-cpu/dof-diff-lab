# Auditoría de preparación para publicación pública

**Fecha de corte:** 19 de agosto de 2026. La revisión se realizó sobre una instantánea verificable de la rama predeterminada y su historial, con ocho frentes independientes: código y seguridad, datos y privacidad, automatizaciones, documentación, arquitectura, etiquetas e insights, calidad micro e historia Git.

> **Veredicto:** el árbol de trabajo queda preparado para una superficie pública minimizada y explicable. Sin embargo, el repositorio existente **no debe hacerse público todavía** porque su historia conserva al menos dos compromisos de privacidad: una dirección de correo personal en commits históricos y HTML crudo del sitio fuente en un commit previo. Hacer público el mismo repositorio expondría ambos elementos aunque el árbol actual esté saneado.

## Hallazgos materiales y tratamiento

| Prioridad | Hallazgo verificado | Tratamiento aplicado | Estado |
|---|---|---|---|
| Bloqueante | HTML crudo del DOF, con scripts, formularios e identificadores de terceros, estaba versionado en `data/raw/`. | Se eliminó del árbol actual. El monitor retiene sólo URL, hash, tamaño y MIME; ni artifacts ni Pages reciben HTML crudo. | Corregido en árbol; persiste en historia. |
| Bloqueante | La historia Git contiene un correo personal en commits anteriores. | No se reescribió la historia sin autorización expresa. | Pendiente de decisión del propietario. |
| Alta | La fecha manual del workflow se interpolaba dentro de Bash con permisos de escritura. | La fecha se entrega por entorno, se valida como ISO y como fecha real antes de invocar el monitor. | Corregido. |
| Alta | Captura, commit y despliegue compartían un job con permisos combinados. | El flujo ahora separa `capture` (sólo lectura), `publish` (sólo contenidos) y `deploy` (Pages/OIDC). | Corregido. |
| Alta | Acciones de GitHub referenciadas por tags mutables. | Todas las acciones del workflow DOF y CI se fijan a SHAs completos revisables. | Corregido. |
| Media | El sitio agregaba conteos sin evidencia visible de cada coincidencia. | La página pública muestra nota, enlace oficial, regla, versión y fragmento activador, junto con el límite de interpretación. | Corregido. |
| Media | Faltaban licencia, aviso visible de no afiliación y canal de seguridad. | Se añadieron `LICENSE`, `SECURITY.md`, portada de alcance y aviso persistente en el sitio. | Corregido en árbol. |
| Media | `.gitignore` era demasiado limitado y CI no detectaba credenciales rastreadas. | Se ampliaron exclusiones y CI ejecuta una comprobación de patrones de credenciales antes de pruebas. | Corregido. |
| Alta | La prueba OCR incluía un PDF binario cuya autorización y contenido no podían demostrarse con la auditoría estática. | Se eliminó el fixture y la prueba genera un PDF raster sintético durante su ejecución. | Corregido. |

## Política de publicación aplicada

La superficie pública publicada se limita a metadatos derivados del índice oficial, hashes, estado de ejecución, diffs y enlaces canónicos. No se presentan etiquetas como dictámenes: una coincidencia de regla no es probabilidad, vigencia ni conclusión jurídica. El sitio usa `noindex,nofollow` y publica `robots.txt` para desalentar la indexación de sus derivados; esta medida no reemplaza los controles de un proveedor de búsqueda.

| Superficie | Publicable | No publicable |
|---|---|---|
| Catálogo | Código, URL oficial, título, sección, emisor, etiquetas y hash por nota. | Texto íntegro de notas, PDFs, Word o imágenes. |
| Procedencia | URL, HTTP, MIME, tamaño y SHA-256. | HTML, scripts, formularios, cookies lógicas y trackers del sitio fuente. |
| Sitio | Conteos, evidencia de regla, límite de interpretación y enlace oficial. | Conclusiones legales, recomendaciones o contenido fuente embebido. |
| Git | Código, documentación y derivados saneados. | Historia previa con correo personal y raw HTML, salvo saneamiento autorizado. |

## Decisión pendiente antes de hacer público

La corrección de código no sanea objetos históricos. Existen dos rutas seguras y gratuitas:

| Ruta | Resultado | Consecuencia |
|---|---|---|
| **Nuevo repositorio público saneado** | Se crea un repositorio público con un único historial limpio a partir del árbol preparado. El repositorio actual puede conservarse privado como archivo operativo. | Evita exponer correo y raw histórico; cambia la URL pública. |
| **Reescritura del repositorio actual** | Se reescribe toda la historia, se eliminan objetos/ramas expuestos y se fuerza una nueva historia pública. | Conserva la URL, pero es disruptivo, requiere coordinación y no puede garantizar el borrado de clones o referencias ya replicadas. |

No se ejecutará ninguna de las rutas ni se cambiará la visibilidad sin confirmación explícita. Una vez elegida la ruta, se habilitará GitHub Pages en modo gratuito y se ejecutará el workflow desde la rama pública. [1]

## Verificación local aplicada

La preparación se valida con los siguientes contratos. La prueba OCR genera su propio PDF sintético y no requiere documentos de fuente dentro del repositorio:

```text
python3 tests/check_monitor.py
python3 tests/check_monitor_workflow.py
python3 tests/check_public_readiness.py
python3 tests/check_cli.py
```

[1]: https://docs.github.com/pages/getting-started-with-github-pages/creating-a-github-pages-site "GitHub Pages — configuración de un sitio"
