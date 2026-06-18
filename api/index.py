import json
import os
import random
from functools import lru_cache
from pathlib import Path

import gspread
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from oauth2client.service_account import ServiceAccountCredentials

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

DAYS_WEEKDAY = ["6/29", "6/30", "7/1", "7/2", "7/3"]
HOURS_WEEKDAY = range(19, 23)
DAYS_WEEKEND = ["7/4", "7/5"]
HOURS_WEEKEND = range(10, 23)
ALL_DAYS_ORDER = DAYS_WEEKDAY + DAYS_WEEKEND
TIME_SLOTS = [f"{d} {h}:00-{h+1}:00" for d in DAYS_WEEKDAY for h in HOURS_WEEKDAY] + [f"{d} {h}:00-{h+1}:00" for d in DAYS_WEEKEND for h in HOURS_WEEKEND]
GRADES = ["中1", "中2", "中3", "高1", "高2", "高3"]
MENTOR_STREAMS = ["文系", "理系"]
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")


@lru_cache()
def get_spreadsheet():
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    spreadsheet_url = os.environ.get("SPREADSHEET_URL")
    if not gcp_json or not spreadsheet_url:
        raise RuntimeError("Missing GCP_SERVICE_ACCOUNT_JSON or SPREADSHEET_URL environment variable")

    credentials_json = json.loads(gcp_json)
    if "private_key" in credentials_json:
        credentials_json["private_key"] = credentials_json["private_key"].replace("\\n", "\n")

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json, scope)
    client = gspread.authorize(creds)
    return client.open_by_url(spreadsheet_url)


def load_data_from_sheet(sheet_name: str) -> pd.DataFrame:
    try:
        sh = get_spreadsheet()
        try:
            worksheet = sh.worksheet(sheet_name)
        except Exception:
            return pd.DataFrame()
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if "パスワード" in df.columns:
            df["パスワード"] = df["パスワード"].astype(str)
        return df.fillna("")
    except Exception:
        return pd.DataFrame()


def save_data_to_sheet(df: pd.DataFrame, sheet_name: str):
    sh = get_spreadsheet()
    try:
        worksheet = sh.worksheet(sheet_name)
    except Exception:
        worksheet = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
    df = df.fillna("")
    worksheet.clear()
    if not df.empty:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())


def append_data_to_sheet(df: pd.DataFrame, sheet_name: str):
    sh = get_spreadsheet()
    try:
        worksheet = sh.worksheet(sheet_name)
    except Exception:
        worksheet = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
    df = df.fillna("")
    existing_data = worksheet.get_all_values()
    if not existing_data:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    else:
        worksheet.append_rows(df.values.tolist())


def get_status() -> bool:
    try:
        df = load_data_from_sheet("settings")
        if df.empty or "status" not in df.columns:
            return True
        return df.iloc[0]["status"] == "OPEN"
    except Exception:
        return True


def set_status(is_open: bool):
    df = pd.DataFrame([{"status": "OPEN" if is_open else "CLOSED"}])
    save_data_to_sheet(df, "settings")


def get_sort_key(val):
    if not val or pd.isna(val) or not isinstance(val, str):
        return (99, 99)
    try:
        parts = val.split(" ")
        if len(parts) < 2:
            return (99, 99)
        date_part, time_part = parts[0], parts[1]
        d_index = ALL_DAYS_ORDER.index(date_part) if date_part in ALL_DAYS_ORDER else 99
        h_num = int(time_part.split(":")[0])
        return (d_index, h_num)
    except Exception:
        return (99, 99)


def calculate_shift_score(m_name, target_slot, mentor_assignments):
    score = 0
    assigned = mentor_assignments.get(m_name, set())
    current_day = target_slot.split(" ")[0]
    day_shifts = [s for s in assigned if s.startswith(current_day)]
    if not day_shifts:
        if assigned:
            score += 10
    else:
        idx = TIME_SLOTS.index(target_slot) if target_slot in TIME_SLOTS else -1
        if idx != -1:
            adj = [TIME_SLOTS[idx - 1] if idx > 0 else "", TIME_SLOTS[idx + 1] if idx < len(TIME_SLOTS) - 1 else ""]
            if any(a in assigned for a in adj):
                score += 100
    return score + random.random()


