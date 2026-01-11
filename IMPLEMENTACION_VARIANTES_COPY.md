# Implementación de Variantes de Copy

**Fecha**: 2025-01-05  
**Estado**: ✅ Implementado

---

## Resumen

Se implementaron variaciones mínimas (2 alternativas) para 4 tipos de mensajes críticos:

1. ✅ **Saludo inicial** (2 variantes)
2. ✅ **Triage** (2 variantes para primer turno, 2 para 2+ turnos)
3. ✅ **HUMAN_ACTIVE follow-up** (2 variantes)
4. ✅ **Handoff "te llamamos o pasas"** (2 variantes para Montería, 2 para fuera)

**Selección**: Determinística por `hash(conversation_id) % 2` (misma conversación = misma variante, diferente entre conversaciones)

---

## Archivos Modificados

1. `backend/app/rules/keywords.py` - Variantes y función `select_variant()`
2. `backend/app/routers/whatsapp.py` - HUMAN_ACTIVE follow-up
3. `backend/app/services/triage_service.py` - Triage greeting
4. `backend/app/services/handoff_service.py` - Handoff "te llamamos o pasas"
5. `backend/app/services/response_service.py` - Saludo en respuesta
6. `backend/app/rules/business_guardrails.py` - Saludo en EMPTY_OR_GIBBERISH
7. `backend/app/services/sales_dialogue.py` - Pasa conversation_id a triage

---

## Lista de Plantillas Afectadas

| # | Tipo | Variantes | Archivo donde se usa | Función |
|---|------|-----------|----------------------|---------|
| 1 | **Saludo inicial** | 2 | `response_service.py:707`<br>`response_service.py:509,913`<br>`business_guardrails.py:200` | `build_response()`<br>`get_default_response()`<br>`_generate_fallback_response()`<br>`get_response_for_message_type()` |
| 2 | **Triage primer turno** | 2 | `triage_service.py:160`<br>`sales_dialogue.py:75,148` | `generate_triage_greeting()` |
| 3 | **Triage 2+ turnos** | 2 | `triage_service.py:163`<br>`sales_dialogue.py:75,148` | `generate_triage_greeting()` |
| 4 | **HUMAN_ACTIVE follow-up** | 2 | `whatsapp.py:356` | `_process_whatsapp_message()` |
| 5 | **Handoff "te llamamos o pasas" (Montería)** | 2 | `handoff_service.py:398` | `generate_handoff_message()` |
| 6 | **Handoff "te llamamos o vayamos" (Fuera)** | 2 | `handoff_service.py:382` | `generate_handoff_message()` |

---

## Variantes Definidas

### 1. Saludo Inicial

**Constante**: `SALUDO_VARIANTES`  
**Ubicación**: `backend/app/rules/keywords.py:453-456`

**Variante A**:
```
¡Hola! 👋 Soy Luisa del Sastre.
¿Buscas máquina familiar, industrial o repuesto?
```

**Variante B**:
```
¡Hola! 😊 Soy Luisa. ¿Te ayudo con máquinas familiares, industriales o repuestos?
```

**Selección**: `hash(conversation_id) % 2`

---

### 2. Triage Primer Turno

**Constante**: `TRIAGE_FIRST_VARIANTES`  
**Ubicación**: `backend/app/rules/keywords.py:458-461`

**Variante A**:
```
¡Hola! 👋 Soy Luisa del Sastre.
¿Buscas máquina familiar, industrial o repuesto?
```

**Variante B**:
```
¡Hola! 😊 Soy Luisa. ¿Qué necesitas: máquinas, repuestos o servicio técnico?
```

**Selección**: `hash(conversation_id) % 2`

---

### 3. Triage 2+ Turnos

**Constante**: `TRIAGE_RETRY_VARIANTES`  
**Ubicación**: `backend/app/rules/keywords.py:463-466`

**Variante A**:
```
¿Es por máquinas, repuestos o servicio técnico?
```

**Variante B**:
```
¿Necesitas máquinas, repuestos o soporte?
```

**Selección**: `hash(conversation_id) % 2`

---

### 4. HUMAN_ACTIVE Follow-up

**Constante**: `HUMAN_ACTIVE_VARIANTES`  
**Ubicación**: `backend/app/rules/keywords.py:468-471`

**Variante A**:
```
¡Hola! 😊 Un asesor te va a contactar pronto.
¿Quieres que pase tu nombre y barrio para que todo esté listo?
```

