# Estructura de Base de Datos de Catálogo - Luisa

## Organización General

```
backend/assets/
├── catalog/                          # Catálogo de imágenes de productos
│   ├── I001_ssgemsy_sg8802e/        # Carpeta por imagen (image_id_slug)
│   │   ├── image_1.png              # Imagen del producto
│   │   ├── meta.json                # Metadata específica de esta imagen
│   │   └── README.md                # Documentación de la imagen
│   ├── I002_[slug]/                 # Próxima imagen
│   └── ...
├── catalog_index.json               # Índice central del catálogo
├── metadata/                        # Metadata de posts completos (legacy)
│   └── P004.json
└── CATALOG_STRUCTURE.md             # Este archivo
```

## Convención de Nombres

### Image ID
- Formato: `I###` (I001, I002, I003...)
- Incremental, único por imagen
- No reutilizar IDs eliminados

### Slug
- Formato: `marca_modelo` en minúsculas
- Ejemplo: `ssgemsy_sg8802e`
- Sin espacios, sin caracteres especiales
- Usar guiones bajos para separar palabras

### Carpeta
- Formato: `{image_id}_{slug}/`
- Ejemplo: `I001_ssgemsy_sg8802e/`

## Estructura de meta.json

Cada imagen tiene su propio `meta.json` con:

```json
{
  "image_id": "I001",                    // ID único incremental
  "title": "...",                        // Título descriptivo
  "source_platform": "facebook",         // facebook | instagram
  "source_type": "post_image",          // post_image | story | ad
  "source_date": "2024-10-15",          // Fecha del post (opcional)
  "category": "recta_industrial_mecatronica",  // Categoría válida
  "brand": "SSGEMSY",                   // Marca detectada
  "model": "SG8802E",                   // Modelo detectado
  "represents": "...",                   // Qué representa la imagen
  "key_features": [...],                // Características visibles/mencionadas
  "benefits": [...],                    // Beneficios del producto
  "use_cases": [...],                   // Casos de uso (≥3)
  "send_when_customer_says": [...],     // Palabras clave (≥5)
  "handoff_triggers": [...],            // Triggers de escalamiento
  "conversation_role": "...",           // Cuándo usar esta imagen
  "cta": {
    "educational": "...",               // Mensaje educativo
    "qualifier": "...",                 // Pregunta qualifier
    "closing": "..."                    // CTA de cierre
  },
  "language": "es-CO",                  // Idioma
  "priority": 8                         // Prioridad 1-10
}
```

## Categorías Válidas

- `recta_industrial_mecatronica`
- `recta_industrial`
- `fileteadora_industrial`
- `familiar`
- `repuestos_accesorios`
- `servicio_reparacion`
- `educativo`

## Catalog Index

El archivo `catalog_index.json` mantiene un índice centralizado:

```json
{
  "version": "1.0",
  "last_updated": "2024-12-13",
  "total_images": 1,
  "images": [
    {
      "image_id": "I001",
      "slug": "ssgemsy_sg8802e",
      "title": "...",
      "category": "recta_industrial_mecatronica",
      "brand": "SSGEMSY",
      "model": "SG8802E",
      "path": "catalog/I001_ssgemsy_sg8802e/",
      "priority": 8
    }
  ],
  "categories": {
    "recta_industrial_mecatronica": 1,
    "recta_industrial": 0,
    ...
  }
}
```

## Proceso de Agregar Nueva Imagen

1. **Analizar imagen y post**
   - Extraer texto visible del post
   - Identificar marca y modelo
   - Detectar características mencionadas
   - Inferir qué representa la imagen

2. **Crear carpeta**
   - Generar image_id incremental
   - Crear slug basado en marca_modelo
   - Crear carpeta `{image_id}_{slug}/`

3. **Guardar archivos**
   - Guardar imagen como `image_1.png`
   - Crear `meta.json` con toda la información
   - Crear `README.md` opcional

4. **Actualizar índice**
   - Agregar entrada en `catalog_index.json`
   - Actualizar contadores de categorías
   - Actualizar `total_images`

## Uso en Producción

En producción, Luisa puede:
- Acceder al path completo: `backend/assets/catalog/{image_id}_{slug}/image_1.png`
- Cargar metadata: `backend/assets/catalog/{image_id}_{slug}/meta.json`
- Buscar por palabras clave usando `send_when_customer_says`
- Filtrar por categoría usando `catalog_index.json`

## Ventajas de Esta Estructura

1. **Escalable**: Cada imagen es independiente
2. **Organizada**: Fácil de navegar y mantener
3. **Buscable**: Índice centralizado para búsquedas rápidas
4. **Portable**: Puede moverse a Google Drive manteniendo estructura
5. **Versionable**: Cada imagen tiene su propia metadata
6. **Flexible**: Fácil agregar más imágenes sin afectar otras

