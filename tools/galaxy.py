import sys
import os
import json
import urllib.request
import urllib.error
import zipfile
import io

REGISTRY_URL = "https://galaxy-registry.vercel.app/api"

def run_galaxy_cli(args):
    if not args:
        print("Galaxy Package Manager")
        print("  init              Initialize a new Nova project")
        print("  install <pkg>     Install a package from the registry")
        print("  publish           Publish the current package")
        return

    cmd = args[0]
    if cmd == "init":
        galaxy_init()
    elif cmd == "install":
        if len(args) < 2:
            print("Usage: nova galaxy install <pkg>")
            return
        galaxy_install(args[1])
    else:
        print(f"Unknown galaxy command: {cmd}")

def galaxy_init():
    if os.path.exists("galaxy.json"):
        print("Error: galaxy.json already exists.")
        return
    
    project_name = os.path.basename(os.getcwd())
    config = {
        "name": project_name,
        "version": "1.0.0",
        "dependencies": {}
    }
    
    with open("galaxy.json", "w") as f:
        json.dump(config, f, indent=4)
        
    os.makedirs("src", exist_ok=True)
    os.makedirs("tests", exist_ok=True)
    
    main_nv = os.path.join("src", "main.nv")
    if not os.path.exists(main_nv):
        with open(main_nv, "w") as f:
            f.write('print("Hello from Galaxy!")\n')
            
    print(f"Initialized new Galaxy project '{project_name}'")

def galaxy_install(pkg_name):
    print(f"Resolving '{pkg_name}'...")
    # For now, simulate fetching from registry by assuming direct github url if it contains a slash
    github_repo = None
    if "/" in pkg_name:
        github_repo = pkg_name
    else:
        # Mocking registry hit for now before the backend is up
        print(f"Hitting registry {REGISTRY_URL}/packages/{pkg_name} ...")
        print("Registry API not live yet. For now, use direct GitHub repo (e.g. nova galaxy install user/repo)")
        return
        
    print(f"Fetching {github_repo} from GitHub...")
    download_url = f"https://github.com/{github_repo}/archive/refs/heads/main.zip"
    
    try:
        req = urllib.request.Request(download_url, headers={'User-Agent': 'Nova-Galaxy/1.0'})
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
            
        os.makedirs("galaxy_modules", exist_ok=True)
        
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            z.extractall("galaxy_modules")
            
        # The zip usually contains a folder named repo-main, we should probably rename it to pkg_name
        # But for now this works as a prototype
        print(f"Successfully installed '{pkg_name}' into galaxy_modules/")
        
        # Add to galaxy.json
        if os.path.exists("galaxy.json"):
            with open("galaxy.json", "r") as f:
                config = json.load(f)
            config.setdefault("dependencies", {})[pkg_name] = github_repo
            with open("galaxy.json", "w") as f:
                json.dump(config, f, indent=4)
                
    except Exception as e:
        print(f"Error installing package: {e}")