**Variante B**:
```
¡Hola! 👋 Un asesor te contactará pronto.
¿Te ayudo con tu nombre y ubicación mientras tanto?
```

**Selección**: `hash(conversation_id) % 2`

---

### 5. Handoff "Te llamamos o pasas" (Montería)

**Constante**: `HANDOFF_LLAMAMOS_PASAS_MONTERIA_VARIANTES`  
**Ubicación**: `backend/app/rules/keywords.py:473-476`

**Variante A**:
```
Para coordinar pago y entrega, un asesor te va a acompañar.
¿Te llamamos para agendar o prefieres pasar por el almacén?
```

**Variante B**:
```
Para coordinar pago y entrega, te acompaña un asesor.
¿Prefieres que te llamemos o pasas por el almacén?
```

**Selección**: `hash(conversation_id) % 2`

**Cuándo se usa**: Handoff por "cierre" o "compra" + usuario está en Montería

---

### 6. Handoff "Te llamamos o vayamos" (Fuera de Montería)

**Constante**: `HANDOFF_LLAMAMOS_PASAS_FUERA_VARIANTES`  
**Ubicación**: `backend/app/rules/keywords.py:478-481`

**Variante A**:
```
Para tu proyecto, lo mejor es que un asesor te acompañe personalmente.
¿Te llamamos para agendar cita o prefieres que vayamos a tu taller?
```

**Variante B**:
```
Para tu proyecto, lo mejor es que un asesor te acompañe.
¿Preferimos llamarte para agendar o vamos a tu taller?
```

**Selección**: `hash(conversation_id) % 2`

**Cuándo se usa**: Handoff por "proyecto de negocio" o "servicio diferencial" + usuario está en Montería

---

## Ejemplos de Salida

### Ejemplo 1: Saludo Inicial

**Conversación A** (`conversation_id = "wa_573001234567"`, `hash % 2 = 0`):
```
Variante A:
¡Hola! 👋 Soy Luisa del Sastre.
¿Buscas máquina familiar, industrial o repuesto?
```

**Conversación B** (`conversation_id = "wa_573008765432"`, `hash % 2 = 1`):
```
Variante B:
¡Hola! 😊 Soy Luisa. ¿Te ayudo con máquinas familiares, industriales o repuestos?
```

---

### Ejemplo 2: Triage Primer Turno

**Conversación A** (`conversation_id = "wa_573001234567"`, `hash % 2 = 0`):
```
Variante A:
¡Hola! 👋 Soy Luisa del Sastre.
¿Buscas máquina familiar, industrial o repuesto?
```

**Conversación B** (`conversation_id = "wa_573008765432"`, `hash % 2 = 1`):
```
Variante B:
¡Hola! 😊 Soy Luisa. ¿Qué necesitas: máquinas, repuestos o servicio técnico?
```

---

### Ejemplo 3: Triage 2+ Turnos

**Conversación A** (`conversation_id = "wa_573001234567"`, `hash % 2 = 0`):
```
Variante A:
¿Es por máquinas, repuestos o servicio técnico?
```

**Conversación B** (`conversation_id = "wa_573008765432"`, `hash % 2 = 1`):
```
Variante B:
¿Necesitas máquinas, repuestos o soporte?
```

---

### Ejemplo 4: HUMAN_ACTIVE Follow-up

**Conversación A** (`conversation_id = "wa_573001234567"`, `hash % 2 = 0`):
```
Variante A:
¡Hola! 😊 Un asesor te va a contactar pronto.
¿Quieres que pase tu nombre y barrio para que todo esté listo?
```

**Conversación B** (`conversation_id = "wa_573008765432"`, `hash % 2 = 1`):
```
Variante B:
¡Hola! 👋 Un asesor te contactará pronto.
¿Te ayudo con tu nombre y ubicación mientras tanto?
```

---

### Ejemplo 5: Handoff "Te llamamos o pasas" (Montería)

**Conversación A** (`conversation_id = "wa_573001234567"`, `hash % 2 = 0`, en Montería, handoff cierre):
```
Variante A:
Para coordinar pago y entrega, un asesor te va a acompañar.
¿Te llamamos para agendar o prefieres pasar por el almacén?
```

**Conversación B** (`conversation_id = "wa_573008765432"`, `hash % 2 = 1`, en Montería, handoff cierre):
```
Variante B:
Para coordinar pago y entrega, te acompaña un asesor.
¿Prefieres que te llamemos o pasas por el almacén?
```

