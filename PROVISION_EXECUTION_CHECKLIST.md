# 🔒 Checklist de Ejecución Segura - provision.sh

## ⚠️ ADVERTENCIA CRÍTICA

**Este script modifica el firewall (UFW) y puede bloquear tu acceso SSH si algo falla.**

**SIEMPRE ejecuta desde una sesión SSH que puedas mantener abierta durante todo el proceso.**

---

## 📋 1. CHECKLIST PRE-EJECUCIÓN

### 1.1 Verificación de Acceso SSH

```bash
# Verificar que tienes acceso SSH activo
whoami
# Debe mostrar: ubuntu (o tu usuario)

# Verificar que puedes ejecutar sudo sin contraseña
sudo -n true && echo "✅ Sudo sin contraseña OK" || echo "❌ Necesitas contraseña"
```

**✅ REQUERIDO:** Debes poder ejecutar `sudo` sin contraseña.

### 1.2 Verificar Estado Actual del Sistema

```bash
# Verificar si Docker ya está instalado
docker --version 2>/dev/null && echo "✅ Docker ya instalado" || echo "⚠️  Docker NO instalado"

# Verificar si UFW está activo
sudo ufw status | head -5

# Verificar regla SSH actual
sudo ufw status | grep "22/tcp"

# Verificar si hay procesos de apt corriendo
ps aux | grep -E "apt|dpkg" | grep -v grep || echo "✅ No hay procesos apt corriendo"

# Verificar servicios automáticos de apt
sudo systemctl status apt-daily.service --no-pager | head -3
sudo systemctl status unattended-upgrades.service --no-pager | head -3
```

**📝 ANOTA:**
- ¿Docker está instalado? → El script lo detectará y saltará instalación
- ¿UFW está activo? → El script verificará regla SSH antes de activar
- ¿Hay procesos apt? → Espera a que terminen antes de ejecutar

### 1.3 Verificar Espacio en Disco

```bash
# Verificar espacio disponible
df -h /

# Verificar espacio en /var (donde apt guarda paquetes)
df -h /var
```

**✅ REQUERIDO:** Mínimo 2GB libres en `/` y `/var`.

### 1.4 Verificar Conectividad de Red

```bash
# Verificar acceso a internet
ping -c 3 8.8.8.8

# Verificar acceso a repositorios Docker
curl --max-time 5 -I https://download.docker.com/linux/ubuntu/gpg || echo "⚠️  No se puede acceder a Docker repos"
```

**✅ REQUERIDO:** Acceso a internet funcionando.

### 1.5 Preparar Sesión SSH Persistente

```bash
# Usar screen o tmux para mantener sesión activa
# Opción 1: screen
screen -S provision

# Opción 2: tmux
tmux new -s provision

# Si ya estás en screen/tmux, verifica:
echo $STY  # Debe mostrar algo si estás en screen
echo $TMUX  # Debe mostrar algo si estás en tmux
```

**✅ RECOMENDADO:** Usar `screen` o `tmux` para evitar perder sesión.

---

## 🚀 2. COMANDO DE EJECUCIÓN

### 2.1 Ubicación del Script

```bash
# Verificar que el script existe y es ejecutable
ls -la /opt/provision.sh || ls -la ./provision.sh

# Si no existe, copiarlo desde tu máquina local:
# scp -i ~/.ssh/luisa-lightsail.pem provision.sh ubuntu@44.215.107.112:/tmp/
# sudo mv /tmp/provision.sh /opt/
# sudo chmod +x /opt/provision.sh
```

### 2.2 Comando Exacto de Ejecución

```bash
# Opción 1: Desde /opt (si lo moviste ahí)
cd /opt
sudo ./provision.sh 2>&1 | tee provision.log

# Opción 2: Desde directorio actual
sudo ./provision.sh 2>&1 | tee provision.log

# Opción 3: Con logging completo
sudo bash -x ./provision.sh 2>&1 | tee provision.log
```

**✅ RECOMENDADO:** Usar `tee` para guardar log completo mientras ves output en tiempo real.

---

## 📊 3. OUTPUT ESPERADO POR FASE

### 3.1 Fase Inicial (0-30 segundos)

**Output esperado:**
```
[HH:MM:SS] [INFO] 🚀 Iniciando PROVISIONAMIENTO INICIAL de LUISA...
[HH:MM:SS] [WARN] ⚠️  Este proceso puede tardar 5-15 minutos en VPS pequeños (512MB-1GB RAM)
[HH:MM:SS] [WARN] ⚠️  NO CANCELES el proceso - los comandos apt-get pueden tardar varios minutos
```

**✅ NORMAL:** Mensajes de advertencia sobre tiempo.

**❌ PROBLEMA:** Si ves errores de permisos o "command not found" → Abortar.

---

### 3.2 Fase: Esperando Locks de APT (30s - 5min)