def run_matching(df_st: pd.DataFrame, df_mt: pd.DataFrame):
    results = []
    mentor_schedule = {}
    mentor_streams = {}
    mentor_assignments = {}
    mentor_names_list = list(df_mt["メンター氏名"])

    for _, row in df_mt.iterrows():
        m_name = row["メンター氏名"]
        mentor_schedule[m_name] = set(str(row["可能日時"]).split(",")) if row["可能日時"] else set()
        mentor_assignments[m_name] = set()
        mentor_streams[m_name] = str(row["文理"]).split(",") if row["文理"] else []

    students_list = []
    for _, s_row in df_st.iterrows():
        s_slots = str(s_row["可能日時"]).split(",") if s_row["可能日時"] else []
        students_list.append({
            "data": s_row,
            "s_slots_set": set([s.strip() for s in s_slots]),
            "num_slots": len(s_slots),
        })
    students_list.sort(key=lambda x: x["num_slots"])

    def is_unmatched(m_name):
        return len(mentor_assignments[m_name]) == 0

    for s_obj in students_list:
        s_row = s_obj["data"]
        s_name = s_row["生徒氏名"]
        s_stream = s_row["文理"]
        s_slots = s_obj["s_slots_set"]
        assigned_mentor, assigned_slot = None, None
        candidates = []

        for slot in s_slots:
            for m_name in mentor_names_list:
                if slot in mentor_schedule[m_name]:
                    if s_stream == "未定" or s_stream in mentor_streams.get(m_name, []):
                        candidates.append((m_name, slot))

        if candidates:
            candidates.sort(
                key=lambda x: (
                    0 if is_unmatched(x[0]) else 1,
                    -calculate_shift_score(x[0], x[1], mentor_assignments),
                )
            )
            assigned_mentor, assigned_slot = candidates[0]
        else:
            for slot in s_slots:
                for m_name in mentor_names_list:
                    if slot in mentor_schedule[m_name]:
                        assigned_mentor, assigned_slot = m_name, slot
                        break
                if assigned_mentor:
                    break

        if assigned_mentor:
            mentor_schedule[assigned_mentor].remove(assigned_slot)
            mentor_assignments[assigned_mentor].add(assigned_slot)
            results.append({
                "生徒氏名": s_name,
                "決定メンター": assigned_mentor,
                "決定日時": assigned_slot,
                "ステータス": "決定",
                "学校": s_row["学校"],
                "学年": s_row["学年"],
                "生徒文理": s_stream,
            })
        else:
            results.append({
                "生徒氏名": s_name,
                "決定メンター": "",
                "決定日時": "",
                "ステータス": "未定(空きなし)",
                "学校": s_row["学校"],
                "学年": s_row["学年"],
                "生徒文理": s_stream,
            })

    return results


def build_schedule_context(prefix: str, selected_slots):
    selected = set(s.strip() for s in selected_slots if s)
    weekday_rows = []
    weekend_rows = []
    idx = 0

    for h in HOURS_WEEKDAY:
        time_label = f"{h}:00-{h+1}:00"
        cells = []
        for day in DAYS_WEEKDAY:
            slot = f"{day} {time_label}"
            cells.append(
                {
                    "day": day,
                    "slot_name": f"{prefix}_slot_{idx}",
                    "slot_value": slot,
                    "checked": slot in selected,
                }
            )
            idx += 1
        weekday_rows.append({"time": time_label, "cells": cells})

    for h in HOURS_WEEKEND:
        time_label = f"{h}:00-{h+1}:00"
        cells = []
        for day in DAYS_WEEKEND:
            slot = f"{day} {time_label}"
            cells.append(
                {
                    "day": day,
                    "slot_name": f"{prefix}_slot_{idx}",
                    "slot_value": slot,
                    "checked": slot in selected,
                }
            )
            idx += 1
        weekend_rows.append({"time": time_label, "cells": cells})

    return {"weekday_rows": weekday_rows, "weekend_rows": weekend_rows}


