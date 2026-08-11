"""
Atlas Metadata - Complete list of all atlases with abbreviations and descriptions
Maps abbreviations to authors and detailed descriptions
"""

ATLAS_METADATA = {
    # Glasser
    'MG360J12': {
        'author': 'Glasser',
        'description': 'Matt Glasser 2016 360-ROI with Ji 2019 12 Cole-Anticevic networks',
        'num_regions': 360,
        'source': 'Glasser2016; Ji2019'
    },
    
    # HCPICA
    'HCPICA': {
        'author': 'HCPICA',
        'description': 'HCP 25-node ICA maps',
        'num_regions': 25,
        'source': 'Smith2009; Smith2013',
        'is_multicomponent': True,
        'num_components': 20
    },
    
    # Laird
    'AL20': {
        'author': 'Laird',
        'description': 'Angela Laird 2011 20-node ICA maps',
        'num_regions': 20,
        'source': 'Laird2011',
        'is_multicomponent': True,
        'num_components': 20
    },
    
    # Schaefer variants
    'AS200K17': {
        'author': 'Woodward',
        'description': 'Schaefer 2018 200-ROI with Kong 2021 17 networks',
        'num_regions': 200,
        'source': 'Schaefer2018; Kong2021'
    },
    'AS200Y17': {
        'author': 'Woodward',
        'description': 'Schaefer 2018 200-ROI with Yeo 2011 17 networks',
        'num_regions': 200,
        'source': 'Schaefer2018; Yeo2011'
    },
    'AS400K17': {
        'author': 'Woodward',
        'description': 'Schaefer 2018 400-ROI with Kong 2021 17 networks',
        'num_regions': 400,
        'source': 'Schaefer2018; Kong2021'
    },
    'AS400Y17': {
        'author': 'Woodward',
        'description': 'Schaefer 2018 400-ROI with Yeo 2011 17 networks',
        'num_regions': 400,
        'source': 'Schaefer2018; Yeo2011'
    },
    
    # Shen
    'XS268_8': {
        'author': 'Shen',
        'description': 'Xilin Shen 2013 268-ROI with 8 networks',
        'num_regions': 268,
        'source': 'Shen2013'
    },
    'XS368_8': {
        'author': 'Shen',
        'description': 'Xilin Shen 2013 368-ROI with 8 networks',
        'num_regions': 368,
        'source': 'Shen2013'
    },
    
    # Shirer
    'WS90_14': {
        'author': 'Shirer',
        'description': 'William Shirer 2012 90-ROI with 14 networks',
        'num_regions': 90,
        'source': 'Shirer2012'
    },
    
    # UKBICA
    'UKBICA': {
        'author': 'UKBICA',
        'description': 'UK Biobank 25-node ICA maps',
        'num_regions': 25,
        'source': 'Smith2009; Alfaro-Almagro2018',
        'is_multicomponent': True,
        'num_components': 20
    },
    
    # WashU variants
    'EG286_12': {
        'author': 'WashU',
        'description': 'Evan Gordon 2016 286-ROI with 12 networks',
        'num_regions': 286,
        'source': 'Power2011; Gordon2016'
    },
    'TL12': {
        'author': 'WashU',
        'description': 'Tim Laumann 2015 12 networks (Power 2011)',
        'num_regions': 12,
        'source': 'Power2011; Laumann2015'
    },
    'EG17': {
        'author': 'WashU',
        'description': 'Evan Gordon 2017 17 networks',
        'num_regions': 17,
        'source': 'Power2011; Gordon2017'
    },
    'EG5': {
        'author': 'WashU',
        'description': 'Evan Gordon 2023 5 networks',
        'num_regions': 5,
        'source': 'Gordon2023'
    },
    
    # Woodward task networks
    'TW_TASK_NETS_1RESP': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Respiration (Motor)',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_2RESP': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Respiration',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_AAR': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Auditory/Auditory Related',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_AUD': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Auditory',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_DMNA': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - DMN-A',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_DMNB': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - DMN-B',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_FoVF': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Field of View/Foveal',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_INIT': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Initiation',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_LN': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Language Network',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_MAIN': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Main Network',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_MDN': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Multiple Demand Network',
        'source': 'Woodward2024'
    },
    'TW_TASK_NETS_RE': {
        'author': 'Woodward',
        'description': 'Todd Woodward 2024 - Right Executive',
        'source': 'Woodward2024'
    },
    
    # Yeo variants
    'TY7': {
        'author': 'YeoLab',
        'description': 'Thomas Yeo 7 networks',
        'num_regions': 7,
        'source': 'Yeo2011'
    },
    'TY17': {
        'author': 'YeoLab',
        'description': 'Thomas Yeo 17 networks',
        'num_regions': 17,
        'source': 'Yeo2011'
    },
    'XY200K17': {
        'author': 'YeoLab',
        'description': 'Xiaoxuan Yan 2023 200-ROI with Kong 2021 17 networks',
        'num_regions': 200,
        'source': 'Yan2023; Kong2021'
    },
    'XY200Y17': {
        'author': 'YeoLab',
        'description': 'Xiaoxuan Yan 2023 200-ROI with Yeo 2011 17 networks',
        'num_regions': 200,
        'source': 'Yan2023; Yeo2011'
    },
    'XY400K17': {
        'author': 'YeoLab',
        'description': 'Xiaoxuan Yan 2023 400-ROI with Kong 2021 17 networks',
        'num_regions': 400,
        'source': 'Yan2023; Kong2021'
    },
    'XY400Y17': {
        'author': 'YeoLab',
        'description': 'Xiaoxuan Yan 2023 400-ROI with Yeo 2011 17 networks',
        'num_regions': 400,
        'source': 'Yan2023; Yeo2011'
    },
    
    # Du
    'DU15NET': {
        'author': 'Du',
        'description': 'Jingnan Du 2024 15 networks',
        'num_regions': 15,
        'source': 'Du2024'
    },
}

def get_abbreviations_by_author(author):
    """Get all abbreviations for a given author"""
    return [abbr for abbr, meta in ATLAS_METADATA.items() if meta.get('author') == author]

def get_authors():
    """Get list of unique authors"""
    return sorted(set(meta.get('author') for meta in ATLAS_METADATA.values()))

def get_atlas_info(abbreviation):
    """Get metadata for an abbreviation"""
    return ATLAS_METADATA.get(abbreviation, {})