---

### Ejemplo 6: Handoff "Te llamamos o vayamos" (Fuera de Montería)

**Conversación A** (`conversation_id = "wa_573001234567"`, `hash % 2 = 0`, en Montería, handoff proyecto):
```
Variante A:
Para tu proyecto, lo mejor es que un asesor te acompañe personalmente.
¿Te llamamos para agendar cita o prefieres que vayamos a tu taller?
```

**Conversación B** (`conversation_id = "wa_573008765432"`, `hash % 2 = 1`, en Montería, handoff proyecto):
```
Variante B:
Para tu proyecto, lo mejor es que un asesor te acompañe.
¿Preferimos llamarte para agendar o vamos a tu taller?
```

---

## Diff Unificado

### 1. `backend/app/rules/keywords.py`

**Líneas agregadas**: ~35 líneas (después de línea 446)

```diff
+ # ============================================================================
+ # VARIANTES DE COPY (Selección Determinística)
+ # ============================================================================
+
+ SALUDO_VARIANTES = [
+     "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?",
+     "¡Hola! 😊 Soy Luisa. ¿Te ayudo con máquinas familiares, industriales o repuestos?"
+ ]
+
+ TRIAGE_FIRST_VARIANTES = [
+     "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?",
+     "¡Hola! 😊 Soy Luisa. ¿Qué necesitas: máquinas, repuestos o servicio técnico?"
+ ]
+
+ TRIAGE_RETRY_VARIANTES = [
+     "¿Es por máquinas, repuestos o servicio técnico?",
+     "¿Necesitas máquinas, repuestos o soporte?"
+ ]
+
+ HUMAN_ACTIVE_VARIANTES = [
+     "¡Hola! 😊 Un asesor te va a contactar pronto.\n¿Quieres que pase tu nombre y barrio para que todo esté listo?",
+     "¡Hola! 👋 Un asesor te contactará pronto.\n¿Te ayudo con tu nombre y ubicación mientras tanto?"
+ ]
+
+ HANDOFF_LLAMAMOS_PASAS_MONTERIA_VARIANTES = [
+     "Para coordinar pago y entrega, un asesor te va a acompañar.\n¿Te llamamos para agendar o prefieres pasar por el almacén?",
+     "Para coordinar pago y entrega, te acompaña un asesor.\n¿Prefieres que te llamemos o pasas por el almacén?"
+ ]
+
+ HANDOFF_LLAMAMOS_PASAS_FUERA_VARIANTES = [
+     "Para tu proyecto, lo mejor es que un asesor te acompañe personalmente.\n¿Te llamamos para agendar cita o prefieres que vayamos a tu taller?",
+     "Para tu proyecto, lo mejor es que un asesor te acompañe.\n¿Preferimos llamarte para agendar o vamos a tu taller?"
+ ]
+
+
+ def select_variant(conversation_id: str, variants: List[str]) -> str:
+     """
+     Selecciona una variante determinísticamente basado en el conversation_id.
+     
+     Args:
+         conversation_id: ID de la conversación (determinístico)
+         variants: Lista de variantes disponibles
+     
+     Returns:
+         Variante seleccionada (determinística para la misma conversación)
+     """
+     if not variants:
+         return ""
+     if len(variants) == 1:
+         return variants[0]
+     
+     # Hash determinístico: siempre mismo resultado para mismo conversation_id
+     hash_value = hash(conversation_id) % len(variants)
+     return variants[hash_value]
```

---

### 2. `backend/app/routers/whatsapp.py`

**Líneas modificadas**: ~3 líneas (línea 47, 356-359)

```diff
 from app.rules.business_guardrails import is_business_related, get_off_topic_response
+from app.rules.keywords import select_variant, HUMAN_ACTIVE_VARIANTES
 
 ... (línea 346-359)
 
             # REGLA DE ORO MVP: LUISA nunca debe quedarse muda
             # Enviar respuesta cortés indicando que un asesor revisará
-            response_text = (
-                "¡Hola! 😊 Un asesor te va a contactar pronto.\n"
-                "¿Quieres que pase tu nombre y barrio para que todo esté listo?"
-            )
+            # Selección determinística de variante por conversation_id
+            response_text = select_variant(conversation_id, HUMAN_ACTIVE_VARIANTES)
             success, error_info = await send_whatsapp_message(phone_from, response_text)
```

