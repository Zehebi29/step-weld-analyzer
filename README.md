# Step Weld Analyzer

STEP模型焊缝工艺信息解析工具

从 STEP 三维模型中自动提取焊缝特征信息，输出结构化数据（Excel + JSON）。

## 功能

- **焊缝识别**：从 STEP 装配体中识别焊缝实体（WLD product）
- **位置信息**：焊缝在全局坐标系中的位置、方向
- **几何特征**：相邻零件面、边、拓扑关系
- **尺寸测量**：焊缝长度、焊缝厚度（leg length/throat thickness）
- **基材信息**：相邻基材厚度 T1、T2
- **间隙分析**：焊接间隙 gap
- **间距计算**：焊缝之间的距离
- **类型推断**：焊接类型（对接/角接/搭接/塞焊）和工艺方法

## 输出格式

- `output/welds.xlsx` — Excel 表格，每行一条焊缝
- `output/welds.json` — JSON 结构化数据

## 项目结构

```
step-weld-analyzer/
├── data/               # STEP 模型文件
├── src/                # 核心代码
│   ├── step_parser.py      # STEP 文件解析
│   ├── weld_extractor.py   # 焊缝特征提取
│   ├── geometry_utils.py   # 几何计算
│   ├── excel_exporter.py   # Excel 输出
│   ├── json_exporter.py    # JSON 输出
│   └── main.py             # 主入口
├── output/             # 输出结果
├── scripts/            # 辅助脚本
├── requirements.txt
└── README.md
```

## 数据来源

- **STEP 模型**：三维模型中的焊缝实体（AP214/AP242 标准）
- **二维图纸**（可选）：通过 VLM 解析 PDF 图纸中的焊缝标注
