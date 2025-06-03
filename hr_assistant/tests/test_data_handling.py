# hr_assistant/tests/test_data_handling.py
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

# Attempt to import ObjectId, handle if not available for testing basic sanitize
try:
    from bson.objectid import ObjectId
    BSON_AVAILABLE_FOR_TEST = True
except ImportError:
    BSON_AVAILABLE_FOR_TEST = False
    # Define a dummy ObjectId class for tests if bson is not available
    class ObjectId:
        def __init__(self, id=None):
            # Generate a dummy hex string if id is None, similar to ObjectId behavior
            self.id_str = id if id else "dummyhexstrings12345"
        def __str__(self):
            return self.id_str
        def __repr__(self):
            return f"ObjectId('{self.id_str}')"
        def __eq__(self, other):
            return isinstance(other, ObjectId) and self.id_str == other.id_str
        def __hash__(self):
            return hash(self.id_str)

# Imports from the application
# We need to ensure MONGODB_AVAILABLE is True for MongoDBService tests, or mock it.
# For simplicity in this context, we might need to patch MONGODB_AVAILABLE directly in tests for MongoDBService.
# from hr_assistant.services.mongodb_service import MongoDBService, MONGODB_AVAILABLE as MONGODB_SERVICE_AVAILABLE
from hr_assistant.main import sanitize_for_json
# For employee module tests, we might need to initialize its own services or mock them
# from hr_assistant.modules.employee import get_employee_data_tool, initialize_services as init_employee_services


# --- Tests for sanitize_for_json from main.py ---

def test_sanitize_objectid():
    """Tests that ObjectId instances are converted to strings."""
    if not BSON_AVAILABLE_FOR_TEST:
        # Create a dummy ObjectId if bson is not installed
        test_oid = ObjectId("507f1f77bcf86cd799439011")
    else:
        test_oid = ObjectId() # Real ObjectId if bson is installed

    data = {
        "_id": test_oid,
        "nested": {
            "oid_field": test_oid
        },
        "list_of_oids": [test_oid, test_oid]
    }
    sanitized = sanitize_for_json(data)
    assert isinstance(sanitized["_id"], str)
    assert isinstance(sanitized["nested"]["oid_field"], str)
    assert isinstance(sanitized["list_of_oids"][0], str)
    assert sanitized["_id"] == str(test_oid)

def test_sanitize_datetime():
    """Tests that datetime instances are converted to ISO format strings."""
    now = datetime.now(timezone.utc)
    data = {
        "created_at": now,
        "nested": {
            "updated_at": now
        },
        "list_of_dates": [now, now]
    }
    sanitized = sanitize_for_json(data)
    assert sanitized["created_at"] == now.isoformat()
    assert sanitized["nested"]["updated_at"] == now.isoformat()
    assert sanitized["list_of_dates"][0] == now.isoformat()

def test_sanitize_mixed_data():
    """Tests sanitization with a complex structure including various types."""
    if not BSON_AVAILABLE_FOR_TEST:
        test_oid = ObjectId("507f1f77bcf86cd799439012")
    else:
        test_oid = ObjectId()

    now = datetime.now(timezone.utc)
    data = {
        "id_field": test_oid,
        "timestamp": now,
        "name": "Test Data",
        "value": 123,
        "is_active": True,
        "details": {
            "sub_id": test_oid,
            "sub_time": now,
            "notes": ["note1", {"deep_oid": test_oid}]
        },
        "items": [
            {"item_oid": test_oid, "item_time": now},
            "string_item",
            456
        ]
    }
    sanitized = sanitize_for_json(data)
    assert isinstance(sanitized["id_field"], str)
    assert sanitized["timestamp"] == now.isoformat()
    assert isinstance(sanitized["details"]["sub_id"], str)
    assert sanitized["details"]["sub_time"] == now.isoformat()
    assert isinstance(sanitized["details"]["notes"][1]["deep_oid"], str)
    assert isinstance(sanitized["items"][0]["item_oid"], str)
    assert sanitized["items"][0]["item_time"] == now.isoformat()
    assert sanitized["name"] == "Test Data" # Check other types remain
    assert sanitized["value"] == 123
    assert sanitized["is_active"] is True