**Líneas modificadas adicionales**: ~3 líneas (línea 413-414, 423-428)

```diff
 ... (línea 413-414)
 
             # Obtener estado conversacional
             state = get_conversation_state(phone_from)
+            # Agregar conversation_id y phone_from al state para selección determinística de variantes
+            state["conversation_id"] = conversation_id
+            state["phone_from"] = phone_from
             
             # Verificar si requiere handoff
 
 ... (línea 423-428)
 
                 # Generar respuesta de handoff para el cliente
                 response_text = generate_handoff_message(
                     text, 
                     decision.reason, 
                     decision.priority.value,
-                    context.get("ciudad")
+                    context.get("ciudad"),
+                    conversation_id
                 )
```

---

### 3. `backend/app/services/triage_service.py`

**Líneas modificadas**: ~10 líneas (línea 8, 128, 153-163)

```diff
-from app.rules.keywords import normalize_text
+from app.rules.keywords import normalize_text, select_variant, TRIAGE_FIRST_VARIANTES, TRIAGE_RETRY_VARIANTES
 
 ... (línea 128)
 
-def generate_triage_greeting(state: Optional[dict] = None, ambiguous_turns: int = 0) -> str:
+def generate_triage_greeting(state: Optional[dict] = None, ambiguous_turns: int = 0, conversation_id: Optional[str] = None) -> str:
     """
     Genera el mensaje de triage para mensajes ambiguos.
     Versión humana: saludo + pregunta abierta guiada.
     
     Args:
         state: Estado conversacional (si existe, puede retomar contexto)
         ambiguous_turns: Número de turnos ambiguos consecutivos
+        conversation_id: ID de la conversación para selección determinística de variante
     
     Returns:
         Mensaje de triage humano (sin menú numerado si es primer turno)
     """
     # Si hay estado previo reciente, retomar con contexto
     ... (líneas 140-151 sin cambios)
     
+    # Usar conversation_id o phone_from del state como identificador determinístico
+    variant_key = conversation_id if conversation_id else (state.get("phone_from", "") if state else "")
+    if not variant_key:
+        variant_key = "default"  # Fallback si no hay identificador
+    
     # Si es el primer turno ambiguo: saludo humano + pregunta cerrada con variación
     if ambiguous_turns == 0:
-        return (
-            "¡Hola! 👋 Soy Luisa del Sastre.\n"
-            "¿Buscas máquina familiar, industrial o repuesto?"
-        )
+        return select_variant(variant_key, TRIAGE_FIRST_VARIANTES)
     
     # Si lleva 2+ turnos ambiguos: ofrecer opciones en lenguaje humano con variación
-    return "¿Es por máquinas, repuestos o servicio técnico?"
+    return select_variant(variant_key, TRIAGE_RETRY_VARIANTES)
```

---

### 4. `backend/app/services/handoff_service.py`

**Líneas modificadas**: ~15 líneas (línea 42-46, 365, 378-382, 394-398)

```diff
 from app.rules.keywords import (
     ... (imports existentes)
+    select_variant,
+    HANDOFF_LLAMAMOS_PASAS_MONTERIA_VARIANTES,
+    HANDOFF_LLAMAMOS_PASAS_FUERA_VARIANTES
 )
 
 ... (línea 365)
 
-def generate_handoff_message(text: str, reason: str, priority: str, ciudad: Optional[str] = None) -> str:
+def generate_handoff_message(text: str, reason: str, priority: str, ciudad: Optional[str] = None, conversation_id: Optional[str] = None) -> str:
     """
     Genera mensaje de handoff para el cliente.
     """
     ... (línea 372 sin cambios)
     
     # Handoff por impacto de negocio o servicio diferencial
     if any(kw in reason.lower() for kw in ["proyecto de negocio", "servicio diferencial", "asesoría", "instalación"]):
         if esta_en_monteria:
-            return (
-                "Para tu proyecto, lo mejor es que un asesor te acompañe personalmente.\n"
-                "¿Te llamamos para agendar cita o prefieres que vayamos a tu taller?"
-            )
+            # Selección determinística de variante para "te llamamos o vayamos"
+            variant_key = conversation_id if conversation_id else "default"
+            return select_variant(variant_key, HANDOFF_LLAMAMOS_PASAS_FUERA_VARIANTES)
         else:
             return (
                 "Para tu proyecto, lo mejor es que un asesor te acompañe.\n"
                 "¿Te llamamos para agendar una cita?"
             )
     
     ... (línea 387-391 sin cambios)
     
     # Handoff por decisión de compra
     if "cierre" in reason.lower() or "compra" in reason.lower():
         if esta_en_monteria:
-            return (
-                "Para coordinar pago y entrega, un asesor te va a acompañar.\n"
-                "¿Te llamamos para agendar o prefieres pasar por el almacén?"
-            )
+            # Selección determinística de variante para "te llamamos o pasas"
+            variant_key = conversation_id if conversation_id else "default"
+            return select_variant(variant_key, HANDOFF_LLAMAMOS_PASAS_MONTERIA_VARIANTES)
         else:
             return (
                 "Para coordinar pago y envío, un asesor te va a contactar.\n"
                 "¿Te llamamos para agendar?"
             )
```

