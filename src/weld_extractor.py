"""Weld feature extractor — extract weld information from STEP models.

Pipeline:
1. Parse STEP assembly tree → identify weld products and occurrences
2. Load geometry via pythonocc-core → compute weld features
3. Return structured weld data

Extracted features per weld:
  - ID / name
  - Position (center, start/end points)
  - Length
  - Adjacent parts (part IDs, thickness T1/T2)
  - Joint type (butt/fillet/lap)
  - Gap (clearance between parts)
  - Distance to nearest neighboring weld
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import math
import numpy as np

from .step_parser import StepParser, StepAssembly, Product
from . import geometry_utils


@dataclass
class WeldFeature:
    """Extracted features for a single weld."""
    id: str
    name: str = ''
    
    # Position
    center: Tuple[float, float, float] = (0, 0, 0)
    start_point: Optional[Tuple[float, float, float]] = None
    end_point: Optional[Tuple[float, float, float]] = None
    
    # Dimensions
    length: float = 0.0
    leg_length: float = 0.0        # fillet leg length (if applicable)
    throat_thickness: float = 0.0  # effective throat
    
    # Adjacent parts
    part1_id: str = ''
    part2_id: str = ''
    T1: float = 0.0   # base material thickness, part 1 (mm)
    T2: float = 0.0   # base material thickness, part 2 (mm)
    
    # Joint properties
    joint_type: str = 'unknown'   # butt / fillet / lap / spot
    gap: float = 0.0              # gap between parts (mm)
    
    # Weld process
    process_type: str = 'unknown'  # GMAW / SMAW / SAW / etc.
    
    # Spatial context
    distance_to_prev_weld: float = 0.0  # pitch / spacing
    
    # Raw data
    occ_shape = None  # OCC TopoDS_Shape reference
    source: str = ''  # 'step_entity', 'vlm_parsed', 'manual'


@dataclass 
class WeldExtractionResult:
    """Complete weld extraction result."""
    model_name: str = ''
    total_parts: int = 0
    total_welds: int = 0
    welds: List[WeldFeature] = field(default_factory=list)
    part_thicknesses: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            'model_name': self.model_name,
            'total_parts': self.total_parts,
            'total_welds': self.total_welds,
            'notes': self.notes,
            'welds': [w.__dict__ for w in self.welds],
            'part_thicknesses': self.part_thicknesses,
        }


class WeldExtractor:
    """Extract weld features from a STEP model."""
    
    def __init__(self, step_path: str):
        self.step_path = step_path
        self.parser = StepParser(step_path)
        self.assembly = self.parser.parse()
        self.result = WeldExtractionResult()
        self._shapes: Dict[int, any] = {}  # entity_id -> OCC shape
        
    def extract(self) -> WeldExtractionResult:
        """Run extraction pipeline."""
        self.result.model_name = self.parser.filepath.stem
        
        # Count total parts
        self.result.total_parts = len(self.assembly.products)
        
        # Extract weld products
        self._extract_weld_products()
        
        # Try to load geometry and compute features
        self._try_load_geometry()
        
        # Compute distances between welds
        self._compute_weld_spacing()
        
        self.result.total_welds = len(self.result.welds)
        return self.result
    
    def _extract_weld_products(self):
        """Extract weld information from STEP assembly tree."""
        for eid in self.assembly.weld_products:
            p = self.assembly.products.get(eid)
            if not p:
                continue
            
            weld = WeldFeature(
                id=p.product_id,
                name=f"{p.name} {p.description}".strip(),
                source='step_entity',
            )
            
            # Find adjacent parts from assembly usages
            for usage in self.parser.find_weld_occurrences():
                if usage.child_id == eid or usage.parent_id == eid:
                    weld.name = f"{weld.name} [{usage.name}]"
            
            self.result.welds.append(weld)
        
        # Also look for explicit welding occurrences
        weld_occurrences = self.parser.find_weld_occurrences()
        for u in weld_occurrences:
            # Check if this references parts not already captured
            # Find the product IDs
            parent_prod = self._find_product_for_definition(u.parent_id)
            child_prod = self._find_product_for_definition(u.child_id)
            
            if parent_prod and child_prod:
                # Check if this pair is already covered
                existing = [w for w in self.result.welds 
                          if parent_prod.product_id in w.part1_id or 
                             parent_prod.product_id in w.part2_id]
                if not existing:
                    weld = WeldFeature(
                        id=f"WELD_{u.entity_id}",
                        name=f"{u.name} - {parent_prod.name} → {child_prod.name}",
                        part1_id=parent_prod.product_id,
                        part2_id=child_prod.product_id,
                        source='step_entity',
                    )
                    self.result.welds.append(weld)
    
    def _find_product_for_definition(self, def_id: int) -> Optional[Product]:
        """Find the PRODUCT that owns a PRODUCT_DEFINITION."""
        pd = self.assembly.product_definitions.get(def_id)
        if not pd:
            return None
        # Usually PRODUCT references come through PRODUCT_DEFINITION_FORMATION
        for prod in self.assembly.products.values():
            if pd.frame_id in prod.frame_ids:
                return prod
        return None
    
    def _try_load_geometry(self):
        """Try to load STEP geometry and compute weld features."""
        try:
            from OCC.Core.STEPControl import STEPControl_Reader
            from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Edge, TopoDS_Face
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
            from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Circle
            
            reader = STEPControl_Reader()
            status = reader.ReadFile(self.step_path)
            
            if status != 1:  # IFSelect_RetDone
                self.result.notes.append("WARNING: Failed to read STEP geometry with OCC")
                return
            
            # Transfer all roots
            reader.TransferRoots()
            nshapes = reader.NbShapes()
            self.result.notes.append(f"Loaded {nshapes} shapes from STEP")
            
            # For each shape, try to extract weld features
            for i in range(1, nshapes + 1):
                shape = reader.Shape(i)
                if shape.IsNull():
                    continue
                
                # Get bounding box
                try:
                    bbox = geometry_utils.bounding_box(shape)
                    center = geometry_utils.bbox_center(bbox)
                    dims = geometry_utils.bbox_dimensions(bbox)
                    
                    # Count faces and edges
                    face_count = 0
                    edge_count = 0
                    exp_face = TopExp_Explorer(shape, TopAbs_FACE)
                    while exp_face.More():
                        face_count += 1
                        exp_face.Next()
                    exp_edge = TopExp_Explorer(shape, TopAbs_EDGE)
                    while exp_edge.More():
                        edge_count += 1
                        exp_edge.Next()
                    
                    # If we have corresponding weld products, update them
                    if i <= len(self.result.welds):
                        w = self.result.welds[i-1]
                        w.center = center
                        w.occ_shape = shape
                        
                    self.result.notes.append(
                        f"  Shape #{i}: bbox=({dims[0]:.1f}x{dims[1]:.1f}x{dims[2]:.1f}) "
                        f"faces={face_count} edges={edge_count}"
                    )
                except Exception as e:
                    self.result.notes.append(f"  Shape #{i}: error computing bbox: {e}")
                    
        except ImportError:
            self.result.notes.append("pythonocc-core not available — geometry features limited")
        except Exception as e:
            self.result.notes.append(f"Geometry loading error: {e}")
    
    def _compute_weld_spacing(self):
        """Compute distances between consecutive welds."""
        if len(self.result.welds) < 2:
            return
        
        # Sort welds by some criterion (e.g., position along a path)
        centers = [(w.center[0], w.center[1], w.center[2]) for w in self.result.welds]
        
        for i in range(1, len(self.result.welds)):
            d = geometry_utils.distance_between_points(centers[i-1], centers[i])
            self.result.welds[i].distance_to_prev_weld = d
