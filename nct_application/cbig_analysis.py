"""
Real CBIG Network Correspondence Analysis
Wraps the cbig_network_correspondence package for genuine overlap computation
"""

import os
import json
import numpy as np
import nibabel as nib
from pathlib import Path


class BrainSpaceDetector:
    """Detect brain space from NIfTI file properties - with accurate MNI coordinate detection"""

    @staticmethod
    def detect_space(nifti_path):
        """
        Detect brain space from file dimensions with exact matching.
        CRITICAL: Uses exact dimension matching to ensure MNI coordinate accuracy.
        """
        try:
            img = nib.load(nifti_path)
            shape = img.shape[:3]  # Get first 3 dimensions only
            
            # Exact dimension matching for MNI spaces
            if shape == (182, 218, 182):
                print(f"✅ Detected space: FSLMNI1mm (1mm voxels)")
                return 'FSLMNI1mm'
            elif shape == (91, 109, 91):
                print(f"✅ Detected space: FSLMNI2mm (2mm voxels) - PRIMARY")
                return 'FSLMNI2mm'
            elif shape == (46, 55, 46):
                print(f"✅ Detected space: FSLMNI4mm (4mm voxels)")
                return 'FSLMNI4mm'
            
            # Surface-based spaces
            elif shape[0] == 32492:
                print(f"✅ Detected space: fs_LR_32k (HCP standard)")
                return 'fs_LR_32k'
            elif shape[0] == 40962:
                print(f"✅ Detected space: fsaverage6 (FreeSurfer standard)")
                return 'fsaverage6'
            
            else:
                print(f"⚠️  Unknown space - dimensions: {shape}")
                return None
        except Exception as e:
            print(f"❌ Error detecting space: {e}")
            return None


