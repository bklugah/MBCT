"""Brain atlas definitions"""


class Atlas:
    """Brain atlas"""
    def __init__(self, name, code, networks, parcels, source=""):
        self.name = name
        self.code = code
        self.networks = networks
        self.parcels = parcels
        self.source = source


class AtlasManager:
    """Manages available atlases"""
    
    ATLASES = {
        'MG360J12': Atlas('Glasser 2016 360-ROI (12 Cole-Anticevic networks)', 'MG360J12', 12, 360, 'Glasser2016; Ji2019'),
        'HCPICA': Atlas('HCP 25-node ICA maps', 'HCPICA', 25, 25, 'Smith2009; Smith2013'),
        'AL20': Atlas('Angela Laird 20-node ICA', 'AL20', 20, 20, 'Laird2011'),
        'AS200K17': Atlas('Schaefer 200-ROI (17 Kong networks)', 'AS200K17', 17, 200, 'Schaefer2018; Kong2021'),
        'AS200Y17': Atlas('Schaefer 200-ROI (17 Yeo networks)', 'AS200Y17', 17, 200, 'Schaefer2018; Yeo2011'),
        'AS400K17': Atlas('Schaefer 400-ROI (17 Kong networks)', 'AS400K17', 17, 400, 'Schaefer2018; Kong2021'),
        'AS400Y17': Atlas('Schaefer 400-ROI (17 Yeo networks)', 'AS400Y17', 17, 400, 'Schaefer2018; Yeo2011'),
        'XS268_8': Atlas('Xilin Shen 268-ROI (8 networks)', 'XS268_8', 8, 268, 'Shen2013'),
        'XS368_8': Atlas('Xilin Shen 368-ROI (8 networks)', 'XS368_8', 8, 368, 'Shen2013'),
        'WS90_14': Atlas('William Shirer 90-ROI (14 networks)', 'WS90_14', 14, 90, 'Shirer2012'),
        'UKBICA': Atlas('UKBiobank 25-node ICA maps', 'UKBICA', 25, 25, 'Smith2009; Alfaro-Almagro2018'),
        'EG286_12': Atlas('Gordon 286-ROI (12 networks)', 'EG286_12', 12, 286, 'Power2011; Gordon2016'),
        'TL12': Atlas('Tim Laumann 12 networks', 'TL12', 12, 12, 'Power2011; Laumann2015'),
        'EG17': Atlas('Gordon 2017 17 networks', 'EG17', 17, 333, 'Power2011; Gordon2017'),
        'TY7': Atlas('Thomas Yeo 7 networks', 'TY7', 7, 400, 'Yeo2011'),
        'TY17': Atlas('Thomas Yeo 17 networks', 'TY17', 17, 400, 'Yeo2011'),
        'XY200K17': Atlas('Xiaoxuan Yan 200-ROI (17 Kong networks)', 'XY200K17', 17, 200, 'Yan2023; Kong2021'),
        'XY200Y17': Atlas('Xiaoxuan Yan 200-ROI (17 Yeo networks)', 'XY200Y17', 17, 200, 'Yan2023; Yeo2011'),
        'XY400K17': Atlas('Xiaoxuan Yan 400-ROI (17 Kong networks)', 'XY400K17', 17, 400, 'Yan2023; Kong2021'),
        'XY400Y17': Atlas('Xiaoxuan Yan 400-ROI (17 Yeo networks)', 'XY400Y17', 17, 400, 'Yan2023; Yeo2011'),
        'EG5': Atlas('Gordon 2023 5 networks', 'EG5', 5, 333, 'Gordon2023'),
        'TW_TASK_NETS': Atlas('Todd Woodward 2024 Task-based Networks', 'TW_TASK_NETS', 12, 12, 'Woodward2024'),
        'DU15NET': Atlas('Jingnan Du 2024 15 networks', 'DU15NET', 15, 15, 'Du2024'),
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
