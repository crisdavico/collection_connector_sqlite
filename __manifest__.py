# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Collections SQLite Connector",
    "version": "19.0.1.8.0",
    "category": "Sales/CRM",
    "summary": "Read-only SQLite seller, customer, and invoice source for Collections",
    "author": "Seedian",
    "website": "https://seedian.ai",
    "depends": ["collection"],
    "data": [
        "views/collection_connector_views.xml",
        "data/collection_connector_data.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}