**Output esperado:**
```
[HH:MM:SS] [INFO] 📦 Actualizando repositorios de paquetes...
[HH:MM:SS] [WARN]    Esto puede tardar 2-5 minutos en VPS pequeños - NO CANCELES
[HH:MM:SS] [INFO] Esperando servicios automáticos de apt... (0s/300s)
[HH:MM:SS] [INFO] Esperando servicios automáticos de apt... (5s/300s)
...
[HH:MM:SS] [INFO] Esperando locks de apt... (0s/300s)
```

**✅ NORMAL:**
- Mensajes de espera cada 5 segundos
- Puede tardar hasta 5 minutos si hay procesos apt corriendo

**❌ PROBLEMA:**
- Si ves "Timeout esperando servicios automáticos de apt" → **ABORTAR**
- Si ves "Timeout esperando locks de apt" → **ABORTAR**
- Si tarda más de 5 minutos sin progreso → **ABORTAR**

**🔧 ACCIÓN SI HAY TIMEOUT:**
```bash
# Detener procesos manualmente
sudo systemctl stop apt-daily.service apt-daily-upgrade.service unattended-upgrades.service
sudo killall apt apt-get dpkg 2>/dev/null || true
# Esperar 30 segundos y reintentar
```

---

### 3.3 Fase: apt-get update (2-5 minutos)

**Output esperado:**
```
[HH:MM:SS] [INFO] 📦 Actualizando repositorios de paquetes...
[HH:MM:SS] [INFO] ✅ Repositorios actualizados
```

**✅ NORMAL:**
- Puede tardar 2-5 minutos en VPS pequeños
- Output mínimo (modo quiet `-yq`)

**❌ PROBLEMA:**
- Si ves "apt-get update falló o excedió timeout" → **ABORTAR**
- Si tarda más de 10 minutos → **ABORTAR**

---

### 3.4 Fase: apt-get upgrade (0-10 minutos)

**Output esperado (si hay actualizaciones):**
```
[HH:MM:SS] [INFO] 📦 Verificando actualizaciones del sistema...
[HH:MM:SS] [INFO] Hay actualizaciones pendientes, actualizando...
[HH:MM:SS] [WARN]    Esto puede tardar 3-10 minutos - NO CANCELES
[HH:MM:SS] [INFO] ✅ Sistema actualizado
```

**O si no hay actualizaciones:**
```
[HH:MM:SS] [INFO] 📦 Verificando actualizaciones del sistema...
[HH:MM:SS] [INFO] ✅ Sistema ya está actualizado, saltando upgrade
```

**✅ NORMAL:**
- Puede tardar 3-10 minutos si hay actualizaciones
- Puede saltarse si no hay actualizaciones

**❌ PROBLEMA:**
- Si ves "apt-get upgrade falló o excedió timeout" → **ABORTAR**
- Si tarda más de 15 minutos → **ABORTAR**

---

### 3.5 Fase: Instalación de Dependencias (1-3 minutos)

**Output esperado:**
```
[HH:MM:SS] [INFO] 📦 Instalando dependencias básicas...
[HH:MM:SS] [INFO] ✅ Dependencias instaladas
```

**✅ NORMAL:**
- Tarda 1-3 minutos
- Instala: curl, git, ufw, ca-certificates, gnupg, lsb-release, sqlite3

**❌ PROBLEMA:**
- Si ves "Instalación de dependencias falló" → **ABORTAR**

---

### 3.6 Fase: Configuración UFW / SSH (CRÍTICA) (10-30 segundos)

**Output esperado:**
```
[HH:MM:SS] [INFO] 🔥 Configurando firewall (UFW)...
[HH:MM:SS] [WARN] Regla SSH no encontrada, agregando...
[HH:MM:SS] [INFO] Regla SSH agregada
[HH:MM:SS] [INFO] ✅ Regla SSH verificada y garantizada
[HH:MM:SS] [INFO] ✅ Regla SSH ya existe
[HH:MM:SS] [WARN] Activando UFW...
[HH:MM:SS] [INFO] ✅ UFW activado
```

**✅ NORMAL:**
- Verifica/agrega regla SSH primero
- Luego activa UFW
- Mensajes claros de cada paso

**❌ PROBLEMA CRÍTICO:**
- Si ves "CRÍTICO: No se pudo agregar regla SSH. Abortando." → **SCRIPT ABORTA AUTOMÁTICAMENTE**
- Si ves "CRÍTICO: Regla SSH no se aplicó correctamente. Abortando." → **SCRIPT ABORTA AUTOMÁTICAMENTE**
- Si ves "CRÍTICO: No se pudo activar UFW." → **SCRIPT ABORTA AUTOMÁTICAMENTE**

