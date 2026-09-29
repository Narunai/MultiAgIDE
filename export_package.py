import os
import sys
import datetime
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.package_manager import PackageManager


def main():
    print("========================================================")
    print("  MultiAgIDE Studio - Portable Package Exporter")
    print("========================================================")

    pm = PackageManager(BASE_DIR)
    slots = pm.get_exportable_slots()

    print(f"Found {len(slots)} slots to export:")
    for s in slots:
        projs = f" [Projects: {', '.join(s['projects'])}]" if s['projects'] else ""
        print(f"  Slot #{s['id']:2d}: {s['name']} ({s['email']}){projs}")

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    default_name = f"MultiAgIDE_Backup_{now_str}.zip"
    default_output = BASE_DIR / default_name

    out_arg = sys.argv[1] if len(sys.argv) > 1 else str(default_output)

    print(f"\nStarting export to: {out_arg}")
    print("Bundling accounts, Google auth tokens, settings, and workspaces...")

    res = pm.export_package(
        out_arg,
        include_workspaces=True,
        exclude_transient_caches=True,
        progress_callback=lambda cur, tot, name: (
            print(f"  [{cur}/{tot}] ({int(cur/max(1, tot)*100)}%) {os.path.basename(name)}")
            if cur % 50 == 0 or cur == tot else None
        )
    )

    size_mb = res["archive_size_bytes"] / (1024 * 1024)
    print("\n--------------------------------------------------------")
    print("  Export completed successfully!")
    print(f"  Package: {res['output_path']}")
    print(f"  Size: {size_mb:.1f} MB ({res['files_count']} files)")
    print(f"  Exported Slots: {len(res['slots_exported'])}")
    print("--------------------------------------------------------")
    print("You can now copy this file to another computer and run")
    print("import.bat or click 'Import' in the MultiAgIDE dashboard.")
    print("========================================================\n")


if __name__ == "__main__":
    main()
