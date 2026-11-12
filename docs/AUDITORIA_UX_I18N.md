# Auditoría de UI/UX e internacionalización (Entrega 2)

Este documento registra la revisión de usabilidad de la interfaz Django y el
soporte bilingüe implementado con `gettext`. Cada hallazgo indica el problema
observado en la versión de la Entrega 1, el cambio aplicado y dónde verificarlo.

## 1. Método

- Revisión heurística con las 10 heurísticas de Nielsen sobre los flujos
  *crear plan*, *consultar plan*, *historial* y los nuevos flujos de la Entrega 2
  (reporte asíncrono, aliados, actividad y estado del sistema).
- Verificación de accesibilidad básica (WCAG 2.1 AA): foco visible, navegación por
  teclado, etiquetas, regiones `aria-live`, contraste de los componentes nuevos.
- Pruebas automatizadas: `organization/tests/test_i18n.py`,
  `organization/tests/test_views.py` y `organization/tests/test_microservice_views.py`.

## 2. Hallazgos y correcciones

| # | Heurística | Hallazgo (Entrega 1) | Corrección (Entrega 2) | Evidencia |
| --- | --- | --- | --- | --- |
| 1 | Visibilidad del estado | Al generar un reporte no existía retroalimentación; no había procesos de fondo. | Página de estado con insignia *En proceso / Listo / Falló*, región `aria-live`, refresco automático cada 3 s y enlace de descarga. | `report_status.html` |
| 2 | Visibilidad del estado | Tras crear un plan la página cambiaba sin confirmación. | Mensajes del framework `messages` con `role="status"`. | `base.html`, `views.py` |
| 3 | Visibilidad del estado | No se podía saber si un servicio estaba caído. | Página **Estado** con salud y latencia de cada microservicio, y página 503 específica con botón *Reintentar*. | `system_status.html`, `service_unavailable.html` |
| 4 | Concordancia con el mundo real | Solo había salarios en la moneda original. | Equivalente en USD obtenido de una API de terceros, con aviso cuando las tasas pueden estar desactualizadas. | `_unit_tree.html`, `detail.html` |
| 5 | Control y libertad | El historial no ofrecía regresar desde el detalle. | Migas de pan *Historial / Plan #N* y enlaces de retorno en todas las páginas de error. | `detail.html`, `404.html` |
| 6 | Consistencia | La navegación no indicaba la página actual. | `aria-current="page"` con subrayado de acento en el enlace activo. | `base.html`, `styles.css` |
| 7 | Prevención de errores | El formulario solo validaba en el servidor. | Validación en cliente del mínimo de caracteres antes del envío, atributos `minlength`, `maxlength` y `required`, campo marcado como obligatorio y botón deshabilitado durante el envío para evitar planes duplicados. | `generate.html`, `app.js`, `forms.py` |
| 8 | Reconocer antes que recordar | El formato de reporte no tenía opciones visibles. | Grupo de opciones (`fieldset` + `legend`) con CSV y JSON preseleccionado. | `detail.html`, `forms.py` |
| 9 | Flexibilidad | Sin cambio de idioma. | Selector de idioma en la cabecera (se envía al cambiar; con botón de respaldo sin JavaScript); la preferencia se guarda en cookie. | `base.html`, `app.js` |
| 10 | Diseño minimalista | En móvil los enlaces de navegación se desbordaban. | Menú colapsable con `aria-expanded`; sin JavaScript los enlaces se muestran envueltos. | `base.html`, `styles.css` |
| 11 | Ayuda ante errores | Las páginas 404/500 eran las genéricas de Django. | Plantillas propias traducidas con acciones de recuperación. | `templates/404.html`, `templates/500.html` |
| 12 | Ayuda ante errores | Un servicio caído producía un error de servidor. | Degradación controlada: si falla la conversión el plan se muestra igual; si falla el aliado o las notificaciones se explica el motivo. | `test_microservice_views.py::DegradedModeTests` |
| 13 | Accesibilidad | Algunos textos sin tildes y sin foco visible en controles nuevos. | Textos nuevos con ortografía completa y `:focus-visible` con contorno de 3 px. | `styles.css` |

## 3. Internacionalización

- **Mecanismo:** `gettext` de Django (`{% trans %}`, `{% blocktrans %}` con
  plurales, `gettext` y `gettext_lazy` en Python) y Flask-Babel en los
  microservicios. No quedan textos de interfaz escritos directamente en las
  plantillas ni en los mensajes de error.
- **Idiomas:** español (predeterminado, cadenas fuente) e inglés
  (`locale/en/LC_MESSAGES/django.po` y
  `services/*/*/translations/en/LC_MESSAGES/messages.po`).
- **Selección del idioma:** `LocaleMiddleware` usa la cookie del selector o la
  cabecera `Accept-Language`. Django propaga el idioma activo a los
  microservicios en cada llamada. Los errores JSON, los reportes CSV y los
  correos llegan así en el idioma del usuario.
- **Contenido generado:** los nombres de áreas y vacantes son datos producidos por
  el proveedor de IA y se muestran tal como se generaron. La interfaz que los rodea
  sí está traducida.
- **Herramienta sin GNU gettext:** `python scripts/i18n.py extract-django`
  actualiza el catálogo de Django, `compile` genera los `.mo` y `check` falla si
  queda una cadena sin traducir. El último paso se ejecuta en GitHub Actions.

## 4. Pendientes conocidos

- Las cadenas del Service Layer heredado (ruta de reversión del estrangulador)
  conservan la ortografía sin tildes de la Entrega 1 para no romper el contrato
  de mensajes ya probado.
- No se realizó una prueba con usuarios reales; la auditoría es heurística.