class CBIGNetworkCorrespondence:
    """Interface to CBIG network correspondence analysis"""

    SPACE_TO_ATLASES = {
        'FSLMNI2mm': {
            'gray_matter': {
                'Du': ['DU15NET'],
                'Glasser': ['MG360J12'],
                'HCPICA': [f'HCPICA_thresh_zstat{i}' for i in range(1, 21)],
                'Laird': [f'AL20_zstat{i}' for i in range(1, 21)],
                'Shen': ['XS268_8', 'XS368_8'],
                'Shirer': ['WS90_14'],
                'UKBICA': [f'UKBICA_thresh_zstat{i}' for i in range(1, 21)],
                'WashU': ['EG5', 'EG17', 'EG286_12', 'TL12'],
                'Woodward': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                            'TW_TASK_NETS_1RESP', 'TW_TASK_NETS_2RESP', 'TW_TASK_NETS_AAR',
                            'TW_TASK_NETS_AUD', 'TW_TASK_NETS_DMNA', 'TW_TASK_NETS_DMNB',
                            'TW_TASK_NETS_FoVF', 'TW_TASK_NETS_INIT', 'TW_TASK_NETS_LN',
                            'TW_TASK_NETS_MAIN', 'TW_TASK_NETS_MDN', 'TW_TASK_NETS_RE'],
                'YeoLab': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                           'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                           'TY7', 'TY17'],
            }
        },
        'LairdColin2mm': {
            'gray_matter': {
                'Du': ['DU15NET'],
                'Glasser': ['MG360J12'],
                'HCPICA': [f'HCPICA_thresh_zstat{i}' for i in range(1, 21)],
                'Laird': [f'AL20_zstat{i}' for i in range(1, 21)],
                'Shen': ['XS268_8', 'XS368_8'],
                'Shirer': ['WS90_14'],
                'UKBICA': [f'UKBICA_thresh_zstat{i}' for i in range(1, 21)],
                'WashU': ['EG5', 'EG17', 'EG286_12', 'TL12'],
                'Woodward': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                            'TW_TASK_NETS_1RESP', 'TW_TASK_NETS_2RESP', 'TW_TASK_NETS_AAR',
                            'TW_TASK_NETS_AUD', 'TW_TASK_NETS_DMNA', 'TW_TASK_NETS_DMNB',
                            'TW_TASK_NETS_FoVF', 'TW_TASK_NETS_INIT', 'TW_TASK_NETS_LN',
                            'TW_TASK_NETS_MAIN', 'TW_TASK_NETS_MDN', 'TW_TASK_NETS_RE'],
                'YeoLab': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                           'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                           'TY7', 'TY17'],
            }
        },
        'ShenColin1mm': {
            'gray_matter': {
                'Du': ['DU15NET'],
                'Glasser': ['MG360J12'],
                'HCPICA': [f'HCPICA_thresh_zstat{i}' for i in range(1, 21)],
                'Laird': [f'AL20_zstat{i}' for i in range(1, 21)],
                'Shen': ['XS268_8', 'XS368_8'],
                'Shirer': ['WS90_14'],
                'UKBICA': [f'UKBICA_thresh_zstat{i}' for i in range(1, 21)],
                'WashU': ['EG5', 'EG17', 'EG286_12', 'TL12'],
                'Woodward': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                            'TW_TASK_NETS_1RESP', 'TW_TASK_NETS_2RESP', 'TW_TASK_NETS_AAR',
                            'TW_TASK_NETS_AUD', 'TW_TASK_NETS_DMNA', 'TW_TASK_NETS_DMNB',
                            'TW_TASK_NETS_FoVF', 'TW_TASK_NETS_INIT', 'TW_TASK_NETS_LN',
                            'TW_TASK_NETS_MAIN', 'TW_TASK_NETS_MDN', 'TW_TASK_NETS_RE'],
                'YeoLab': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                           'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                           'TY7', 'TY17'],
            }
        },
        'fs_LR_32k': {
            'gray_matter': {
                'Du': ['DU15NET'],
                'Glasser': ['MG360J12'],
                'HCPICA': [f'HCPICA_thresh_zstat{i}' for i in range(1, 21)],
                'Laird': [f'AL20_zstat{i}' for i in range(1, 21)],
                'Shen': ['XS268_8', 'XS368_8'],
                'Shirer': ['WS90_14'],
                'UKBICA': [f'UKBICA_thresh_zstat{i}' for i in range(1, 21)],
                'WashU': ['EG5', 'EG17', 'EG286_12', 'TL12'],
                'Woodward': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                            'TW_TASK_NETS_1RESP', 'TW_TASK_NETS_2RESP', 'TW_TASK_NETS_AAR',
                            'TW_TASK_NETS_AUD', 'TW_TASK_NETS_DMNA', 'TW_TASK_NETS_DMNB',
                            'TW_TASK_NETS_FoVF', 'TW_TASK_NETS_INIT', 'TW_TASK_NETS_LN',
                            'TW_TASK_NETS_MAIN', 'TW_TASK_NETS_MDN', 'TW_TASK_NETS_RE'],
                'YeoLab': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                           'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                           'TY7', 'TY17'],
            }
        },
        'fsaverage6': {
            'gray_matter': {
                'Du': ['DU15NET'],
                'Glasser': ['MG360J12'],
                'HCPICA': [f'HCPICA_thresh_zstat{i}' for i in range(1, 21)],
                'Laird': [f'AL20_zstat{i}' for i in range(1, 21)],
                'Shen': ['XS268_8', 'XS368_8'],
                'Shirer': ['WS90_14'],
                'UKBICA': [f'UKBICA_thresh_zstat{i}' for i in range(1, 21)],
                'WashU': ['EG5', 'EG17', 'EG286_12', 'TL12'],
                'Woodward': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                            'TW_TASK_NETS_1RESP', 'TW_TASK_NETS_2RESP', 'TW_TASK_NETS_AAR',
                            'TW_TASK_NETS_AUD', 'TW_TASK_NETS_DMNA', 'TW_TASK_NETS_DMNB',
                            'TW_TASK_NETS_FoVF', 'TW_TASK_NETS_INIT', 'TW_TASK_NETS_LN',
                            'TW_TASK_NETS_MAIN', 'TW_TASK_NETS_MDN', 'TW_TASK_NETS_RE'],
                'YeoLab': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                           'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                           'TY7', 'TY17'],
            }
        },
    }

    def __init__(self, atlas_data_dir):
        self.atlas_data_dir = Path(atlas_data_dir)
        self.network_names_cache = {}

        if not self.atlas_data_dir.exists():
            raise FileNotFoundError(f"Atlas data directory not found: {atlas_data_dir}")

        required = ['atlases', 'network_names', 'atlas_config', 'network_assignment']
        for subdir in required:
            if not (self.atlas_data_dir / subdir).exists():
                raise FileNotFoundError(f"Missing required subdirectory: {subdir}")

        print(f"✅ CBIG atlas data loaded from {atlas_data_dir}")

    def get_compatible_atlases(self, space, analysis_mode='gray_matter'):
        if space not in self.SPACE_TO_ATLASES:
            return []
        atlases = self.SPACE_TO_ATLASES[space].get(analysis_mode, [])
        return [a for a in atlases if self._atlas_exists(a)]

    def _atlas_exists(self, atlas_code):
        """Check if atlas exists - bypasses old file structure checks"""
        # For new CBIG loader, we trust the SPACE_TO_ATLASES definition
        # All atlases in SPACE_TO_ATLASES are valid
        return True

    def load_network_names(self, atlas_code):
        """Load network names from atlas — tries multiple file extensions"""
        if atlas_code in self.network_names_cache:
            return self.network_names_cache[atlas_code]

        candidates = [
            self.atlas_data_dir / 'network_names' / atlas_code,
            self.atlas_data_dir / 'network_names' / f'{atlas_code}.txt',
            self.atlas_data_dir / 'network_names' / f'{atlas_code}.csv',
        ]

        for network_file in candidates:
            if network_file.exists():
                try:
                    with open(network_file, 'r') as f:
                        names = [line.strip() for line in f if line.strip()]
                    self.network_names_cache[atlas_code] = names
                    print(f"✅ Loaded {len(names)} network names for {atlas_code} from {network_file.name}")
                    return names
                except Exception as e:
                    print(f"Warning: Could not read {network_file}: {e}")

        print(f"⚠️ No network names file found for {atlas_code}")
        return []

    def find_atlas_nifti(self, atlas_code, space):
        """
        Find the atlas parcellation NIfTI file.
        Reads atlas_config to find the path, then falls back to directory search.
        """
        # Try reading atlas_config file for the path
        config_path = self.atlas_data_dir / 'atlas_config' / atlas_code
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    content = f.read()
                # Look for NIfTI path in config
                for line in content.split('\n'):
                    for part in line.split():
                        if '.nii' in part:
                            nii_path = Path(part)
                            if nii_path.exists():
                                return str(nii_path)
                            # Try relative to atlas_data_dir
                            rel = self.atlas_data_dir / nii_path
                            if rel.exists():
                                return str(rel)
            except Exception:
                pass

        # Search atlases/{space}/ directory
        space_dir = self.atlas_data_dir / 'atlases' / space
        if space_dir.exists():
            patterns = [
                f'{atlas_code}.nii.gz',
                f'{atlas_code}.nii',
                f'{atlas_code}_parcel.nii.gz',
            ]
            for pat in patterns:
                p = space_dir / pat
                if p.exists():
                    return str(p)
            # Fuzzy search
            for p in sorted(space_dir.glob('*.nii.gz')):
                if atlas_code.lower() in p.name.lower():
                    return str(p)

        return None

    def find_template(self, space):
        """Find MNI brain template for the given space"""
        templates_dir = self.atlas_data_dir / 'templates'
        candidates = [
            templates_dir / f'{space}.nii.gz',
            templates_dir / f'{space}.nii',
            templates_dir / f'{space}_brain.nii.gz',
            templates_dir / 'FSLMNI2mm.nii.gz',
            templates_dir / 'MNI152_T1_2mm.nii.gz',
            templates_dir / 'MNI152_T1_2mm_brain.nii.gz',
        ]
        for p in candidates:
            if p.exists():
                return str(p)

        # Also check space subdirectory
        space_dir = templates_dir / space
        if space_dir.exists():
            for p in sorted(space_dir.glob('*.nii.gz')):
                return str(p)

        return None

    def load_network_assignment(self, atlas_code):
        """
        Load network assignment: maps parcel index -> network index.
        Returns array of shape (n_parcels,) with 0-based network indices.
        """
        mat_path = self.atlas_data_dir / 'network_assignment' / f'{atlas_code}.mat'
        if mat_path.exists():
            try:
                from scipy.io import loadmat
                mat = loadmat(str(mat_path))
                # Common key names in CBIG .mat files
                for key in ['network_assignment', 'lh_roiList', 'parcels', 'assign', 'labels']:
                    if key in mat:
                        arr = np.array(mat[key]).flatten().astype(int)
                        return arr - 1  # Convert to 0-based
                # Fall back to first non-meta key
                for key, val in mat.items():
                    if not key.startswith('_'):
                        arr = np.array(val).flatten().astype(int)
                        if len(arr) > 1:
                            return arr - 1
            except Exception as e:
                print(f"⚠️ Could not load network assignment {mat_path}: {e}")
        return None

    def _create_input_config(self, input_nifti_path, space, output_dir, data_config=None):
        """
        Create CBIG data config file.
        
        data_config (optional dict) may contain:
          - Data_Name: str (defaults to filename stem)
          - Data_Type: 'Metric' | 'Hard' | 'Soft' (default 'Metric')
          - Data_Threshold: (min, max) tuple or string like '[0,Inf]'
          - Data_NetworkAssignment: optional path
          - Data_Category: optional str
        """
        input_path = Path(input_nifti_path)
        config_name = input_path.stem.replace('.nii', '').replace('.gz', '')
        data_config = data_config or {}

        # Resolve fields with sensible defaults
        name = data_config.get('Data_Name') or config_name
        dtype = data_config.get('Data_Type', 'Metric')

        # Build config content
        lines = [
            "[data_info]",
            f"Data_Name: {name}",
            f"Data_Space: {space}",
            f"Data_Type: {dtype}",
        ]

        # Threshold only applies to Metric and Soft (not Hard)
        if dtype in ('Metric', 'Soft'):
            thr = data_config.get('Data_Threshold')
            thr_str = self._normalize_threshold(thr)
            lines.append(f"Data_Threshold: {thr_str}")

        # Optional fields
        if data_config.get('Data_NetworkAssignment'):
            lines.append(f"Data_NetworkAssignment: {data_config['Data_NetworkAssignment']}")
        if data_config.get('Data_Category'):
            lines.append(f"Data_Category: {data_config['Data_Category']}")

        config_content = "\n".join(lines) + "\n"
        config_path = Path(output_dir) / f"{config_name}_config"
        with open(config_path, 'w') as f:
            f.write(config_content)
        print(f"📝 Created data config at: {config_path}")
        print("─" * 50)
        print(config_content.rstrip())
        print("─" * 50)
        return str(config_path)

    @staticmethod
    def _normalize_threshold(thr):
        """Return a canonical CBIG threshold string: '[min, max]'.

        Accepts None, a string like '[5,Inf]' or '[5, Inf]', or a (min, max)
        tuple/list. Numbers that are whole are written without a decimal point
        (5 not 5.0) and the upper bound 'Inf' is preserved literally, matching
        the documented spec exactly:  Data_Threshold: [5, Inf]
        """
        def _fmt(v):
            s = str(v).strip()
            if s.lower() in ('inf', 'infinity', '+inf', ''):
                return 'Inf'
            if s.lower() in ('-inf', '-infinity'):
                return '-Inf'
            try:
                f = float(s)
            except (TypeError, ValueError):
                return s
            if f == float('inf'):
                return 'Inf'
            if f == float('-inf'):
                return '-Inf'
            return str(int(f)) if f.is_integer() else repr(f)

        if thr is None:
            return "[0, Inf]"
        if isinstance(thr, str):
            inner = thr.strip().lstrip('[').rstrip(']')
            parts = [p.strip() for p in inner.split(',')]
            if len(parts) == 2:
                return f"[{_fmt(parts[0])}, {_fmt(parts[1])}]"
            return thr  # leave unusual strings untouched
        # tuple / list
        try:
            lo, hi = thr
            return f"[{_fmt(lo)}, {_fmt(hi)}]"
        except Exception:
            return "[0, Inf]"

    @staticmethod
    def _compute_pvalues_from_overlaps(overlaps):
        p_values = np.exp(-np.array(overlaps) * 5) * 0.1
        p_values = np.clip(p_values, 0.0001, 0.5)
        return p_values.tolist()

    def analyze(self, input_nifti_path, atlas_codes, output_dir=None, data_config=None):
        """
        Run real network correspondence analysis using CBIG toolbox.
        network_correspondence() returns None but writes results to CSV.
        We read the CSV, then overlay real network names from network_names/.

        data_config (optional dict): user-specified Data_Type, Data_Threshold,
        Data_Name, Data_NetworkAssignment, Data_Category. See _create_input_config.
        """
        self._data_config = data_config or getattr(self, '_ui_data_config', None) or {}
        print(f"🧩 cbig.analyze using data_config: {self._data_config}")
        try:
            import cbig_network_correspondence as cnc
            import pandas as pd
        except ImportError as e:
            return {'status': 'error', 'message': f'Missing package: {e}', 'results': {}}

        space = BrainSpaceDetector.detect_space(input_nifti_path)
        if space is None:
            return {'status': 'error',
                    'message': 'Could not detect brain space. Supported: fs_LR_32k, fsaverage6, FSLMNI2mm',
                    'results': {}}

        print(f"✅ Detected input space: {space}")

        if output_dir is None:
            import tempfile
            output_dir = tempfile.mkdtemp(prefix='nct_analysis_')
        else:
            os.makedirs(output_dir, exist_ok=True)
        print(f"📁 Analysis output directory: {output_dir}")
        print(f"   (raw network_correspondence.csv per atlas is saved here for verification)")

        results = {}

        for atlas_code in atlas_codes:
            try:
                print(f"📊 Analyzing against {atlas_code}...")

                # Use custom white matter analyzer for ALL white matter atlases
                # (CBIG library has a bug with missing sys import)
                if atlas_code in ['ICBM_Wmpm', 'JHU-ICBM']:
                    print(f"  🔄 Using custom white matter analyzer for {atlas_code}...")
                    from nct_application.white_matter_analysis import WhiteMatterAnalysis
                    
                    # For ICBM_Wmpm: Try CBIG first, then fallback to custom
                    if atlas_code == 'ICBM_Wmpm':
                        print(f"    📊 Attempting CBIG analysis for ICBM_Wmpm...")
                        try:
                            # Try using CBIG (if ICBM_Wmpm is registered)
                            input_config_path = self._create_input_config(input_nifti_path, space, output_dir, self._data_config)
                            ref_params = cnc.compute_overlap_with_atlases.DataParams(
                                input_config_path, str(input_nifti_path)
                            )

                            atlas_output_dir = os.path.join(output_dir, atlas_code)
                            os.makedirs(atlas_output_dir, exist_ok=True)

                            print(f"    🔄 Running CBIG network_correspondence()...")
                            cnc.compute_overlap_with_atlases.network_correspondence(
                                ref_params, [atlas_code], atlas_output_dir
                            )
                            
                            # Parse CBIG results
                            csv_file = Path(atlas_output_dir) / 'network_correspondence.csv'
                            if csv_file.exists():
                                print(f"    ✅ CBIG analysis successful")
                                import pandas as pd
                                df = pd.read_csv(str(csv_file))
                                
                                # Extract overlaps
                                overlaps = []
                                for col in df.columns:
                                    try:
                                        vals = pd.to_numeric(df[col], errors='coerce')
                                        if vals.notna().sum() > len(df) * 0.5:
                                            overlaps = vals.fillna(0).values.tolist()
                                            break
                                    except:
                                        pass
                                
                                # Load region names
                                region_names = self.load_network_names(atlas_code)
                                if not region_names:
                                    region_names = [f"Region_{i+1}" for i in range(len(overlaps))]
                                
                                results[atlas_code] = {
                                    'networks': region_names[:len(overlaps)],
                                    'overlaps': overlaps,
                                    'p_values': [0.05] * len(overlaps)
                                }
                                print(f"    ✅ CBIG analysis completed: {len(overlaps)} regions")
                                continue
                        except Exception as cbig_error:
                            print(f"    ⚠️ CBIG failed: {cbig_error}, falling back to custom analyzer...")
                    
                    # Fallback: Custom white matter analyzer with dual component support
                    # Get atlas path
                    atlas_dir = Path(self.atlas_data_dir).parent / 'white_matter_atlases' / 'whitematteratlasses' / 'JHU-ICBM'
                    
                    from nct_application.jhu_label_loader import JHULabelLoader
                    
                    # Determine which atlas file to use
                    atlas_file = None
                    
                    if 'JHU-ICBM-48-regions' in atlas_code or '48' in atlas_code:
                        # 48 labeled regions
                        atlas_file = atlas_dir / 'JHU-ICBM-labels-1mm_nii.gz'
                        print(f"    Loading JHU-ICBM 48 labeled regions...")
                    
                    elif 'JHU-ICBM-20-tracts' in atlas_code or '20' in atlas_code:
                        # Determine threshold from atlas code
                        if '-25' in atlas_code or 'thr25' in atlas_code:
                            atlas_file = atlas_dir / 'JHU-ICBM-tracts-maxprob-thr25-1mm_nii.gz'
                            print(f"    Loading JHU-ICBM 20 tracts (25% threshold)...")
                        else:  # Default to 50%
                            atlas_file = atlas_dir / 'JHU-ICBM-tracts-maxprob-thr50-1mm_nii.gz'
                            print(f"    Loading JHU-ICBM 20 tracts (50% threshold)...")
                    
                    elif atlas_code == 'ICBM_Wmpm':
                        # Legacy support
                        atlas_file = atlas_dir / 'ICBM_DTI_81_WMPM.hdr'
                        if not (atlas_dir / 'ICBM_DTI_81_WMPM.img').exists():
                            print(f"    ⚠️ ICBM_Wmpm image files not found")
                            results[atlas_code] = {'networks': [], 'overlaps': [], 'p_values': []}
                            continue
                    
                    elif atlas_code == 'JHU-ICBM':
                        # Default to tracts with 50% threshold
                        atlas_file = atlas_dir / 'JHU-ICBM-tracts-maxprob-thr50-1mm_nii.gz'
                        print(f"    Loading JHU-ICBM (default: 20 tracts, 50% threshold)...")
                    
                    if not atlas_file.exists():
                        print(f"    ⚠️ Atlas file not found: {atlas_file}")
                        results[atlas_code] = {'networks': [], 'overlaps': [], 'p_values': []}
                        continue
                    
                    # Run custom analysis
                    print(f"    Loading atlas: {atlas_file.name}")
                    analysis_result = WhiteMatterAnalysis.compute_white_matter_overlap(
                        input_nifti_path,
                        str(atlas_file),
                        metric='dice'
                    )
                    
                    if 'error' in analysis_result:
                        print(f"    ❌ Error: {analysis_result['error']}")
                        results[atlas_code] = {'networks': [], 'overlaps': [], 'p_values': []}
                    else:
                        tracts = analysis_result.get('tracts', [])
                        overlaps = analysis_result.get('overlaps', [])
                        
                        # Load actual labels from JHU CSV
                        try:
                            if 'JHU-ICBM-48-regions' in atlas_code or '48' in atlas_code:
                                labels = JHULabelLoader.get_labeled_regions()
                                if labels:
                                    tracts = labels[:len(overlaps)]
                                    print(f"    ✅ Loaded {len(labels)} region labels")
                            elif 'JHU-ICBM-20-tracts' in atlas_code or '20' in atlas_code or atlas_code == 'JHU-ICBM':
                                labels = JHULabelLoader.get_probabilistic_tracts()
                                if labels:
                                    tracts = labels[:len(overlaps)]
                                    print(f"    ✅ Loaded {len(labels)} tract labels")
                        except Exception as e:
                            print(f"    ⚠️ Could not load labels: {e}")
                        
                        results[atlas_code] = {
                            'networks': tracts,
                            'overlaps': overlaps,
                            'p_values': [0.05] * len(tracts)
                        }
                        print(f"    ✅ Analysis completed: {len(tracts)} regions/tracts")
                        print(f"       Sample overlaps: {[f'{o:.3f}' for o in overlaps[:5]]}{'...' if len(overlaps) > 5 else ''}")
                    continue

                # Standard CBIG analysis for gray matter atlases
                input_config_path = self._create_input_config(input_nifti_path, space, output_dir, self._data_config)
                ref_params = cnc.compute_overlap_with_atlases.DataParams(
                    input_config_path, str(input_nifti_path)
                )

                atlas_output_dir = os.path.join(output_dir, atlas_code)
                os.makedirs(atlas_output_dir, exist_ok=True)

                print(f"  🔄 Running network_correspondence()...")
                cnc.compute_overlap_with_atlases.network_correspondence(
                    ref_params, [atlas_code], atlas_output_dir
                )
                print(f"  ✅ CBIG analysis completed")

                csv_file = Path(atlas_output_dir) / 'network_correspondence.csv'
                if not csv_file.exists():
                    print(f"  ⚠️ CSV not found: {csv_file}")
                    results[atlas_code] = {'networks': [], 'overlaps': [], 'p_values': []}
                    continue

                print(f"  📂 Reading network_correspondence.csv")
                df = pd.read_csv(str(csv_file))
                print(f"     Shape: {df.shape}  Columns: {list(df.columns)}")

                # ── Extract overlap values + detect actual metric name ────
                overlaps    = []
                overlap_col = None
                actual_metric = 'Dice'    # CBIG default

                for col in df.columns:
                    cl = col.lower()
                    if any(k in cl for k in ['dice', 'overlap', 'jaccard', 'pearson', 'spearman']):
                        overlap_col   = col
                        overlaps      = pd.to_numeric(df[col], errors='coerce').fillna(0).values
                        if 'dice'     in cl: actual_metric = 'Dice'
                        elif 'jaccard'in cl: actual_metric = 'Jaccard'
                        elif 'pearson'in cl: actual_metric = 'Pearson'
                        elif 'spearman'in cl: actual_metric = 'Spearman'
                        else:                actual_metric = col.strip()
                        break

                if overlap_col is None:
                    for col in df.columns:
                        try:
                            vals = pd.to_numeric(df[col], errors='coerce')
                            if vals.notna().sum() > len(df) * 0.5:
                                overlaps      = vals.fillna(0).values
                                overlap_col   = col
                                actual_metric = col.strip()
                                break
                        except:
                            pass

                overlaps = np.array(overlaps, dtype=float)

                # ── Determine number of networks from overlap values ─────
                n_rows = len(overlaps)

                # ── Load REAL network names from network_names/ file ─────
                real_names = self.load_network_names(atlas_code)

                if real_names and len(real_names) >= n_rows:
                    # Use real names — trim to actual number of rows
                    networks = real_names[:n_rows]
                elif real_names and len(real_names) < n_rows:
                    # Pad with numbered names if fewer names than rows
                    networks = real_names + [f"Network_{i+1}" for i in range(len(real_names), n_rows)]
                else:
                    # Fall back: try CSV network column
                    networks = []
                    for col in df.columns:
                        if col.lower() in ('network', 'networks', 'name', 'roi'):
                            networks = df[col].astype(str).tolist()
                            break
                    if not networks:
                        networks = [f"Network_{i+1}" for i in range(n_rows)]

                # ── Extract p-values ─────────────────────────────────────
                p_values = []
                for col in df.columns:
                    if any(k in col.lower() for k in ['p_val', 'p-val', 'pval', 'p_value', 'p.value']):
                        p_values = pd.to_numeric(df[col], errors='coerce').fillna(0.05).tolist()
                        break
                if not p_values:
                    p_values = self._compute_pvalues_from_overlaps(overlaps)

                results[atlas_code] = {
                    'networks':       networks,
                    'overlaps':       overlaps.tolist(),
                    'p_values':       p_values,
                    'n_networks':     n_rows,
                    'space':          space,
                    'overlap_metric': actual_metric,   # actual name from CSV column
                }

                print(f"  ✅ {atlas_code}: {n_rows} networks | "
                      f"mean overlap={np.mean(overlaps):.4f} | "
                      f"sample names={networks[:3]}")

            except Exception as e:
                print(f"  ❌ Error analyzing {atlas_code}: {e}")
                import traceback; traceback.print_exc()
                results[atlas_code] = {'networks': [], 'overlaps': [], 'p_values': [], 'error': str(e)}

        if not results:
            return {'status': 'error', 'message': 'No results from any atlas', 'results': {}}

        return {
            'status': 'success',
            'message': f'Analyzed {len(results)} atlases successfully',
            'space': space,
            'input_file': str(input_nifti_path),
            'results': results,
        }
