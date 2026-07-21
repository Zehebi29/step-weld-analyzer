"""Integrate VLM drawing analysis into the weld extraction pipeline."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .weld_extractor import WeldFeature, WeldExtractionResult


@dataclass
class VlmWeld:
    """Weld information from VLM drawing analysis."""
    weld_id: str
    weld_type: str
    process: str = ''
    length_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    angle_deg: Optional[float] = None
    root_gap_mm: Optional[float] = None
    root_face_mm: Optional[float] = None
    part1: str = ''
    part2: str = ''
    T1_mm: Optional[float] = None
    T2_mm: Optional[float] = None
    position: str = ''
    notes: str = ''


class VlmDrawingIntegrator:
    """Integrate VLM-analyzed drawing data with STEP extraction results."""
    
    def __init__(self, vlm_json_path: str):
        with open(vlm_json_path, 'r', encoding='utf-8') as f:
            self.vlm_data = json.load(f)
    
    def integrate(self, result: WeldExtractionResult) -> WeldExtractionResult:
        """Merge VLM data into extraction result."""
        vlm_welds = self._collect_all_welds()
        
        for vw in vlm_welds:
            # Check if this weld is already in the result
            existing = [w for w in result.welds 
                       if vw.weld_id in w.id or 
                       (vw.part1 and vw.part1[:8] in w.part1_id) or
                       (vw.part1 and vw.part1[:8] in w.part2_id)]
            
            if existing:
                # Update existing weld with VLM data
                ew = existing[0]
                if not ew.joint_type or ew.joint_type == 'unknown':
                    ew.joint_type = vw.weld_type
                if not ew.process_type or ew.process_type == 'unknown':
                    ew.process_type = vw.process
                if not ew.length and vw.length_mm:
                    ew.length = vw.length_mm
                if not ew.T1 and vw.T1_mm:
                    ew.T1 = vw.T1_mm
                if not ew.T2 and vw.T2_mm:
                    ew.T2 = vw.T2_mm
                if not ew.gap and vw.root_gap_mm:
                    ew.gap = vw.root_gap_mm
                if vw.notes:
                    ew.name = f"{ew.name} | {vw.notes}"
            else:
                # Add as a new weld entry from VLM
                nw = WeldFeature(
                    id=vw.weld_id,
                    name=f"{vw.weld_type} {vw.position} [{vw.notes}]",
                    length=vw.length_mm or 0,
                    leg_length=vw.thickness_mm or 0,
                    T1=vw.T1_mm or 0,
                    T2=vw.T2_mm or 0,
                    gap=vw.root_gap_mm or 0,
                    joint_type=vw.weld_type,
                    process_type=vw.process,
                    source='vlm_drawing',
                )
                result.welds.append(nw)
        
        result.total_welds = len(result.welds)
        result.notes.append(f"Integrated {len(vlm_welds)} weld entries from VLM drawing analysis")
        
        return result
    
    def _collect_all_welds(self) -> List[VlmWeld]:
        """Collect all unique welds from all drawing sheets."""
        welds: Dict[str, VlmWeld] = {}
        
        for sheet_name, data in self.vlm_data.items():
            if not isinstance(data, dict):
                continue
            
            dwg = data.get('drawing_info', {})
            sheet_welds = data.get('welds', []) or []
            
            for w in sheet_welds:
                if not isinstance(w, dict):
                    continue
                
                wid = w.get('weld_id', f'{sheet_name}_weld')
                
                if wid in welds:
                    # Merge: prefer non-null values
                    existing = welds[wid]
                    for key in ['weld_type', 'process', 'part1', 'part2', 'position', 'notes']:
                        if not getattr(existing, key) and w.get(key):
                            setattr(existing, key, w[key])
                    for key in ['length_mm', 'thickness_mm', 'angle_deg', 
                               'root_gap_mm', 'root_face_mm', 'T1_mm', 'T2_mm']:
                        if getattr(existing, key) is None and w.get(key) is not None:
                            try:
                                setattr(existing, key, float(w[key]))
                            except (ValueError, TypeError):
                                pass
                else:
                    vw = VlmWeld(
                        weld_id=wid,
                        weld_type=w.get('type', ''),
                        process=w.get('process', ''),
                        length_mm=self._safe_float(w.get('length_mm')),
                        thickness_mm=self._safe_float(w.get('thickness_mm')),
                        angle_deg=self._safe_float(w.get('angle_deg')),
                        root_gap_mm=self._safe_float(w.get('root_gap_mm')),
                        root_face_mm=self._safe_float(w.get('root_face_mm')),
                        part1=w.get('part1', ''),
                        part2=w.get('part2', ''),
                        T1_mm=self._safe_float(w.get('T1_mm')),
                        T2_mm=self._safe_float(w.get('T2_mm')),
                        position=w.get('position', ''),
                        notes=w.get('notes', ''),
                    )
                    welds[wid] = vw
        
        return list(welds.values())
    
    @staticmethod
    def _safe_float(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