**🚨 SI EL SCRIPT ABORTA EN ESTA FASE:**
```bash
# Verificar regla SSH manualmente
sudo ufw status | grep "22/tcp"

# Si no existe, agregarla manualmente ANTES de continuar
sudo ufw allow 22/tcp comment 'SSH'

# Verificar que se agregó
sudo ufw status | grep "22/tcp"

# Solo entonces continuar con el script
```

---

### 3.7 Fase: Instalación Docker (3-8 minutos)

**Output esperado (si Docker NO está instalado):**
```
[HH:MM:SS] [INFO] 🐳 Verificando Docker...
[HH:MM:SS] [INFO] Instalando Docker...
[HH:MM:SS] [WARN]    Esto puede tardar 3-5 minutos - NO CANCELES
[HH:MM:SS] [INFO] Descargando GPG key de Docker...
[HH:MM:SS] [INFO] ✅ GPG key de Docker descargada
[HH:MM:SS] [INFO] Actualizando repositorios para Docker...
[HH:MM:SS] [INFO] Instalando Docker Engine...
[HH:MM:SS] [INFO] ✅ Docker instalado
[HH:MM:SS] [INFO] Usuario ubuntu agregado al grupo docker
[HH:MM:SS] [INFO] Esperando a que Docker esté listo...
[HH:MM:SS] [INFO] Intento 1/12: Docker aún no responde, esperando 5s...
[HH:MM:SS] [INFO] ✅ Docker está funcionando
```

**O si Docker YA está instalado:**
```
[HH:MM:SS] [INFO] 🐳 Verificando Docker...
[HH:MM:SS] [INFO] Docker ya está instalado, saltando instalación
```

**✅ NORMAL:**
- Si Docker no está instalado: tarda 3-8 minutos
- Si Docker ya está instalado: se salta en segundos
- Retry loop puede mostrar varios intentos

**❌ PROBLEMA:**
- Si ves "Falló descarga de GPG key de Docker (timeout 30s)" → **ABORTAR**
- Si ves "Docker no responde después de 60s" → **ABORTAR**
- Si ves "Instalación de Docker falló" → **ABORTAR**

**🔧 ACCIÓN SI DOCKER NO RESPONDE:**
```bash
# Verificar estado del servicio
sudo systemctl status docker

# Reiniciar Docker
sudo systemctl restart docker

# Esperar y verificar manualmente
sleep 10
docker info
```

---

### 3.8 Fase: Verificación Docker Compose (5-10 segundos)

**Output esperado:**
```
[HH:MM:SS] [INFO] ✅ Docker Compose disponible: Docker Compose version v5.0.0
```

**✅ NORMAL:**
- Muestra versión de Docker Compose

**❌ PROBLEMA:**
- Si ves "Docker Compose no está disponible" → **ABORTAR**

---

### 3.9 Fase: Creación de Directorio (5 segundos)

**Output esperado:**
```
[HH:MM:SS] [INFO] 📁 Creando directorio de aplicación...
[HH:MM:SS] [INFO] ✅ Directorio creado: /opt/luisa
```

**✅ NORMAL:**
- Crea `/opt/luisa` si no existe

---

### 3.10 Fase: Finalización (5 segundos)

**Output esperado:**
```
==========================================
✅ PROVISIONAMIENTO COMPLETADO
==========================================

Próximos pasos:
1. Clona el repositorio en /opt/luisa
2. Ejecuta: sudo ./deploy.sh

Verificaciones:
  - Docker: docker --version
  - Docker Compose: docker compose version
  - Firewall: sudo ufw status

==========================================

[HH:MM:SS] [INFO] 🎉 Provisionamiento completado exitosamente
```

**✅ NORMAL:**
- Mensaje de éxito claro
- Instrucciones de próximos pasos

---

## 🚨 4. SEÑALES DE PROBLEMA Y CUÁNDO ABORTAR

### 4.1 Abortar INMEDIATAMENTE si ves:

1. **"CRÍTICO: No se pudo agregar regla SSH"**
   - **Riesgo:** Bloqueo de SSH
   - **Acción:** El script aborta automáticamente. Verifica manualmente antes de continuar.

2. **"Timeout esperando servicios automáticos de apt"**
   - **Riesgo:** Sistema en estado inconsistente
   - **Acción:** Detén procesos manualmente y reintenta.

3. **"Docker no responde después de 60s"**
   - **Riesgo:** Docker instalado pero no funcional
   - **Acción:** Verifica `systemctl status docker` y reinicia si es necesario.

### 4.2 Abortar después de 15 minutos sin progreso:

- Si el script está "colgado" en una fase por más de 15 minutos sin output nuevo
- Presiona `Ctrl+C` una vez (no múltiples veces)
- Verifica logs: `tail -50 provision.log`

### 4.3 NO Abortar si ves:

