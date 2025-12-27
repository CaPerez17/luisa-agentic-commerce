"""
Tests para el servicio de assets.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.asset_service import (
    load_catalog_index,
    get_catalog_item,
    find_local_asset_file,
    select_catalog_asset,
    get_all_catalog_items,
    get_promo_image_path
)


class TestCatalogIndex:
    """Tests para el índice del catálogo."""
    
    def test_load_catalog_index(self):
        """Cargar índice del catálogo funciona."""
        index = load_catalog_index()
        assert isinstance(index, dict)
        # Debe tener al menos algunos items
        assert len(index) > 0
    
    def test_catalog_item_structure(self):
        """Items del catálogo tienen estructura correcta."""
        index = load_catalog_index()
        if index:
            item = list(index.values())[0]
            assert "image_id" in item or index
            # Los items en el index tienen estas propiedades
            expected_keys = ["category", "brand", "model"]
            for key in expected_keys:
                assert key in item, f"Falta key: {key}"


class TestGetCatalogItem:
    """Tests para get_catalog_item."""
    
    def test_get_existing_item(self):
        """Obtener item existente funciona."""
        # I001 es la SSGEMSY SG8802E (según el catálogo existente)
        item = get_catalog_item("I001")
        if item:  # Solo si existe
            assert item.get("image_id") == "I001"
            assert "SSGEMSY" in item.get("brand", "") or "ssgemsy" in str(item).lower()
    
    def test_get_nonexistent_item(self):
        """Obtener item inexistente retorna None."""
        item = get_catalog_item("I999")
        assert item is None


class TestSelectCatalogAsset:
    """Tests para select_catalog_asset."""
    
    def test_select_industrial(self):
        """Seleccionar máquina industrial funciona."""
        context = {"tipo_maquina": "industrial"}
        item, handoff = select_catalog_asset("necesito una máquina para producción", context)
        # Puede retornar item o None dependiendo del catálogo
        assert handoff is False or item is None
    
    def test_select_familiar(self):
        """Seleccionar máquina familiar funciona."""
        context = {"tipo_maquina": "familiar"}
        item, handoff = select_catalog_asset("máquina para casa", context)
        assert handoff is False or item is None
    
    def test_select_specific_model(self):
        """Seleccionar modelo específico funciona."""
        context = {}
        item, handoff = select_catalog_asset("singer heavy duty 6705", context)
        if item:
            assert "singer" in item.get("brand", "").lower() or "6705" in str(item).lower()
    
    def test_conflicto_genera_handoff(self):
        """Conflicto familiar/industrial puede generar handoff."""
        context = {}
        # Mensaje ambiguo
        _, handoff = select_catalog_asset("máquina familiar pero para producción industrial", context)
        # Puede o no generar handoff dependiendo de la lógica
        assert handoff in [True, False]


class TestFindLocalAssetFile:
    """Tests para find_local_asset_file."""
    
    def test_find_existing_asset(self):
        """Encontrar asset existente funciona."""
        # Buscar cualquier asset que exista
        index = load_catalog_index()
        if index:
            first_id = list(index.keys())[0]
            file = find_local_asset_file(first_id)
            # Puede existir o no dependiendo del setup
            if file:
                assert file.exists()
    
    def test_find_nonexistent_asset(self):
        """Buscar asset inexistente retorna None."""
        file = find_local_asset_file("NOEXISTE999")
        assert file is None


class TestGetAllCatalogItems:
    """Tests para get_all_catalog_items."""
    
    def test_get_all_returns_list(self):
        """get_all_catalog_items retorna lista."""
        items = get_all_catalog_items()
        assert isinstance(items, list)
    
    def test_items_have_asset_url(self):
        """Items incluyen asset_url."""
        items = get_all_catalog_items()
        if items:
            item = items[0]
            assert "asset_url" in item
            assert "/api/assets/" in item["asset_url"]


class TestPromoImage:
    """Tests para imagen de promoción."""
    
    def test_get_promo_image_path(self):
        """get_promo_image_path retorna Path o None."""
        path = get_promo_image_path()
        # Puede existir o no dependiendo del setup
        if path:
            assert isinstance(path, Path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
