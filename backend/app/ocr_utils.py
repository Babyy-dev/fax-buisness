import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SUPPORTED_PDF_EXTS = {".pdf"}

HEADER_ALIASES = {
    "product": ["品名", "品番", "商品名", "品目", "製品名", "品名/品目", "商品/品目"],
    "quantity": ["数量", "数", "数量(箱)", "数量(本)", "数量(個)", "数量/箱", "数量/本"],
    "unit_price": ["単価", "価格", "単価(円)", "単価(¥)"],
    "amount": ["金額", "合計", "金額(円)", "金額(税込)"],
    "product_code": ["品番", "型式", "型番", "商品コード", "アイテムコード", "品番/規格"],
    "unit": ["単位", "単位/梱", "単位(箱)", "単位(本)", "単位(個)"],
    "unit_number": ["ユニットNo", "ユニットNO", "ユニットNo.", "ユニット番号", "Unit No"],
    "delivery_number": ["納品番号", "納品No", "納品NO", "伝票No", "伝票番号", "伝票No."],
}


class OCRException(RuntimeError):
    pass


def _get_region() -> str:
    return os.getenv("AWS_REGION", "ap-northeast-1")


def _get_textract_client():
    return boto3.client("textract", region_name=_get_region())


def _get_s3_client():
    return boto3.client("s3", region_name=_get_region())