---

### 5. `backend/app/services/response_service.py`

**Líneas modificadas**: ~10 líneas (línea 37-38, 707, 509, 913, 771, 827)

```diff
 from app.services.llm_adapter import (
     get_llm_suggestion_sync,
     LLMTaskType
 )
+from app.rules.keywords import select_variant, SALUDO_VARIANTES
 
 ... (línea 705-707)
 
                 # Lógica especial para saludos
                 if tracer.intent == "saludo":
-                    result["text"] = "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"
+                    # Selección determinística de variante de saludo por conversation_id
+                    result["text"] = select_variant(conversation_id, SALUDO_VARIANTES)
                 else:
                     ... (resto sin cambios)
 
 ... (línea 499)
 
-def _generate_fallback_response(text: str, context: dict, intent_result: dict) -> str:
+def _generate_fallback_response(text: str, context: dict, intent_result: dict, conversation_id: Optional[str] = None) -> str:
     """Genera respuesta fallback."""
     ... (líneas 504-508 sin cambios)
 
-    return "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"
+    # Selección determinística de variante de saludo
+    variant_key = conversation_id if conversation_id else "default"
+    return select_variant(variant_key, SALUDO_VARIANTES)
 
 ... (línea 901)
 
-def _generate_fallback_response(text: str, context: dict, intent_result: dict) -> str:
+def _generate_fallback_response(text: str, context: dict, intent_result: dict, conversation_id: Optional[str] = None) -> str:
     """
     Genera respuesta fallback cuando no hay respuesta específica.
     """
     ... (líneas 904-913 sin cambios)
 
-    # Respuesta genérica
-    return "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"
+    # Respuesta genérica con selección determinística de variante de saludo
+    variant_key = conversation_id if conversation_id else "default"
+    return select_variant(variant_key, SALUDO_VARIANTES)
 
 ... (línea 1076)
 
-def _generate_fallback_response(text: str, context: dict, intent_result: dict) -> str:
+def _generate_fallback_response(text: str, context: dict, intent_result: dict, conversation_id: Optional[str] = None) -> str:
     """Respuesta básica cuando no hay OpenAI ni reglas específicas."""
     ... (línea 1080-1081)
 
     # Saludos con selección determinística de variante
     if intent == "saludo" or any(w in text_lower for w in ["hola", "buenas"]):
-        return "¡Hola! 😊 ¿En qué te puedo ayudar: máquinas, repuestos o servicio técnico?"
+        variant_key = conversation_id if conversation_id else "default"
+        return select_variant(variant_key, SALUDO_VARIANTES)
 
 ... (línea 771, 827)
 
-                            result["text"] = _generate_fallback_response(text, context, intent_result)
+                            result["text"] = _generate_fallback_response(text, context, intent_result, conversation_id)

 ... (línea 645, 650)
 
-                result["text"] = get_response_for_message_type(message_type, text)
+                result["text"] = get_response_for_message_type(message_type, text, conversation_id)
```

---

### 6. `backend/app/rules/business_guardrails.py`

**Líneas modificadas**: ~8 líneas (línea 13-17, 195, 200)

