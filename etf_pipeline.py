"""下載 ETF 持股 Excel，並轉成統一格式的 JSON（適用 GitHub Actions 排程）。"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import pandas as pd
import requests

OUTPUT_DIR = Path("etf-data")
OUTPUT_DIR.mkdir(exist_ok=True)

# GitHub Actions 主機是 UTC，必須明確使用台灣時區，否則日期可能差一天
TODAY_STR = 20261019#datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; etf-pipeline/1.0)"}

TARGETS = [
    {
        "prefix": "981A",
        "url": "https://www.ezmoney.com.tw/ETF/Fund/AssetExcelNPOI?fundCode=49YTW",
    },
    {
        "prefix": "403A",
        "url": "https://www.ezmoney.com.tw/ETF/Fund/AssetExcelNPOI?fundCode=63YTW",
    },
    {
        "prefix": "991A",
        "url": f"https://www.fhtrust.com.tw/api/assetsExcel/ETF23/{TODAY_STR}",
    },
]

# 欄位名稱對應（支援多種變體）
COLUMN_MAPPING = {
    "代號": ["證券代號", "股票代號"],
    "名稱": ["證券名稱", "股票名稱"],
    "股數": ["股數"],
    "金額": ["金額"],
    "權重": ["權重(%)", "持股權重", "權重"],
}
TARGET_COLUMNS = ["代號", "名稱", "股數", "權重"]


# ---------------------------------------------------------------- 下載
def download(item: dict) -> Path | None:
    prefix, url = item["prefix"], item["url"]
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        filename = None
        cd = response.headers.get("Content-Disposition", "")
        if cd:
            m = re.search(r'filename=["\']?([^"\';]+)', cd)
            if m:
                filename = unquote(m.group(1))
        if not filename:
            filename = f"{prefix}_download.xlsx"

        if prefix == "991A":
            m = re.search(r"\d{4}[-_]\d{2}[-_]\d{2}", filename)
            date_str = re.sub(r"[-_]", "", m.group(0)) if m else TODAY_STR
            filename = f"{prefix}_ETF_Investment_Portfolio_{date_str}.xlsx"
        elif not filename.startswith(prefix):
            filename = f"{prefix}_{filename}"

        output_file = OUTPUT_DIR / filename
        output_file.write_bytes(response.content)
        print(f"[OK] 下載成功：{output_file} ({len(response.content):,} bytes)")
        return output_file
    except Exception as e:
        print(f"[FAIL] 下載失敗 ({prefix}) {url}\n       {e}")
        return None


# ---------------------------------------------------------------- 轉換
def excel_to_data(excel_path: Path) -> dict:
    """讀取 Excel，回傳 {sheet名稱: [持股records]}。"""
    xls = pd.ExcelFile(excel_path)
    portfolio_data = {}

    for sheet_name in xls.sheet_names:
        raw_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        header_row_index = None
        for idx, row in raw_df.iterrows():
            cells = [str(v) for v in row.values]
            if any(k in c for c in cells for k in ("證券代號", "股票代號")):
                header_row_index = idx
                break

        df = pd.read_excel(
            xls,
            sheet_name=sheet_name,
            header=header_row_index if header_row_index is not None else 0,
        )
        df.columns = df.columns.astype(str).str.strip()

        rename_dict = {}
        for target_key, names in COLUMN_MAPPING.items():
            for col in df.columns:
                if col in names:
                    rename_dict[col] = target_key
                    break
        df = df.rename(columns=rename_dict)

        available = [c for c in TARGET_COLUMNS if c in df.columns]
        if not available:
            print(f"[WARN] {excel_path.name} 的 Sheet [{sheet_name}] 找不到對應欄位")
            continue

        cleaned = df[available].dropna(how="all")
        # NaN 轉 None，輸出合法 JSON（null），而不是非法的 NaN
        cleaned = cleaned.astype(object).where(cleaned.notna(), None)
        portfolio_data[sheet_name] = cleaned.to_dict(orient="records")

    return portfolio_data


# ---------------------------------------------------------------- 清理舊報表
MAX_REPORTS = 240


def cleanup_old_reports() -> None:
    """只保留最新的 MAX_REPORTS 份 report_YYYYMMDD.json，其餘（最舊的）刪除。

    以檔名日期排序（而非檔案修改時間），因為 git checkout 會重設修改時間。
    """
    reports = sorted(
        f for f in OUTPUT_DIR.glob("report_*.json")
        if re.fullmatch(r"report_\d{8}\.json", f.name)
    )  # 檔名日期為 YYYYMMDD，字串排序即等於時間排序

    for f in reports[:-MAX_REPORTS] if len(reports) > MAX_REPORTS else []:
        f.unlink()
        print(f"[CLEAN] 已刪除超出上限的舊報表：{f.name}")


# ---------------------------------------------------------------- 主程式
def run() -> int:
    report = {}
    failed = 0

    for target in TARGETS:
        prefix = target["prefix"]
        xlsx = download(target)
        if not xlsx:
            failed += 1
            continue
        try:
            report[prefix] = excel_to_data(xlsx)
            print(f"[OK] 轉換完成：{prefix}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] 轉換失敗 {xlsx.name}: {e}")

    if not report:
        print("沒有任何資料可輸出（可能是休市日或網站異常）")
        return 1

    report_path = OUTPUT_DIR / f"report_{TODAY_STR}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)
    print(f"[OK] 合併報表：{report_path}（包含 {', '.join(report)}）")

    return 1 if failed else 0


def main() -> int:
    rc = run()
    cleanup_old_reports()  # 在新報表寫入之後清理，確保最終數量不超過上限
    return rc


if __name__ == "__main__":
    sys.exit(main())