def _normalize_header(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip().lower()


def _parse_number(value: str) -> float:
    if not value:
        return 0.0
    cleaned = re.sub(r"[^\d\.\-]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _collect_block_text(blocks_by_id: Dict[str, dict], block: dict) -> str:
    words: List[str] = []
    for rel in block.get("Relationships", []):
        if rel.get("Type") != "CHILD":
            continue
        for child_id in rel.get("Ids", []):
            child = blocks_by_id.get(child_id)
            if not child:
                continue
            if child.get("BlockType") == "WORD":
                words.append(child.get("Text", ""))
            elif child.get("BlockType") == "SELECTION_ELEMENT":
                if child.get("SelectionStatus") == "SELECTED":
                    words.append("[X]")
    return " ".join(words).strip()


def _extract_tables(blocks: List[dict]) -> List[List[List[str]]]:
    blocks_by_id = {block["Id"]: block for block in blocks}
    tables: List[List[List[str]]] = []
    for block in blocks:
        if block.get("BlockType") != "TABLE":
            continue
        rows: Dict[int, Dict[int, str]] = {}
        for rel in block.get("Relationships", []):
            if rel.get("Type") != "CHILD":
                continue
            for cell_id in rel.get("Ids", []):
                cell = blocks_by_id.get(cell_id)
                if not cell or cell.get("BlockType") != "CELL":
                    continue
                row_idx = cell.get("RowIndex", 1)
                col_idx = cell.get("ColumnIndex", 1)
                text = _collect_block_text(blocks_by_id, cell)
                rows.setdefault(row_idx, {})[col_idx] = text
        if not rows:
            continue
        max_col = max((max(cols.keys()) for cols in rows.values()), default=0)
        table_rows: List[List[str]] = []
        for row_idx in sorted(rows.keys()):
            row = ["" for _ in range(max_col)]
            for col_idx, text in rows[row_idx].items():
                if 1 <= col_idx <= max_col:
                    row[col_idx - 1] = text
            table_rows.append(row)
        if table_rows:
            tables.append(table_rows)
    return tables


def _find_header_row(table: List[List[str]]) -> Tuple[int, Dict[str, int]]:
    best_row = 0
    best_match: Dict[str, int] = {}
    for row_idx, row in enumerate(table):
        mapping: Dict[str, int] = {}
        for col_idx, cell in enumerate(row):
            normalized = _normalize_header(cell)
            for key, aliases in HEADER_ALIASES.items():
                if key in mapping:
                    continue
                for alias in aliases:
                    if alias in cell or _normalize_header(alias) in normalized:
                        mapping[key] = col_idx
                        break
        if len(mapping) > len(best_match):
            best_match = mapping
            best_row = row_idx
        if len(mapping) >= 2:
            break
    return best_row, best_match


def _lines_from_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
    extracted: List[Dict[str, Any]] = []
    for table in tables:
        header_row, mapping = _find_header_row(table)
        if "product" not in mapping:
            continue
        for row in table[header_row + 1 :]:
            product_text = row[mapping["product"]].strip() if mapping.get("product") is not None else ""
            if not product_text:
                continue
            quantity = 1
            if "quantity" in mapping:
                quantity = int(_parse_number(row[mapping["quantity"]])) or 1
            unit_price = 0.0
            if "unit_price" in mapping:
                unit_price = _parse_number(row[mapping["unit_price"]])
            amount = 0.0
            if "amount" in mapping:
                amount = _parse_number(row[mapping["amount"]])
            product_code = ""
            if "product_code" in mapping:
                product_code = row[mapping["product_code"]].strip()
            unit = ""
            if "unit" in mapping:
                unit = row[mapping["unit"]].strip()
            unit_number = ""
            if "unit_number" in mapping:
                unit_number = row[mapping["unit_number"]].strip()
            delivery_number = ""
            if "delivery_number" in mapping:
                delivery_number = row[mapping["delivery_number"]].strip()
            extracted.append(
                {
                    "extracted_text": product_text,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": amount or unit_price * quantity,
                    "product_code": product_code,
                    "unit": unit,
                    "unit_number": unit_number,
                    "delivery_number": delivery_number,
                }
            )
    return extracted


def _lines_from_blocks(blocks: List[dict]) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        text = block.get("Text", "").strip()
        if not text:
            continue
        qty_match = re.search(r"(\d+)\s*(本|箱|個|pcs|pc)?$", text)
        quantity = int(qty_match.group(1)) if qty_match else 1
        lines.append(
            {
                "extracted_text": text,
                "quantity": quantity,
                "unit_price": 0.0,
                "line_total": 0.0,
            }
        )
    return lines


def _collect_raw_text(blocks: List[dict]) -> str:
    lines: List[str] = []
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        text = block.get("Text", "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _fetch_textract_blocks_for_image(file_path: Path) -> List[dict]:
    client = _get_textract_client()
    with file_path.open("rb") as handle:
        payload = handle.read()
    try:
        response = client.analyze_document(Document={"Bytes": payload}, FeatureTypes=["TABLES"])
    except (BotoCoreError, ClientError) as exc:
        raise OCRException(f"Textract analyze_document failed: {exc}") from exc
    return response.get("Blocks", [])


def _fetch_textract_blocks_for_pdf(file_path: Path) -> List[dict]:
    bucket = os.getenv("TEXTRACT_S3_BUCKET")
    if not bucket:
        raise OCRException("TEXTRACT_S3_BUCKET is required for PDF analysis with Textract.")
    prefix = os.getenv("TEXTRACT_S3_PREFIX", "textract")
    key = f"{prefix}/{uuid.uuid4().hex}-{file_path.name}"
    s3 = _get_s3_client()
    try:
        s3.upload_file(str(file_path), bucket, key)
    except (BotoCoreError, ClientError) as exc:
        raise OCRException(f"Failed to upload PDF to S3: {exc}") from exc

    client = _get_textract_client()
    try:
        response = client.start_document_analysis(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
            FeatureTypes=["TABLES"],
        )
    except (BotoCoreError, ClientError) as exc:
        raise OCRException(f"Textract start_document_analysis failed: {exc}") from exc

    job_id = response.get("JobId")
    if not job_id:
        raise OCRException("Textract did not return a JobId.")

    blocks: List[dict] = []
    next_token: Optional[str] = None
    for _ in range(60):
        try:
            kwargs = {"JobId": job_id}
            if next_token:
                kwargs["NextToken"] = next_token
            result = client.get_document_analysis(**kwargs)
        except (BotoCoreError, ClientError) as exc:
            raise OCRException(f"Textract get_document_analysis failed: {exc}") from exc

        status = result.get("JobStatus")
        if status == "SUCCEEDED":
            blocks.extend(result.get("Blocks", []))
            next_token = result.get("NextToken")
            if not next_token:
                break
        elif status == "FAILED":
            raise OCRException("Textract analysis failed.")
        else:
            time.sleep(2)
            continue
    return blocks


def _extract_metadata(blocks: List[dict]) -> Dict[str, str]:
    patterns = {
        "order_number": re.compile(r"(注文番号|注文No|注文NO|受注番号)\\s*[:：]?\\s*([A-Za-z0-9\\-]+)"),
        "delivery_number": re.compile(r"(納品番号|納品No|伝票No|伝票番号)\\s*[:：]?\\s*([A-Za-z0-9\\-]+)"),
        "invoice_number": re.compile(r"(請求番号|請求No|請求NO)\\s*[:：]?\\s*([A-Za-z0-9\\-]+)"),
    }
    meta: Dict[str, str] = {}
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        text = block.get("Text", "")
        for key, pattern in patterns.items():
            if key in meta:
                continue
            match = pattern.search(text)
            if match:
                meta[key] = match.group(2)
    return meta


def extract_order_data(file_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, str], str]:
    suffix = file_path.suffix.lower()
    if suffix in SUPPORTED_IMAGE_EXTS:
        blocks = _fetch_textract_blocks_for_image(file_path)
    elif suffix in SUPPORTED_PDF_EXTS:
        blocks = _fetch_textract_blocks_for_pdf(file_path)
    else:
        raise OCRException("Unsupported file type for OCR.")

    tables = _extract_tables(blocks)
    table_lines = _lines_from_tables(tables)
    lines = table_lines if table_lines else _lines_from_blocks(blocks)
    meta = _extract_metadata(blocks)
    raw_text = _collect_raw_text(blocks)
    return lines, meta, raw_text


def extract_order_lines(file_path: Path) -> List[Dict[str, Any]]:
    lines, _meta, _raw_text = extract_order_data(file_path)
    return lines
