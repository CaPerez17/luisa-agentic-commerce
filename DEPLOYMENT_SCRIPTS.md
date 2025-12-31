# 🚀 Scripts de Despliegue Mejorados para VPS Pequeños

## 📋 Resumen de Cambios

Los scripts han sido **optimizados para VPS pequeños (512MB-1GB RAM)** donde los comandos `apt-get` pueden tardar varios minutos.

### Problemas Resueltos

1. ✅ **`apt-get update` sin timeouts** → Ahora con timeout de 10 minutos
2. ✅ **`apt-get upgrade` en cada deploy** → Movido a `provision.sh` (one-time)
3. ✅ **Falta de `DEBIAN_FRONTEND=noninteractive`** → Agregado para evitar prompts
4. ✅ **No maneja locks de apt** → Función `wait_for_apt_lock()` implementada
5. ✅ **Sin mensajes de progreso** → Timestamps y mensajes claros
6. ✅ **`docker compose build --no-cache` siempre** → Solo rebuild si necesario
7. ✅ **Sin advertencias sobre tiempos largos** → Mensajes claros sobre duración

---

## 📁 Estructura de Scripts

### `provision.sh` - Provisionamiento Inicial (ONE-TIME)

**Cuándo usarlo:** Solo la primera vez, cuando configuras el servidor desde cero.

**Qué hace:**
- Instala Docker y dependencias del sistema
- Configura firewall (UFW)
- Actualiza paquetes del sistema
- Prepara el entorno base

**Tiempo estimado:** 5-15 minutos en VPS pequeños

**Características:**
- ✅ Maneja locks de apt automáticamente
- ✅ Timeouts razonables (10-15 min por operación)
- ✅ Mensajes claros: "NO CANCELES - puede tardar X minutos"
- ✅ Usa `DEBIAN_FRONTEND=noninteractive`
- ✅ Usa `apt-get -yq` (quiet, más rápido)

### `deploy.sh` - Despliegue Rápido (IDEMPOTENTE)

**Cuándo usarlo:** Después de `provision.sh`, cada vez que despliegas código nuevo.

**Qué hace:**
- Clona/actualiza el repositorio
- Configura `.env`
- Construye y levanta contenedores Docker
- **NO instala paquetes del sistema**

**Tiempo estimado:** 2-5 minutos

**Características:**
- ✅ Rápido (sin apt-get)
- ✅ Idempotente (puede ejecutarse múltiples veces)
- ✅ Timeouts en git clone/fetch
- ✅ Build inteligente (sin `--no-cache` innecesario)
- ✅ Verificaciones de salud automáticas

---

## 🎯 Guía de Uso

### Primera Vez (Provisionamiento)

```bash
# 1. Conectarse al servidor
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

# 2. Subir scripts
# Desde tu máquina local:
scp -i ~/.ssh/luisa-lightsail.pem provision.sh deploy.sh ubuntu@44.215.107.112:/tmp/

# 3. En el servidor, mover a ubicación permanente
sudo mv /tmp/provision.sh /opt/
sudo mv /tmp/deploy.sh /opt/
sudo chmod +x /opt/provision.sh /opt/deploy.sh

# 4. Ejecutar provisionamiento (ONE-TIME)
sudo /opt/provision.sh

# ⚠️ IMPORTANTE: NO CANCELES durante apt-get update/upgrade
# Puede tardar 5-15 minutos en VPS pequeños
```

### Despliegues Posteriores

```bash
# 1. Conectarse al servidor
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

# 2. Ejecutar despliegue (rápido, 2-5 minutos)
cd /opt/luisa
sudo /opt/deploy.sh

# O si el script está en el repo:
sudo ./deploy.sh
```

---

## 🔧 Mejoras Técnicas Detalladas

### 1. Manejo de Locks de APT

**Problema:** `apt-get` puede fallar si otro proceso está usando el lock.

**Solución:**
```bash
wait_for_apt_lock() {
    local max_wait=300  # 5 minutos máximo
    local waited=0
    
    while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
        if [ $waited -ge $max_wait ]; then
            log_error "Timeout esperando locks de apt"
            exit 1
        fi
        log_info "Esperando locks de apt... (${waited}s/${max_wait}s)"
        sleep 5
        waited=$((waited + 5))
    done
}
```

**Por qué:** Evita errores de "Unable to lock" y espera automáticamente.

### 2. Timeouts en Comandos Lentos

**Problema:** `apt-get update` puede colgarse indefinidamente en conexiones lentas.

**Solución:**
```bash
# Timeout de 10 minutos para apt-get update
if timeout 600 apt-get update -yq; then
    log_info "✅ Repositorios actualizados"
else
    log_error "❌ apt-get update falló o excedió timeout"
    exit 1
fi
```

**Por qué:** Evita procesos colgados y permite diagnóstico rápido.

