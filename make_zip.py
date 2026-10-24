import zipfile, pathlib
with zipfile.ZipFile("backend.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in pathlib.Path("app").rglob("*.py"):
        z.write(f)
    z.write("requirements-deploy.txt", "requirements.txt")
print("backend.zip created")
