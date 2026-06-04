# Contributing to Nova

## Contributor License Agreement

By submitting code to this project, you agree that:

1. Your contributions are licensed under the same CC BY-NC 4.0 license
2. You grant the project maintainer (Laksh Goyal) the right to:
   - Use your contributions in any version of Nova
   - Include your contributions in commercial versions (if any)
   - Modify and adapt your contributions
3. You confirm that your contributions are original work
4. You understand that your contributions cannot be used by others for commercial purposes

## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Contributing Libraries

The best way to contribute is by creating useful Nova libraries and publishing them to the Galaxy registry:

```bash
# Scaffold a library
galaxy init library my-lib
cd my-lib

# Write your library code in src/

# Publish to the registry
galaxy publish
```

This validates your manifest, computes SHA-256 hashes, and opens a pre-filled GitHub Issue on the galaxy-registry repository. See [galaxy-registry.vercel.app](https://galaxy-registry.vercel.app) for details.

## Running the Installer

**macOS / Linux (bash):**
```bash
curl -O https://galaxy-registry.vercel.app/install.sh && bash install.sh
```
**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri https://galaxy-registry.vercel.app/install.ps1 -OutFile install.ps1; powershell -File install.ps1
```
**Python fallback (any platform):**
```bash
curl -O https://galaxy-registry.vercel.app/install.py && python install.py
```

## Running Tests

```bash
python -m unittest tests/test_galaxy.py
```

# Contributors

## Creator & Maintainer
- Laksh Goyal - Original author

## How to Get Credit
Submit a pull request with your changes and your name will be added here.

All contributors agree that their contributions are under the CC BY-NC 4.0 license.
