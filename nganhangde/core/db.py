import hashlib
import json
import os
import re
import sqlite3
from typing import Iterable
from .migrations import migrate
from .parser import Question
from .texutil import strip_accents_vi

INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")


def format_import_type_summary(stat: dict) -> str:
    """Định dạng chuỗi thống kê số câu đã nhập theo từng loại TN, ĐS, TLN, TL."""
    bt = stat.get("by_type") or {}
    tn = int(bt.get("TN", 0))
    ds = int(bt.get("DS", 0))
    tln = int(bt.get("KQ", 0)) + int(bt.get("TLN", 0))
    tl = int(bt.get("TL", 0))
    return f"TN: {tn} | ĐS: {ds} | TLN: {tln} | TL: {tl}"


class QuestionBankDB:
    def __init__(self, db_path: str = "nganhang.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn, db_path)

    def close(self) -> None:
        self.conn.close()

    def add_question(self, q: Question, asset_base_dir: str | None = None) -> tuple[int | None, bool]:
        info = q.id_info()
        fp = q.fingerprint()
        stem_plain = strip_accents_vi(f"{q.stem} {' '.join(q.choices)}").lower()
        raw_tex = q.raw or q.to_latex(True)
        try:
            cur = self.conn.execute(
                """INSERT INTO questions (
                    qid, ids_json, tags_json, lop, mon, chuong, muc_do, bai, dang,
                    qtype, stem, stem_plain, choices_json, correct_json, short_ans,
                    solution, cmd_name, cmd_opt, lock_shuffle, group_id, raw, fingerprint
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    q.primary_id, json.dumps(q.ids, ensure_ascii=False), json.dumps(q.tags, ensure_ascii=False),
                    info.lop if info else "", info.mon if info else "", info.chuong if info else "",
                    info.muc_do if info else "", info.bai if info else "", info.dang if info else "",
                    q.qtype, q.stem, stem_plain, json.dumps(q.choices, ensure_ascii=False),
                    json.dumps(q.correct), q.short_ans, q.solution, q.cmd_name, q.cmd_opt,
                    1 if q.lock_shuffle else 0, q.group_id, raw_tex, fp,
                ),
            )
            qid_row = cur.lastrowid
            for rel_img in INCLUDEGRAPHICS_RE.findall(raw_tex):
                sha = ""
                if asset_base_dir:
                    full = rel_img if os.path.isabs(rel_img) else os.path.join(asset_base_dir, rel_img)
                    if os.path.exists(full):
                        sha = hashlib.sha1(open(full, "rb").read()).hexdigest()
                self.conn.execute(
                    "INSERT INTO assets (question_id, rel_path, sha1, kind) VALUES (?, ?, ?, ?)",
                    (qid_row, rel_img, sha, "image"),
                )
            self.conn.commit()
            return qid_row, True
        except sqlite3.IntegrityError:
            return None, False

    def bulk_import(
        self,
        questions: Iterable[Question],
        asset_base_dir: str | None = None,
        batch_size: int = 2000,
    ) -> dict[str, int]:
        """Nhập hàng loạt siêu tốc bằng 1 transaction theo lô (50.000 câu chỉ mất vài giây, không treo máy)."""
        q_list = list(questions)
        added = skipped = 0
        cur = self.conn.cursor()
        before_counts: dict[str, int] = {"TN": 0, "DS": 0, "KQ": 0, "TL": 0}
        try:
            for qt, cnt in cur.execute("SELECT qtype, COUNT(*) FROM questions GROUP BY qtype").fetchall():
                k = (qt or "TL").upper()
                before_counts[k] = int(cnt)
        except Exception:
            pass
        defer_fts = len(q_list) >= 300
        try:
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=OFF;")
            cur.execute("PRAGMA temp_store=MEMORY;")
            cur.execute("PRAGMA cache_size=-64000;")
            if defer_fts:
                cur.execute("DROP TRIGGER IF EXISTS questions_ai;")
        except Exception:
            defer_fts = False

        sql_q = """INSERT OR IGNORE INTO questions (
            qid, ids_json, tags_json, lop, mon, chuong, muc_do, bai, dang,
            qtype, stem, stem_plain, choices_json, correct_json, short_ans,
            solution, cmd_name, cmd_opt, lock_shuffle, group_id, raw, fingerprint
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

        batch_rows: list[tuple] = []
        batch_assets: list[tuple[str, list[str]]] = []

        def _flush():
            nonlocal added, skipped
            if not batch_rows:
                return
            before = self.conn.total_changes
            cur.execute("BEGIN")
            cur.executemany(sql_q, batch_rows)
            if asset_base_dir and batch_assets:
                for fp_val, imgs in batch_assets:
                    row = cur.execute("SELECT id FROM questions WHERE fingerprint = ?", (fp_val,)).fetchone()
                    if not row:
                        continue
                    qid_row = row[0]
                    for rel_img in imgs:
                        sha = ""
                        full = rel_img if os.path.isabs(rel_img) else os.path.join(asset_base_dir, rel_img)
                        if os.path.exists(full):
                            try:
                                sha = hashlib.sha1(open(full, "rb").read()).hexdigest()
                            except Exception:
                                sha = ""
                        cur.execute(
                            "INSERT INTO assets (question_id, rel_path, sha1, kind) VALUES (?, ?, ?, ?)",
                            (qid_row, rel_img, sha, "image"),
                        )
            self.conn.commit()
            ins = self.conn.total_changes - before
            # Trừ số dòng assets nếu có
            ins_q = min(ins, len(batch_rows))
            added += ins_q
            skipped += max(0, len(batch_rows) - ins_q)
            batch_rows.clear()
            batch_assets.clear()

        for q in q_list:
            info = q.id_info()
            fp = q.fingerprint()
            stem_plain = strip_accents_vi(f"{q.stem} {' '.join(q.choices)}").lower()
            raw_tex = q.raw or q.to_latex(True)
            batch_rows.append((
                q.primary_id,
                json.dumps(q.ids, ensure_ascii=False),
                json.dumps(q.tags, ensure_ascii=False),
                info.lop if info else "",
                info.mon if info else "",
                info.chuong if info else "",
                info.muc_do if info else "",
                info.bai if info else "",
                info.dang if info else "",
                q.qtype,
                q.stem,
                stem_plain,
                json.dumps(q.choices, ensure_ascii=False),
                json.dumps(q.correct),
                q.short_ans,
                q.solution,
                q.cmd_name,
                q.cmd_opt,
                1 if q.lock_shuffle else 0,
                q.group_id,
                raw_tex,
                fp,
            ))
            if asset_base_dir:
                imgs = INCLUDEGRAPHICS_RE.findall(raw_tex)
                if imgs:
                    batch_assets.append((fp, imgs))
            if len(batch_rows) >= batch_size:
                _flush()
        _flush()
        if defer_fts:
            try:
                cur.execute("INSERT INTO questions_fts(questions_fts) VALUES('rebuild');")
                cur.execute(
                    """CREATE TRIGGER IF NOT EXISTS questions_ai AFTER INSERT ON questions BEGIN
                        INSERT INTO questions_fts(rowid, qid, stem, stem_plain)
                        VALUES (new.id, new.qid, new.stem, new.stem_plain);
                    END;"""
                )
                cur.execute("PRAGMA synchronous=NORMAL;")
                self.conn.commit()
            except Exception:
                pass
        after_counts: dict[str, int] = {"TN": 0, "DS": 0, "KQ": 0, "TL": 0}
        try:
            for qt, cnt in cur.execute("SELECT qtype, COUNT(*) FROM questions GROUP BY qtype").fetchall():
                k = (qt or "TL").upper()
                after_counts[k] = int(cnt)
        except Exception:
            pass
        by_type = {
            k: max(0, after_counts.get(k, 0) - before_counts.get(k, 0))
            for k in ("TN", "DS", "KQ", "TL")
        }
        return {"added": added, "duplicates": skipped, "by_type": by_type}

    def list_assets(self, question_id: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM assets WHERE question_id = ?", (question_id,)).fetchall()]

    def search(self, keyword: str = "", id_glob: str = "", qtype: str = "", muc_do: str = "", limit: int = 200) -> list[sqlite3.Row]:
        clauses, params = [], []
        if keyword.strip():
            tokens = [f'"{tok}"*' for tok in strip_accents_vi(keyword.strip()).lower().split() if tok]
            if tokens:
                sql_base = "SELECT q.* FROM questions_fts f JOIN questions q ON q.id = f.rowid"
                clauses.append("questions_fts MATCH ?")
                params.append(" AND ".join(tokens))
            else:
                sql_base = "SELECT q.* FROM questions q"
        else:
            sql_base = "SELECT q.* FROM questions q"
        if id_glob.strip():
            clauses.append("q.qid GLOB ?")
            params.append(id_glob.strip())
        if qtype.strip():
            clauses.append("q.qtype = ?")
            params.append(qtype.strip())
        if muc_do.strip():
            clauses.append("q.muc_do = ?")
            params.append(muc_do.strip())
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        return self.conn.execute(f"{sql_base}{where_sql} ORDER BY q.used_count ASC, q.id DESC LIMIT ?", params).fetchall()

    def update_question_stem(self, row_id: int, new_stem: str) -> None:
        new_plain = strip_accents_vi(new_stem).lower()
        self.conn.execute("UPDATE questions SET stem = ?, stem_plain = ? WHERE id = ?", (new_stem, new_plain, row_id))
        self.conn.commit()

    def delete_question(self, row_id: int) -> None:
        self.conn.execute("DELETE FROM questions WHERE id = ?", (row_id,))
        self.conn.commit()

    def add_workspace_node(self, name: str, parent_id: int | None = None, node_type: str = "folder", ref_batch_id: int | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO workspace_nodes (parent_id, name, node_type, ref_batch_id) VALUES (?, ?, ?, ?)",
            (parent_id, name, node_type, ref_batch_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_workspace_nodes(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT id, parent_id, name, node_type, ref_batch_id FROM workspace_nodes ORDER BY id ASC").fetchall()]

    def delete_workspace_node(self, node_id: int) -> None:
        self.conn.execute("DELETE FROM workspace_nodes WHERE id = ?", (node_id,))
        self.conn.commit()