def test_sanitize_already_serializable():
    """Tests that already serializable data is not broken."""
    data = {
        "name": "Test",
        "age": 30,
        "city": "New York",
        "scores": [1, 2, 3],
        "metadata": {"key": "value"}
    }
    sanitized = sanitize_for_json(data.copy()) # Pass a copy
    assert sanitized == data

def test_sanitize_with_none_values():
    """Tests that None values are handled correctly."""
    data = {
        "name": "Test",
        "middle_name": None,
        "details": {"description": None}
    }
    sanitized = sanitize_for_json(data)
    assert sanitized["middle_name"] is None
    assert sanitized["details"]["description"] is None

# --- Tests for MongoDBService ---

@patch('hr_assistant.services.mongodb_service.MONGODB_AVAILABLE', True)
@patch('hr_assistant.services.mongodb_service.MongoClient')
def test_mongodb_service_convert_objectid_direct(MockMongoClient):
    """Tests the _convert_objectid_to_str method of MongoDBService directly."""
    # Mock MongoClient and its dependencies minimally, not strictly needed for this direct test
    # but good practice if _connect was more complex or called early.
    mock_client_instance = MockMongoClient.return_value
    mock_client_instance.admin.command.return_value = {"ok": 1} # Mock ping

    from hr_assistant.services.mongodb_service import MongoDBService
    service = MongoDBService()

    oid1 = ObjectId() if BSON_AVAILABLE_FOR_TEST else ObjectId("testoid1")
    oid2 = ObjectId() if BSON_AVAILABLE_FOR_TEST else ObjectId("testoid2")

    data = {
        "_id": oid1,
        "other_field": "value",
        "nested": {"sub_oid": oid2},
        "list_field": [oid1, {"another_oid": oid2}, "stringval"]
    }

    converted = service._convert_objectid_to_str(data)

    assert isinstance(converted["_id"], str)
    assert converted["_id"] == str(oid1)
    assert converted["other_field"] == "value"
    assert isinstance(converted["nested"]["sub_oid"], str)
    assert converted["nested"]["sub_oid"] == str(oid2)
    assert isinstance(converted["list_field"][0], str)
    assert converted["list_field"][0] == str(oid1)
    assert isinstance(converted["list_field"][1]["another_oid"], str)
    assert converted["list_field"][1]["another_oid"] == str(oid2)
    assert converted["list_field"][2] == "stringval"

@patch('hr_assistant.services.mongodb_service.MONGODB_AVAILABLE', True)
@patch('hr_assistant.services.mongodb_service.MongoClient')
def test_get_employee_by_id_converts_objectid(MockMongoClient, mock_mongo_available_true_unused):
    from hr_assistant.services.mongodb_service import MongoDBService

    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_client_instance = MockMongoClient.return_value
    mock_client_instance.admin.command.return_value = {"ok": 1}
    mock_client_instance.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection

    original_oid = ObjectId() if BSON_AVAILABLE_FOR_TEST else ObjectId("original123abc")
    mock_employee_data = {"_id": original_oid, "name": "Test User", "dept_oid": original_oid}
    mock_collection.find_one.return_value = mock_employee_data

    service = MongoDBService()
    result = service.get_employee_by_id("some_id")

    assert result is not None
    assert isinstance(result["_id"], str)
    assert result["_id"] == str(original_oid)
    assert isinstance(result["dept_oid"], str)
    assert result["dept_oid"] == str(original_oid)
    mock_collection.find_one.assert_called_once()

