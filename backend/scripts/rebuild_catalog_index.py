#!/usr/bin/env python3
"""
Catalog Index Manager - Regenera el índice completo del catálogo
Ejecutar: python scripts/rebuild_catalog_index.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Ajustar paths según desde dónde se ejecute
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
CATALOG_DIR = BACKEND_DIR / "assets" / "catalog"
INDEX_FILE = BACKEND_DIR / "assets" / "catalog_index.json"


def extract_slug_from_folder(folder_name: str) -> str:
    """Extrae el slug del nombre de la carpeta (sin el prefijo Ixxx_)"""
    if "_" in folder_name:
        parts = folder_name.split("_", 1)
        if len(parts) > 1:
            return parts[1]
    return folder_name


def validate_item(item_data: dict, image_id: str, folder_name: str) -> Tuple[bool, Optional[str]]:
    """Valida un item antes de incluirlo en el índice"""
    if not item_data.get("image_id"):
        return False, "falta image_id"
    
    if item_data["image_id"] != image_id:
        return False, f"image_id no coincide: esperado {image_id}, encontrado {item_data['image_id']}"
    
    if not item_data.get("category"):
        return False, "category vacía"
    
    if not item_data.get("represents"):
        return False, "represents vacío"
    
    priority = item_data.get("priority", 0)
    if not isinstance(priority, (int, float)):
        return False, f"priority no es numérico: {priority}"
    
    return True, None


def scan_catalog() -> Tuple[List[Dict], List[Dict]]:
    """Escanea el catálogo completo y retorna items válidos e inválidos"""
    valid_items = []
    invalid_items = []
    
    if not CATALOG_DIR.exists():
        print(f"⚠️  Directorio de catálogo no encontrado: {CATALOG_DIR}")
        return valid_items, invalid_items
    
    for folder in sorted(CATALOG_DIR.iterdir()):
        if not folder.is_dir():
            continue
        
        folder_name = folder.name
        
        # Solo procesar carpetas que empiecen con I
        if not folder_name.startswith("I"):
            continue
        
        # Extraer image_id del nombre de la carpeta
        image_id = None
        if "_" in folder_name:
            image_id = folder_name.split("_")[0]
        else:
            invalid_items.append({
                "image_id": folder_name,
                "folder": folder_name,
                "reason": "formato de nombre inválido (debe ser Ixxx_slug)"
            })
            continue
        
        # Buscar meta.json
        meta_path = folder / "meta.json"
        if not meta_path.exists():
            invalid_items.append({
                "image_id": image_id,
                "folder": folder_name,
                "reason": "meta.json no encontrado"
            })
            continue
        
        # Leer meta.json
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
        except json.JSONDecodeError as e:
            invalid_items.append({
                "image_id": image_id,
                "folder": folder_name,
                "reason": f"Error parseando JSON: {e}"
            })
            continue
        except Exception as e:
            invalid_items.append({
                "image_id": image_id,
                "folder": folder_name,
                "reason": f"Error leyendo meta.json: {e}"
            })
            continue
        
        # Validar item
        is_valid, error_msg = validate_item(meta_data, image_id, folder_name)
        if not is_valid:
            invalid_items.append({
                "image_id": image_id,
                "folder": folder_name,
                "reason": error_msg
            })
            continue
        
        # Extraer solo campos necesarios
        slug = extract_slug_from_folder(folder_name)
        path = f"catalog/{folder_name}/"
        
        item = {
            "image_id": meta_data["image_id"],
            "slug": slug,
            "path": path,
            "category": meta_data.get("category", ""),
            "brand": meta_data.get("brand", ""),
            "model": meta_data.get("model", ""),
            "represents": meta_data.get("represents", ""),
            "conversation_role": meta_data.get("conversation_role", ""),
            "priority": int(meta_data.get("priority", 0)),
            "send_when_customer_says": meta_data.get("send_when_customer_says", [])
        }
        
        valid_items.append(item)
    
    return valid_items, invalid_items


def generate_index():
    """Genera el índice completo del catálogo"""
    valid_items, invalid_items = scan_catalog()
    
    # Ordenar: primero por priority (desc), luego por image_id (asc)
    valid_items.sort(key=lambda x: (-x["priority"], x["image_id"]))
    
    # Generar índice
    index = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_items": len(valid_items),
        "items": valid_items
    }
    
    # Guardar índice
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    # Imprimir resultados
    print("=" * 60)
    print("CATALOG INDEX MANAGER - RESULTADO")
    print("=" * 60)
    print(f"\n✅ Total de imágenes indexadas: {len(valid_items)}")
    
    if valid_items:
        print(f"\n📋 Image IDs incluidos:")
        for item in valid_items:
            brand_model = f"{item.get('brand', '')} {item.get('model', '')}".strip()
            print(f"   {item['image_id']}: {brand_model} ({item['category']})")
    
    if invalid_items:
        print(f"\n⚠️  Image IDs excluidos: {len(invalid_items)}")
        for item in invalid_items:
            print(f"   {item['image_id']} ({item['folder']}): {item['reason']}")
    else:
        print(f"\n✅ No hay items excluidos")
    
    print("\n" + "=" * 60)
    print(f"Índice guardado en: {INDEX_FILE}")
    print("=" * 60)
    
    return len(valid_items), len(invalid_items)


if __name__ == "__main__":
    try:
        valid_count, invalid_count = generate_index()
        sys.exit(0 if invalid_count == 0 else 1)
    except Exception as e:
        print(f"❌ Error fatal: {e}", file=sys.stderr)
        sys.exit(1)

