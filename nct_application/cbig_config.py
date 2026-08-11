"""
CBIG configuration management
Handles atlas directory path and first-run setup
"""

import json
import os
from pathlib import Path


class CBIGConfig:
    """Manage CBIG atlas data directory path"""
    
    CONFIG_FILE = Path.home() / '.nct_cbig_config.json'
    
    @classmethod
    def get_atlas_dir(cls):
        """Get the atlas directory.

        Resolution order:
          1. A user-configured path in ~/.nct_cbig_config.json (if valid).
          2. The atlas data bundled with the app (so a packaged build works
             with no setup), located via the resource resolver and common
             relative locations.
        Returns None only if nothing is found.
        """
        # 1) user-configured path
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE) as f:
                    config = json.load(f)
                    atlas_dir = config.get('atlas_dir')
                    if atlas_dir and os.path.isdir(atlas_dir):
                        return atlas_dir
            except Exception:
                pass

        # 2) bundled / relative fallback (works in a PyInstaller build and from source)
        import sys
        candidates = []

        # 2a) PyInstaller frozen locations — check these FIRST and directly,
        # without depending on importing the paths helper.
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                candidates.append(Path(meipass) / 'cbig_network_correspondence_data')
            exe_dir = Path(sys.executable).resolve().parent
            candidates.append(exe_dir / 'cbig_network_correspondence_data')
            candidates.append(exe_dir / '_internal' / 'cbig_network_correspondence_data')

        # 2b) the paths helper (resource + user-data dirs)
        try:
            from paths import resource_dir, user_data_dir
            candidates.append(Path(resource_dir()) / 'cbig_network_correspondence_data')
            candidates.append(Path(user_data_dir()) / 'cbig_network_correspondence_data')
        except Exception as _e:
            print(f"[atlas] paths helper unavailable: {_e}")

        # 2c) relative to this file (source layout and frozen package layout)
        here = Path(__file__).resolve().parent          # .../nct_application
        candidates += [
            here.parent / 'cbig_network_correspondence_data',
            here / 'cbig_network_correspondence_data',
            Path.cwd() / 'cbig_network_correspondence_data',
        ]

        print("[atlas] searching for cbig_network_correspondence_data in:")
        seen = set()
        for c in candidates:
            cs = str(c)
            if cs in seen:
                continue
            seen.add(cs)
            try:
                exists = Path(c).is_dir()
                print(f"   {'FOUND ' if exists else 'no    '} {c}")
                if exists:
                    return cs
            except Exception as _e:
                print(f"   err    {c}  ({_e})")
        print("[atlas] NOT FOUND in any candidate location.")
        return None
    
    @classmethod
    def set_atlas_dir(cls, path):
        """Save atlas directory path"""
        path = str(Path(path).resolve())
        if not os.path.isdir(path):
            raise ValueError(f"Directory does not exist: {path}")
        
        config = {}
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE) as f:
                    config = json.load(f)
            except:
                pass
        
        config['atlas_dir'] = path
        
        with open(cls.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Atlas directory saved: {path}")
    
    @classmethod
    def clear_atlas_dir(cls):
        """Clear the saved atlas directory"""
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE) as f:
                    config = json.load(f)
                config.pop('atlas_dir', None)
                with open(cls.CONFIG_FILE, 'w') as f:
                    json.dump(config, f, indent=2)
            except:
                pass
    
    @classmethod
    def is_first_run(cls):
        """Check if this is the first run (atlas dir not configured)"""
        return cls.get_atlas_dir() is None
