import os
import subprocess
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCTOR_EXE = os.path.join(REPO_ROOT, "examples", "schema_doctor.exe")
NOVA_EXE = os.path.join(REPO_ROOT, "nova.exe")

@pytest.fixture(scope="module")
def doctor_bin():
    if not os.path.isfile(DOCTOR_EXE):
        # Build if not present
        src = os.path.join(REPO_ROOT, "examples", "schema_doctor.nv")
        res = subprocess.run([NOVA_EXE, "build", "-o", DOCTOR_EXE, src], capture_output=True, text=True)
        assert res.returncode == 0, f"Failed to build schema_doctor.exe: {res.stdout}\n{res.stderr}"
    assert os.path.isfile(DOCTOR_EXE)
    return DOCTOR_EXE

def test_binary_size_under_350kb(doctor_bin):
    size_bytes = os.path.getsize(doctor_bin)
    size_kb = size_bytes / 1024.0
    print(f"schema_doctor.exe size: {size_kb:.2f} KB ({size_bytes} bytes)")
    assert size_kb < 350.0, f"Binary exceeds 350KB limit: {size_kb:.2f} KB"

def test_cli_help(doctor_bin):
    for flag in ["--help", "help", "-h"]:
        res = subprocess.run([doctor_bin, flag], capture_output=True, text=True)
        assert res.returncode == 0
        assert "Nova Schema Doctor" in res.stdout
        assert "Usage: schema_doctor" in res.stdout

def test_cli_valid_payload(doctor_bin, tmp_path):
    schema = {
        "type": "object",
        "required": ["name", "age", "active", "scores"],
        "properties": {
            "name": {"type": "string", "minLength": 2, "maxLength": 50},
            "age": {"type": "integer", "minimum": 0, "maximum": 120},
            "active": {"type": "boolean"},
            "scores": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "integer", "minimum": 0}
            }
        }
    }
    data = {
        "name": "Nova User",
        "age": 30,
        "active": True,
        "scores": [10, 20, 30]
    }
    
    schema_file = tmp_path / "schema.json"
    data_file = tmp_path / "data.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    data_file.write_text(json.dumps(data), encoding="utf-8")
    
    res = subprocess.run([doctor_bin, str(schema_file), str(data_file)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "[PASS]" in res.stdout
    assert "conforms to schema" in res.stdout

def test_cli_invalid_payload_catches_errors(doctor_bin, tmp_path):
    schema = {
        "type": "object",
        "required": ["name", "email", "age"],
        "properties": {
            "name": {"type": "string", "minLength": 5},
            "email": {"type": "string"},
            "age": {"type": "integer", "minimum": 18, "maximum": 65}
        }
    }
    # Violations:
    # 1. "name" too short (3 < 5)
    # 2. "email" missing
    # 3. "age" wrong type (string instead of integer)
    data = {
        "name": "Bob",
        "age": "underage"
    }
    
    schema_file = tmp_path / "schema.json"
    data_file = tmp_path / "data.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    data_file.write_text(json.dumps(data), encoding="utf-8")
    
    res = subprocess.run([doctor_bin, str(schema_file), str(data_file)], capture_output=True, text=True)
    assert res.returncode != 0
    assert "[FAIL]" in res.stdout
    assert "required property missing" in res.stdout
    assert "expected type 'integer'" in res.stdout
    assert "less than minLength" in res.stdout

def test_cli_missing_file(doctor_bin, tmp_path):
    schema_file = tmp_path / "nonexistent_schema.json"
    data_file = tmp_path / "data.json"
    data_file.write_text("{}", encoding="utf-8")
    
    res = subprocess.run([doctor_bin, str(schema_file), str(data_file)], capture_output=True, text=True)
    assert res.returncode != 0
    assert "Error: schema file not found" in res.stdout

