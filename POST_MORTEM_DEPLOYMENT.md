# Post-Mortem: Despliegue LUISA en AWS Lightsail

**Fecha del Incidente**: 31 de Diciembre 2025, 00:11 - 03:12 UTC  
**Duración**: ~3 horas  
**Severidad**: Alta (sistema no disponible durante despliegue)  
**Estado Final**: Resuelto (sistema operativo desde 03:12 UTC)

---

## Summary

Durante el despliegue inicial de LUISA en un VPS Lightsail de 512MB, el sistema experimentó múltiples eventos de Out of Memory (OOM) que mataron procesos críticos (docker-buildx, apt-extracttemp, networkd-dispatcher), causando reinicios del servidor y fallos en builds de Docker. El sistema finalmente se estabilizó después del tercer reinicio (02:19 UTC) cuando Docker completó el build exitosamente y los contenedores arrancaron correctamente.

---

## Impact

- **Disponibilidad**: Sistema no disponible durante ~3 horas
- **Builds de Docker**: 3 builds fallidos por OOM antes del éxito
- **SSH/Console**: Errores intermitentes durante eventos OOM (00:22-00:23 UTC)
- **Reinicios**: 3 reinicios del servidor (00:11, 01:31, 02:19 UTC)
- **HTTPS Público**: No disponible debido a Security Group de Lightsail (no crítico para demo local)

---

## Timeline

### 29 Dic 2025, 23:49 UTC
- `apt-get upgrade` ejecutado exitosamente
- Docker instalado (23:53 UTC)

### 30 Dic 2025, 00:08 UTC
- Primer intento de build Docker falla (OOM durante `apt-get install sqlite3` en contenedor)
- Log: `failed to read oom_kill event` en journal Docker

### 31 Dic 2025, 00:11 UTC
- **Reboot #1** del servidor
- Docker reiniciado (00:11:08 UTC)

### 31 Dic 2025, 00:22-00:23 UTC
- **Errores SSH intermitentes**:
  - `kex_exchange_identification: Connection closed by remote host`
  - `banner line contains invalid characters`
- Coincide con eventos OOM

### 31 Dic 2025, 00:38:09 UTC
- **OOM Event #1**: `docker-compose invoked oom-killer`
- Proceso matado: `docker-buildx` (PID 2113)
- Memoria disponible: `free:1535 kB`, `Free swap = 0kB`
- Build cancelado: `rpc error: code = Canceled desc = context canceled`

### 31 Dic 2025, 01:09:37 UTC
- **OOM Event #2**: `apt-extracttemp invoked oom-killer`
- Proceso matado: `networkd-dispatcher` (PID 435) a las 01:13:50
- `systemd-journald` también afectado (watchdog timeout)

### 31 Dic 2025, 01:31 UTC
- **Reboot #2** del servidor
- Docker reiniciado (01:31:17 UTC)

### 31 Dic 2025, 01:46 UTC
- Build Docker exitoso (después del reboot)
- Contenedores creados pero múltiples reinicios de health checks

### 31 Dic 2025, 02:19 UTC
- **Reboot #3** del servidor (último)
- Docker reiniciado (02:20:43 UTC)
- Buildkit inicializado (02:21:00 UTC)

### 31 Dic 2025, 03:11-03:12 UTC
- **Build final exitoso**
- Contenedores arrancados:
  - `luisa-backend`: Up (healthy) desde 03:12
  - `luisa-caddy`: Up desde 03:12
- **Certificado SSL obtenido**: 03:12:51 UTC (HTTP-01 challenge exitoso)
- **Health endpoint funcionando**: `http://localhost:8000/health` responde correctamente

---

## Root Cause

### Root Cause Principal

**Out of Memory (OOM) durante builds de Docker en VPS de 512MB sin swap**

**Evidencia**:
- `Dec 31 00:38:09`: `docker-compose invoked oom-killer: gfp_mask=0x140cca`
- `Dec 31 00:38:10`: `Out of memory: Killed process 2113 (docker-buildx) total-vm:1297524kB`
- `Dec 31 00:38:10`: `Free swap = 0kB` (sin swap disponible)
- `Dec 31 01:09:37`: `apt-extracttemp invoked oom-killer`
- `Dec 31 01:13:50`: `Out of memory: Killed process 435 (networkd-dispat)`

**Análisis**:
- VPS t3.nano con 416MB RAM total
- Docker build process (`docker-buildx`) consumió >1.2GB de memoria virtual
- Sin swap, el kernel mató procesos cuando la RAM física se agotó
- Builds de Docker son intensivos en memoria (compilación, descarga de paquetes, layers)

---

## Contributing Factors

### Factor 1: Ausencia de Swap
- **Evidencia**: `Free swap = 0kB` en todos los eventos OOM
- **Impacto**: Sin swap, el sistema no puede "swappear" memoria inactiva durante picos de uso
- **Por qué importa**: Builds de Docker tienen picos de memoria que exceden la RAM física disponible

### Factor 2: Tamaño del VPS (512MB)
- **Evidencia**: `Mem: 416MB total` (t3.nano)
- **Impacto**: Insuficiente para builds de Docker sin swap
- **Por qué importa**: Docker buildkit + compilación de Python + apt-get requieren memoria significativa