@patch('hr_assistant.services.mongodb_service.MONGODB_AVAILABLE', True)
@patch('hr_assistant.services.mongodb_service.MongoClient')
def test_search_employees_converts_objectid(MockMongoClient, mock_mongo_available_true_unused):
    from hr_assistant.services.mongodb_service import MongoDBService

    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_client_instance = MockMongoClient.return_value
    mock_client_instance.admin.command.return_value = {"ok": 1}
    mock_client_instance.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection

    oid1 = ObjectId() if BSON_AVAILABLE_FOR_TEST else ObjectId("oidsearch1")
    oid2 = ObjectId() if BSON_AVAILABLE_FOR_TEST else ObjectId("oidsearch2")
    mock_results_data = [
        {"_id": oid1, "name": "User One", "ref_oid": oid2},
        {"_id": oid2, "name": "User Two", "ref_oid": oid1}
    ]
    mock_collection.find.return_value.limit.return_value = mock_results_data

    service = MongoDBService()

    # Test search_employees_by_text
    results_text = service.search_employees_by_text("test query")
    assert len(results_text) == 2
    for item in results_text:
        assert isinstance(item["_id"], str)
        assert isinstance(item["ref_oid"], str)

    # Reset mock for next call if needed, or use different mock instances
    mock_collection.find.return_value.limit.return_value = mock_results_data # Re-assign for clarity or if find is stateful

    # Test search_employees_by_criteria
    results_criteria = service.search_employees_by_criteria({"name": "User"})
    assert len(results_criteria) == 2
    for item in results_criteria:
        assert isinstance(item["_id"], str)
        assert isinstance(item["ref_oid"], str)

# --- Tests for Employee Module (get_employee_data_tool) ---

# We need to patch the services used by employee module at their lookup location
@patch('hr_assistant.modules.employee.MONGODB_AVAILABLE', True)
@patch('hr_assistant.modules.employee.VECTOR_SEARCH_AVAILABLE', False) # Assuming not needed for this specific test
@patch('hr_assistant.modules.employee.QUERY_PARSER_AVAILABLE', True) # Or False to test simple_query_parse path
@patch('hr_assistant.modules.employee.query_parser_service') # Mock the instance if QUERY_PARSER_AVAILABLE is True
@patch('hr_assistant.modules.employee.mongodb_service') # Mock the instance
def test_self_query_uses_requester_id(
    mock_employee_mongo_service,
    mock_employee_qps_service,
    mock_qps_available,
    mock_vs_available,
    mock_mongo_available_in_employee
    ):
    from hr_assistant.modules.employee import get_employee_data_tool, initialize_services

    # Initialize services within the employee module (they will use the mocks)
    # This is important because employee.py might have its own global instances of services
    initialize_services()


    requester_id = "user_self_123"
    query = "show my information"

    # Configure QueryParserService mock (if used)
    if mock_qps_available: # Corresponds to QUERY_PARSER_AVAILABLE = True
        mock_employee_qps_service.parse_query.return_value = {
            "original_query": query,
            "intent": "get_employee_info",
            "parameters": {"employee_id": requester_id, "is_self_query": True},
            "data_requested": [],
            "confidence": 0.9
        }

    # Configure MongoDBService mock (used by employee module)
    # This mock is injected into hr_assistant.modules.employee.mongodb_service
    mock_requester_data = {
        "_id": requester_id, "firstName": "Self", "lastName": "User",
        "employeeInfo": [{"grade": "L5", "depName": "IT"}], "role": "Engineer"
    }
    mock_employee_mongo_service.get_employee_by_id.return_value = mock_requester_data

    # Mock get_employee_team_members if _get_requester_info calls it
    if hasattr(mock_employee_mongo_service, 'get_employee_team_members'):
        mock_employee_mongo_service.get_employee_team_members.return_value = []


    result = get_employee_data_tool(query=query, requester_id=requester_id)

    assert result["success"] is True
    # Crucially, check that the mongodb_service.get_employee_by_id was called for the requester_id
    # This call happens inside _get_requester_info and potentially in _execute_search_with_fallbacks

    # Check call to _get_requester_info
    mock_employee_mongo_service.get_employee_by_id.assert_any_call(requester_id)

    # If using simple_query_parse (QUERY_PARSER_AVAILABLE = False),
    # the employee_id from self-query is directly used in _execute_search_with_fallbacks
    # If using QueryParserService, it depends on its output.
    # For this test, we assume the parsed query (mocked or real) correctly identifies the employee_id as requester_id.

    # The first call to get_employee_by_id is for requester_info.
    # The second call is to fetch the actual target employee data.
    calls = [call(requester_id), call(requester_id)]
    mock_employee_mongo_service.get_employee_by_id.assert_has_calls(calls, any_order=True)

    # Verify that the returned data corresponds to the requester
    assert len(result["data"]) == 1
    assert result["data"][0]["_id"] == requester_id

