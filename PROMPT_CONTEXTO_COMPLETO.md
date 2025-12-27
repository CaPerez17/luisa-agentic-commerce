# 🎯 PROMPT DE CONTEXTO COMPLETO - PROYECTO LUISA

---

## 📋 RESUMEN EJECUTIVO

**Proyecto:** Sistema de Asistente Comercial "LUISA" para Almacén y Taller El Sastre  
**Cliente:** Almacén y Taller El Sastre - Montería, Colombia  
**Propósito:** Asistente conversacional de ventas que simula Facebook Messenger/WhatsApp  
**Fecha:** Diciembre 2024  
**Workspace:** `/Users/camilope/AI-Agents/Sastre`

---

## 🏢 CONTEXTO DEL NEGOCIO

### ¿Qué es El Sastre?
Almacén y Taller El Sastre es un negocio en **Montería, Colombia** que ofrece:
- **Máquinas de coser familiares e industriales** (varias marcas)
- **Fileteadoras** (familiares e industriales)
- **Taller de reparación** de máquinas
- **Accesorios y repuestos**
- **Servicio técnico con garantía**
- **Envío + instalación** a todo el país
- **Asesoría a emprendedores** (cómo empezar, qué máquina comprar según proyecto)

### Diferencial Competitivo
- **Acompañamiento completo**: No solo venden máquinas, sino soluciones
- **Instalación en sitio**: Van a municipios/pueblos/veredas
- **Capacitación**: Enseñan a usar las máquinas
- **Soporte técnico local**: Reparación garantizada
- **Financiación**: Trabajan con Addi/Sistecrédito

### Ubicación
- Calle 34 #1-30, Montería, Córdoba, Colombia
- Envíos a todo el país

---

## 🤖 ARQUITECTURA DEL SISTEMA

### Stack Tecnológico
```
Backend:  FastAPI (Python 3.12) + SQLite
Frontend: HTML/CSS/JS puro (sin framework)
Estilo:   Tipo Facebook Messenger/WhatsApp
Puerto:   Backend: 8000, Frontend: 8080
```

### Estructura de Archivos
```
Sastre/
├── backend/
│   ├── main.py                    # API FastAPI principal (~2014 líneas)
│   ├── intent_analyzer.py         # Subagente de análisis de intención
│   ├── requirements.txt           # Dependencias Python
│   ├── luisa.db                   # Base de datos SQLite
│   └── assets/
│       ├── catalog/               # Catálogo de máquinas
│       │   ├── I001_ssgemsy.../   # Carpeta por máquina
│       │   │   ├── image_1.png    # Imagen de la máquina
│       │   │   └── meta.json      # Metadata de la máquina
│       │   ├── I002_union.../
│       │   ├── I003_kansew.../
│       │   ├── I004_singer.../
│       │   ├── I005_kingter.../
│       │   ├── I006_singer.../
│       │   └── promociones/
│       │       └── promocion_navidad_2024.png
│       └── catalog_index.json     # Índice del catálogo
├── frontend/
│   ├── index.html                 # Interfaz de chat
│   ├── styles.css                 # Estilos tipo Messenger
│   └── app.js                     # Lógica del frontend
├── outbox/                        # JSONs de handoffs generados
└── README.md                      # Documentación
```

### Base de Datos (SQLite)
- **conversations**: Conversaciones activas/escaladas
- **messages**: Historial de mensajes
- **handoffs**: Escalamientos a humanos
- **catalog_items**: Items del catálogo (para modo Drive)
- **cache_metadata**: Caché de assets de Drive

---

## 📦 CATÁLOGO ACTUAL (6 máquinas)

| ID   | Marca    | Modelo     | Categoría                    | Prioridad |
|------|----------|------------|------------------------------|-----------|
| I001 | SSGEMSY  | SG8802E    | recta_industrial_mecatronica | 8         |
| I002 | UNION    | UN300      | familiar                     | 6         |
| I003 | KANSEW   | KS653      | familiar                     | 6         |
| I004 | SINGER   | S0105      | fileteadora_familiar         | 7         |
| I005 | KINGTER  | -          | fileteadora_familiar         | 7         |
| I006 | SINGER   | Heavy Duty | familiar                     | 8         |

### Categorías Válidas
- `recta_industrial_mecatronica`
- `recta_industrial`
- `fileteadora_industrial`
- `familiar`
- `fileteadora_familiar`
- `repuestos_accesorios`
- `servicio_reparacion`
- `educativo`

