# delivery-mode

醫療研究資料清洗專案，用於建立可重現的 Python pandas data cleaning workflow。原始 Excel 檔案不會被修改；所有檢查與後續清理步驟都應透過 `scripts/` 中的程式重現。

## 專案目的

本專案針對 `rawdata_all.xlsx` 的主要分析工作表「用這一個」進行資料盤點與品質檢查，產出缺失值、型態、摘要統計、類別值分布與潛在資料問題報告，作為後續清理規則與研究定義確認的依據。

## 資料夾結構

```text
delivery-mode/
├── data/
│   ├── raw/          # 原始資料副本，不直接修改
│   ├── interim/      # 中間資料
│   └── processed/    # 清理後資料
├── outputs/          # 報告與分析輸出
├── scripts/          # 可重現 Python scripts
├── logs/             # 執行紀錄
├── docs/             # 文件
├── .gitignore
├── README.md
├── requirements.txt
└── environment.yml
```

## 如何執行

使用 pip：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/01_data_audit.py
```

使用 conda：

```bash
conda env create -f environment.yml
conda activate delivery-mode
python scripts/01_data_audit.py
```

執行後會在 `outputs/` 產生：

```text
01_sheet_overview.xlsx
02_missing_report.xlsx
03_numeric_summary.xlsx
04_category_value_counts.xlsx
05_potential_data_issues.xlsx
```

## Data Cleaning Workflow

1. 將原始資料保存在 `data/raw/`，不直接修改。
2. 使用 `scripts/01_data_audit.py` 進行資料盤點與品質檢查。
3. 根據 `outputs/` 報告確認欄位定義、異常值與類別編碼。
4. 將人工確認後的清理規則寫成新的 Python scripts，輸出至 `data/interim/` 或 `data/processed/`。
5. 每次清理邏輯更新後重新執行 scripts，確保結果可重現。

## Git Workflow

1. 每次變更 scripts、文件或環境檔後執行 `git status`。
2. 確認變更內容後執行 `git add` 與 `git commit`。
3. 使用清楚的 commit message，例如 `Initial project structure and data audit pipeline`。
4. 將進度 push 到 GitHub repository。
