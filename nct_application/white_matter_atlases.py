"""White Matter Atlas definitions"""


class WhiteMattersAtlas:
    """White Matter Atlas"""
    def __init__(self, name, code, tracts, source=""):
        self.name = name
        self.code = code
        self.tracts = tracts
        self.source = source


class WhiteMattersAtlasManager:
    """Manages available white matter atlases"""
    
    ATLASES = {
        'JHU-ICBM-1mm': WhiteMattersAtlas(
            'Johns Hopkins ICBM Labels (1mm)',
            'JHU-ICBM-1mm',
            48,
            'Mori et al. / Johns Hopkins'
        ),
        'JHU-ICBM-2mm': WhiteMattersAtlas(
            'Johns Hopkins ICBM Labels (2mm)',
            'JHU-ICBM-2mm',
            48,
            'Mori et al. / Johns Hopkins'
        ),
        'Mori-Atlas': WhiteMattersAtlas(
            'Mori White Matter Atlas',
            'Mori-Atlas',
            20,
            'Mori et al. 2005'
        ),
        'ICBM-DTI-81': WhiteMattersAtlas(
            'ICBM DTI-81 White Matter Labels',
            'ICBM-DTI-81',
            81,
            'ICBM / DTI-81'
        ),
        'Harvard-Oxford-WM': WhiteMattersAtlas(
            'Harvard-Oxford White Matter Atlas',
            'Harvard-Oxford-WM',
            50,
            'Harvard-Oxford / Desikan-Killiany'
        ),
        'FSL-MNI-WM': WhiteMattersAtlas(
            'FSL Standard White Matter Atlas',
            'FSL-MNI-WM',
            15,
            'FSL / MNI'
        ),
        'Catani-Thiebaut-WM': WhiteMattersAtlas(
            'Catani & Thiebaut White Matter Tracts',
            'Catani-Thiebaut-WM',
            31,
            'Catani & Thiebaut 2008'
        ),
        'Wakana-Tracts': WhiteMattersAtlas(
            'Wakana Fiber Tract Atlas',
            'Wakana-Tracts',
            29,
            'Wakana et al. 2007'
        ),
        'Eve-WM': WhiteMattersAtlas(
            'Eve Brain White Matter Atlas',
            'Eve-WM',
            25,
            'Eve Brain / Montreal'
        ),
        'WMQL-Tracts': WhiteMattersAtlas(
            'White Matter Query Language (WMQL) Tracts',
            'WMQL-Tracts',
            40,
            'Yeh et al. 2018'
        ),
    }
    
    @classmethod
    def get_atlas(cls, code):
        return cls.ATLASES.get(code)
    
    @classmethod
    def list_atlases(cls):
        return sorted(list(cls.ATLASES.keys()))
    
    @classmethod
    def get_atlas_list_for_dropdown(cls):
        """Get list of (name, code) tuples for GUI dropdown"""
        items = []
        for code in sorted(cls.ATLASES.keys()):
            atlas = cls.ATLASES[code]
            items.append((f"{atlas.name} ({code})", code))
        return items
