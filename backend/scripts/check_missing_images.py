#!/usr/bin/env python3
"""
Script para verificar qué imágenes faltan en el catálogo
"""

import json
from pathlib import Path

CATALOG_DIR = Path(__file__).parent.parent / "assets" / "catalog"

def check_missing_images():
    """Verifica qué imágenes faltan en el catálogo"""
    print("🔍 Verificando imágenes en el catálogo...\n")
    
    missing = []
    found = []
    placeholders = []
    
    for folder in sorted(CATALOG_DIR.iterdir()):
        if not folder.is_dir() or not folder.name.startswith("I"):
            continue
        
        image_id = folder.name.split("_")[0]
        meta_file = folder / "meta.json"
        
        if not meta_file.exists():
            print(f"⚠️  {image_id}: No tiene meta.json")
            continue
        
        # Buscar imagen
        image_found = False
        image_path = None
        
        for ext in ["png", "jpg", "jpeg", "webp"]:
            img_file = folder / f"image_1.{ext}"
            if img_file.exists():
                image_path = img_file
                image_found = True
                break
        
        if image_found:
            # Verificar si es placeholder
            try:
                with open(image_path, 'rb') as f:
                    header = f.read(20)
                    if header.startswith(b'# Placeholder') or header.startswith(b'#Placeholder'):
                        placeholders.append((image_id, image_path))
                        print(f"⚠️  {image_id}: Tiene placeholder de texto")
                    else:
                        found.append((image_id, image_path))
                        print(f"✅ {image_id}: Tiene imagen válida ({image_path.name})")
            except Exception as e:
                print(f"❌ {image_id}: Error leyendo imagen: {e}")
        else:
            missing.append(image_id)
            print(f"❌ {image_id}: NO tiene imagen")
    
    print("\n" + "="*50)
    print("📊 RESUMEN:")
    print("="*50)
    print(f"✅ Imágenes encontradas: {len(found)}")
    print(f"⚠️  Placeholders encontrados: {len(placeholders)}")
    print(f"❌ Imágenes faltantes: {len(missing)}")
    
    if missing:
        print("\n📋 Imágenes que necesitas agregar:")
        for img_id in missing:
            folder = CATALOG_DIR / f"{img_id}_*"
            folders = list(CATALOG_DIR.glob(f"{img_id}_*"))
            if folders:
                print(f"  • {folders[0].name}/image_1.png (o .jpg/.jpeg/.webp)")
    
    if placeholders:
        print("\n⚠️  Placeholders que necesitas reemplazar:")
        for img_id, path in placeholders:
            print(f"  • {path}")
    
    return len(missing) + len(placeholders) == 0

if __name__ == "__main__":
    all_ok = check_missing_images()
    exit(0 if all_ok else 1)

