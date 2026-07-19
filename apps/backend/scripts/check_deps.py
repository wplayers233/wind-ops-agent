import importlib

REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pytest",
    "httpx",
]

print("[deps] checking required Python packages...")
for module_name in REQUIRED_MODULES:
    importlib.import_module(module_name)
    print(f"[deps] ok: {module_name}")
print("[deps] all required packages are available")
