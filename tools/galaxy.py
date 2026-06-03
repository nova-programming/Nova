import sys
import os
import json
import urllib.request
import urllib.error
import zipfile
import io

REGISTRY_URL = "https://galaxy-registry.vercel.app"

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
            f.write('print("Hello from Galaxy!")\\n')
            
    print(f"Initialized new Galaxy project '{project_name}'")

def galaxy_install(pkg_name):
    print(f"Resolving '{pkg_name}'...")
    
    github_repo = None
    download_url = None
    
    if "/" in pkg_name:
        github_repo = pkg_name
        download_url = f"https://github.com/{github_repo}/archive/refs/heads/main.zip"
    else:
        try:
            req = urllib.request.Request(f"{REGISTRY_URL}/api/packages/{pkg_name}")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                github_repo = data.get("github_repo")
                download_url = data.get("download_url")
        except urllib.error.HTTPError as e:
            print(f"Error: Package '{pkg_name}' not found in registry (HTTP {e.code})")
            return
        except Exception as e:
            print(f"Failed to connect to registry: {e}")
            return
            
    if not download_url:
        print("Error: Could not resolve download URL.")
        return
        
    print(f"Fetching {github_repo} from GitHub...")
    
    try:
        req = urllib.request.Request(download_url, headers={'User-Agent': 'Nova-Galaxy/1.0'})
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
            
        os.makedirs("galaxy_modules", exist_ok=True)
        
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            z.extractall("galaxy_modules")
            
        print(f"Successfully installed '{pkg_name}' into galaxy_modules/")
        
        if os.path.exists("galaxy.json"):
            with open("galaxy.json", "r") as f:
                config = json.load(f)
            config.setdefault("dependencies", {})[pkg_name] = github_repo
            with open("galaxy.json", "w") as f:
                json.dump(config, f, indent=4)
                
    except Exception as e:
        print(f"Error installing package: {e}")