# To run these tests, you would typically use pytest from your terminal:
# pytest hr_assistant/tests/test_data_handling.py
# Ensure that PYTHONPATH is set up correctly if running from a different directory,
# or install your package in editable mode (pip install -e .).
# Also, ensure 'bson' (from pymongo) is installed if you want to test with real ObjectIds.
# If not, the dummy ObjectId class will be used.

# For MongoDBService tests, we'd need to do something like:
# from hr_assistant.services.mongodb_service import MongoDBService
# Then inside the test:
# with patch('hr_assistant.services.mongodb_service.MONGODB_AVAILABLE', True):
#     service = MongoDBService()
#     # ... setup mocks for service.client ...
#     # ... call service methods ...
# This ensures the service initializes even if pymongo isn't actually installed in the test env,
# by overriding the MONGODB_AVAILABLE check.
# Alternatively, ensure pymongo is a dev dependency for tests.

# For employee module tests:
# from hr_assistant.modules.employee import get_employee_data_tool, initialize_services
# # Before tests that use these services:
# with patch('hr_assistant.modules.employee.MONGODB_AVAILABLE', True), \
#      patch('hr_assistant.modules.employee.VECTOR_SEARCH_AVAILABLE', True), \ # or False if not needed
#      patch('hr_assistant.modules.employee.QUERY_PARSER_AVAILABLE', True): # or False
#      initialize_services() # This will attempt to init the (mocked) services
# Then run the test.
# mock_mongo_service would be the one passed to the test function.
# Example: mock_mongo_service.get_employee_by_id.return_value = {"_id": "test_user_123", "name": "Test User"}

# More detailed test structure for MongoDBService:
# @patch('hr_assistant.services.mongodb_service.MONGODB_AVAILABLE', True)
# @patch('hr_assistant.services.mongodb_service.MongoClient')
# def test_get_employee_by_id_converts_objectid_detail(MockMongoClient, mock_mongo_available_true):
#     # Setup mock client and collection
#     mock_collection = MagicMock()
#     mock_db = MagicMock()
#     mock_client_instance = MockMongoClient.return_value
#     mock_client_instance.admin.command.return_value = {"ok": 1} # Mock ping
#     mock_client_instance.__getitem__.return_value = mock_db
#     mock_db.__getitem__.return_value = mock_collection

#     original_oid = ObjectId() if BSON_AVAILABLE_FOR_TEST else ObjectId("original123abc")
#     mock_employee_data = {"_id": original_oid, "name": "Test User", "dept_oid": original_oid}
#     mock_collection.find_one.return_value = mock_employee_data

#     service = MongoDBService() # MongoDBService will use the mocked MongoClient
#     result = service.get_employee_by_id("some_id")

#     assert result is not None
#     assert isinstance(result["_id"], str)
#     assert result["_id"] == str(original_oid)
#     assert isinstance(result["dept_oid"], str)
#     assert result["dept_oid"] == str(original_oid)
#     mock_collection.find_one.assert_called_once()
#     # Add more assertions as needed
```
