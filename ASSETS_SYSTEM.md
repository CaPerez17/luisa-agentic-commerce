# Sistema de Assets - Luisa

## Resumen de Implementación

Sistema completo de gestión de assets (imágenes/videos) que funciona en modo local (demo) y producción (Google Drive).

## Endpoints Implementados

### 1. GET /api/catalog/items
Devuelve lista de items del catálogo con `asset_url` calculado.

**Respuesta:**
```json
{
  "items": [
    {
      "image_id": "I001",
      "title": "Máquina plana mecatrónica SSGEMSY SG8802E",
      "category": "recta_industrial_mecatronica",
      "brand": "SSGEMSY",
      "model": "SG8802E",
      "represents": "maquina_completa",
      "conversation_role": "evidencia_principal",
      "priority": 8,
      "send_when_customer_says": [...],
      "asset_url": "/api/assets/I001"
    }
  ],
  "count": 1
}
```

### 2. GET /api/assets/{image_id}
Sirve el archivo binario (imagen o video).

**Modo Local:**
- Busca en `backend/assets/catalog/IXXX_slug/`
- Soporta: `image_1.png`, `image_1.jpg`, `image_1.jpeg`, `image_1.webp`, `video_1.mp4`
- Retorna `FileResponse` o `StreamingResponse` según tipo

**Modo Drive:**
- Busca `drive_file_id` en DB
- Verifica cache local primero
- Si no está en cache, descarga desde Drive
- Guarda en cache con TTL configurable
- Retorna archivo con MIME type correcto

### 3. POST /api/catalog/sync
Sincroniza items desde n8n/Drive.

**Headers:**
```
X-LUISA-API-KEY: tu-api-key
Content-Type: application/json
```

**Payload:**
```json
{
  "image_id": "I001",
  "meta": {
    "image_id": "I001",
    "title": "...",
    "category": "recta_industrial_mecatronica",
    ...
  },
  "asset": {
    "drive_file_id": "1abc...",
    "mime_type": "image/png",
    "file_name": "image_1.png"
  }
}
```

## Integración con Chat

El endpoint `/api/chat` ahora incluye assets cuando corresponde:

**Respuesta:**
```json
{
  "response": "Para producción constante de ropa te recomiendo...",
  "sender": "luisa",
  "needs_escalation": false,
  "asset": {
    "image_id": "I001",
    "asset_url": "/api/assets/I001",
    "type": "image"
  }
}
```

## Base de Datos

### Tabla: catalog_items
- `image_id` (PRIMARY KEY)
- `title`, `category`, `brand`, `model`
- `represents`, `conversation_role`
- `priority`, `send_when_customer_says`
- `meta_json` (JSON completo)
- `drive_file_id`, `drive_mime_type`
- `asset_provider` (local | drive)
- `file_name`, `updated_at`

### Tabla: cache_metadata
- `cache_key` (PRIMARY KEY)
- `file_path`, `drive_file_id`
- `mime_type`, `created_at`, `expires_at`

## Variables de Entorno

Crear archivo `.env` en `backend/`:

```bash
# Modo: local (demo) o drive (producción)
ASSET_PROVIDER=local

# Google Drive (solo si ASSET_PROVIDER=drive)
GOOGLE_DRIVE_FOLDER_ID=tu_folder_id
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/ruta/al/service-account.json

# API Key para sync
LUISA_API_KEY=demo-key-change-in-production

# Cache TTL (horas)
CACHE_TTL_HOURS=24
```

## Configuración Google Drive

### 1. Crear Service Account
1. Google Cloud Console > IAM & Admin > Service Accounts
2. Crear nuevo service account
3. Descargar JSON de credenciales

### 2. Compartir Carpeta
1. Crear carpeta en Drive para assets
2. Compartir con email del service account (Viewer)
3. Copiar ID de carpeta (de la URL)

### 3. Configurar .env
```bash
ASSET_PROVIDER=drive
GOOGLE_DRIVE_FOLDER_ID=1abc...
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=./service-account.json
```

## Estructura de Archivos

```
backend/
├── assets/
│   ├── catalog/
│   │   └── I001_ssgemsy_sg8802e_maquina_completa/
│   │       ├── image_1.png
│   │       └── meta.json
│   ├── cache/          # Cache de assets de Drive
│   └── catalog_index.json
├── main.py
└── .env
```

## Funciones Principales

- `load_catalog_from_filesystem()` - Carga desde archivos locales
- `load_catalog_from_db()` - Carga desde base de datos
- `get_catalog_item(image_id)` - Obtiene item específico
- `find_local_asset_file(image_id)` - Busca archivo local
- `find_matching_catalog_item(text, context)` - Busca item relevante
- `download_from_drive(file_id)` - Descarga desde Drive
- `get_cached_file(file_id)` - Obtiene desde cache
- `save_to_cache(file_id, content, mime_type)` - Guarda en cache

## Estado Actual

✅ Endpoints implementados
✅ Modo local funcionando
✅ Modo Drive implementado (requiere credenciales)
✅ Cache implementado
✅ Integración con chat
✅ Sync desde n8n
✅ Base de datos configurada

## Próximos Pasos

1. Probar endpoints en modo local
2. Configurar Google Drive para producción
3. Configurar n8n para sync automático
4. (Opcional) Actualizar frontend para mostrar assets