### Estructura de meta.json
```json
{
  "image_id": "I001",
  "title": "Máquina plana mecatrónica SSGEMSY SG8802E",
  "category": "recta_industrial_mecatronica",
  "brand": "SSGEMSY",
  "model": "SG8802E",
  "represents": "maquina_completa",
  "key_features": [...],
  "benefits": [...],
  "use_cases": [...],
  "send_when_customer_says": [...],
  "handoff_triggers": ["precio", "disponibilidad", ...],
  "conversation_role": "evidencia_principal",
  "cta": {
    "educational": "...",
    "qualifier": "...",
    "closing": "..."
  },
  "priority": 8
}
```

---

## 🧠 LÓGICA CONVERSACIONAL (main.py)

### Flujo Principal
1. **`/api/chat`** recibe mensaje del cliente
2. **`analyze_message()`** analiza intención y detecta escalamiento
3. **`intent_analyzer.analyze()`** determina intención primaria
4. **`generate_response()`** genera respuesta directiva
5. **`select_catalog_asset()`** selecciona imagen si corresponde
6. Si `needs_escalation` → **`notify_whatsapp()`** genera handoff

### Tipos de Intención (IntentType)
- SALUDO, DESPEDIDA
- SOLICITAR_FOTOS
- PREGUNTAR_PRECIO, PREGUNTAR_DISPONIBILIDAD
- BUSCAR_MAQUINA_FAMILIAR, BUSCAR_MAQUINA_INDUSTRIAL
- BUSCAR_FILETEADORA, BUSCAR_REPUESTOS
- SOLICITAR_SERVICIO, SOLICITAR_INSTALACION, SOLICITAR_ENVIO
- PREGUNTAR_FORMA_PAGO, CONFIRMAR_COMPRA
- BUSCAR_RECOMENDACION, PREGUNTAR_CARACTERISTICAS
- PREGUNTAR_PROMOCIONES

### Reglas de Handoff Obligatorio
Escalar inmediatamente cuando detecte:
1. **Impacto de negocio**: "montar negocio", "emprendimiento", "taller", "producción"
2. **Servicio diferencial**: "instalación", "visita", "asesoría", "capacitación"
3. **Geográfico**: Ciudad diferente a Montería, municipio/pueblo/vereda
4. **Decisión de compra**: "precio", "formas de pago", "Addi", "disponibilidad"
5. **Ambigüedad crítica**: Múltiples necesidades técnicas + producción constante

### Mensajes de Handoff
Dependiendo del contexto, ofrecer:
- "¿Prefieres que te llamemos para agendar una cita?"
- "¿Agendamos una visita del equipo a tu taller?" (solo si está en Montería)
- "¿Prefieres pasar por el almacén?" (solo si está en Montería)

### Contexto Conversacional
`extract_context_from_history()` extrae:
- `tipo_maquina`: familiar | industrial
- `uso`: ropa | gorras | calzado | accesorios
- `volumen`: bajo | alto
- `ciudad`: montería | bogotá | etc.
- `marca_interes`: SSGEMSY | UNION | etc.
- `modelo_interes`: SG8802E | UN300 | etc.
- `ultimo_tema`: promocion | especificaciones | fotos
- `esperando_confirmacion`: bool

---

## 🖼️ SISTEMA DE ASSETS

### Modo Local (Demo)
- Assets en `backend/assets/catalog/IXXX_slug/image_1.png`
- `catalog_index.json` como fuente de verdad
- Funciona sin credenciales

### Modo Drive (Producción - NO implementado aún)
- Variables de entorno: `ASSET_PROVIDER=drive`
- Service account de Google
- Cache local en `backend/assets/cache/`

### Endpoints de Assets
- `GET /api/catalog/items` → Lista items con asset_url
- `GET /api/assets/{image_id}` → Sirve imagen/video
- `GET /api/assets/promo_navidad` → Imagen de promoción navideña
- `POST /api/catalog/sync` → Sync desde n8n

---

## 🐛 PROBLEMAS CONOCIDOS Y ESTADO ACTUAL

### ✅ Resueltos
1. Database locking → Conexiones SQLite ahora se cierran correctamente
2. Imágenes no se muestran → Rutas corregidas, validación de headers PNG/JPG
3. Promoción de navidad → Endpoint y lógica implementados
4. Especificaciones de máquina → Detecta y responde correctamente

### ⚠️ Problemas Pendientes
1. **Manejo de contexto conversacional débil**: Cuando el usuario responde "si" a "Te muestro las ofertas disponibles:", la imagen de promoción no siempre se muestra
2. **Respuestas genéricas**: A veces Luisa pregunta "¿Buscas máquina familiar o industrial?" cuando debería continuar el tema anterior
3. **Detección de especificaciones incompleta**: Si el usuario pregunta "que especificaciones tiene?" sin mencionar la máquina, a veces no encuentra la máquina correcta del contexto

