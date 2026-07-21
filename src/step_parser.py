"""STEP file parser — parse AP214/AP242 STEP files into structured data."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path


@dataclass
class STEPEntity:
    """A single STEP entity: #id=KEYWORD(...)"""
    id: int
    keyword: str
    raw_args: str
    line_no: int


@dataclass
class Product:
    """PRODUCT entity"""
    entity_id: int
    product_id: str
    name: str
    description: str
    frame_ids: List[int]


@dataclass
class ProductDefinition:
    """PRODUCT_DEFINITION entity"""
    entity_id: int
    definition_id: str
    description: str
    frame_id: int  # reference to PRODUCT_DEFINITION_FORMATION
    frame_type_id: int


@dataclass
class NextAssemblyUsageOccurrence:
    """NEXT_ASSEMBLY_USAGE_OCCURRENCE — assembly tree edge"""
    entity_id: int
    name: str
    description: str
    parent_id: int     # reference to PRODUCT_DEFINITION (relating)
    child_id: int      # reference to PRODUCT_DEFINITION (related)
    reference_id: str


@dataclass
class ShapeRepresentation:
    """SHAPE_DEFINITION_REPRESENTATION mapping"""
    entity_id: int
    definition_id: int  # ref to PRODUCT_DEFINITION_SHAPE
    representation_id: int  # ref to REPRESENTATION (geometry)


@dataclass
class StepAssembly:
    """Complete parsed assembly structure"""
    products: Dict[int, Product] = field(default_factory=dict)
    product_definitions: Dict[int, ProductDefinition] = field(default_factory=dict)
    usages: List[NextAssemblyUsageOccurrence] = field(default_factory=list)
    shape_reps: List[ShapeRepresentation] = field(default_factory=list)
    weld_products: List[int] = field(default_factory=list)
    
    def get_product_by_id(self, pid: str) -> Optional[Product]:
        for p in self.products.values():
            if p.product_id == pid:
                return p
        return None


def parse_entity_id(text: str) -> Optional[int]:
    """Extract entity ID from '#123' format"""
    m = re.match(r'#(\d+)', text.strip())
    return int(m.group(1)) if m else None


def parse_references(text: str) -> List[int]:
    """Extract all entity references from text like '(#13,#299)'"""
    return [int(x) for x in re.findall(r'#(\d+)', text)]


def parse_strings(text: str) -> List[str]:
    """Extract all single-quoted strings from text"""
    return re.findall(r"'([^']*)'", text)


class StepParser:
    """Parse ISO 10303-21 STEP files (AP214/AP242)"""
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.entities: Dict[int, STEPEntity] = {}
        self.assembly = StepAssembly()
        self._raw_lines: List[str] = []
        
    def parse(self) -> StepAssembly:
        """Parse the STEP file and return assembly structure."""
        with open(self.filepath, 'r', encoding='utf-8', errors='replace') as f:
            self._raw_lines = f.readlines()
        
        # First pass: parse all entities
        for i, line in enumerate(self._raw_lines):
            line = line.strip()
            if not line or line.startswith('/') or line.startswith('ISO-') or \
               line.startswith('HEADER') or line.startswith('DATA') or \
               line.startswith('ENDSEC') or line.startswith('END-ISO'):
                continue
            
            m = re.match(r'#(\d+)=(\w+)\((.*)\)\s*;', line)
            if m:
                eid = int(m.group(1))
                keyword = m.group(2)
                # Handle nested parentheses
                args = line[line.index('(')+1:line.rindex(')')]
                self.entities[eid] = STEPEntity(
                    id=eid, keyword=keyword, 
                    raw_args=args, line_no=i+1
                )
        
        # Second pass: build assembly
        for eid, ent in self.entities.items():
            if ent.keyword == 'PRODUCT':
                strings = parse_strings(ent.raw_args)
                refs = parse_references(ent.raw_args)
                pid = strings[0] if len(strings) > 0 else ''
                name = strings[1] if len(strings) > 1 else ''
                desc = strings[2] if len(strings) > 2 else ''
                prod = Product(eid, pid, name, desc, refs)
                self.assembly.products[eid] = prod
                
                # Check if this is a weld product
                if '_WLD' in pid or 'WLD' in pid:
                    self.assembly.weld_products.append(eid)
            
            elif ent.keyword == 'PRODUCT_DEFINITION':
                strings = parse_strings(ent.raw_args)
                refs = parse_references(ent.raw_args)
                pd = ProductDefinition(
                    entity_id=eid,
                    definition_id=strings[0] if strings else '',
                    description=strings[1] if len(strings) > 1 else '',
                    frame_id=refs[0] if len(refs) > 0 else 0,
                    frame_type_id=refs[1] if len(refs) > 1 else 0
                )
                self.assembly.product_definitions[eid] = pd
            
            elif ent.keyword == 'NEXT_ASSEMBLY_USAGE_OCCURRENCE':
                strings = parse_strings(ent.raw_args)
                refs = parse_references(ent.raw_args)
                usage = NextAssemblyUsageOccurrence(
                    entity_id=eid,
                    name=strings[0] if strings else '',
                    description=strings[1] if len(strings) > 1 else '',
                    parent_id=refs[0] if len(refs) > 0 else 0,
                    child_id=refs[1] if len(refs) > 1 else 0,
                    reference_id=strings[2] if len(strings) > 2 else ''
                )
                self.assembly.usages.append(usage)
        
        return self.assembly
    
    def get_entity(self, eid: int) -> Optional[STEPEntity]:
        return self.entities.get(eid)
    
    def get_entity_line(self, eid: int) -> Optional[str]:
        ent = self.entities.get(eid)
        if ent:
            return self._raw_lines[ent.line_no - 1].rstrip()
        return None
    
    def find_weld_occurrences(self) -> List[NextAssemblyUsageOccurrence]:
        """Find NEXT_ASSEMBLY_USAGE_OCCURRENCE entries related to welding."""
        return [u for u in self.assembly.usages 
                if 'WELD' in u.name.upper() or 'WELD' in u.description.upper()]
    
    def summarize(self) -> str:
        """Print summary of the assembly."""
        a = self.assembly
        lines = [
            f"File: {self.filepath.name}",
            f"Total entities: {len(self.entities)}",
            f"Products: {len(a.products)}",
            f"Product Definitions: {len(a.product_definitions)}",
            f"Assembly Usages: {len(a.usages)}",
            f"Weld Products: {len(a.weld_products)}",
            "",
            "Weld Products:",
        ]
        for eid in a.weld_products:
            p = a.products.get(eid)
            if p:
                lines.append(f"  #{eid}: {p.product_id} — {p.name} {p.description}")
        
        lines.append("")
        lines.append("Weld Occurrences:")
        for u in self.find_weld_occurrences():
            lines.append(f"  #{u.entity_id}: {u.name} — parent=#{u.parent_id} child=#{u.child_id}")
        
        return '\n'.join(lines)


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'data/4628964.stp'
    parser = StepParser(path)
    parser.parse()
    print(parser.summarize())
