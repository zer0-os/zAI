from typing import Dict, Type, Any
from wallet.adapters.base_adapter import BaseAdapter
from wallet.exceptions import AdapterError

class AdapterRegistry:
    """Manages wallet adapters and handles method routing"""
    
    def __init__(self):
        self._adapters: Dict[str, BaseAdapter] = {}
        
    def register(self, adapter: BaseAdapter) -> None:
        """Register a new adapter instance"""
        namespace = adapter.namespace
        if namespace in self._adapters:
            raise AdapterError(f"Adapter namespace '{namespace}' already registered")
        self._adapters[namespace] = adapter
        
    def get_adapter(self, namespace: str) -> BaseAdapter:
        """Get adapter by namespace"""
        if namespace not in self._adapters:
            raise AdapterError(f"No adapter found for namespace '{namespace}'")
        return self._adapters[namespace]
    
    def list_adapters(self) -> Dict[str, BaseAdapter]:
        """Return all registered adapters"""
        return self._adapters.copy() 