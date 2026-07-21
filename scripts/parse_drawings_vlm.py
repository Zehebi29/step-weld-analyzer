#!/usr/bin/env python3
"""Parse engineering drawings using SiliconFlow VLM (Qwen3-VL-32B)."""

import base64
import json
import os
import sys
from pathlib import Path

SILICONFLOW_API_KEY = os.environ.get('SILICONFLOW_API_KEY', '')

if not SILICONFLOW_API_KEY and os.path.exists('/home/ubuntu/app/weld-seam-compiler/backend/.env'):
    with open('/home/ubuntu/app/weld-seam-compiler/backend/.env', 'r') as f:
        for line in f:
            if 'SILICONFLOW_API_KEY' in line:
                SILICONFLOW_API_KEY = line.strip().split('=', 1)[1].strip("'\"")

API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "Qwen/Qwen3-VL-32B-Instruct"  # or Qwen/Qwen3-VL-32B-Thinking

# System prompt for weld drawing analysis
SYSTEM_PROMPT = """你是一位船舶/机械焊接工艺专家。分析这张工程图纸，提取所有焊接相关信息。

请按以下结构输出 JSON（只输出 JSON，不要其他文字）：
{
  "drawing_info": {
    "title": "图纸标题",
    "part_number": "零件号",
    "revision": "版本",
    "scale": "比例",
    "material": "材料"
  },
  "welds": [
    {
      "weld_id": "焊缝编号或标注",
      "type": "对接/角接/搭接/塞焊/点焊/其他",
      "process": "GMAW/SMAW/SAW/GTAW/其他",
      "length_mm": 焊缝长度数值,
      "thickness_mm": 焊缝厚度/焊脚尺寸,
      "angle_deg": 坡口角度,
      "root_gap_mm": 根部间隙,
      "root_face_mm": 钝边高度,
      "part1": "相邻零件1编号或描述",
      "part2": "相邻零件2编号或描述",
      "T1_mm": 零件1厚度,
      "T2_mm": 零件2厚度,
      "position": "焊缝位置描述",
      "notes": "其他标注说明"
    }
  ],
  "assembly_notes": [
    "装配说明/焊接工艺说明"
  ]
}

注意：
- 不确定的字段填 null
- 如果某个焊缝信息不完整，尽量根据图纸标注推理
- 特别关注：坡口形式（V/X/U/J型）、焊接方法代号、焊条型号、预热要求
"""


def encode_image(image_path: str, max_size_mb: int = 10) -> str:
    """Encode image to base64, resizing if too large."""
    img_path = Path(image_path)
    size_mb = img_path.stat().st_size / (1024 * 1024)
    
    if size_mb > max_size_mb:
        print(f"  ⚠ Image too large ({size_mb:.1f}MB), resizing...", file=sys.stderr)
        from PIL import Image
        img = Image.open(img_path)
        scale = (max_size_mb * 0.8 / size_mb) ** 0.5
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)
        import io
        buf = io.BytesIO()
        img.save(buf, format='PNG', optimize=True)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    
    with open(img_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def analyze_drawing(image_path: str) -> dict:
    """Analyze a single engineering drawing using SiliconFlow VLM."""
    print(f"\n🔍 Analyzing: {Path(image_path).name}")
    
    # Encode image
    b64_image = encode_image(image_path, max_size_mb=8)
    print(f"  Image size: {len(b64_image) // 1024} KB base64")
    
    # Prepare API request
    import urllib.request
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"}
                    },
                    {
                        "type": "text",
                        "text": "请分析这张工程图纸中的焊接信息，按照要求的JSON格式输出。特别注意焊缝标注、焊接符号、尺寸标注和工艺说明。"
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"}
    }
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read())
        content = result['choices'][0]['message']['content']
        
        # Try to parse as JSON
        try:
            parsed = json.loads(content)
            return parsed
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if m:
                return json.loads(m.group(1))
            print(f"  ⚠ Response not JSON:\n{content[:500]}", file=sys.stderr)
            return {"error": "non_json_response", "raw": content[:500]}
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ❌ HTTP {e.code}: {error_body[:300]}", file=sys.stderr)
        return {"error": f"http_{e.code}", "detail": error_body[:300]}
    except Exception as e:
        print(f"  ❌ Error: {e}", file=sys.stderr)
        return {"error": str(e)}


if __name__ == '__main__':
    import sys
    image_paths = sys.argv[1:] if len(sys.argv) > 1 else []
    
    if not image_paths:
        # Default: analyze all 3 drawings
        drawings_dir = Path(__file__).parent.parent / 'data' / 'drawings' / 'pngs'
        # Use the main page (not page 2) for each
        image_paths = [
            str(drawings_dir / 'sheet1.png'),
            str(drawings_dir / 'sheet2.png'),
            str(drawings_dir / 'sheet3.png'),
        ]
        # Also add page 2 of sheet1 and sheet2
        for suffix in ['sheet1-1.png', 'sheet2-1.png']:
            p = drawings_dir / suffix
            if p.exists():
                image_paths.append(str(p))
    
    results = {}
    for path in image_paths:
        result = analyze_drawing(path)
        results[Path(path).name] = result
    
    # Output combined JSON
    output_path = Path(__file__).parent.parent / 'output' / 'vlm_drawing_analysis.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Analysis saved to {output_path}")
    
    # Print summary
    for img_name, data in results.items():
        welds = data.get('welds', []) or []
        dwg = data.get('drawing_info', {})
        print(f"\n📄 {img_name}: {dwg.get('title', 'N/A')}")
        print(f"   Welds found: {len(welds)}")
        for w in welds:
            print(f"   - [{w.get('weld_id','?')}] {w.get('type','?')} "
                  f"L={w.get('length_mm','?')}mm T={w.get('thickness_mm','?')}mm "
                  f"Gap={w.get('root_gap_mm','?')}mm")
