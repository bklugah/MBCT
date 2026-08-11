"""
Updated Label Loader - Parses JHU_combined_MNI.csv
Supports both JHU-ICBM labeled regions (48) and probabilistic tracts (20)
"""

import pandas as pd
from pathlib import Path

class JHULabelLoader:
    """Load and cache JHU-ICBM labels from CSV"""
    
    _cache = {}  # Class-level cache
    
    @classmethod
    def load_csv(cls, csv_path=None):
        """Load JHU_combined_MNI.csv and parse labels"""
        if 'csv_data' in cls._cache:
            return cls._cache['csv_data']
        
        try:
            if csv_path is None:
                # Try to find CSV in atlas directory
                base_dir = Path(__file__).parent.parent
                csv_path = base_dir / 'white_matter_atlases' / 'whitematteratlasses' / 'JHU-ICBM' / 'JHU_combined_MNI.csv'
                
                # Also check uploads if not found
                if not csv_path.exists():
                    csv_path = Path('/mnt/user-data/uploads/JHU_combined_MNI.csv')
            
            csv_path = Path(csv_path)
            
            if not csv_path.exists():
                print(f"⚠️ CSV file not found: {csv_path}")
                return None
            
            # Read CSV
            df = pd.read_csv(str(csv_path))
            cls._cache['csv_data'] = df
            print(f"✅ Loaded JHU_combined_MNI.csv ({len(df)} entries)")
            return df
            
        except Exception as e:
            print(f"⚠️ Error loading CSV: {e}")
            return None
    
    @classmethod
    def get_labeled_regions(cls, csv_path=None):
        """Get 48 labeled white matter regions from JHU-labels"""
        if 'labeled_regions' in cls._cache:
            return cls._cache['labeled_regions']
        
        df = cls.load_csv(csv_path)
        if df is None:
            return []
        
        # Filter for JHU-labels (skip index 0 which is "Unclassified")
        labels_df = df[df['atlas'] == 'JHU-labels'].copy()
        labels_df = labels_df[labels_df['index'] > 0]  # Skip background
        
        regions = labels_df.sort_values('index')['label'].tolist()
        cls._cache['labeled_regions'] = regions
        
        print(f"✅ Loaded {len(regions)} JHU-ICBM labeled regions")
        return regions
    
    @classmethod
    def get_probabilistic_tracts(cls, csv_path=None):
        """Get 20 probabilistic fiber tracts from JHU-tracts"""
        if 'probabilistic_tracts' in cls._cache:
            return cls._cache['probabilistic_tracts']
        
        df = cls.load_csv(csv_path)
        if df is None:
            return []
        
        # Filter for JHU-tracts
        tracts_df = df[df['atlas'] == 'JHU-tracts'].copy()
        
        tracts = tracts_df.sort_values('index')['label'].tolist()
        cls._cache['probabilistic_tracts'] = tracts
        
        print(f"✅ Loaded {len(tracts)} JHU-ICBM probabilistic tracts")
        return tracts
    
    @classmethod
    def get_all_labels(cls, component='both', csv_path=None):
        """
        Get all labels for specified component
        
        Parameters:
        -----------
        component : str
            'labeled' - 48 labeled regions
            'tracts' - 20 probabilistic tracts
            'both' - all 68 (48 regions + 20 tracts)
        
        Returns:
        --------
        dict with keys: 'labeled_regions', 'tracts', 'all_labels'
        """
        result = {
            'labeled_regions': cls.get_labeled_regions(csv_path),
            'tracts': cls.get_probabilistic_tracts(csv_path),
        }
        
        # Combine both if requested
        if component == 'both':
            result['all_labels'] = result['labeled_regions'] + result['tracts']
        elif component == 'labeled':
            result['all_labels'] = result['labeled_regions']
        elif component == 'tracts':
            result['all_labels'] = result['tracts']
        
        return result
    
    @classmethod
    def get_component_info(cls, csv_path=None):
        """Get component information for UI display"""
        regions = cls.get_labeled_regions(csv_path)
        tracts = cls.get_probabilistic_tracts(csv_path)
        
        return {
            'labeled_regions': {
                'count': len(regions),
                'description': 'JHU DTI-81 White-Matter Labels - 48 discrete regions',
                'file': 'JHU-ICBM-labels-1mm_nii.gz'
            },
            'probabilistic_tracts': {
                'count': len(tracts),
                'description': 'JHU White-Matter Tractography Atlas - 20 probabilistic tracts',
                'files': {
                    '25%': 'JHU-ICBM-tracts-maxprob-thr25-1mm_nii.gz',
                    '50%': 'JHU-ICBM-tracts-maxprob-thr50-1mm_nii.gz'
                }
            }
        }
    
    @classmethod
    def initialize_cache(cls, csv_path=None):
        """Pre-load all labels at startup"""
        print("🔄 Loading JHU-ICBM labels from CSV...")
        cls.load_csv(csv_path)
        cls.get_labeled_regions(csv_path)
        cls.get_probabilistic_tracts(csv_path)
        print("✅ JHU-ICBM labels cached (48 regions + 20 tracts)")
    
    @classmethod
    def clear_cache(cls):
        """Clear cached labels"""
        cls._cache.clear()
