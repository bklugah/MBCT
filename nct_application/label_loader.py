"""
Label Loader - Caches atlas region/tract names at startup
Parses XML and TXT files for ICBM_Wmpm and JHU-ICBM atlases
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

class LabelLoader:
    """Load and cache atlas labels (regions/tracts)"""
    
    _cache = {}  # Class-level cache
    
    @classmethod
    def load_jhu_icbm_tracts(cls, atlas_dir=None):
        """
        Load JHU-ICBM tract names from XML files
        Returns list of 20 tract names in order
        """
        if 'JHU_ICBM_tracts' in cls._cache:
            return cls._cache['JHU_ICBM_tracts']
        
        tracts = []
        
        try:
            if atlas_dir is None:
                # Find atlas directory
                base_dir = Path(__file__).parent.parent
                atlas_dir = base_dir / 'white_matter_atlases' / 'whitematteratlasses' / 'JHU-ICBM'
            else:
                atlas_dir = Path(atlas_dir)
            
            # Try JHU-tracts.xml first
            xml_file = atlas_dir / 'JHU-tracts.xml'
            if xml_file.exists():
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Extract labels in order
                for label_elem in root.findall('.//label'):
                    name = label_elem.text
                    if name:
                        tracts.append(name.strip())
                
                if tracts:
                    cls._cache['JHU_ICBM_tracts'] = tracts
                    print(f"✅ Loaded {len(tracts)} JHU-ICBM tracts from XML")
                    return tracts
            
            # Fallback: try JHU-labels.xml
            xml_file = atlas_dir / 'JHU-labels.xml'
            if xml_file.exists():
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                for label_elem in root.findall('.//label'):
                    name = label_elem.text
                    if name:
                        tracts.append(name.strip())
                
                if tracts:
                    cls._cache['JHU_ICBM_tracts'] = tracts
                    print(f"✅ Loaded {len(tracts)} JHU-ICBM tracts from XML")
                    return tracts
        
        except Exception as e:
            print(f"⚠️ Error loading JHU-ICBM tract names: {e}")
        
        # Fallback: generate generic names
        default_tracts = [
            "Anterior thalamic radiation L",
            "Anterior thalamic radiation R",
            "Corticospinal tract L",
            "Corticospinal tract R",
            "Cingulum (cingulate gyrus) L",
            "Cingulum (cingulate gyrus) R",
            "Cingulum (hippocampus) L",
            "Cingulum (hippocampus) R",
            "Forceps major",
            "Forceps minor",
            "Inferior fronto-occipital fasciculus L",
            "Inferior fronto-occipital fasciculus R",
            "Inferior longitudinal fasciculus L",
            "Inferior longitudinal fasciculus R",
            "Superior longitudinal fasciculus L",
            "Superior longitudinal fasciculus R",
            "Uncinate fasciculus L",
            "Uncinate fasciculus R",
            "Superior longitudinal fasciculus (temporal part) L",
            "Superior longitudinal fasciculus (temporal part) R",
        ]
        cls._cache['JHU_ICBM_tracts'] = default_tracts
        return default_tracts
    
    @classmethod
    def load_icbm_wmpm_regions(cls, atlas_dir=None):
        """
        Load ICBM_Wmpm region names from MniLabelLookupTable.txt
        Returns list of 50 region names in order
        """
        if 'ICBM_Wmpm_regions' in cls._cache:
            return cls._cache['ICBM_Wmpm_regions']
        
        regions = []
        
        try:
            if atlas_dir is None:
                # Find atlas directory
                base_dir = Path(__file__).parent.parent
                atlas_dir = base_dir / 'white_matter_atlases' / 'whitematteratlasses' / 'ICBM_Wmpm'
            else:
                atlas_dir = Path(atlas_dir)
            
            txt_file = atlas_dir / 'MniLabelLookupTable.txt'
            if txt_file.exists():
                with open(txt_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        # Format: INDEX<tab>CODE<tab>NAME
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            # Get name (last part, handle multi-tab entries)
                            name = parts[-1].strip()
                            regions.append(name)
                        elif len(parts) == 2:
                            name = parts[1].strip()
                            regions.append(name)
                
                if regions:
                    cls._cache['ICBM_Wmpm_regions'] = regions
                    print(f"✅ Loaded {len(regions)} ICBM_Wmpm regions from TXT")
                    return regions
        
        except Exception as e:
            print(f"⚠️ Error loading ICBM_Wmpm region names: {e}")
        
        # Fallback: generate generic names
        default_regions = [
            f"Region_{i+1}" for i in range(50)
        ]
        cls._cache['ICBM_Wmpm_regions'] = default_regions
        return default_regions
    
    @classmethod
    def get_tract_name(cls, atlas_code, index):
        """Get single tract/region name by index"""
        if atlas_code == 'JHU-ICBM':
            tracts = cls.load_jhu_icbm_tracts()
            if 0 <= index < len(tracts):
                return tracts[index]
            return f"Tract_{index+1}"
        
        elif atlas_code == 'ICBM_Wmpm':
            regions = cls.load_icbm_wmpm_regions()
            if 0 <= index < len(regions):
                return regions[index]
            return f"Region_{index+1}"
        
        return f"Unknown_{index+1}"
    
    @classmethod
    def get_all_labels(cls, atlas_code):
        """Get all labels for an atlas"""
        if atlas_code == 'JHU-ICBM':
            return cls.load_jhu_icbm_tracts()
        elif atlas_code == 'ICBM_Wmpm':
            return cls.load_icbm_wmpm_regions()
        return []
    
    @classmethod
    def initialize_cache(cls):
        """Pre-load all labels at startup"""
        print("🔄 Loading atlas labels...")
        cls.load_jhu_icbm_tracts()
        cls.load_icbm_wmpm_regions()
        print("✅ Atlas labels cached")
    
    @classmethod
    def clear_cache(cls):
        """Clear cached labels"""
        cls._cache.clear()