### 3. DEBIAN_FRONTEND=noninteractive

**Problema:** `apt-get` puede pedir confirmación interactiva y colgarse.

**Solución:**
```bash
export DEBIAN_FRONTEND=noninteractive
apt-get install -yq ...
```

**Por qué:** Responde automáticamente "yes" a todas las preguntas.

### 4. apt-get -yq (Quiet Mode)

**Problema:** Output verboso hace que parezca que está colgado.

**Solución:**
```bash
apt-get update -yq  # -y: yes automático, -q: quiet (menos output)
```

**Por qué:** Menos output = menos confusión + más rápido.

### 5. Separación de Provisionamiento y Despliegue

**Problema:** `apt-get upgrade` en cada deploy es innecesario y lento.

**Solución:**
- `provision.sh`: Instala Docker, actualiza sistema (ONE-TIME)
- `deploy.sh`: Solo despliega código (RÁPIDO, IDEMPOTENTE)

**Por qué:** Despliegues posteriores son 10x más rápidos (2-5 min vs 15+ min).

### 6. Build Inteligente de Docker

**Problema:** `docker compose build --no-cache` en cada deploy es innecesario.

**Solución:**
```bash
# Sin --no-cache: usa cache si Dockerfile no cambió
docker compose build backend
```

**Por qué:** Builds posteriores son más rápidos si no cambió el Dockerfile.

### 7. Timeouts en Git

**Problema:** `git clone` puede colgarse en conexiones lentas.

**Solución:**
```bash
if timeout 300 git clone "$REPO_URL" .; then
    log_info "✅ Repositorio clonado"
else
    log_error "git clone falló o excedió timeout (5 minutos)"
    exit 1
fi
```

**Por qué:** Evita procesos colgados y permite diagnóstico.

### 8. Mensajes con Timestamps

**Problema:** Sin timestamps, es difícil saber si está colgado o solo lento.

**Solución:**
```bash
log_info() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] [INFO]${NC} $1"
}
```

**Por qué:** Permite ver progreso en tiempo real.

---

## 📊 Comparación de Tiempos

| Operación | Script Anterior | Script Mejorado | Mejora |
|-----------|----------------|-----------------|--------|
| **Primera vez (provision)** | 15-20 min | 5-15 min | Similar |
| **Despliegues posteriores** | 15-20 min | 2-5 min | **3-4x más rápido** |
| **apt-get update** | Sin timeout | 10 min timeout | Más seguro |
| **Build Docker** | Siempre --no-cache | Cache inteligente | 2-3x más rápido |

---

## 🚨 Troubleshooting

### "apt-get update tarda mucho"

**Normal en VPS pequeños.** El script tiene timeout de 10 minutos. Si excede:
- Verifica conexión a internet: `ping -c 3 8.8.8.8`
- Verifica mirrors de apt: `cat /etc/apt/sources.list`
- Espera, puede tardar hasta 10 minutos en conexiones muy lentas

### "Docker build falla por memoria"

**En VPS de 512MB:**
```bash
# Limpiar cache antes de build
docker system prune -f
docker builder prune -f

# Build con menos paralelismo
docker compose build --parallel 1 backend
```

### "git clone timeout"

**Verifica:**
- Conexión a internet: `ping github.com`
- Firewall permite HTTPS: `sudo ufw status`
- Si persiste, clona manualmente y copia archivos

### "Contenedores no arrancan"

**Diagnóstico:**
```bash
# Ver logs
docker compose logs backend
docker compose logs caddy

# Ver estado
docker compose ps

# Verificar .env
cat /opt/luisa/.env | grep -v '^#' | grep -v '^$'
```

---

## ✅ Checklist de Verificación Post-Despliegue

```bash
# 1. Contenedores corriendo
docker compose ps

# 2. Health check local
curl http://localhost:8000/health

# 3. Health check público (puede tardar 1-2 min por certificado SSL)
curl https://luisa-agent.online/health

# 4. Logs sin errores
docker compose logs --tail=50 backend
docker compose logs --tail=50 caddy

# 5. Firewall activo
sudo ufw status
```

---

## 📝 Notas Importantes

1. **NO canceles durante `apt-get update/upgrade`** - Puede dejar el sistema en estado inconsistente
2. **Ejecuta `provision.sh` solo UNA VEZ** - Después usa `deploy.sh`
3. **`deploy.sh` es idempotente** - Puedes ejecutarlo múltiples veces sin problemas
4. **En VPS pequeños, los builds pueden tardar 3-5 minutos** - Es normal
5. **El certificado SSL puede tardar 1-2 minutos** - Caddy lo obtiene automáticamente

---

## 🔗 Referencias

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Caddy Documentation](https://caddyserver.com/docs/)
- [UFW Firewall Guide](https://help.ubuntu.com/community/UFW)

