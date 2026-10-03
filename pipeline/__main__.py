"""Command-line entry point. Replace with your pipeline.

Run:
    python -m pipeline --emails data/emails --reference data/reference --out output
"""
import argparse
import glob
import os
from pathlib import Path

from .extract import Extractor
from .transform import Transformer
from .database import PipelineDatabase



def main():
    parser = argparse.ArgumentParser(description="Incident email IE pipeline")
    parser.add_argument("--emails", required=True, type=Path, help="folder of .eml files")
    parser.add_argument("--reference", required=True, type=Path, help="folder of reference list CSV files")
    parser.add_argument("--out", required=True, type=Path, help="output folder")
    args = parser.parse_args()
    
    
    extractor = Extractor()
    transformer = Transformer(args.reference)
    db = PipelineDatabase(args.out)

    eml_files = glob.glob(os.path.join(args.emails, "**/*.eml"), recursive=True)
    if not eml_files:
        eml_files = glob.glob(os.path.join(args.emails, "*.eml"))

    print(f"Processing {len(eml_files)} email files...")

    for file_path in eml_files:
        parsed_email = extractor.parse_file(file_path)
        extracted = extractor.extract_structured_data(parsed_email)

        # Resolve Incidents
        incident_map = {}
        for inc_mention in extracted["incidents"]:
            inc_id, is_new = transformer.resolve("incident", inc_mention)
            db.insert_entity(inc_id, "incident", inc_mention, is_new)
            incident_map[inc_mention] = inc_id

        # Resolve Sites
        site_map = {}
        for site_mention in extracted["sites"]:
            site_id, is_new = transformer.resolve("site", site_mention)
            db.insert_entity(site_id, "site", site_mention, is_new)
            site_map[site_mention] = site_id
    

        # Resolve Organisations
        org_map = {}
        for org_mention in extracted["organisations"]:
            org_id, is_new = transformer.resolve("organisation", org_mention)
            db.insert_entity(org_id, "organisation", org_mention, is_new)
            org_map[org_mention] = org_id

        # Save Relations
        for rel in extracted["relations"]:
            f_type, f_mention = rel["from_type"], rel["from_mention"]
            t_type, t_mention = rel["to_type"], rel["to_mention"]

            f_id = (incident_map.get(f_mention) if f_type == "incident" 
                    else site_map.get(f_mention) if f_type == "site" 
                    else org_map.get(f_mention))
            
            t_id = (incident_map.get(t_mention) if t_type == "incident" 
                    else site_map.get(t_mention) if t_type == "site" 
                    else org_map.get(t_mention))

            if f_id and t_id:
                db.insert_relation(f_id, rel["relation"], t_id)

        # Save Observations
        for obs in extracted["observations"]:
            s_id = site_map.get(obs["site_mention"])
            if s_id:
                db.insert_observation(
                    entity_id=s_id,
                    prop_name=obs["property_name"],
                    prop_value=obs["property_value"],
                    reported_at=obs["reported_at"],
                    email_id=obs["email_id"]
                )
        
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Pipeline executed successfully. Output written to {args.out}")


if __name__ == "__main__":
    main()
