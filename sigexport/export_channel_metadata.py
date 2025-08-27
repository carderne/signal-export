"""Export logic for channel metadata"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sigexport.models import Contact, Contacts


def export_channel_metadata(
    dest: Path,
    contacts: Contacts,
    owner: Optional[Contact],
    include_chats: Optional[list[str]] = None,
) -> None:
    """for each channel, write two files containing information about that group's membership:
    "meta.json": a JSON object with member information
    "members.csv": a flattened table of the info in meta.json, with one row per group member
    """

    owner_name = owner.profile_name if owner else None
    owner_service_id = owner.serviceId if owner else None

    contacts_by_serviceId = {c.serviceId: c for c in contacts.values()}
    all_groups = [g for g in contacts.values() if g.is_group]
    for key, c in contacts.items():
        name = c.name or c.id
        if not c.is_group:
            continue
        if include_chats is not None and c.name not in include_chats:
            continue
        # ensure that the output folder for this channel exists
        os.makedirs(dest / name, exist_ok=True)
        members = [contacts_by_serviceId[m] for m in c.members] if c.members else []
        group_meta = {
            "name": name,
            "exported_by": owner_name,
            "exported_on": datetime.now().isoformat(),
            "members": [
                {
                    "name": member.name,
                    "display_name": member.profile_name,
                    "number": member.number,
                    "other_groups": [
                        g.name
                        for g in all_groups
                        # if the other group has this member too
                        if member.serviceId in (g.members or [])
                        # but not if we're looking at the current group
                        if key != g.id
                        # redact the owner's group memberships
                        and member.serviceId != owner_service_id
                    ],
                }
                for member in members
            ],
        }
        flat_meta = [
            {
                "group_name": group_meta["name"],
                "exported_by": group_meta["exported_by"],
                "exported_on": group_meta["exported_on"],
                "num_shared_groups": len(m["other_groups"]),
                **m,
            }
            for m in group_meta["members"]
        ]

        members_json_path = dest / name / "meta.json"
        with open(members_json_path, "w", encoding="utf-8") as members_json:
            json.dump(group_meta, members_json, ensure_ascii=False, indent=2)

        members_csv_path = dest / name / "members.csv"
        if len(flat_meta) > 0:
            with open(members_csv_path, "w", encoding="utf-8") as members_csv:
                writer = csv.DictWriter(members_csv, fieldnames=flat_meta[0].keys())
                writer.writeheader()
                writer.writerows(flat_meta)
