import os
import csv
import json
import requests
from datetime import datetime, timedelta

# SSRS 報表基礎 URL
REPORT_BASE_URL = "http://rep3/ReportServer?/Z99-Emp/EmpDoorRecQuery"

def fetch_and_process_attendance():
    now = datetime.now()
    today_str = now.strftime("%Y/%m/%d")
    
    # 建立 SSRS CSV 查詢參數
    params = {
        'rs:Format': 'CSV',
        'p_sDate': f"{today_str} 05:00:00",
        'p_eDate': f"{today_str} 17:00:00"
    }

    print(f"正在抓取 {today_str} 的打卡資料...")

    # 如果 SSRS 需要 NTLM/Basic 認證，可設定 auth=(username, password)
    username = os.getenv("SSRS_USER")
    password = os.getenv("SSRS_PASS")
    auth = (username, password) if username and password else None

    try:
        response = requests.get(REPORT_BASE_URL, params=params, auth=auth, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8-sig' # 處理 BOM 頭
        
        lines = response.text.splitlines()
        reader = csv.DictReader(lines)
        
        valid_times = []
        for row in reader:
            t_date = row.get('t_date', '').strip()
            min_time = row.get('min_Time', '').strip()
            
            if t_date and min_time:
                date_str = f"{t_date} {min_time}"
                try:
                    dt = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
                    valid_times.append(dt)
                except ValueError:
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        valid_times.append(dt)
                    except ValueError:
                        pass

        if valid_times:
            # 取得最早或最新的打卡時間
            entry_time = min(valid_times) # 最早簽到時間
            exit_time = entry_time + timedelta(hours=9) # +9 小時退勤
            
            output_data = {
                "status": "success",
                "entry_time": entry_time.strftime("%Y/%m/%d %H:%M"),
                "exit_time": exit_time.strftime("%Y/%m/%d %H:%M"),
                "last_updated": now.strftime("%Y/%m/%d %H:%M:%S")
            }
        else:
            output_data = {
                "status": "no_data",
                "entry_time": "--:--",
                "exit_time": "--:--",
                "last_updated": now.strftime("%Y/%m/%d %H:%M:%S")
            }

    except Exception as e:
        print(f"抓取或解析失敗: {e}")
        output_data = {
            "status": "error",
            "message": str(e),
            "entry_time": "--:--",
            "exit_time": "--:--",
            "last_updated": now.strftime("%Y/%m/%d %H:%M:%S")
        }

    # 將結果輸出成 data.json 供 HTML 讀取
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("data.json 更新完成：", output_data)

if __name__ == "__main__":
    fetch_and_process_attendance()