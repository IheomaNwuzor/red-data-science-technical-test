import csv
import os
from rapidfuzz import fuzz, process

class Transformer:
    def __init__(self, reference_dir: str):
        self.reference_dir = reference_dir
        self.reference_data = {
            "lrf": {},
            "incident": {},
            "organisation": {},
            "site": {}
        }
        self._load_reference_files()

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        for prefix in ["the ", "a ", "an "]:
            if text.startswith(prefix):
                text = text[len(prefix):]
        return text.strip()

    def _load_reference_files(self):
        mapping = {
            "lrf": "lrfs.csv",
            "incident": "incidents.csv",
            "organisation": "organisations.csv",
            "site": "sites.csv"
        }
        for entity_type, filename in mapping.items():
            filepath = os.path.join(self.reference_dir, filename)
            if not os.path.exists(filepath):
                continue
            with open(filepath, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entity_id = row.get("id") or row.get(f"{entity_type}_id")
                    name = row.get("name") or row.get("title") or row.get("label")
                    if entity_id and name:
                        cleaned = self._clean_text(name)
                        self.reference_data[entity_type][cleaned] = entity_id
                        if "aliases" in row and row["aliases"]:
                            for alias in row["aliases"].split(";"):
                                self.reference_data[entity_type][self._clean_text(alias)] = entity_id

    def resolve(self, entity_type: str, mention_text: str) -> tuple[str, bool]:
        cleaned_mention = self._clean_text(mention_text)
        if not cleaned_mention:
            return f"NEW_{entity_type.upper()}_{abs(hash(mention_text))}", True

        ref_dict = self.reference_data.get(entity_type, {})

        if cleaned_mention in ref_dict:
            return ref_dict[cleaned_mention], False

        choices = list(ref_dict.keys())
        if choices:
            match = process.extractOne(cleaned_mention, choices, scorer=fuzz.token_set_ratio)
            if match and match[1] >= 85:
                matched_key = match[0]
                return ref_dict[matched_key], False

        new_id = f"NEW_{entity_type.upper()}_{abs(hash(cleaned_mention))}"
        return new_id, True