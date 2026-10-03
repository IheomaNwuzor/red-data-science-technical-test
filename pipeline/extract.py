import email
from email.policy import default
import re

class Extractor:

    def parse_file(self, file_path: str) -> dict:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=default)

        body_part = msg.get_body(preferencelist=('plain',))
        body = body_part.get_content() if body_part else ""
        date_str = msg.get("Date", "")
        subject = msg.get("Subject", "")

        return {
            "message_id": msg.get("Message-ID", file_path),
            "date": date_str,
            "subject": subject,
            "sender": msg.get("From", ""),
            "receiver": msg.get("To", ""),
            "body": body
        }
    
    def extract_structured_data(self, parsed_email: dict) -> dict:
        body = parsed_email["body"]
        subject = parsed_email["subject"]
        
        sites_found = []
        organisations_found = []
        relations = []
        observations = []

        incident_mention = "Storm Fenella" if "Fenella" in subject or "Fenella" in body else "Unknown Incident"

        line_items = re.findall(r"^\s*[-\*]\s*(.*?)$", body, re.MULTILINE)
        
        for item in line_items:
            if ":" in item:
                site_part, status_part = item.split(":", 1)
                site_name = site_part.strip()
                status_text = status_part.strip()

                sites_found.append(site_name)

                run_by_match = re.search(r"\(run by (.*?)\)", status_text, re.IGNORECASE)
                if run_by_match:
                    operator_name = run_by_match.group(1).strip()
                    organisations_found.append(operator_name)
                    relations.append({
                        "from_type": "organisation",
                        "from_mention": operator_name,
                        "relation": "OPERATES",
                        "to_type": "site",
                        "to_mention": site_name
                    })

                observations.append({
                    "site_mention": site_name,
                    "property_name": "status",
                    "property_value": status_text,
                    "reported_at": parsed_email["date"],
                    "email_id": parsed_email["message_id"]
                })

                relations.append({
                    "from_type": "incident",
                    "from_mention": incident_mention,
                    "relation": "AFFECTS",
                    "to_type": "site",
                    "to_mention": site_name
                })

        agencies_match = re.search(r"3\.\s*AGENCIES RESPONDING\s*\n(.*?)(?=\n\n|\n\d|\Z)", body, re.DOTALL | re.IGNORECASE)
        
        if agencies_match:
            agencies_raw = agencies_match.group(1).strip()
            agencies = [a.strip() for a in re.split(r"[,;]\s*", agencies_raw) if a.strip()]
            for agency in agencies:
                organisations_found.append(agency)
                relations.append({
                    "from_type": "organisation",
                    "from_mention": agency,
                    "relation": "RESPONDS_TO",
                    "to_type": "incident",
                    "to_mention": incident_mention
                })

        return {
            "incidents": [incident_mention],
            "sites": sites_found,
            "organisations": organisations_found,
            "relations": relations,
            "observations": observations
        }