def extract_slots(form_data, prefix: str):
    return [value for key, value in form_data.items() if key.startswith(prefix + "_slot_")]


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "is_accepting": get_status(), "title": "ALOHA面談日程調整"},
    )


@app.get("/student", response_class=HTMLResponse)
def student_get(request: Request):
    return templates.TemplateResponse(
        "student.html",
        {
            "request": request,
            "title": "中高生用 希望調査",
            "form": {},
            "messages": [],
            **build_schedule_context("student", []),
            "grades": GRADES,
            "streams": ["文系", "理系", "未定"],
        },
    )


@app.post("/student", response_class=HTMLResponse)
async def student_post(request: Request):
    form = await request.form()
    s_name = form.get("s_name", "").strip()
    s_line_name = form.get("s_line_name", "").strip()
    s_school = form.get("s_school", "").strip()
    s_grade = form.get("s_grade", "").strip()
    s_stream = form.get("s_stream", "").strip()
    s_request_mentor = form.get("s_request_mentor", "").strip()
    s_questions = form.get("s_questions", "").strip()
    selected_slots = extract_slots(form, "student")

    errors = []
    if not s_name:
        errors.append("氏名を入力してください。")
    if not s_line_name:
        errors.append("LINE名を入力してください。")
    if not s_school:
        errors.append("学校名を入力してください。")
    if not s_grade:
        errors.append("学年を選択してください。")
    if not s_stream:
        errors.append("文理を選択してください。")
    if not s_questions:
        errors.append("質問内容を入力してください。")
    if not selected_slots:
        errors.append("少なくとも1つの日時を選択してください。")

    message = None
    if not errors:
        df_s = load_data_from_sheet("students")
        new_row = {
            "生徒氏名": s_name,
            "LINE名": s_line_name,
            "学校": s_school,
            "学年": s_grade,
            "文理": s_stream,
            "指名希望": s_request_mentor,
            "質問内容": s_questions,
            "可能日時": ",".join(selected_slots),
        }
        if not df_s.empty and "生徒氏名" in df_s.columns:
            df_s = df_s[df_s["生徒氏名"] != s_name]
            df_s = pd.concat([df_s, pd.DataFrame([new_row])], ignore_index=True)
            message = f"{s_name} さんの情報を更新しました。"
        else:
            df_s = pd.DataFrame([new_row])
            message = "登録しました。"
        save_data_to_sheet(df_s, "students")

    context = {
        "request": request,
        "title": "中高生用 希望調査",
        "form": {
            "s_name": s_name,
            "s_line_name": s_line_name,
            "s_school": s_school,
            "s_grade": s_grade,
            "s_stream": s_stream,
            "s_request_mentor": s_request_mentor,
            "s_questions": s_questions,
        },
        "messages": errors if errors else [message],
        **build_schedule_context("student", selected_slots),
        "grades": GRADES,
        "streams": ["文系", "理系", "未定"],
    }
    return templates.TemplateResponse("student.html", context)


@app.get("/mentor", response_class=HTMLResponse)
def mentor_get(request: Request):
    return templates.TemplateResponse(
        "mentor.html",
        {
            "request": request,
            "title": "大学生用 空きコマ登録・確認",
            "form": {},
            "messages": [],
            **build_schedule_context("mentor", []),
            "mentor_streams": MENTOR_STREAMS,
        },
    )


