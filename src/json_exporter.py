"""Export weld extraction results to JSON."""

import json
from pathlib import Path
from typing import Any, Dict
from .weld_extractor import WeldExtractionResult


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle OCC shapes (not serializable)
        if hasattr(obj, 'IsNull'):
            return None
        return super().default(obj)


def export_to_json(result: WeldExtractionResult, output_path: str) -> str:
    """Export extraction results to JSON file."""
    data = result.to_dict()
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, cls=CustomEncoder)
    
    return str(output)