- Mensajes de "Esperando locks de apt..." (normal, puede tardar hasta 5 min)
- Mensajes de "Intento X/12: Docker aún no responde..." (normal, retry loop)
- Tiempos largos en `apt-get update/upgrade` (normal en VPS pequeños)

---

## ✅ 5. CHECKLIST POST-EJECUCIÓN

### 5.1 Verificar Acceso SSH (CRÍTICO)

```bash
# Desde OTRA terminal/sesión, verifica que puedes conectarte
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 "echo 'SSH funciona'"

# Si no puedes conectarte, desde la sesión actual:
sudo ufw status | grep "22/tcp"
# Debe mostrar: 22/tcp ALLOW IN Anywhere
```

**✅ REQUERIDO:** SSH debe funcionar desde otra sesión.

---

### 5.2 Verificar Docker

```bash
# Verificar versión
docker --version
# Debe mostrar: Docker version X.X.X

# Verificar que Docker funciona
docker info | head -5
# Debe mostrar información del sistema Docker

# Verificar Docker Compose
docker compose version
# Debe mostrar: Docker Compose version vX.X.X
```

**✅ REQUERIDO:** Docker y Docker Compose deben funcionar.

---

### 5.3 Verificar Firewall (UFW)

```bash
# Verificar estado
sudo ufw status verbose

# Verificar reglas críticas
sudo ufw status | grep -E "22/tcp|80/tcp|443/tcp"
# Debe mostrar:
#   22/tcp                     ALLOW IN    Anywhere
#   80/tcp                     ALLOW IN    Anywhere
#   443/tcp                    ALLOW IN    Anywhere
```

**✅ REQUERIDO:** UFW activo con reglas SSH, HTTP, HTTPS.

---

### 5.4 Verificar Dependencias Instaladas

```bash
# Verificar paquetes críticos
for pkg in curl git ufw ca-certificates gnupg lsb-release sqlite3; do
    dpkg -l | grep -q "^ii.*$pkg" && echo "✅ $pkg instalado" || echo "❌ $pkg NO instalado"
done
```

**✅ REQUERIDO:** Todos los paquetes deben estar instalados.

---

### 5.5 Verificar Directorio de Aplicación

```bash
# Verificar que existe
ls -la /opt/luisa
# Debe mostrar el directorio (puede estar vacío)
```

**✅ REQUERIDO:** `/opt/luisa` debe existir.

---

### 5.6 Verificar Logs del Script

```bash
# Verificar que no hay errores críticos
grep -i "error\|critical\|abort\|falló\|failed" provision.log | tail -20

# Verificar tiempo total de ejecución
grep "Iniciando PROVISIONAMIENTO" provision.log
grep "Provisionamiento completado" provision.log
```

**✅ REQUERIDO:** No debe haber errores críticos en los logs.

---

## 📝 6. RESUMEN DE VERIFICACIONES FINALES

Ejecuta este comando completo para verificación rápida:

```bash
echo "=== VERIFICACIÓN POST-PROVISIONAMIENTO ===" && \
echo "1. SSH:" && \
sudo ufw status | grep "22/tcp" && \
echo "2. Docker:" && \
docker --version && docker compose version && \
echo "3. UFW:" && \
sudo ufw status | head -3 && \
echo "4. Directorio:" && \
ls -d /opt/luisa && \
echo "✅ Todas las verificaciones pasaron"
```

**✅ Si todas las verificaciones pasan:** El provisionamiento fue exitoso.

**❌ Si alguna falla:** Revisa la sección correspondiente arriba y corrige manualmente.

---

## 🔄 7. SI ALGO FALLA

### 7.1 Si pierdes acceso SSH:

1. **NO ENTRES EN PÁNICO**
2. Usa la consola web de AWS Lightsail
3. Desde la consola web, ejecuta:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw reload
   ```

### 7.2 Si Docker no funciona:

```bash
# Verificar estado
sudo systemctl status docker

# Reiniciar
sudo systemctl restart docker

# Verificar logs
sudo journalctl -u docker -n 50
```

### 7.3 Si UFW bloquea algo:

```bash
# Ver reglas actuales
sudo ufw status numbered

# Agregar regla temporalmente
sudo ufw allow PORT/tcp

# O desactivar temporalmente (NO recomendado en producción)
sudo ufw disable
```

---

## ✅ ESTADO FINAL ESPERADO

Después de ejecutar `provision.sh` exitosamente, debes tener:

- ✅ Docker instalado y funcionando
- ✅ Docker Compose disponible
- ✅ UFW activo con reglas SSH, HTTP, HTTPS
- ✅ Dependencias básicas instaladas
- ✅ Directorio `/opt/luisa` creado
- ✅ **Acceso SSH garantizado**

**Tiempo total estimado:** 5-15 minutos en VPS pequeños.

**Próximo paso:** Ejecutar `deploy.sh` para desplegar la aplicación.

