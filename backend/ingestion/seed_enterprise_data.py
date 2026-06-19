import os
import sys
import asyncio
from loguru import logger

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from ingestion.document_ingestion_service import DocumentIngestionService
from workflows.knowledge_structurer import KnowledgeStructurer
from workflows.workflow_rule_engine import WorkflowRuleEngine

async def seed_enterprise_data():
    logger.info("Initializing Enterprise ITSM Operational Manuals Seed Process...")
    
    knowledge_dir = os.path.join(backend_path, "knowledge-base")
    os.makedirs(knowledge_dir, exist_ok=True)
    
    # 1. Define example operational documents
    manuals = {
        "service_request_workflow_manual.txt": """
        ITSM SOP: Service Request Catalog Onboarding Manual
        
        Section 1: Asset Request and Laptop Allocation Procedures
        Employees requesting a new laptop, upgrade, or software access must submit a Service Request.
        Parameters needed for laptop requests: employee_email, laptop_model, price.
        
        Section 2: Budget Thresholds and Pending Approvals
        - If the laptop price is greater than $1000, the system must trigger Director Approval.
        - High priority catalog items require department head authorization.
        
        Capabilities: laptop request, asset requests, catalog navigation, asset allocation.
        Target Domain: service_request_management
        """,
        
        "incident_workflow_manual.txt": """
        ITSM SOP: Asset-Related Incident Management Manual
        
        Section 1: Hardware & System Incident Procedures
        Employees experiencing device issues (Laptop, Desktop, or Screen/Monitor) like system crashes, hangs, boot failures, or display flickering should log a Hardware Incident.
        Required diagnostic details: device_type, system_symptom, serial_number.
        Target Domain: incident_management
        
        Section 2: Printer & Scanner Incident Procedures
        Employees encountering printing failures, scanning issues, configuration needs, or paper jams should report a Printer/Scanner Incident.
        Required diagnostic details: issue_detail, printer_location, error_code.
        Target Domain: incident_management
        """
    }

    # Write manuals to the local knowledge base directory
    for filename, content in manuals.items():
        file_path = os.path.join(knowledge_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
        logger.info(f"Created enterprise manual: {filename}")

    # 2. Run Synchronizer Ingestion
    ingestion_service = DocumentIngestionService(watch_dir=knowledge_dir)
    sync_res = await ingestion_service.synchronize_enterprise_sources()
    
    # 3. Run Structuring extraction & Dynamic Skill Registry compiling
    structurer = KnowledgeStructurer()
    struct_res = await structurer.structure_all_pending_documents()
    
    # 4. Seed Workflow Rules
    rule_engine = WorkflowRuleEngine()
    
    # Rule A: Asset Price Threshold
    await rule_engine.register_rule(
        skill_id="service_request_management_agent",
        condition_name="Laptop Price Cost Check",
        condition_logic={
            "parameter": "price",
            "operator": "greater_than",
            "value": "1000"
        },
        actions=["trigger_director_approval"]
    )

    # 5. Seed Category Trees
    from database.models import OperationalDomain
    from database.session import SessionLocal
    db = SessionLocal()
    try:
        incident_domain = db.query(OperationalDomain).filter(OperationalDomain.domain_name == "incident_management").first()
        if incident_domain:
            incident_domain.categories = {
                "Hardware Issues": {
                    "Desktop / Laptop": [
                        "Battery discharging in less than an Hour",
                        "Charger not working",
                        "Keyboard not working",
                        "Mouse Not Working",
                        "Mouse issues",
                        "Others",
                        "Screen Damaged",
                        "Touchpad issues"
                    ],
                    "System Issues": [],
                    "System Crash": [],
                    "System Hang": [],
                    "Screen": [],
                    "System not booting": []
                },
                "Printer/Scanner": {
                    "Printer": [
                        "Paper Jam",
                        "Unable to print documents",
                        "Existing printer reconfiguration"
                    ],
                    "Scanner": [
                        "Unable to scan documents",
                        "Email to scan not working"
                    ]
                },
                "SAP MDG": {
                    "Common to all masters": [
                        "500 internal server error on initiating workflows",
                        "Customers Vendors Materials locked in other MDG CR",
                        "Error while uploading bulk changes in MDG",
                        "Maintaining master data in DV2",
                        "MDG Change request related queries",
                        "QS2 activities for materials, customers, vendors"
                    ],
                    "Customer": [
                        "Sold to party introduced through portal, not reflecting in PRD.",
                        "Colour World customer introduced through the portal, not reflecting in PRD.",
                        "Name change initiated, not updated in PRD.",
                        "Address change initiated in MDG, not updated in PRD.",
                        "Address change in customer code not existing in MDG.",
                        "GST number maintained through portal, but not reflecting in PRD.",
                        "Customer groups 1 to 5 changed through portal, not reflecting in PRD.",
                        "Unable to introduce customer through MDG portal.",
                        "Bulk customer changes effected through the portal, not reflecting in PRD.",
                        "Customer class changed through portal, but not reflecting in PRD.",
                        "Credit limits updated through portal, but not reflecting in PRD.",
                        "Unable to initiate customer bulk changes through the portal.",
                        "Bulk credit limit changes made through portal, not reflecting in PRD.",
                        "Bulk territory changes made through portal, not reflecting in PRD.",
                        "Parent-sister mapping workflow initiated, but not updated in PRD.",
                        "Customer block / unblock workflow initiated but not updated in PRD.",
                        "Customer payment term changed through the portal, not reflecting in PRD.",
                        "Customer extended to sales area through the portal, not reflecting in PRD.",
                        "Customer territory changed through the portal, not reflecting in PRD.",
                        "Customer contact number changed through the portal, not reflecting in PRD.",
                        "Rollback of MDG change request.",
                        "MDG change request activation from the backend.",
                        "Sales area not existing in MDG for extension.",
                        "500 internal server error' error while initiating workflow.",
                        "BUT000 error in existing customer codes",
                        "Getting city code error during customer creation",
                        "Partner function error' while initiating customer change workflows.",
                        "Others"
                    ],
                    "Employee": [
                        "Employee code extension",
                        "Employee email-id changes",
                        "Employee locked in other change requests"
                    ],
                    "Material": [
                        "Material introduced through MDG but not available in production server.",
                        "Material block/unblock workflow initiated in portal, changes not reflecting in PRD.",
                        "Classification data workflow initiated, but changes not reflecting in PRD.",
                        "Shelf life updated during APCO SKU introduction has not got maintained in PRD.",
                        "Shelf life changed through portal, not reflecting in PRD.",
                        "Secondary unit of measure & weight update workflow initiated, but changes not reflecting in PRD.",
                        "Sales organisation extended through the portal, not reflecting in PRD.",
                        "Inspection types updated in portal, not reflecting in PRD.",
                        "Batch management changed in portal, but changes not reflecting in PRD.",
                        "Special procurement changed in portal, but changes not reflecting in PRD.",
                        "Backflush indicator updated in materials, change not reflecting in PRD.",
                        "Source list initiated in MDG, not reflecting in PRD.",
                        "Location data extension workflow initiated in portal, but not extended in PRD.",
                        "Material code is not available in MDG portal to initiate change request.",
                        "Warehouse extension workflow initiated, not extended in PRD.",
                        "Rollback of MDG change request.",
                        "MDG change request activation from the backend.",
                        "Control code workflow initiated, but changes not reflecting in PRD.",
                        "Storage location workflow initiated, but changes not reflecting in PRD.",
                        "Warehouse details changed through the workflow, but changes not reflecting in PRD.",
                        "Unable to initiate material bulk changes through the portal.",
                        "MRO not getting introduced even after second approval.",
                        "Weights and volume have not got maintained in new SKUs introduced.",
                        "500 internal server error' error while initiating workflow.",
                        "Bulk material changes effected through portal, not reflecting in PRD.",
                        "Unable to introduce material from MDG portal.",
                        "Unable to initiate change workflow from MDG portal (BRM related).",
                        "Material does not exist in MDG to initiate workflow.",
                        "Others"
                    ],
                    "System Issues": [
                        "MDG system down"
                    ],
                    "MDG PO integration": [],
                    "MDG new integration/RFC/Service": [],
                    "MDG Master data download requests": [],
                    "MDG Sync issue Debugging": [],
                    "Vendor Master non bulk update/Create": [],
                    "Vendor Master Bulk update/Create": []
                }
            }
            logger.info("Seeded category tree for incident_management.")
            
        sr_domain = db.query(OperationalDomain).filter(OperationalDomain.domain_name == "service_request_management").first()
        if sr_domain:
            sr_domain.categories = {
                "Asset allocation / surrender": {
                    "display_id": 26,
                    "description": "Generic allocation and surrender form for laptops, desktops, and tablets.",
                    "fields": {
                        "sr_name": {
                            "label": "SR Name",
                            "type": "custom_dropdown",
                            "required": True,
                            "choices": [
                                "Laptop Request for New Joinee",
                                "Laptop Request in cases of Transfer / Promotion",
                                "Request for allocation of Temporary / Project / Team laptop/Desktop",
                                "Request for replacement of Desktop/Laptop/Tab",
                                "Surrender of Laptop",
                                "Self certified assets",
                                "Request for laptop allocation (Offrole Only)"
                            ]
                        },
                        "untitled": {
                            "label": "Details",
                            "type": "custom_paragraph",
                            "required": True
                        }
                    },
                    "dynamic_sections": {
                        "Laptop Request for New Joinee": [
                            {"name": "date_of_joining", "label": "Date of Joining", "type": "custom_date", "required": True, "question": "What is the new joinee's Date of Joining (YYYY-MM-DD)?"},
                            {"name": "name_of_new_joinee", "label": "Name of New Joinee", "type": "custom_text", "required": True, "question": "What is the full Name of the New Joinee?"},
                            {"name": "new_joinee_employee_code", "label": "New Joinee employee Code", "type": "custom_text", "required": True, "question": "What is the New Joinee's Employee Code?"},
                            {"name": "new_joinee_contact_number", "label": "New joinee contact number", "type": "custom_number", "required": True, "question": "What is the New Joinee's Contact Number?"},
                            {"name": "new_employee_department", "label": "New joinee department", "type": "custom_text", "required": False, "question": "What is the New Joinee's Department?"},
                            {"name": "location_name", "label": "Location Name", "type": "custom_text", "required": True, "question": "What is the Location Name for delivery?"},
                            {"name": "joiningg_location", "label": "Joining Location", "type": "custom_lookup_bigint", "required": True, "question": "What is the Joining Location ID?"},
                            {"name": "name_of_admin", "label": "Name of Admin", "type": "custom_text", "required": False, "question": "What is the name of the Admin?"},
                            {"name": "contact_number_of_admin", "label": "Contact Number of Admin", "type": "custom_number", "required": False, "question": "What is the contact number of the Admin?"},
                            {"name": "address", "label": "Address", "type": "custom_paragraph", "required": False, "question": "What is the delivery address?"},
                            {"name": "new_joinee_designation", "label": "New Joinee Designation", "type": "custom_text", "required": True, "question": "What is the designation of the new joinee?"}
                        ],
                        "Laptop Request in cases of Transfer / Promotion": [
                            {"name": "asset", "label": "Existing Asset Serial No", "type": "custom_lookup_bigint", "required": False, "question": "What is the existing asset's serial number or ID?"},
                            {"name": "location", "label": "Location", "type": "custom_lookup_bigint", "required": True, "question": "What is the new Location ID or Name?"},
                            {"name": "reason_for_new_asset", "label": "Reason for New Asset", "type": "custom_dropdown", "required": True, "choices": ["Transfer", "Promotion"], "question": "What is the reason for the new asset? (Transfer or Promotion)"},
                            {"name": "shipping_address", "label": "Shipping Address", "type": "custom_paragraph", "required": True, "question": "What is the complete shipping address?"},
                            {"name": "employee_id_admin", "label": "Employee Id Admin", "type": "custom_text", "required": True, "question": "What is the Admin's Employee ID?"},
                            {"name": "nameof_admin", "label": "Name of Admin", "type": "custom_text", "required": True, "question": "What is the Admin's full name?"},
                            {"name": "contact_no_of_admin", "label": "Contact No. of Admin", "type": "custom_text", "required": True, "question": "What is the Admin's contact number?"}
                        ],
                        "Request for allocation of Temporary / Project / Team laptop/Desktop": [
                            {"name": "request_for", "label": "Request for", "type": "custom_dropdown", "required": True, "choices": ["Project", "Team", "Temporary"], "question": "Is this request for a Project, Team, or Temporary requirement?"},
                            {"name": "budgeted_unbudgeted", "label": "Budgeted/UnBudgeted", "type": "custom_dropdown", "required": True, "choices": ["Budgeted", "UnBudgeted"], "question": "Is this request budgeted or unbudgeted?"},
                            {"name": "asset_type", "label": "Asset Type", "type": "custom_dropdown", "required": True, "choices": ["Laptop", "Desktop", "Tablet", "iPad"], "question": "What is the Asset Type required? (Laptop, Desktop, Tablet, iPad)"},
                            {"name": "assets", "label": "Assets", "type": "custom_lookup_bigint", "required": False, "question": "What is the Asset ID to allocate?"},
                            {"name": "quantity", "label": "Quantity", "type": "custom_text", "required": True, "question": "What quantity is required?"},
                            {"name": "date_required", "label": "Date Required", "type": "custom_date", "required": True, "question": "What is the Date Required (YYYY-MM-DD)?"},
                            {"name": "temp_req_location", "label": "Temp Req Location", "type": "custom_lookup_bigint", "required": True, "question": "What is the delivery Location ID or Name?"},
                            {"name": "temp_req_address", "label": "Temp Req Address", "type": "custom_paragraph", "required": False, "question": "What is the delivery address?"},
                            {"name": "return_date", "label": "Expected Return Date", "type": "custom_date", "required": True, "question": "What is the Expected Return Date (YYYY-MM-DD)?"},
                            {"name": "reason_for_temporary_requirement", "label": "Reason for Temporary Requirement", "type": "custom_text", "required": True, "question": "What is the reason for this temporary requirement?"},
                            {"name": "please_select_the_approver", "label": "Please select the Approver", "type": "custom_lookup_bigint", "required": True, "question": "Who is the approver for this request?"}
                        ],
                        "Request for replacement of Desktop/Laptop/Tab": [
                            {"name": "replacement_location", "label": "Replacement Location", "type": "custom_lookup_bigint", "required": True, "question": "What is the Replacement Location ID or Name?"},
                            {"name": "replacement_address", "label": "Replacement Address", "type": "custom_paragraph", "required": True, "question": "What is the complete delivery address?"},
                            {"name": "existing_asset_serial_no", "label": "Existing Asset Serial No", "type": "custom_lookup_bigint", "required": False, "question": "What is the existing asset ID?"},
                            {"name": "asset_serial_no", "label": "Asset Serial no", "type": "custom_text", "required": True, "question": "What is the existing asset's Serial Number?"},
                            {"name": "admin_employee_id", "label": "Admin Employee ID", "type": "custom_text", "required": True, "question": "What is the Admin's Employee ID?"},
                            {"name": "admin_name", "label": "Admin Name", "type": "custom_text", "required": True, "question": "What is the Admin's full name?"},
                            {"name": "admin_contact_no", "label": "Admin Contact No", "type": "custom_text", "required": True, "question": "What is the Admin's contact number?"}
                        ],
                        "Surrender of Laptop": [
                            {"name": "asset_no", "label": "Asset No", "type": "custom_lookup_bigint", "required": True, "question": "What is the Asset Number/ID being surrendered?"},
                            {"name": "date_of_dispatch", "label": "Date of Dispatch", "type": "custom_date", "required": True, "question": "What is the Date of Dispatch (YYYY-MM-DD)?"},
                            {"name": "surrender_type", "label": "Surrender Type", "type": "custom_dropdown", "required": True, "choices": ["Hand", "Couriered"], "question": "What is the surrender type? (Hand or Couriered)"},
                            {"name": "surrender_to_employee_code_agency_name_and_pod_details", "label": "POD details", "type": "custom_text", "required": True, "question": "What are the Surrender Recipient's Employee Code / Agency Name and POD details?"},
                            {"name": "power_adaptor", "label": "Power Adaptor", "type": "custom_dropdown", "required": True, "choices": ["Yes", "No"], "question": "Are you also surrendering the Power Adaptor? (Yes or No)"}
                        ],
                        "Self certified assets": [
                            {"name": "asset_serialno", "label": "Asset Serial No", "type": "custom_text", "required": True, "question": "What is the Asset Serial Number?"},
                            {"name": "make", "label": "Make", "type": "custom_text", "required": False, "question": "What is the make/brand of the asset?"},
                            {"name": "model", "label": "Model", "type": "custom_text", "required": False, "question": "What is the model of the asset?"},
                            {"name": "asset_location", "label": "Asset Location", "type": "custom_lookup_bigint", "required": False, "question": "What is the Location ID or Name?"},
                            {"name": "reason_for_self_certification", "label": "Reason for Self certification", "type": "custom_text", "required": True, "question": "What is the reason for self certification?"}
                        ],
                        "Request for laptop allocation (Offrole Only)": [
                            {"name": "budgeted_unbudgeted", "label": "Budgeted/UnBudgeted", "type": "custom_dropdown", "required": True, "choices": ["Budgeted", "UnBudgeted"], "question": "Is this request budgeted or unbudgeted?"},
                            {"name": "date_of_joining_off_role", "label": "Date of Joining(Off-Role)", "type": "custom_date", "required": True, "question": "What is the off-role joinee's Date of Joining (YYYY-MM-DD)?"},
                            {"name": "name_of_employee_off_role", "label": "Name of Employee(Off-Role)", "type": "custom_text", "required": True, "question": "What is the Name of the off-role Employee?"},
                            {"name": "employee_code_off_role", "label": "Employee Code(Off-Role)", "type": "custom_text", "required": True, "question": "What is the off-role Employee Code?"},
                            {"name": "contact_off_role", "label": "Contact Number (Off-Role)", "type": "custom_number", "required": True, "question": "What is the off-role Employee's Contact Number?"},
                            {"name": "department_off_role", "label": "Department(Off-Role)", "type": "custom_text", "required": False, "question": "What is the off-role department?"},
                            {"name": "location_name_off_role", "label": "Location Name(Off-Role)", "type": "custom_text", "required": True, "question": "What is the off-role Location Name?"},
                            {"name": "joining_location_off_role", "label": "Joining Location(Off-Role)", "type": "custom_text", "required": True, "question": "What is the off-role Joining Location?"},
                            {"name": "name_of_admin_off_role", "label": "Name of Admin (Asian Paints)", "type": "custom_text", "required": True, "question": "What is the Admin's Name?"},
                            {"name": "contact_number_of_admin_off_role", "label": "Contact Number of Admin (Asian Paints)", "type": "custom_number", "required": True, "question": "What is the Admin's Contact Number?"},
                            {"name": "address_off_role", "label": "Address", "type": "custom_paragraph", "required": True, "question": "What is the complete delivery address?"},
                            {"name": "designation_off_role", "label": "Designation(Off-Role)", "type": "custom_text", "required": True, "question": "What is the off-role employee's Designation?"},
                            {"name": "please_select_the_approver", "label": "Please select the Approver", "type": "custom_lookup_bigint", "required": True, "question": "Who is the approver for this request?"}
                        ]
                    }
                },
                "Fixed Assets": {
                    "display_id": 158,
                    "description": "Fixed asset transfer, disposal, or login permission services.",
                    "fields": {
                        "sr_name": {
                            "label": "SR Name",
                            "type": "custom_dropdown",
                            "required": True,
                            "choices": [
                                "New Service Request in Fixed Assets",
                                "Initiate Asset Transfer",
                                "Dispose an asset",
                                "Create new login for Fixed Assets (NGP ID)"
                            ]
                        }
                    },
                    "dynamic_sections": {
                        "New Service Request in Fixed Assets": [
                            {"name": "subject", "label": "Subject", "type": "custom_text", "required": True, "question": "What is the subject for this service request?"},
                            {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide the details/description for this service request."}
                        ],
                        "Initiate Asset Transfer": [
                            {"name": "asset_number", "label": "Asset Number", "type": "custom_text", "required": True, "question": "What is the Asset Number to transfer?"},
                            {"name": "asset_description", "label": "Asset Description", "type": "custom_paragraph", "required": True, "question": "Please provide a brief description of the asset."},
                            {"name": "asset_qty", "label": "Asset Qty", "type": "custom_number", "required": True, "question": "What is the quantity of the asset being transferred?"},
                            {"name": "transfer_to_location_amp_plant_code", "label": "Transfer Location & Plant", "type": "custom_text", "required": True, "question": "What is the destination Location & Plant Code?"},
                            {"name": "transfer_effective_date", "label": "Transfer Effective Date", "type": "custom_date", "required": True, "question": "What is the effective date of transfer (YYYY-MM-DD)?"},
                            {"name": "select_receiver_employee_code", "label": "Select Receiver Employee", "type": "custom_lookup_bigint", "required": True, "question": "What is the Receiver's Employee Code?"},
                            {"name": "new_cost_center", "label": "New cost center", "type": "custom_text", "required": True, "question": "What is the new cost center code?"},
                            {"name": "location_code", "label": "Location code", "type": "custom_text", "required": True, "question": "What is the destination location code?"},
                            {"name": "new_equipment_code", "label": "New Equipment Code", "type": "custom_text", "required": True, "question": "What is the new equipment code?"}
                        ],
                        "Dispose an asset": [
                            {"name": "transfer_from", "label": "Disposal plant code", "type": "custom_text", "required": True, "question": "What is the disposal plant/location code?"}
                        ],
                        "Create new login for Fixed Assets (NGP ID)": [
                            {"name": "sap_id", "label": "SAP ID", "type": "custom_text", "required": True, "question": "What is the user's SAP ID?"},
                            {"name": "user_name", "label": "User Name", "type": "custom_text", "required": True, "question": "What is the user's Name?"},
                            {"name": "role", "label": "Role", "type": "custom_text", "required": True, "question": "What is the user's Role?"},
                            {"name": "plant_code", "label": "Plant Code", "type": "custom_text", "required": True, "question": "What is the user's Plant Code?"},
                            {"name": "function_owner", "label": "Function Owner", "type": "custom_text", "required": True, "question": "Who is the Function Owner?"},
                            {"name": "reference_id", "label": "Reference ID", "type": "custom_text", "required": True, "question": "What is the Reference ID?"},
                            {"name": "user_type_52", "label": "User Type 52", "type": "custom_dropdown", "required": True, "choices": ["Yes", "No"], "question": "Is this a Type 52 User? (Yes/No)"},
                            {"name": "provide_details", "label": "Provide Details", "type": "custom_paragraph", "required": True, "question": "Please provide additional login details."}
                        ]
                    }
                },
                "Additional Hardware Requirement": {
                    "display_id": 67,
                    "description": "Additional Hardware Requirement (RAM/HDD/peripherals/parts).",
                    "fields": {
                        "sr_name": {
                            "label": "SR Name",
                            "type": "custom_dropdown",
                            "required": False,
                            "choices": [
                                "Ad-hoc request",
                                "Additional Requirement/Device Upgradation"
                            ]
                        },
                        "detail": {
                            "label": "Detail",
                            "type": "custom_paragraph",
                            "required": True,
                            "question": "Please provide the details of your request."
                        },
                        "cost_center_details": {
                            "label": "Cost Center Details",
                            "type": "custom_text",
                            "required": True,
                            "question": "What is the Cost Center Details?"
                        },
                        "plant_code": {
                            "label": "Plant Code",
                            "type": "custom_text",
                            "required": True,
                            "question": "What is the Plant Code?"
                        },
                        "gl_code": {
                            "label": "GL code",
                            "type": "custom_text",
                            "required": False,
                            "question": "What is the GL code?"
                        },
                        "service_tag_no": {
                            "label": "Service Tag No",
                            "type": "custom_text",
                            "required": False,
                            "question": "What is the Service Tag No?"
                        },
                        "quantity": {
                            "label": "Quantity",
                            "type": "custom_text",
                            "required": False,
                            "question": "What quantity is required?"
                        },
                        "ship_to_address": {
                            "label": "Ship to address",
                            "type": "custom_text",
                            "required": False,
                            "question": "What is the shipping address?"
                        },
                        "contact_person_name": {
                            "label": "Contact Person Name",
                            "type": "custom_text",
                            "required": True,
                            "question": "What is the Contact Person Name?"
                        },
                        "contact_person_number": {
                            "label": "Contact Person Number",
                            "type": "custom_number",
                            "required": True,
                            "question": "What is the Contact Person Number?"
                        }
                    },
                    "dynamic_sections": {
                        "Ad-hoc request": [
                            {"name": "activity_to_be_done", "label": "Activity to be done", "type": "custom_paragraph", "required": False, "question": "What is the activity to be done?"},
                            {"name": "details", "label": "Details", "type": "custom_paragraph", "required": False, "question": "Please provide any additional details for the ad-hoc request."}
                        ],
                        "Additional Requirement/Device Upgradation": []
                    }
                }
            }
            logger.info("Seeded category tree for service_request_management.")
            
            # Add new Service Requests to service_request_management
            sr_domain.categories["MDG"] = {
                "display_id": 32,
                "description": "SAP MDG bulk or non-bulk master updates, org element creation, and user provisioning.",
                "fields": {
                    "sr_name": {
                        "label": "SR Name",
                        "type": "custom_dropdown",
                        "required": True,
                        "choices": [
                            "Bulk customer block/unblock for IBU",
                            "Bulk Customer Credit Limit Update (IBU)",
                            "Bulk Master Update",
                            "Bulk / Non-Bulk Master Update for IBU",
                            "New user provisioning in MDG",
                            "User Maintenance And CR Forward",
                            "Request for GST Maintenance - Input",
                            "Request for GST Maintenance - Output",
                            "Master Update – Non-Bulk",
                            "New org element create/update"
                        ]
                    },
                    "please_select_the_ibu_financial_approver": {
                        "label": "Please select the IBU Financial Approver",
                        "type": "custom_lookup_bigint",
                        "required": False,
                        "question": "Who is the IBU Financial Approver?"
                    },
                    "please_select_the_mdg_approver": {
                        "label": "Please select the MDG Approver",
                        "type": "custom_lookup_bigint",
                        "required": False,
                        "question": "Who is the MDG Approver?"
                    }
                },
                "dynamic_sections": {
                    "Bulk customer block/unblock for IBU": [
                        {"name": "company_code", "label": "Company Code", "type": "custom_dropdown", "required": True, "choices": ["IWS1", "IID2", "IID1", "IBD1", "ILK2", "ILK1", "INP1", "IBH1", "IEG1", "IET1"], "question": "What is the Company Code?"},
                        {"name": "in_which_system", "label": "In which system", "type": "custom_dropdown", "required": True, "choices": ["PRD", "MDP", "Both"], "question": "In which system? (PRD, MDP, or Both)"},
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."},
                        {"name": "select_ibu_financial_approvers", "label": "Select IBU Financial Approvers", "type": "custom_lookup_bigint", "required": True, "question": "Please select the IBU Financial Approver."}
                    ],
                    "Bulk Customer Credit Limit Update (IBU)": [
                        {"name": "company_code", "label": "Company Code", "type": "custom_dropdown", "required": True, "choices": ["IWS1", "IID2", "IID1", "IBD1", "ILK2", "ILK1", "INP1", "IBH1", "IEG1", "IET1"], "question": "What is the Company Code?"},
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."},
                        {"name": "sales_org", "label": "Sales Org", "type": "custom_text", "required": True, "question": "What is the Sales Org?"}
                    ],
                    "Bulk Master Update": [
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."},
                        {"name": "select_the_type", "label": "Select the Type", "type": "custom_dropdown", "required": True, "choices": ["APIL", "APCO", "APPL", "APCL", "RIPL", "APPG", "APWS"], "question": "What is the Type? (e.g. APIL, APCO)"},
                        {"name": "master_type", "label": "Master Type", "type": "custom_dropdown", "required": False, "choices": ["Customer", "Employee", "Materials", "Vendor"], "question": "What is the Master Type? (Customer, Employee, Materials, Vendor)"},
                        {"name": "business_need", "label": "Business Need", "type": "custom_text", "required": True, "question": "What is the Business Need?"}
                    ],
                    "Bulk / Non-Bulk Master Update for IBU": [
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."},
                        {"name": "business_need", "label": "Business Need", "type": "custom_text", "required": True, "question": "What is the Business Need?"},
                        {"name": "company_codes", "label": "Company Codes", "type": "custom_dropdown", "required": True, "choices": ["ISL2", "ISL1", "INP1", "IBH1", "IID1", "ILK2", "IEG1", "IVU1", "ISB1", "IFJ1"], "question": "What is the Company Code?"},
                        {"name": "master_types", "label": "Master Types", "type": "custom_dropdown", "required": True, "choices": ["Customer", "Employee", "Materials", "Vendor", "IEG1"], "question": "What is the Master Type?"}
                    ],
                    "New user provisioning in MDG": [
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."},
                        {"name": "workflow", "label": "Workflow", "type": "custom_dropdown", "required": True, "choices": ["MRO", "Material", "Vendor", "Customer"], "question": "What is the Workflow? (MRO, Material, Vendor, Customer)"},
                        {"name": "territory_code", "label": "Territory Code", "type": "custom_text", "required": False, "question": "What is the Territory Code?"},
                        {"name": "reference_id", "label": "Reference ID", "type": "custom_text", "required": False, "question": "What is the Reference ID?"},
                        {"name": "senior_or_regional_manager_id", "label": "Senior Or Regional Manager ID", "type": "custom_text", "required": False, "question": "What is the Senior Or Regional Manager ID?"},
                        {"name": "plant_manager_id", "label": "Plant Manager ID", "type": "custom_text", "required": False, "question": "What is the Plant Manager ID?"}
                    ],
                    "User Maintenance And CR Forward": [
                        {"name": "symptom", "label": "Symptom", "type": "custom_text", "required": True, "question": "What is the symptom?"},
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."}
                    ],
                    "Request for GST Maintenance - Input": [
                        {"name": "hsn_sac", "label": "HSN/SAC", "type": "custom_text", "required": True, "question": "What is the HSN/SAC code?"},
                        {"name": "is_hsn_sac_introduced_already_in_erp", "label": "Is HSN/SAC introduced already in ERP", "type": "custom_dropdown", "required": True, "choices": ["No", "Yes"], "question": "Is HSN/SAC introduced already in ERP? (No or Yes)"},
                        {"name": "whether_it_is_applicable_for_rcm", "label": "Whether it is applicable for RCM", "type": "custom_dropdown", "required": True, "choices": ["Yes", "No"], "question": "Is it applicable for RCM? (Yes or No)"},
                        {"name": "rate_in_percentage", "label": "Rate in Percentage", "type": "custom_text", "required": True, "question": "What is the Rate in Percentage?"},
                        {"name": "set_approver", "label": "Set Approver", "type": "custom_lookup_bigint", "required": True, "question": "Who is the approver?"},
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."}
                    ],
                    "Request for GST Maintenance - Output": [
                        {"name": "is_hsn_sac_introduced_already_in_erp", "label": "Is HSN/SAC introduced already in ERP", "type": "custom_dropdown", "required": True, "choices": ["No", "Yes"], "question": "Is HSN/SAC introduced already in ERP? (No or Yes)"},
                        {"name": "hsn_sac", "label": "HSN/SAC", "type": "custom_text", "required": True, "question": "What is the HSN/SAC code?"},
                        {"name": "rate_in_percentage", "label": "Rate in Percentage", "type": "custom_text", "required": True, "question": "What is the Rate in Percentage?"},
                        {"name": "set_approver", "label": "Set Approver", "type": "custom_lookup_bigint", "required": True, "question": "Who is the approver?"},
                        {"name": "details", "label": "Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."}
                    ],
                    "Master Update – Non-Bulk": [
                        {"name": "mention_details", "label": "Mention Details ", "type": "custom_paragraph", "required": True, "question": "Please mention details."},
                        {"name": "select_type", "label": "Select type", "type": "custom_dropdown", "required": True, "choices": ["APIL", "APCO", "APPL", "APCL", "RIPL", "APPG", "APWS"], "question": "What is the Type? (e.g. APIL, APCO)"},
                        {"name": "select_master_type", "label": "Select Master Type", "type": "custom_dropdown", "required": True, "choices": ["Customer", "Material", "Vendor"], "question": "What is the Master Type? (Customer, Material, Vendor)"},
                        {"name": "mention_business_need", "label": "Mention Business Need", "type": "custom_text", "required": True, "question": "What is the Business Need?"}
                    ],
                    "New org element create/update": [
                        {"name": "add_details", "label": "Add Details", "type": "custom_paragraph", "required": True, "question": "Please provide details."},
                        {"name": "select_your_master_type", "label": "Select your Master Type", "type": "custom_dropdown", "required": True, "choices": ["GL", "Cost Center"], "question": "What is the Master Type? (GL or Cost Center)"},
                        {"name": "gl_type", "label": "GL Type", "type": "custom_dropdown", "required": True, "choices": ["Code creation", "Block/Unblock", "Company extension"], "question": "What is the GL Type?"},
                        {"name": "cost_center", "label": "Cost center", "type": "custom_dropdown", "required": True, "choices": ["Creation", "Block/Unblock", "Company extension"], "question": "What is the Cost Center Type?"},
                        {"name": "mention_business_need", "label": "Mention Business Need", "type": "custom_text", "required": True, "question": "What is the Business Need?"}
                    ]
                }
            }
            
            sr_domain.categories["Account Unlock"] = {
                "display_id": 199,
                "description": "Unlock locked SAP accounts.",
                "fields": {
                    "account_unlock_for": {
                        "label": "Account unlock for",
                        "type": "custom_dropdown",
                        "required": True,
                        "choices": ["SAP MDG", "SAP PRD", "SAP EWM"]
                    },
                    "for_whom_to_unlock": {
                        "label": "For whom to unlock?",
                        "type": "custom_dropdown",
                        "required": True,
                        "choices": ["Self", "Common ID's", "Someone else"]
                    }
                },
                "dynamic_sections": {
                    "SAP MDG": [],
                    "SAP PRD": [],
                    "SAP EWM": [
                        {"name": "whom_to_reset_for", "label": "Whom to reset for?", "type": "custom_dropdown", "required": True, "choices": ["Self", "Common ID"], "question": "Who are you resetting for? (Self or Common ID)"},
                        {"name": "add_common_id", "label": "Add Common ID", "type": "custom_text", "required": True, "question": "What is the Common ID?"},
                        {"name": "plant_code", "label": "Plant Code", "type": "custom_dropdown", "required": True, "choices": ["1103", "1104", "1106", "1107", "1108", "1109", "1110", "1116"], "question": "What is the Plant Code?"}
                    ],
                    "Self": [],
                    "Common ID's": [
                        {"name": "common_id", "label": "Common ID", "type": "custom_text", "required": True, "question": "What is the Common ID?"}
                    ],
                    "Someone else": [
                        {"name": "requested_for", "label": "Requested for", "type": "custom_lookup_bigint", "required": True, "question": "Who is the user you are requesting for?"}
                    ]
                }
            }

            sr_domain.categories["Password reset"] = {
                "display_id": 200,
                "description": "Reset SAP account passwords.",
                "fields": {
                    "password_reset_for": {
                        "label": "Password reset for",
                        "type": "custom_dropdown",
                        "required": True,
                        "choices": ["SAP MDG", "SAP PRD", "SAP EWM", "SAP TM/TLB"]
                    },
                    "for_whom_to_reset": {
                        "label": "For whom to reset?",
                        "type": "custom_dropdown",
                        "required": True,
                        "choices": ["Self", "Common ID's", "Someone else"]
                    }
                },
                "dynamic_sections": {
                    "SAP MDG": [],
                    "SAP PRD": [],
                    "SAP EWM": [
                        {"name": "whom_to_reset_for", "label": "whom to reset for?", "type": "custom_dropdown", "required": True, "choices": ["Self", "Common ID"], "question": "Who are you resetting for? (Self or Common ID)"},
                        {"name": "common_id", "label": "Common ID", "type": "custom_text", "required": True, "question": "What is the Common ID?"},
                        {"name": "plant_code", "label": "Plant Code", "type": "custom_dropdown", "required": True, "choices": ["1103", "1104", "1106", "1107", "1108", "1109", "1110", "1116"], "question": "What is the Plant Code?"}
                    ],
                    "SAP TM/TLB": [
                        {"name": "reset_for_whom", "label": "Reset for whom?", "type": "custom_dropdown", "required": True, "choices": ["Self", "Common ID"], "question": "Who are you resetting for? (Self or Common ID)"},
                        {"name": "add_common_id", "label": "Add Common ID", "type": "custom_text", "required": True, "question": "What is the Common ID?"}
                    ],
                    "Self": [],
                    "Common ID's": [
                        {"name": "common_id_s", "label": "Common ID's", "type": "custom_text", "required": True, "question": "What is the Common ID?"}
                    ],
                    "Someone else": [
                        {"name": "requested_for", "label": "Requested for", "type": "custom_lookup_bigint", "required": True, "question": "Who is the user you are requesting for?"}
                    ]
                }
            }

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(sr_domain, "categories")
            logger.info("Successfully updated service_request_management categories dictionary.")
            
        db.commit()
    except Exception as e:
        logger.error(f"Failed to seed category trees: {e}")
        db.rollback()
    finally:
        db.close()

    logger.info("Enterprise Seeding and Dynamic Compilation completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_enterprise_data())