@app.post("/mentor", response_class=HTMLResponse)
async def mentor_post(request: Request):
    form = await request.form()
    action = form.get("action", "save")
    name = form.get("name", "").strip()
    password = form.get("password", "").strip()
    selected_slots = extract_slots(form, "mentor")
    streams = [stream for stream in MENTOR_STREAMS if form.get(f"stream_{stream}") == "on"]
    is_unavailable = form.get("is_unavailable") == "on"

    errors = []
    info = None
    loaded_slots = []

    if action == "load":
        if not name or not password:
            errors.append("氏名とパスワードを入力してください。")
        else:
            df_m = load_data_from_sheet("mentors")
            if not df_m.empty and "メンター氏名" in df_m.columns:
                target = df_m[df_m["メンター氏名"] == name]
                if not target.empty:
                    row = target.iloc[0]
                    if str(row["パスワード"]) == password:
                        loaded_slots = str(row["可能日時"]).split(",") if row["可能日時"] else []
                        streams = str(row["文理"]).split(",") if row["文理"] else []
                        is_unavailable = loaded_slots == ["参加不可"]
                        info = f"{name} さんを読み込みました。"
                    else:
                        errors.append("パスワードが違います。")
                else:
                    info = "新規登録します。"
            else:
                info = "新規登録します。"
    else:
        if not name or not password:
            errors.append("氏名とパスワードを入力してください。")
        if not streams:
            errors.append("文理を選択してください。")
        if not selected_slots and not is_unavailable:
            errors.append("日時を1つ以上選択してください。")
        if not errors:
            df_m = load_data_from_sheet("mentors")
            available_value = "参加不可" if is_unavailable else ",".join(selected_slots)
            new_row = {
                "メンター氏名": name,
                "文理": ",".join(streams),
                "可能日時": available_value,
                "パスワード": password,
            }
            if not df_m.empty and "メンター氏名" in df_m.columns:
                df_m = df_m[df_m["メンター氏名"] != name]
                df_m = pd.concat([df_m, pd.DataFrame([new_row])], ignore_index=True)
            else:
                df_m = pd.DataFrame([new_row])
            save_data_to_sheet(df_m, "mentors")
            info = "保存しました。"
            loaded_slots = selected_slots if not is_unavailable else ["参加不可"]

    form_values = {
        "name": name,
        "password": password,
        "streams": streams,
        "is_unavailable": is_unavailable,
    }
    if loaded_slots:
        form_values["slots"] = loaded_slots

    return templates.TemplateResponse(
        "mentor.html",
        {
            "request": request,
            "title": "大学生用 空きコマ登録・確認",
            "form": form_values,
            "messages": errors if errors else ([info] if info else []),
            **build_schedule_context("mentor", loaded_slots if loaded_slots else selected_slots),
            "mentor_streams": MENTOR_STREAMS,
        },
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_get(request: Request):
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "title": "管理者ダッシュボード",
            "messages": [],
            "students": [],
            "mentors": [],
            "results": [],
            "is_accepting": get_status(),
            "show_dashboard": False,
        },
    )


@app.post("/admin", response_class=HTMLResponse)
async def admin_post(request: Request):
    form = await request.form()
    password = form.get("admin_password", "").strip()
    action = form.get("action", "view")
    errors = []
    info = None
    results = []

    if password != ADMIN_PASSWORD:
        errors.append("管理者パスワードが違います。")
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "title": "管理者ダッシュボード",
                "messages": errors,
                "students": [],
                "mentors": [],
                "results": [],
                "is_accepting": get_status(),
                "show_dashboard": False,
            },
        )

    students = load_data_from_sheet("students")
    mentors = load_data_from_sheet("mentors")

    if action == "toggle_status":
        current = get_status()
        set_status(not current)
        info = "受付ステータスを変更しました。"
    elif action == "match":
        if students.empty or mentors.empty:
            errors.append("生徒またはメンターのデータが不足しています。")
        else:
            results = run_matching(students, mentors)
            results = sorted(results, key=lambda x: get_sort_key(x.get("決定日時", "")))
            info = "マッチングを実行しました。"
    elif action == "clear_students":
        save_data_to_sheet(pd.DataFrame(), "students")
        info = "生徒データを削除しました。"
    elif action == "clear_mentors":
        save_data_to_sheet(pd.DataFrame(), "mentors")
        info = "メンターデータを削除しました。"

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "title": "管理者ダッシュボード",
            "messages": errors if errors else ([info] if info else []),
            "students": students.to_dict("records") if not students.empty else [],
            "mentors": mentors.to_dict("records") if not mentors.empty else [],
            "results": results,
            "is_accepting": get_status(),
            "show_dashboard": True,
        },
    )
