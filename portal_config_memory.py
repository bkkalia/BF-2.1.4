# portal_config_memory.py
# Tracks successful portal configurations for optimized future runs

import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class PortalConfigMemory:
    """Manages portal configuration history and successful patterns."""
    
    def __init__(self, config_file="portal_config_history.json"):
        """Initialize portal config memory with file path."""
        self.config_file = config_file
        self.config_data = self._load_config()
    
    def _load_config(self):
        """Load portal configuration history from JSON file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Loaded portal config history from {self.config_file}")
                return data
            except Exception as e:
                logger.error(f"Error loading portal config history: {e}")
                return {}
        else:
            logger.info("No portal config history file found, starting fresh")
            return {}
    
    def _save_config(self):
        """Save portal configuration history to JSON file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved portal config history to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving portal config history: {e}")
            return False
    
    def get_portal_config(self, portal_name):
        """Get the last successful configuration for a portal."""
        return self.config_data.get(portal_name, {})
    
    def record_successful_config(self, portal_name, config_type, config_value, details=None):
        """
        Record a successful configuration for a portal.
        
        Args:
            portal_name: Name of the portal (from base_urls.csv)
            config_type: Type of config (e.g., 'locator', 'navigation', 'timeout')
            config_value: The successful configuration value
            details: Additional details about the success
        """
        if portal_name not in self.config_data:
            self.config_data[portal_name] = {
                "first_success": datetime.now().isoformat(),
                "last_success": datetime.now().isoformat(),
                "successful_configs": {},
                "success_count": 0
            }
        
        portal_data = self.config_data[portal_name]
        
        # Update config type history
        if config_type not in portal_data["successful_configs"]:
            portal_data["successful_configs"][config_type] = []
        
        # Add new successful config
        config_entry = {
            "value": config_value,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        
        # Keep only last 5 successful configs per type
        portal_data["successful_configs"][config_type].insert(0, config_entry)
        portal_data["successful_configs"][config_type] = portal_data["successful_configs"][config_type][:5]
        
        # Update metadata
        portal_data["last_success"] = datetime.now().isoformat()
        portal_data["success_count"] += 1
        
        self._save_config()
        logger.info(f"Recorded successful {config_type} for {portal_name}: {config_value}")
    
    def get_preferred_locator(self, portal_name, locator_type):
        """
        Get the most recently successful locator for a portal.
        
        Args:
            portal_name: Name of the portal
            locator_type: Type of locator (e.g., 'tenders_by_org', 'back_button')
        
        Returns:
            The most recent successful locator or None
        """
        portal_config = self.get_portal_config(portal_name)
        if not portal_config:
            return None
        
        locator_configs = portal_config.get("successful_configs", {}).get(f"locator_{locator_type}", [])
        if locator_configs:
            return locator_configs[0].get("value")
        
        return None
    
    def record_failure(self, portal_name, failure_type, details=None):
        """
        Record a failure for tracking purposes.
        
        Args:
            portal_name: Name of the portal
            failure_type: Type of failure encountered
            details: Additional failure details
        """
        if portal_name not in self.config_data:
            self.config_data[portal_name] = {
                "first_seen": datetime.now().isoformat(),
                "failures": {}
            }
        
        portal_data = self.config_data[portal_name]
        
        if "failures" not in portal_data:
            portal_data["failures"] = {}
        
        if failure_type not in portal_data["failures"]:
            portal_data["failures"][failure_type] = []
        
        failure_entry = {
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        
        # Keep only last 10 failures per type
        portal_data["failures"][failure_type].insert(0, failure_entry)
        portal_data["failures"][failure_type] = portal_data["failures"][failure_type][:10]
        
        self._save_config()
    
    def get_statistics(self, portal_name):
        """Get statistics for a portal."""
        portal_config = self.get_portal_config(portal_name)
        if not portal_config:
            return None
        
        return {
            "success_count": portal_config.get("success_count", 0),
            "first_success": portal_config.get("first_success"),
            "last_success": portal_config.get("last_success"),
            "config_types": list(portal_config.get("successful_configs", {}).keys())
        }
    
    def export_config_summary(self, output_file="portal_config_summary.txt"):
        """Export a human-readable summary of portal configurations."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("PORTAL CONFIGURATION MEMORY SUMMARY\n")
                f.write("=" * 80 + "\n\n")
                
                for portal_name, portal_data in self.config_data.items():
                    f.write(f"\nPortal: {portal_name}\n")
                    f.write("-" * 80 + "\n")
                    f.write(f"Success Count: {portal_data.get('success_count', 0)}\n")
                    f.write(f"Last Success: {portal_data.get('last_success', 'N/A')}\n")
                    
                    successful_configs = portal_data.get("successful_configs", {})
                    if successful_configs:
                        f.write(f"\nSuccessful Configurations:\n")
                        for config_type, configs in successful_configs.items():
                            f.write(f"  {config_type}:\n")
                            for config in configs[:3]:  # Show top 3
                                f.write(f"    - {config.get('value')} (at {config.get('timestamp')})\n")
                    
                    failures = portal_data.get("failures", {})
                    if failures:
                        f.write(f"\nRecent Failures:\n")
                        for failure_type, failure_list in failures.items():
                            f.write(f"  {failure_type}: {len(failure_list)} occurrences\n")
                    
                    f.write("\n")
                
            logger.info(f"Exported portal config summary to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error exporting config summary: {e}")
            return False


# Global instance
_portal_memory = None

def get_portal_memory():
    """Get or create the global portal memory instance."""
    global _portal_memory
    if _portal_memory is None:
        _portal_memory = PortalConfigMemory()
    return _portal_memory