### 🎯 Objetivos Pendientes
1. Mejorar el manejo de contexto para que Luisa mantenga la narrativa de la conversación
2. Las imágenes deben mostrarse SIEMPRE cuando correspondan (promociones, fotos solicitadas)
3. Respuestas más inteligentes basadas en el historial completo
4. Flujos conversacionales que lleven al cierre de venta en máximo 6-8 turnos

---

## 🔧 CÓMO EJECUTAR

```bash
# Terminal 1 - Backend
cd Sastre/backend
source venv/bin/activate
python main.py
# Corre en http://localhost:8000

# Terminal 2 - Frontend
cd Sastre/frontend
python3 -m http.server 8080
# Abrir http://localhost:8080
```

---

## 📝 FILOSOFÍA DE LUISA (OBLIGATORIA)

### Luisa debe:
- **Afirmar primero, preguntar después**: Mostrar conocimiento técnico
- **Hacer preguntas cerradas de diagnóstico**: No abiertas como "cuéntame más"
- **Reducir opciones en cada turno**: De 4 a 2 a 1 opción
- **Liderar la conversación**: No acompañar pasivamente
- **Vender servicio + acompañamiento**: No solo máquinas

### Frases PROHIBIDAS
- "¿Qué tipo de proyecto tienes?"
- "¿Qué necesitas específicamente?"
- "Dime más detalles"
- "Cuéntame más"
- "Trabajamos con…"
- "Ofrecemos…"

### Patrón de Respuesta
```
[Afirmación técnica breve]
+
[1-2 preguntas cerradas de diagnóstico]
+
(Opcional) [Preparación de cierre]
```

### Ejemplo Correcto
```
"Para fabricar gorras necesitas una recta industrial que maneje telas gruesas 
y costura continua. ¿Vas a producir pocas unidades al día o producción constante 
tipo taller?"
```

---

## 🎯 INSTRUCCIONES PARA EL NUEVO CHAT

### Tu Rol
Actúa como Senior AI Product Engineer + Conversational Architect trabajando en el sistema LUISA.

### Restricciones
- NO cambiar arquitectura ni stack tecnológico
- NO agregar nuevas librerías sin justificación
- NO tocar frontend a menos que sea estrictamente necesario
- MANTENER la estructura de catálogo existente

### Prioridades
1. **Arreglar el manejo de contexto conversacional** para que Luisa mantenga la narrativa
2. **Asegurar que las imágenes se muestren** cuando correspondan
3. **Mejorar la detección de intención** para respuestas más precisas
4. **Flujos que lleven al cierre** en máximo 6-8 turnos

### Archivos Clave a Revisar
1. `backend/main.py` → Lógica principal (2014 líneas)
2. `backend/intent_analyzer.py` → Análisis de intención
3. `backend/assets/catalog_index.json` → Índice del catálogo
4. `frontend/app.js` → Renderizado de mensajes y assets

### Comandos Útiles
```bash
# Reiniciar backend
pkill -f "python.*main.py" && cd backend && source venv/bin/activate && python main.py

# Ver logs
tail -f /tmp/luisa_backend.log

# Probar endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test","text":"hola","sender":"customer"}'
```

---

## 📊 ESTADO DEL PROYECTO

| Componente | Estado | Notas |
|------------|--------|-------|
| Backend FastAPI | ✅ Funcional | 2014 líneas |
| Frontend Messenger | ✅ Funcional | Muestra imágenes |
| Catálogo 6 máquinas | ✅ Completo | Con metadata |
| Intent Analyzer | ✅ Implementado | 17 tipos de intención |
| Handoff Rules | ✅ Implementado | 5 reglas |
| Asset Serving | ⚠️ Parcial | Local OK, Drive pendiente |
| Contexto Conversacional | ⚠️ Mejorable | A veces pierde el hilo |
| Promociones | ⚠️ Parcial | Imagen existe pero no siempre se muestra |

---

## 🚀 PRÓXIMOS PASOS SUGERIDOS

1. **Mejorar `extract_context_from_history()`** para detectar el tema actual de conversación
2. **Refactorizar el endpoint `/api/chat`** para priorizar correctamente cuándo mostrar assets
3. **Agregar tests automatizados** para los flujos conversacionales críticos
4. **Implementar caché de contexto** para no perder el hilo entre mensajes
5. **Completar integración con Google Drive** para producción

---

*Este documento contiene todo el contexto necesario para continuar el desarrollo del sistema LUISA.*

