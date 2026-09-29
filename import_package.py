import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.package_manager import PackageManager


def main():
    print("========================================================")
    print("  MultiAgIDE Studio - Portable Package Importer")
    print("========================================================")

    pm = PackageManager(BASE_DIR)

    if len(sys.argv) > 1:
        pkg_file = sys.argv[1]
    else:
        # Check if there are any .zip or .magpkg files in BASE_DIR
        candidates = list(BASE_DIR.glob("*.zip")) + list(BASE_DIR.glob("*.magpkg"))
        if candidates:
            print("Found package files in current directory:")
            for idx, c in enumerate(candidates, 1):
                print(f"  [{idx}] {c.name}")
            choice = input("\nSelect package number to import (or enter full path): ").strip()
            try:
                c_idx = int(choice) - 1
                if 0 <= c_idx < len(candidates):
                    pkg_file = str(candidates[c_idx])
                else:
                    pkg_file = choice
            except ValueError:
                pkg_file = choice
        else:
            pkg_file = input("Enter path to package file (.zip / .magpkg): ").strip()

    pkg_path = Path(pkg_file).resolve()
    if not pkg_path.exists():
        print(f"Error: File not found: {pkg_path}")
        return

    print(f"\nInspecting package: {pkg_path.name}...")
    try:
        inspection = pm.inspect_package(str(pkg_path))
    except Exception as e:
        print(f"Error inspecting package: {e}")
        return

    manifest = inspection.get("manifest", {})
    slots = manifest.get("slots", [])
    src_base = manifest.get("source_base_dir", "Unknown")
    created = manifest.get("created_at_iso", "Unknown")[:19].replace("T", " ")
    size_mb = inspection.get("archive_size_bytes", 0) / (1024 * 1024)

    print("--------------------------------------------------------")
    print(f"  Package Source: {src_base}")
    print(f"  Created At:     {created}")
    print(f"  Archive Size:   {size_mb:.1f} MB")
    print(f"  Slots Count:    {len(slots)}")
    for s in slots:
        projs = f" [Projects: {', '.join(s.get('projects', []))}]" if s.get('projects') else ""
        print(f"    - Slot #{s.get('id')}: {s.get('name')} ({s.get('email')}){projs}")
    print("--------------------------------------------------------")

    confirm = input("\nProceed with import and Auto-Path Remapping? (Y/n): ").strip().lower()
    if confirm and confirm != 'y':
        print("Import cancelled.")
        return

    print("\nExtracting package and remapping paths...")
    res = pm.import_package(
        str(pkg_path),
        target_base_dir=BASE_DIR,
        mode="merge",
        progress_callback=lambda cur, tot, name: (
            print(f"  [{cur}/{tot}] ({int(cur/max(1, tot)*100)}%) {os.path.basename(name)}")
            if cur % 50 == 0 or cur == tot else None
        )
    )

    print("\n--------------------------------------------------------")
    print("  Import completed successfully!")
    print(f"  Restored Slots: {res['slots_count']}")
    print(f"  Auto-remapped configuration files: {res['remapped_files']}")
    print("--------------------------------------------------------")
    print("All Google accounts, auth sessions, and projects are now")
    print("active and ready to use on this machine!")
    print("Launch MultiAgIDE by running 'launch.bat' or 'python main.py'.")
    print("========================================================\n")


if __name__ == "__main__":
    main()
