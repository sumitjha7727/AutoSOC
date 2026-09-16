"""
Configuration settings loader for SOC Automation System
"""
import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any

class Config:
    """Load and manage configuration from YAML file"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config_data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            return config if config else {}
        except FileNotFoundError:
            print(f"[Config] Config file not found: {self.config_file}")
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation path"""
        keys = key.split('.')
        value = self.config_data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        
        return value if value is not None else default
    
    def get_app_config(self) -> Dict[str, Any]:
        """Get application config"""
        return self.get('app', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database config"""
        return self.get('database', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging config"""
        return self.get('logging', {})
    
    def get_mock_mode(self) -> bool:
        """Check if mock mode is enabled"""
        return self.get('mock_mode.enabled', True)
    
    def __repr__(self) -> str:
        return f"<Config: {self.config_file}>"


# Create global config instance
config = Config("config.yaml")