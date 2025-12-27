# Assets - Base de Datos de Productos

Este directorio contiene los assets (productos) que Luisa puede recomendar a los clientes.

## Estructura

```
assets/
├── images/          # Imágenes de productos
│   └── image_1.jpg  # Imagen de SSGEMSY SG8802E
├── metadata/        # Metadata JSON de cada producto
│   └── P004.json    # Metadata de SSGEMSY SG8802E
└── README.md        # Este archivo
```

## Formato de Metadata

Cada producto tiene un archivo JSON con la siguiente estructura:

```json
{
  "post_id": "P004",
  "title": "Máquina plana mecatrónica SSGEMSY SG8802E",
  "brand": "SSGEMSY",
  "model": "SG8802E",
  "use_cases": ["ropa", "confeccion", "taller"],
  "send_when_customer_says": ["maquina plana", "plana mecatronica"],
  "cta": {
    "educational": "Esta es una recta industrial mecatrónica...",
    "qualifier": "¿La necesitas para taller o para empezar?",
    "closing": "¿En qué ciudad te encuentras?"
  }
}
```

## Campos Importantes

- **post_id**: Identificador único del producto
- **send_when_customer_says**: Palabras clave que activan este producto
- **use_cases**: Casos de uso del producto
- **cta**: Call-to-action con mensajes educativos, qualifiers y closing
- **priority**: Prioridad del producto (1-10)

## Cómo Funciona

Luisa automáticamente:
1. Detecta palabras clave en la conversación
2. Busca el asset más relevante según contexto
3. Usa los CTAs del asset para responder
4. Menciona marca y modelo cuando corresponde

## Agregar Nuevos Assets

1. Guarda la imagen en `images/`
2. Crea un JSON en `metadata/` con el formato indicado
3. Reinicia el backend para cargar el nuevo asset