### Factor 3: Múltiples Intentos de Build Simultáneos
- **Evidencia**: Logs muestran múltiples `sbJoin` events (contenedores reiniciando)
- **Impacto**: Cada intento consume memoria adicional
- **Por qué importa**: Builds fallidos dejaron contenedores "zombies" consumiendo recursos

### Factor 4: Docker Compose Down Colgado
- **Evidencia**: Múltiples interfaces `veth*` no encontradas en logs (01:46-01:50 UTC)
- **Impacto**: Redes Docker no limpiadas correctamente, consumiendo recursos
- **Por qué importa**: `docker compose down` se quedó en "Removing network..." durante OOM

---

## What Went Well

1. **Docker finalmente completó el build** después del tercer reinicio
2. **Certificado SSL obtenido exitosamente** vía HTTP-01 challenge (puerto 80 funcionaba)
3. **Health endpoint funcionando** localmente desde 03:12 UTC
4. **Código sin errores de sintaxis** - los problemas fueron puramente de recursos
5. **UFW configurado correctamente** - puertos 80/443/22 permitidos

---

## What Went Wrong

1. **No se previó la necesidad de swap** para builds en VPS pequeño
2. **Múltiples reinicios** causaron pérdida de tiempo y estado
3. **SSH intermitente** durante OOM dificultó diagnóstico remoto
4. **Security Group de Lightsail** no configurado para puerto 443 (HTTPS público bloqueado)
5. **Falta de timeouts** en scripts de deploy causaron "hangs" aparentes

---

## Action Items

### P0 - Crítico (Implementar antes del próximo despliegue)

| Item | Owner | Prioridad | Estado |
|------|-------|-----------|--------|
| Agregar swap de 1GB al `provision.sh` | DevOps | P0 | ✅ Implementado (03:12 UTC) |
| Verificar Security Group de Lightsail (puertos 80/443) | DevOps | P0 | ⚠️ Pendiente |
| Agregar timeouts a `docker compose down` (20s) | DevOps | P0 | ✅ Implementado |

### P1 - Alto (Mejorar resiliencia)

| Item | Owner | Prioridad | Estado |
|------|-------|-----------|--------|
| Agregar `restart: unless-stopped` a todos los servicios en docker-compose | DevOps | P1 | ✅ Ya implementado |
| Crear runbook de recuperación post-reboot (10 líneas) | SRE | P1 | 📝 Pendiente |
| Agregar healthcheck timeout más corto para detección temprana | DevOps | P1 | 📝 Pendiente |

### P2 - Medio (Optimización)

| Item | Owner | Prioridad | Estado |
|------|-------|-----------|--------|
| Considerar pre-built Docker images en registry | DevOps | P2 | 📝 Pendiente |
| Agregar alertas de memoria >80% | SRE | P2 | 📝 Pendiente |
| Documentar requisitos mínimos de VPS (512MB + 1GB swap) | Docs | P2 | 📝 Pendiente |

---

## Evidencia Clave

### Comandos Ejecutados

```bash
# Verificar OOM
sudo dmesg -T | egrep -i "oom|out of memory|killed process"

# Verificar reinicios
last -x reboot | head -n 10

# Verificar logs Docker
sudo journalctl -u docker --since "48 hours ago" | tail -n 300

# Verificar estado actual
sudo docker compose ps
curl -sS http://localhost:8000/health
```

### Outputs Críticos

**OOM Event #1 (00:38:09)**:
```
kernel: docker-compose invoked oom-killer
kernel: Out of memory: Killed process 2113 (docker-buildx) total-vm:1297524kB
kernel: Free swap = 0kB
```

**OOM Event #2 (01:09:37)**:
```
kernel: apt-extracttemp invoked oom-killer
kernel: Out of memory: Killed process 435 (networkd-dispat)
```

**Certificado SSL Obtenido (03:12:51)**:
```
luisa-caddy: {"level":"info","msg":"certificate obtained successfully","identifier":"luisa-agent.online"}
```

**Health Endpoint OK (03:12+)**:
```json
{
    "status": "healthy",
    "service": "luisa",
    "version": "2.0.0"
}
```

---

## Lecciones Aprendidas

1. **VPS pequeños (512MB) requieren swap para builds de Docker** - Sin swap, builds fallan con OOM
2. **Reinicios limpian estado** - Después del tercer reboot, el sistema quedó estable porque no había procesos residuales
3. **Security Groups son críticos** - HTTPS no funcionó públicamente aunque el certificado se obtuvo correctamente
4. **Timeouts previenen "hangs"** - `docker compose down --timeout 20` evita esperas infinitas
5. **Health checks funcionan** - El sistema se auto-recuperó después de que Docker completó el build

---

## Runbook de Recuperación (10 líneas)

```bash
# 1. Verificar swap
sudo swapon --show

# 2. Si no hay swap, crear (1GB)
sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile

# 3. Limpiar Docker si está colgado
sudo docker ps -aq | xargs -r sudo docker rm -f && sudo docker network prune -f

# 4. Reiniciar Docker si es necesario
sudo systemctl restart docker && sleep 5

# 5. Arrancar servicios
cd /opt/luisa && sudo docker compose up -d

# 6. Verificar health
curl -sS http://localhost:8000/health

# 7. Ver logs si falla
sudo docker compose logs backend --tail=200
```

---

**Documento generado**: 31 Dic 2025, 03:26 UTC  
**Autor**: Staff DevOps + SRE  
**Revisión**: Pendiente

