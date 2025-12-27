#!/usr/bin/env python3
"""
Script para preparar placeholders de imágenes y mostrar instrucciones
"""

from pathlib import Path

CATALOG_DIR = Path(__file__).parent.parent / "assets" / "catalog"

# Mapeo de imágenes según las descripciones proporcionadas
IMAGES_TO_PREPARE = {
    "I001": {
        "folder": "I001_ssgemsy_sg8802e_maquina_completa",
        "name": "SSGEMSY SG8802E",
        "status": "tiene placeholder"
    },
    "I002": {
        "folder": "I002_union_un300_maquina_completa",
        "name": "UNION UN300",
        "status": "falta imagen"
    },
    "I003": {
        "folder": "I003_kansew_ks653_maquina_completa",
        "name": "KANSEW KS653",
        "status": "falta imagen"
    },
    "I004": {
        "folder": "I004_singer_s0105_fileteadora_familiar",
        "name": "SINGER S0105",
        "status": "falta imagen"
    },
    "I005": {
        "folder": "I005_kingter_fileteadora_familiar",
        "name": "KINGTER Fileteadora",
        "status": "falta imagen"
    },
    "I006": {
        "folder": "I006_singer_heavy_duty_maquina_completa",
        "name": "SINGER Heavy Duty",
        "status": "falta imagen"
    }
}

def check_and_prepare():
    print("🔍 Verificando estructura del catálogo...\n")
    
    missing_images = []
    
    for image_id, info in IMAGES_TO_PREPARE.items():
        folder_path = CATALOG_DIR / info["folder"]
        
        if not folder_path.exists():
            print(f"⚠️  {image_id} ({info['name']}): Carpeta no existe")
            continue
        
        # Buscar imagen
        has_image = False
        for ext in ["png", "jpg", "jpeg", "webp"]:
            img_file = folder_path / f"image_1.{ext}"
            if img_file.exists():
                size = img_file.stat().st_size
                if size > 1000:  # Más de 1KB = imagen real
                    has_image = True
                    print(f"✅ {image_id} ({info['name']}): Tiene imagen ({img_file.name}, {size} bytes)")
                    break
                else:
                    print(f"⚠️  {image_id} ({info['name']}): Tiene placeholder de texto")
            else:
                has_image = False
        
        if not has_image:
            missing_images.append((image_id, info))
            print(f"❌ {image_id} ({info['name']}): NO tiene imagen")
    
    print("\n" + "="*60)
    print("📋 RESUMEN:")
    print("="*60)
    print(f"❌ Imágenes faltantes: {len(missing_images)}\n")
    
    if missing_images:
        print("📁 Estructura lista para recibir imágenes:")
        print("")
        for image_id, info in missing_images:
            folder_path = CATALOG_DIR / info["folder"]
            img_path = folder_path / "image_1.png"
            print(f"  {image_id}: {info['name']}")
            print(f"    → {img_path}")
            print("")
        
        print("💡 Para agregar las imágenes:")
        print("  1. Coloca las imágenes PNG/JPG en las rutas indicadas arriba")
        print("  2. O indica la ruta donde están las imágenes y las copiaré")
        print("  3. O arrastra las imágenes a las carpetas correspondientes")
    
    return len(missing_images)

if __name__ == "__main__":
    missing_count = check_and_prepare()
    exit(0 if missing_count == 0 else 1)

