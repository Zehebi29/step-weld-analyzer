"""Step Weld Analyzer — 主入口

Usage:
    python -m src.main --step data/4628964.stp --output output/
    python -m src.main --step data/4628964.stp --excel output/welds.xlsx --json output/welds.json
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from .step_parser import StepParser
from .weld_extractor import WeldExtractor
from .excel_exporter import export_to_excel
from .json_exporter import export_to_json
from .vlm_integrator import VlmDrawingIntegrator


def parse_args():
    parser = argparse.ArgumentParser(
        description='STEP模型焊缝工艺信息解析工具'
    )
    parser.add_argument('--step', required=True,
                       help='STEP 模型文件路径')
    parser.add_argument('--output', default='./output',
                       help='输出目录（默认 ./output）')
    parser.add_argument('--excel',
                       help='Excel 输出路径（默认 output/welds.xlsx）')
    parser.add_argument('--json',
                       help='JSON 输出路径（默认 output/welds.json）')
    parser.add_argument('--summary', action='store_true', default=True,
                       help='打印摘要信息')
    parser.add_argument('--vlm-pdf', nargs='+',
                       help='VLM 解析的 PDF 二维图纸路径（待实现）')
    return parser.parse_args()


def main():
    args = parse_args()
    
    step_path = Path(args.step)
    if not step_path.exists():
        print(f"❌ STEP file not found: {step_path}")
        sys.exit(1)
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    excel_path = args.excel or str(output_dir / 'welds.xlsx')
    json_path = args.json or str(output_dir / 'welds.json')
    
    print(f"🔧 Step Weld Analyzer")
    print(f"   STEP: {step_path}")
    print(f"   Output: {output_dir}")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Phase 1: Parse STEP structure
    print("📋 Phase 1: Parsing STEP structure...")
    parser = StepParser(str(step_path))
    assembly = parser.parse()
    print(f"   Entities: {len(parser.entities)}")
    print(f"   Products: {len(assembly.products)}")
    print(f"   Usages: {len(assembly.usages)}")
    print(f"   Weld Products: {len(assembly.weld_products)}")
    
    if assembly.weld_products:
        print("\n   Weld Products:")
        for eid in assembly.weld_products:
            p = assembly.products.get(eid)
            if p:
                print(f"     #{eid}: {p.product_id}")
    
    # Phase 2: Extract weld features
    print("\n🔍 Phase 2: Extracting weld features...")
    extractor = WeldExtractor(str(step_path))
    result = extractor.extract()
    
    print(f"   Welds found: {result.total_welds}")
    for note in result.notes:
        print(f"   {note}")
    
    # Phase 2b: Integrate VLM drawing analysis (if available)
    vlm_json = output_dir / 'vlm_drawing_analysis.json'
    if vlm_json.exists():
        print(f"\n📐 Phase 2b: Integrating VLM drawing analysis...")
        integrator = VlmDrawingIntegrator(str(vlm_json))
        result = integrator.integrate(result)
        print(f"   Total welds after VLM integration: {result.total_welds}")
    
    # Phase 3: Export to Excel
    print(f"\n📊 Phase 3: Exporting to Excel...")
    excel_out = export_to_excel(result, excel_path)
    print(f"   ✅ {excel_out}")
    
    # Phase 4: Export to JSON
    print(f"\n📄 Phase 4: Exporting to JSON...")
    json_out = export_to_json(result, json_path)
    print(f"   ✅ {json_out}")
    
    print(f"\n✅ Done at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Print summary
    if args.summary and result.welds:
        print("\n" + "=" * 60)
        print("WELD SUMMARY")
        print("=" * 60)
        for w in result.welds:
            print(f"  [{w.id}] {w.name}")
            print(f"    Center: ({w.center[0]:.1f}, {w.center[1]:.1f}, {w.center[2]:.1f})")
            print(f"    Joint: {w.joint_type} | Length: {w.length:.1f}mm")
            if w.T1 or w.T2:
                print(f"    T1={w.T1:.1f}mm T2={w.T2:.1f}mm")
            print()


if __name__ == '__main__':
    main()