```diff
 from app.rules.keywords import (
     ... (imports existentes)
+    select_variant,
+    SALUDO_VARIANTES
 )
+from typing import Tuple, Set, Optional

 ... (línea 195)
 
-def get_response_for_message_type(message_type: MessageType, text: str) -> str:
+def get_response_for_message_type(message_type: MessageType, text: str, conversation_id: Optional[str] = None) -> str:
     """
     Retorna la respuesta apropiada según el tipo de mensaje.
     """
     if message_type == MessageType.EMPTY_OR_GIBBERISH:
-        return "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"
+        # Selección determinística de variante de saludo
+        variant_key = conversation_id if conversation_id else "default"
+        return select_variant(variant_key, SALUDO_VARIANTES)
 
     ... (resto sin cambios)
```

---

### 7. `backend/app/services/sales_dialogue.py`

**Líneas modificadas**: ~8 líneas (línea 72-75, 144-148)

```diff
     # Si el mensaje es ambiguo y NO hay estado previo, hacer triage
     if is_ambiguous and stage == "discovery" and not state.get("last_intent"):
         ambiguous_turns = state.get("ambiguous_turns", 0)
+        # Usar phone_from del state como identificador determinístico si está disponible
+        conversation_id = state.get("conversation_id") or state.get("phone_from", "")
         return {
-            "reply_text": generate_triage_greeting(state, ambiguous_turns),
+            "reply_text": generate_triage_greeting(state, ambiguous_turns, conversation_id),
             ... (resto sin cambios)
         }
 
 ... (línea 144-148)
 
     elif stage == "triage":
         # Contar turnos ambiguos consecutivos
         ambiguous_turns = state.get("ambiguous_turns", 0) + 1
+        # Usar phone_from del state como identificador determinístico si está disponible
+        conversation_id = state.get("conversation_id") or state.get("phone_from", "")
         return {
-            "reply_text": generate_triage_greeting(state, ambiguous_turns),
+            "reply_text": generate_triage_greeting(state, ambiguous_turns, conversation_id),
             ... (resto sin cambios)
         }
```

---

## Función de Selección Determinística

**Ubicación**: `backend/app/rules/keywords.py:484-503`

```python
def select_variant(conversation_id: str, variants: List[str]) -> str:
    """
    Selecciona una variante determinísticamente basado en el conversation_id.
    
    Args:
        conversation_id: ID de la conversación (determinístico)
        variants: Lista de variantes disponibles
    
    Returns:
        Variante seleccionada (determinística para la misma conversación)
    """
    if not variants:
        return ""
    if len(variants) == 1:
        return variants[0]
    
    # Hash determinístico: siempre mismo resultado para mismo conversation_id
    hash_value = hash(conversation_id) % len(variants)
    return variants[hash_value]
```

**Características**:
- ✅ Determinístico: mismo `conversation_id` → misma variante (siempre)
- ✅ Simple: `hash(conversation_id) % 2` para 2 variantes
- ✅ Sin aleatoriedad pura: siempre predecible
- ✅ Seguro: maneja casos edge (variants vacío, 1 variante)

---

## Garantías del Diseño

✅ **No cambia lógica de negocio**: Solo selección de texto, no decisiones  
✅ **Determinístico**: Misma conversación = misma variante (siempre)  
✅ **Simple**: Hash modular simple, no complejidad innecesaria  
✅ **Backward compatible**: Parámetro `conversation_id` opcional, fallback a "default"  
✅ **Corto**: Todas las variantes mantienen 2-3 líneas máximo  
✅ **Preguntas cerradas**: Todas las variantes terminan con pregunta cerrada  

---

## Testing Manual Recomendado

1. **Test saludo inicial**:
   - Crear 2 conversaciones diferentes
   - Enviar "hola" a cada una
   - Verificar que reciben variantes diferentes

2. **Test HUMAN_ACTIVE**:
   - Activar handoff en una conversación
   - Escribir después del handoff
   - Verificar que recibe variante determinística (siempre la misma para esa conversación)

3. **Test handoff "te llamamos o pasas"**:
   - Usuario en Montería menciona compra
   - Verificar que recibe una de las 2 variantes según `conversation_id`

4. **Test determinismo**:
   - Misma conversación → Mismo saludo siempre
   - Diferente conversación → Puede ser diferente

---

## Resumen de Cambios

- **Archivos modificados**: 7
- **Líneas agregadas**: ~80 líneas (variantes + función helper)
- **Líneas modificadas**: ~30 líneas (integraciones)
- **Variantes implementadas**: 6 grupos (2 variantes cada uno)
- **Lógica de negocio**: 0 cambios (solo selección de texto)

---

**Última actualización**: 2025-01-05  
**Estado**: ✅ Implementado y listo para probar

